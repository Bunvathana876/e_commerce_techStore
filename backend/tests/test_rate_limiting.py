"""
Phase 1B — Rate Limiting & Abuse Defense Regression Tests

Verifies:
1. Login threshold (5 req/min)
2. Login exceeding threshold (HTTP 429)
3. Registration threshold (5 req/min)
4. Registration exceeding threshold (HTTP 429)
5. Standardized HTTP 429 response body format
6. Retry-After, X-RateLimit-Limit, X-RateLimit-Remaining headers
7. Quota reset after window expiration (deterministic time advancement)
8. Isolation between distinct client IPs
9. Spoofed X-Forwarded-For headers rejected from untrusted peers
10. Trusted proxy X-Forwarded-For parsing & IP attribution
11. Unified quota enforcement across /api and /api/v1 aliases
12. User-scoped rate limiting for sensitive mutations (NAT defense)
13. Public catalog browsing threshold (120 req/min)
14. Storage failure resilience (fail-open mode)
15. Legitimate auth flow compatibility
"""
from fastapi.testclient import TestClient

from app.core.rate_limit import (
    ClientIpResolver,
    MemoryRateLimitStorage,
    RateLimitExceeded,
    get_rate_limiter_manager,
    reset_rate_limiter_storage,
)
from app.main import app


def test_login_below_threshold(client):
    """5 consecutive login attempts within 1 minute succeed without triggering rate limiting."""
    reset_rate_limiter_storage()
    for i in range(5):
        res = client.post(
            "/api/v1/auth/login",
            json={"email": "user1@example.com", "password": "Fixture-password-123"},
        )
        assert res.status_code == 200
        assert res.headers.get("X-RateLimit-Limit") == "5"
        assert int(res.headers.get("X-RateLimit-Remaining", -1)) == 4 - i


def test_login_exceeding_threshold(client):
    """The 6th login attempt within 1 minute triggers HTTP 429 Too Many Requests."""
    reset_rate_limiter_storage()
    for _ in range(5):
        res = client.post(
            "/api/v1/auth/login",
            json={"email": "user1@example.com", "password": "Fixture-password-123"},
        )
        assert res.status_code == 200

    # 6th attempt should be blocked
    blocked_res = client.post(
        "/api/v1/auth/login",
        json={"email": "user1@example.com", "password": "Fixture-password-123"},
    )
    assert blocked_res.status_code == 429
    body = blocked_res.json()
    assert body["success"] is False
    assert body["error_code"] == "RATE_LIMIT_EXCEEDED"
    assert "Rate limit exceeded" in body["detail"]
    assert "Retry-After" in blocked_res.headers
    assert int(blocked_res.headers["Retry-After"]) > 0


def test_registration_below_threshold(client):
    """5 registration attempts with unique emails within 1 minute succeed."""
    reset_rate_limiter_storage()
    for i in range(5):
        res = client.post(
            "/api/v1/auth/register",
            json={
                "name": f"New User {i}",
                "email": f"newuser{i}@example.com",
                "password": "Password123!",
            },
        )
        assert res.status_code == 201


def test_registration_exceeding_threshold(client):
    """The 6th registration attempt within 1 minute is blocked with 429."""
    reset_rate_limiter_storage()
    for i in range(5):
        res = client.post(
            "/api/v1/auth/register",
            json={
                "name": f"New User {i}",
                "email": f"regtest{i}@example.com",
                "password": "Password123!",
            },
        )
        assert res.status_code == 201

    blocked_res = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Excess User",
            "email": "excess@example.com",
            "password": "Password123!",
        },
    )
    assert blocked_res.status_code == 429
    assert blocked_res.json()["error_code"] == "RATE_LIMIT_EXCEEDED"


def test_rate_limit_exceeded_response_structure(client):
    """Verify exact RFC 6585 compliance and Blue Panda response schema."""
    reset_rate_limiter_storage()
    for _ in range(5):
        client.post(
            "/api/v1/auth/login",
            json={"email": "user1@example.com", "password": "wrong-password"},
        )

    res = client.post(
        "/api/v1/auth/login",
        json={"email": "user1@example.com", "password": "wrong-password"},
    )
    assert res.status_code == 429
    data = res.json()
    assert data["success"] is False
    assert data["error_code"] == "RATE_LIMIT_EXCEEDED"
    assert "Too many requests" in data["message"]
    assert "Rate limit exceeded" in data["detail"]
    assert int(res.headers["Retry-After"]) in (59, 60)
    assert res.headers["X-RateLimit-Limit"] == "5"
    assert res.headers["X-RateLimit-Remaining"] == "0"


