"""
Blue Panda E-Commerce — Production-Grade Rate Limiting & Abuse Defense Engine

Architecture:
1. Client IP & Proxy Trust Resolution:
   - Evaluates socket peer (request.client.host) against configured TRUSTED_PROXY_IPS.
   - If peer is not trusted, all forwarding headers (X-Forwarded-For, X-Real-IP) are rejected,
     preventing internet clients from spoofing their IP.
   - If peer is a trusted proxy (e.g. Caddy / Docker ingress), parses X-Forwarded-For right-to-left,
     skipping internal proxies and attributing to the actual upstream client.
2. Scope & Alias Independence:
   - Unifies routes under logical scopes (e.g. "auth:login", "catalog:browse") so alternating
     between /api and /api/v1 prefixes draws from the identical quota bucket.
3. Pluggable Storage:
   - MemoryRateLimitStorage: Thread-safe, bounded in-memory sliding-window log for dev and testing.
   - RedisRateLimitStorage: Distributed sliding-window log using atomic sorted sets for multi-worker production.
4. RFC 6585 & Blue Panda Contract Compliance:
   - Returns HTTP 429 Too Many Requests with standard Retry-After, X-RateLimit-Limit,
     X-RateLimit-Remaining, and X-RateLimit-Reset headers.
   - Standard error payload: { "success": false, "message": "...", "error_code": "RATE_LIMIT_EXCEEDED", "detail": "..." }
5. Deterministic Testing:
   - Supports custom time providers for zero-sleep sub-millisecond testing and test isolation.
"""
from __future__ import annotations

import ipaddress
import logging
import math
import threading
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from fastapi import HTTPException, Request, Response, status

from app.core.config import settings

logger = logging.getLogger("uvicorn.error")


class RateLimitExceeded(HTTPException):
    """Exception raised when a client exceeds a configured rate limit threshold."""

    def __init__(
        self,
        detail: str,
        retry_after: int,
        limit: int,
        remaining: int = 0,
        reset_seconds: int | None = None,
    ):
        headers = {
            "Retry-After": str(retry_after),
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(reset_seconds if reset_seconds is not None else retry_after),
        }
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
            headers=headers,
        )
        self.retry_after = retry_after
        self.limit = limit
        self.remaining = remaining
        self.reset_seconds = reset_seconds if reset_seconds is not None else retry_after


class ClientIpResolver:
    """
    Secure client IP resolver with trusted-proxy CIDR verification.

    Security rules:
    1. If the direct connecting peer is NOT in trusted_proxies,
       arbitrary X-Forwarded-For and X-Real-IP headers are STRICTLY IGNORED.
    2. If the connecting peer IS in trusted_proxies, X-Forwarded-For is parsed
       from right to left, stopping at the first untrusted upstream IP.
    3. Handles IPv4 and IPv6 transparently via python ipaddress.
    """

    def __init__(self, trusted_proxies: list[str] | None = None):
        self.trusted_networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
        proxies = trusted_proxies if trusted_proxies is not None else settings.TRUSTED_PROXY_IPS
        for item in proxies:
            item = item.strip()
            if not item:
                continue
            try:
                if "/" in item:
                    self.trusted_networks.append(ipaddress.ip_network(item, strict=False))
                else:
                    ip = ipaddress.ip_address(item)
                    self.trusted_networks.append(
                        ipaddress.ip_network(f"{ip}/{32 if ip.version == 4 else 128}")
                    )
            except ValueError:
                logger.warning(f"Invalid trusted proxy IP/CIDR ignored: {item}")

    def is_trusted_proxy(self, ip_str: str) -> bool:
        if not self.trusted_networks:
            return False
        try:
            ip = ipaddress.ip_address(ip_str)
            return any(ip in net for net in self.trusted_networks)
        except ValueError:
            return False

    def resolve_client_ip(self, request: Request) -> str:
        # Default fallback
        peer_host = "127.0.0.1"
        if request.client and request.client.host:
            peer_host = request.client.host

        # Handle Starlette test client default host
        if peer_host == "testclient":
            peer_host = "127.0.0.1"

        # If direct connecting peer is not a trusted proxy, ignore all forwarding headers
        if not self.is_trusted_proxy(peer_host):
            return peer_host

        # Connecting peer is trusted. Check X-Forwarded-For (traversing backwards)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            parts = [p.strip() for p in forwarded_for.split(",") if p.strip()]
            for candidate in reversed(parts):
                try:
                    ip = ipaddress.ip_address(candidate)
                    if not any(ip in net for net in self.trusted_networks):
                        return candidate
                except ValueError:
                    continue

        # Check X-Real-IP if X-Forwarded-For yielded no untrusted IP
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            candidate = real_ip.strip()
            try:
                ip = ipaddress.ip_address(candidate)
                if not any(ip in net for net in self.trusted_networks):
                    return candidate
            except ValueError:
                pass

        return peer_host


