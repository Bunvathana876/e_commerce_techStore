from datetime import datetime
from typing import Any
from urllib.parse import urlparse
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_DEV_SECRETS: set[str] = {
    "dev_secret_key_change_me_super_secure_12345",
    "secret",
    "secretkey",
    "changeme",
    "change_me",
    "password",
    "12345678",
    "jwt_secret",
}

DEFAULT_DEV_CORS_ORIGINS: list[str] = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:3002",
    "http://localhost:3003",
    "http://localhost:8000",
    "http://localhost:5173",
    "http://127.0.0.1",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
    "http://127.0.0.1:3002",
    "http://127.0.0.1:3003",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:5173",
    "http://10.0.2.2:8000",
]

DEFAULT_TRUSTED_PROXY_IPS: list[str] = [
    "127.0.0.1",
    "::1",
    "172.16.0.0/12",
    "10.0.0.0/8",
    "192.168.0.0/16",
]


class Settings(BaseSettings):
    PROJECT_NAME: str = "E-Commerce API"
    PROJECT_DESCRIPTION: str = "Backend API for Flutter E-Commerce Mobile App"
    PROJECT_VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api"

    ENVIRONMENT: str = "development"
    DATABASE_URL: str
    AUTO_INIT_DB: bool = True
    SEED_DEMO_DATA: bool = True
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE_BYTES: int = 5 * 1024 * 1024  # 5 MB default cap
    MAX_IMAGE_DIMENSION: int = 4096
    MAX_IMAGE_PIXELS: int = 16_777_216  # 4096 x 4096 decompression-bomb ceiling

    # Database connection pool tuning (PostgreSQL / Supabase pooler compatibility)
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 5
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800

    JWT_SECRET_KEY: str = "dev_secret_key_change_me_super_secure_12345"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days for dev session stability

    # Keep deployed bearer-only clients on their existing lifetime during rollout.
    AUTH_ISSUE_SESSION_TOKENS: bool = False
    AUTH_ACCEPT_LEGACY_TOKENS: bool = True
    AUTH_LEGACY_ACCEPT_UNTIL: datetime | None = None
    SESSION_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=15, ge=1)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=30, ge=1)
    JWT_ISSUER: str = "blue-panda"
    JWT_AUDIENCE: str = "blue-panda-api"

    ENABLE_DOCS_IN_PRODUCTION: bool = False

    # CORS origins: in development, defaults to local dev origins; in production, must be explicit
    CORS_ORIGINS: list[str] | str = DEFAULT_DEV_CORS_ORIGINS

    # Rate limiting & abuse defense configuration (Phase 1B)
    RATE_LIMITING_ENABLED: bool = True
    RATE_LIMIT_STORAGE_URL: str | None = None
    RATE_LIMIT_FAIL_OPEN: bool = True
    TRUSTED_PROXY_IPS: list[str] | str = DEFAULT_TRUSTED_PROXY_IPS

    # Rate limit quotas (requests per 60 seconds)
    RATE_LIMIT_AUTH_LOGIN: int = 5
    RATE_LIMIT_AUTH_REGISTER: int = 5
    RATE_LIMIT_AUTH_REFRESH: int = 10
    RATE_LIMIT_SENSITIVE_MUTATIONS: int = 20
    RATE_LIMIT_CATALOG_BROWSING: int = 120

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.strip().lower() in {"production", "prod", "staging"}

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            v = v.strip()
            if (v.startswith("'") and v.endswith("'")) or (v.startswith('"') and v.endswith('"')):
                v = v[1:-1].strip()
            if v.startswith("[") and v.endswith("]"):
                try:
                    import json
                    parsed = json.loads(v)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except Exception:
                    pass
            return [item.strip() for item in v.split(",") if item.strip()]
        elif isinstance(v, (list, tuple, set)):
            return [str(item).strip() for item in v if str(item).strip()]
        return v

    @field_validator("TRUSTED_PROXY_IPS", mode="before")
    @classmethod
    def parse_trusted_proxy_ips(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            v = v.strip()
            if (v.startswith("'") and v.endswith("'")) or (v.startswith('"') and v.endswith('"')):
                v = v[1:-1].strip()
            if v.startswith("[") and v.endswith("]"):
                try:
                    import json
                    parsed = json.loads(v)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except Exception:
                    pass
            return [item.strip() for item in v.split(",") if item.strip()]
        elif isinstance(v, (list, tuple, set)):
            return [str(item).strip() for item in v if str(item).strip()]
        return v

    @model_validator(mode="after")
    def validate_production_configuration(self) -> "Settings":
        if not self.AUTH_ISSUE_SESSION_TOKENS and not self.AUTH_ACCEPT_LEGACY_TOKENS:
            raise ValueError("Validation-only auth rollout requires legacy token acceptance.")
        if self.is_production:
            # 1. JWT secret key validation
            raw_secret = (self.JWT_SECRET_KEY or "").strip()
            if not raw_secret:
                raise ValueError(
                    "In production, JWT_SECRET_KEY must be explicitly configured."
                )
            if raw_secret in INSECURE_DEV_SECRETS:
                raise ValueError(
                    "In production, JWT_SECRET_KEY cannot use default, known, or placeholder development secrets."
                )
            if len(raw_secret) < 32:
                raise ValueError(
                    "In production, JWT_SECRET_KEY must be at least 32 characters long."
                )

            # 2. CORS origin validation
            if not self.CORS_ORIGINS:
                raise ValueError(
                    "In production, at least one trusted CORS origin must be explicitly configured in CORS_ORIGINS."
                )
            if any(origin == "*" for origin in self.CORS_ORIGINS):
                raise ValueError(
                    "In production, wildcard '*' CORS origins are strictly prohibited."
                )
            for origin in self.CORS_ORIGINS:
                parsed = urlparse(origin)
                if (
                    parsed.scheme not in ("http", "https")
                    or not parsed.netloc
                    or parsed.path not in ("", "/")
                    or (parsed.path == "/" and origin.endswith("/"))
                ):
                    raise ValueError(
                        f"Invalid CORS origin '{origin}': origins must include scheme (http:// or https://) "
                        "and host/domain without paths or trailing slashes."
                    )
        return self


settings = Settings()

# Backward compatibility alias
DATABASE_URL = settings.DATABASE_URL