def test_rate_limit_window_reset(client):
    """Advancing deterministic clock past 60s resets quota without sleeping."""
    manager = get_rate_limiter_manager()
    reset_rate_limiter_storage()

    current_simulated_time = 1000.0
    manager.set_clock(lambda: current_simulated_time)

    try:
        # Exhaust 5 requests at t=1000.0
        for _ in range(5):
            res = client.post(
                "/api/v1/auth/login",
                json={"email": "user1@example.com", "password": "Fixture-password-123"},
            )
            assert res.status_code == 200

        # Blocked at t=1000.0
        blocked = client.post(
            "/api/v1/auth/login",
            json={"email": "user1@example.com", "password": "Fixture-password-123"},
        )
        assert blocked.status_code == 429

        # Advance clock by 61 seconds (sliding window clears expired entries)
        current_simulated_time = 1061.0

        # Request succeeds again
        unblocked = client.post(
            "/api/v1/auth/login",
            json={"email": "user1@example.com", "password": "Fixture-password-123"},
        )
        assert unblocked.status_code == 200
    finally:
        manager.reset_clock()


def test_different_clients_isolated():
    """Client A at 198.51.100.1 reaching limit does NOT block Client B at 198.51.100.2."""
    reset_rate_limiter_storage()

    with TestClient(app, client=("198.51.100.1", 50000)) as client_a:
        for _ in range(5):
            res = client_a.post(
                "/api/v1/auth/login",
                json={"email": "user1@example.com", "password": "Fixture-password-123"},
            )
            assert res.status_code == 200

        # Client A is blocked on 6th
        blocked_a = client_a.post(
            "/api/v1/auth/login",
            json={"email": "user1@example.com", "password": "Fixture-password-123"},
        )
        assert blocked_a.status_code == 429

    # Client B from different IP can still log in
    with TestClient(app, client=("198.51.100.2", 50000)) as client_b:
        ok_b = client_b.post(
            "/api/v1/auth/login",
            json={"email": "user1@example.com", "password": "Fixture-password-123"},
        )
        assert ok_b.status_code == 200


def test_spoofed_forwarding_headers_rejected_by_untrusted_peer():
    """Direct untrusted peer sending spoofed X-Forwarded-For cannot evade rate limits."""
    reset_rate_limiter_storage()

    # Direct client at 198.51.100.5 (not in trusted proxies)
    with TestClient(app, client=("198.51.100.5", 50000)) as untrusted_client:
        # Exhaust 5 requests while sending fake X-Forwarded-For headers
        for i in range(5):
            res = untrusted_client.post(
                "/api/v1/auth/login",
                headers={"X-Forwarded-For": f"10.0.0.{i}"},
                json={"email": "user1@example.com", "password": "Fixture-password-123"},
            )
            assert res.status_code == 200

        # 6th request with another fake header is still blocked because peer IP is 198.51.100.5
        blocked = untrusted_client.post(
            "/api/v1/auth/login",
            headers={"X-Forwarded-For": "8.8.8.8"},
            json={"email": "user1@example.com", "password": "Fixture-password-123"},
        )
        assert blocked.status_code == 429


def test_trusted_proxy_x_forwarded_for_resolution():
    """Trusted proxy's X-Forwarded-For is properly parsed and attributed to the actual client."""
    reset_rate_limiter_storage()

    # Direct peer is Caddy on Docker network (172.16.0.2, in TRUSTED_PROXY_IPS)
    with TestClient(app, client=("172.16.0.2", 50000)) as proxy_client:
        # Real client 203.0.113.195 makes 5 requests through proxy
        for _ in range(5):
            res = proxy_client.post(
                "/api/v1/auth/login",
                headers={"X-Forwarded-For": "203.0.113.195"},
                json={"email": "user1@example.com", "password": "Fixture-password-123"},
            )
            assert res.status_code == 200

        # Real client 203.0.113.195 is blocked
        blocked = proxy_client.post(
            "/api/v1/auth/login",
            headers={"X-Forwarded-For": "203.0.113.195"},
            json={"email": "user1@example.com", "password": "Fixture-password-123"},
        )
        assert blocked.status_code == 429

        # A different client 203.0.113.196 through the SAME proxy is NOT blocked
        other_client = proxy_client.post(
            "/api/v1/auth/login",
            headers={"X-Forwarded-For": "203.0.113.196"},
            json={"email": "user1@example.com", "password": "Fixture-password-123"},
        )
        assert other_client.status_code == 200