class BaseRateLimitStorage(ABC):
    @abstractmethod
    def check_and_record(
        self, key: str, max_requests: int, window_seconds: int, now: float
    ) -> tuple[bool, int, int]:
        """
        Check if request is limited and record current hit if not limited.
        Returns:
            (is_limited: bool, remaining_quota: int, retry_after_seconds: int)
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all rate limit entries."""
        pass


class MemoryRateLimitStorage(BaseRateLimitStorage):
    """
    Thread-safe in-memory sliding-window log rate limiter with bounded memory.
    """

    def __init__(self, max_keys: int = 50_000):
        self._lock = threading.Lock()
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._max_keys = max_keys

    def check_and_record(
        self, key: str, max_requests: int, window_seconds: int, now: float
    ) -> tuple[bool, int, int]:
        with self._lock:
            if len(self._hits) > self._max_keys:
                self._prune_expired_locked(now)

            cutoff = now - window_seconds
            timestamps = self._hits[key]

            # Filter out entries outside the current sliding window
            valid_timestamps = [ts for ts in timestamps if ts > cutoff]
            self._hits[key] = valid_timestamps

            if len(valid_timestamps) >= max_requests:
                # Quota exhausted: oldest entry determines when first slot re-opens
                oldest_entry = valid_timestamps[0]
                retry_after = max(1, math.ceil(oldest_entry + window_seconds - now))
                return True, 0, retry_after

            # Quota available: record hit
            valid_timestamps.append(now)
            remaining = max_requests - len(valid_timestamps)
            return False, remaining, 0

    def _prune_expired_locked(self, now: float) -> None:
        expired_keys = [
            k for k, ts in self._hits.items()
            if not ts or ts[-1] < now - 3600
        ]
        for k in expired_keys:
            self._hits.pop(k, None)

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()


LUA_SLIDING_WINDOW_RATE_LIMIT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local max_requests = tonumber(ARGV[3])
local member = ARGV[4]

local cutoff = now - window
redis.call('ZREMRANGEBYSCORE', key, 0, cutoff)
local current_count = redis.call('ZCARD', key)

if current_count >= max_requests then
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local oldest_score = cutoff
    if oldest and #oldest >= 2 then
        oldest_score = tonumber(oldest[2])
    end
    local retry_after = math.max(1, math.ceil(oldest_score + window - now))
    return {1, 0, retry_after}
else
    redis.call('ZADD', key, now, member)
    redis.call('EXPIRE', key, math.ceil(window * 2))
    local remaining = max_requests - (current_count + 1)
    return {0, math.max(0, remaining), 0}