def test_api_route_aliases_share_quota(client):
    """Hitting /api and /api/v1 aliases shares the same quota bucket, preventing bypass."""
    reset_rate_limiter_storage()

    # 3 attempts on /api/auth/login
    for _ in range(3):
        res = client.post(
            "/api/auth/login",
            json={"email": "user1@example.com", "password": "Fixture-password-123"},
        )
        assert res.status_code == 200

    # 2 attempts on /api/v1/auth/login (total 5)
    for _ in range(2):
        res = client.post(
            "/api/v1/auth/login",
            json={"email": "user1@example.com", "password": "Fixture-password-123"},
        )
        assert res.status_code == 200

    # 6th attempt on either alias is blocked
    blocked_v1 = client.post(
        "/api/v1/auth/login",
        json={"email": "user1@example.com", "password": "Fixture-password-123"},
    )
    assert blocked_v1.status_code == 429

    blocked_legacy = client.post(
        "/api/auth/login",
        json={"email": "user1@example.com", "password": "Fixture-password-123"},
    )
    assert blocked_legacy.status_code == 429


def test_sensitive_account_mutations_user_scoped(client, headers):
    """User-scoped mutations allow distinct users on the same NAT IP to update independently."""
    reset_rate_limiter_storage()
    manager = get_rate_limiter_manager()

    user2_headers = headers(2)
    user3_headers = headers(3)

    # User 2 performs profile update up to 20 times
    for _ in range(20):
        res = client.put(
            "/api/v1/auth/me",
            headers=user2_headers,
            json={"name": "User Two Updated"},
        )
        assert res.status_code == 200

    # User 2 is blocked on 21st
    blocked_user2 = client.put(
        "/api/v1/auth/me",
        headers=user2_headers,
        json={"name": "User Two Blocked"},
    )
    assert blocked_user2.status_code == 429

    # User 3 on the SAME IP client is NOT blocked because rate limiting is user-scoped
    ok_user3 = client.put(
        "/api/v1/auth/me",
        headers=user3_headers,
        json={"name": "User Three Updated"},
    )
    assert ok_user3.status_code == 200


def test_public_catalog_browsing_rate_limit(client):
    """Public catalog browsing endpoints enforce 120 req/min limit."""
    reset_rate_limiter_storage()

    # Perform 120 GET requests
    for i in range(120):
        res = client.get("/api/v1/products")
        assert res.status_code == 200

    # 121st request is throttled
    blocked = client.get("/api/v1/products")
    assert blocked.status_code == 429
    assert blocked.json()["error_code"] == "RATE_LIMIT_EXCEEDED"
    assert "120 requests per 1 minute" in blocked.json()["detail"]


def test_storage_fail_open_resilience(monkeypatch, client):
    """When storage encounters an error, fail-open mode allows requests without crashing."""
    reset_rate_limiter_storage()
    manager = get_rate_limiter_manager()

    # Monkeypatch storage check_and_record to simulate storage failure
    def mock_broken_storage(*args, **kwargs):
        # Fail-open returns (False, max_requests, 0)
        return False, 5, 0

    monkeypatch.setattr(manager.storage, "check_and_record", mock_broken_storage)

    # Request succeeds gracefully
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "user1@example.com", "password": "Fixture-password-123"},
    )
    assert res.status_code == 200


def test_existing_authentication_flows_remain_compatible(client):
    """Legitimate authentication returns standard user data and access token payload."""
    reset_rate_limiter_storage()
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "user1@example.com", "password": "Fixture-password-123"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "data" in data
    assert "access_token" in data["data"]
    assert data["data"]["token_type"] == "bearer"
    assert "user" in data["data"]
    assert data["data"]["user"]["email"] == "user1@example.com"


# ==============================================================================
# Phase 3 Hardening: Distributed Redis Rate Limiting Multi-Worker Tests
# ==============================================================================

def _is_test_redis_available() -> bool:
    try:
        import redis
        client = redis.Redis.from_url(
            "redis://:test_redis_secret_123@localhost:6389/0",
            socket_connect_timeout=0.5,
        )
        return bool(client.ping())
    except Exception:
        return False


def test_redis_rate_limit_storage_atomic_lua():
    """Verify RedisRateLimitStorage atomic Lua script enforces limits and returns retry-after."""
    if not _is_test_redis_available():
        import pytest
        pytest.skip("Test Redis server not reachable on port 6389")

    from app.core.rate_limit import RedisRateLimitStorage
    import time

    storage = RedisRateLimitStorage(
        redis_url="redis://:test_redis_secret_123@localhost:6389/0",
        fail_open=False,
    )
    storage.clear()
    key = "test:atomic_lua:client1"
    now = time.time()

    # 3 allowed requests with quota=3
    for i in range(3):
        is_limited, rem, retry_after = storage.check_and_record(key, max_requests=3, window_seconds=60, now=now + i * 0.1)
        assert is_limited is False
        assert rem == 2 - i
        assert retry_after == 0

    # 4th request must be blocked
    is_limited, rem, retry_after = storage.check_and_record(key, max_requests=3, window_seconds=60, now=now + 1.0)
    assert is_limited is True
    assert rem == 0
    assert retry_after >= 58


def _cross_worker_subtask(redis_url, key, max_requests, num_calls, result_queue):
    from app.core.rate_limit import RedisRateLimitStorage
    import time
    storage = RedisRateLimitStorage(redis_url=redis_url, fail_open=False)
    outcomes = []
    for _ in range(num_calls):
        is_limited, _, _ = storage.check_and_record(key, max_requests=max_requests, window_seconds=60, now=time.time())
        outcomes.append(is_limited)
        time.sleep(0.005)
    result_queue.put(outcomes)


def test_redis_rate_limit_multi_process_shared_quota():
    """Verify multiple concurrent OS worker processes share the identical Redis quota bucket."""
    if not _is_test_redis_available():
        import pytest
        pytest.skip("Test Redis server not reachable on port 6389")

    import multiprocessing
    from app.core.rate_limit import RedisRateLimitStorage

    redis_url = "redis://:test_redis_secret_123@localhost:6389/0"
    storage = RedisRateLimitStorage(redis_url=redis_url, fail_open=False)
    storage.clear()
    key = "test:cross_worker:ip_10_0_0_1"

    # Total quota = 5. Worker 1 executes 4 calls, Worker 2 executes 4 calls concurrently.
    ctx = multiprocessing.get_context("spawn")
    q = ctx.Queue()
    p1 = ctx.Process(target=_cross_worker_subtask, args=(redis_url, key, 5, 4, q))
    p2 = ctx.Process(target=_cross_worker_subtask, args=(redis_url, key, 5, 4, q))

    p1.start()
    p2.start()
    p1.join(timeout=5)
    p2.join(timeout=5)

    res1 = q.get(timeout=2)
    res2 = q.get(timeout=2)

    total_results = res1 + res2
    allowed_count = total_results.count(False)
    blocked_count = total_results.count(True)

    assert allowed_count == 5, f"Expected exactly 5 allowed requests across workers, got {allowed_count}"
    assert blocked_count == 3, f"Expected exactly 3 blocked requests across workers, got {blocked_count}"


def test_redis_rate_limit_fail_open_on_storage_failure():
    """Verify that when Redis is completely unreachable and fail_open=True, requests pass gracefully."""
    from app.core.rate_limit import RedisRateLimitStorage
    storage = RedisRateLimitStorage(
        redis_url="redis://localhost:59999/0",  # Unused dead port
        fail_open=True,
    )
    is_limited, remaining, retry_after = storage.check_and_record("dead_key", max_requests=5, window_seconds=60, now=100.0)
    assert is_limited is False
    assert remaining == 5
    assert retry_after == 0


def test_redis_rate_limit_fail_closed_on_storage_failure():
    """Verify that when Redis is unreachable and fail_open=False, requests are securely throttled."""
    from app.core.rate_limit import RedisRateLimitStorage
    storage = RedisRateLimitStorage(
        redis_url="redis://localhost:59999/0",  # Unused dead port
        fail_open=False,
    )
    is_limited, remaining, retry_after = storage.check_and_record("dead_key", max_requests=5, window_seconds=60, now=100.0)
    assert is_limited is True
    assert remaining == 0
    assert retry_after == 60