end
"""


class RedisRateLimitStorage(BaseRateLimitStorage):
    """
    Distributed Redis-backed sliding-window rate limit storage using atomic sorted sets
    and an atomic Lua script to guarantee exact multi-worker concurrency safety.
    """

    def __init__(self, redis_url: str, fail_open: bool = True):
        self.redis_url = redis_url
        self.fail_open = fail_open
        self._client: Any = None
        self._script: Any = None
        self._init_client()

    def _init_client(self) -> None:
        try:
            import redis
            self._client = redis.Redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=2.0,
                socket_timeout=2.0,
            )
            self._client.ping()
            self._script = self._client.register_script(LUA_SLIDING_WINDOW_RATE_LIMIT)
        except Exception as e:
            logger.warning(
                f"Redis rate limit storage connection failed ({e}). Fail-open: {self.fail_open}"
            )
            self._client = None
            self._script = None

    def get_client(self) -> Any:
        if self._client is None:
            self._init_client()
        return self._client

    def check_and_record(
        self, key: str, max_requests: int, window_seconds: int, now: float
    ) -> tuple[bool, int, int]:
        client = self.get_client()
        if client is None:
            if self.fail_open:
                return False, max_requests, 0
            return True, 0, 60

        try:
            member = f"{now}:{time.time_ns()}"
            if self._script is not None:
                # Script returns {is_limited (0 or 1), remaining, retry_after}
                res = self._script(
                    keys=[key],
                    args=[now, window_seconds, max_requests, member],
                )
                is_limited = bool(res[0])
                remaining = int(res[1])
                retry_after = int(res[2])
                return is_limited, remaining, retry_after
            else:
                cutoff = now - window_seconds
                pipe = client.pipeline()
                pipe.zremrangebyscore(key, 0, cutoff)
                pipe.zcard(key)
                pipe.zrange(key, 0, 0, withscores=True)
                results = pipe.execute()

                current_count = results[1]
                oldest_with_scores = results[2]

                if current_count >= max_requests:
                    oldest_score = oldest_with_scores[0][1] if oldest_with_scores else cutoff
                    retry_after = max(1, math.ceil(oldest_score + window_seconds - now))
                    return True, 0, retry_after

                pipe2 = client.pipeline()
                pipe2.zadd(key, {member: now})
                pipe2.expire(key, window_seconds * 2)
                pipe2.execute()

                remaining = max_requests - (current_count + 1)
                return False, max(0, remaining), 0
        except Exception as e:
            logger.error(f"Redis rate limit error for key {key}: {e}")
            self._client = None  # Force reconnect on subsequent attempts
            self._script = None
            if self.fail_open:
                return False, max_requests, 0
            return True, 0, 60

    def clear(self) -> None:
        client = self.get_client()
        if client:
            try:
                client.flushdb()
            except Exception as e:
                logger.error(f"Failed to clear Redis rate limit storage: {e}")


class RateLimiterManager:
    """Central coordinator for rate limiting configuration, storage, and request resolution."""

    def __init__(self):
        self.ip_resolver = ClientIpResolver()
        self._clock: Callable[[], float] = time.time
        self.storage: BaseRateLimitStorage = self._create_storage()

    def _create_storage(self) -> BaseRateLimitStorage:
        if settings.RATE_LIMIT_STORAGE_URL:
            return RedisRateLimitStorage(
                redis_url=settings.RATE_LIMIT_STORAGE_URL,
                fail_open=settings.RATE_LIMIT_FAIL_OPEN,
            )
        return MemoryRateLimitStorage()

    def is_enabled(self) -> bool:
        return settings.RATE_LIMITING_ENABLED

    def get_current_time(self) -> float:
        return self._clock()

    def set_clock(self, clock_fn: Callable[[], float]) -> None:
        """Inject custom clock for deterministic testing."""
        self._clock = clock_fn

    def reset_clock(self) -> None:
        """Restore standard wall clock."""
        self._clock = time.time

    def reset(self) -> None:
        """Clear rate limit counters and reset mock clock to system time."""
        self.storage.clear()
        self.reset_clock()

    @staticmethod
    def extract_user_id_from_request(request: Request) -> str | None:
        """Extract authenticated user ID from Bearer token if present, without DB query."""
        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()
            if token:
                from app.core.security import decode_access_token
                payload = decode_access_token(token)
                if payload and "sub" in payload:
                    return str(payload["sub"])
        return None


# Global singleton manager
_manager: RateLimiterManager | None = None


def get_rate_limiter_manager() -> RateLimiterManager:
    global _manager
    if _manager is None:
        _manager = RateLimiterManager()
    return _manager


def reset_rate_limiter_storage() -> None:
    """Helper to reset rate limit storage (used by test fixtures)."""
    get_rate_limiter_manager().reset()


class RateLimiter:
    """
    FastAPI route dependency enforcing rate limits.
    """

    def __init__(
        self,
        times: int,
        seconds: int = 60,
        scope: str | None = None,
        key_func: Callable[[Request], str] | None = None,
        user_scoped: bool = False,
    ):
        self.times = times
        self.seconds = seconds
        self.scope = scope
        self.key_func = key_func
        self.user_scoped = user_scoped

    def __call__(
        self,
        request: Request,
        response: Response,
    ) -> None:
        manager = get_rate_limiter_manager()
        if not manager.is_enabled():
            return

        if self.key_func:
            key = self.key_func(request)
        else:
            client_ip = manager.ip_resolver.resolve_client_ip(request)
            scope_name = self.scope or request.url.path

            user_part = ""
            if self.user_scoped:
                user_id = manager.extract_user_id_from_request(request)
                if user_id:
                    user_part = f":user:{user_id}"

            key = f"rl:{scope_name}:ip:{client_ip}{user_part}"

        now = manager.get_current_time()
        is_limited, remaining, retry_after = manager.storage.check_and_record(
            key=key,
            max_requests=self.times,
            window_seconds=self.seconds,
            now=now,
        )

        if response is not None:
            response.headers["X-RateLimit-Limit"] = str(self.times)
            response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
            response.headers["X-RateLimit-Reset"] = str(retry_after if is_limited else self.seconds)

        if is_limited:
            human_window = f"{self.seconds} seconds" if self.seconds != 60 else "1 minute"
            detail = (
                f"Rate limit exceeded: {self.times} requests per {human_window}. "
                f"Please retry after {retry_after} seconds."
            )
            raise RateLimitExceeded(
                detail=detail,
                retry_after=retry_after,
                limit=self.times,
                remaining=0,
                reset_seconds=retry_after,
            )
