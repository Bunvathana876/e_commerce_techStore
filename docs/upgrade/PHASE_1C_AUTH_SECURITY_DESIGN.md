# Blue Panda E-Commerce — Phase 1C: Secure Authentication Architecture & Design

**Document ID:** BP-DESIGN-PHASE-1C  
**Author:** Senior Authentication Architect & Security Engineering Team  
**Status:** Architecture Design Completed — Awaiting Implementation Authorization  
**Target Milestone:** Phase 1C: JWT Revocation, Refresh Tokens & Password Hardening  
**Related Documents:**
- [`docs/upgrade/BLUE_PANDA_PROJECT_AUDIT.md`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/docs/upgrade/BLUE_PANDA_PROJECT_AUDIT.md)
- [`docs/upgrade/BLUE_PANDA_UPGRADE_ROADMAP.md`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/docs/upgrade/BLUE_PANDA_UPGRADE_ROADMAP.md)
- [`docs/upgrade/BLUE_PANDA_PROGRESS.md`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/docs/upgrade/BLUE_PANDA_PROGRESS.md)
- [`docs/upgrade/PHASE_1C_IMPLEMENTATION_PLAN.md`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/docs/upgrade/PHASE_1C_IMPLEMENTATION_PLAN.md)

---

## 1. Executive Summary

Blue Panda E-Commerce currently relies on a stateless, long-lived JSON Web Token (JWT) architecture. While functional for local development, code inspection confirms several severe security weaknesses:
1. **7-Day Token Lifetime Without Revocation:** Access tokens remain valid for up to 7 days (or 60 minutes in production config) with zero server-side invalidation.
2. **Stateless No-Op Logout:** The `POST /api/v1/auth/logout` endpoint performs no server-side token invalidation. Stolen tokens remain usable until natural expiration.
3. **No Refresh Token Flow:** When an access token expires, clients must immediately eject the user to the login screen, severely degrading UX and checkout retention.
4. **Weak Password Policy:** Password changes enforce only `len(new_password) >= 6` without character entropy requirements, and changing a password does not invalidate other active sessions.
5. **Insecure Client Storage:** Web tokens are stored in browser `localStorage` (vulnerable to XSS extraction), while mobile tokens are stored in unencrypted `SharedPreferences`.

This document designs an enterprise-grade, defense-in-depth authentication lifecycle:
- **Short-lived access tokens** (15 minutes) with strict claim validation (`sub`, `type`, `jti`, `session_id`, `iss`, `aud`, `exp`, `iat`).
- **Opaque, rotating refresh tokens** with cryptographic SHA-256 server-side hashing (raw tokens are never stored in PostgreSQL).
- **Token-family tracking & reuse detection:** Automatic revocation of all family tokens if a previously rotated token is replayed.
- **Session-aware logout & password changes:** Immediate invalidation of individual or all active sessions.
- **Client security modernization:** `HttpOnly`, `Secure`, `SameSite` cookies with CSRF defense for Web clients, and native Keychain/Keystore secure storage with mutex-protected background refresh for Flutter.

---

## 2. Current Authentication Architecture & Confirmed Vulnerabilities

### 2.1 Backend Implementation Audit

| Component | Current Implementation | Confirmed Vulnerability / Limitation |
| :--- | :--- | :--- |
| **Token Generation** ([`security.py`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/backend/app/core/security.py#L27)) | PyJWT HMAC-SHA256 (`HS256`). Claims: `{"sub": str(user.id), "exp": ...}`. | Missing `type`, `jti`, `iss`, `aud`, `iat`, `session_id`. Tokens cannot be revoked or distinguished from other token types. |
| **Token Expiry** ([`config.py`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/backend/app/core/config.py#L49)) | `ACCESS_TOKEN_EXPIRE_MINUTES: 10080` (7 days) in dev; 60 mins in prod compose. | Stolen access tokens retain unauthorized access for up to 168 hours without any recourse. |
| **Token Verification** ([`dependencies.py`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/backend/app/core/dependencies.py#L15)) | `decode_access_token` checks signature and expiration only. | Does not check session active state or token revocation. An inactive or deleted user session remains authorized until JWT expires. |
| **Logout Endpoint** ([`auth.py`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/backend/app/api/v1/routes/auth.py#L78)) | Handler returns `{"success": true, "message": "Logged out successfully."}` without side effects. | Pure no-op. The client drops the token locally, but the bearer token remains cryptographically valid against the API. |
| **Password Change** ([`auth_service.py`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/backend/app/services/auth_service.py#L90)) | Updates `user.password_hash` in place. Checks `len(new_password) < 6`. | Existing sessions and tokens are not invalidated. Weak passwords (e.g. `123456`) are accepted. |
| **Password Hashing** ([`security.py`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/backend/app/core/security.py#L10)) | `bcrypt.gensalt()` with `bcrypt.hashpw()`. | Standard 12-round bcrypt is used (good), but dummy-hash timing equalization is absent on failed logins. |

### 2.2 Client-Side Storage & Lifecycle Audit

| Client | Storage Mechanism | Refresh Behavior | Security Risk |
| :--- | :--- | :--- | :--- |
| **Storefront Web** ([`storefront/src/lib/auth.ts`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/storefront/src/lib/auth.ts#L83)) | `localStorage.getItem("storefront_accessToken")` | None. On 401 or expiration, calls `logout()` and forces login redirect. | Vulnerable to XSS token theft. Users are unexpectedly logged out during checkout or browsing. |
| **Management Web** ([`management/src/lib/auth.ts`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/management/src/lib/auth.ts#L83)) | `localStorage.getItem("mgmt_accessToken")` | None. On 401 or expiration, calls `logout()` and forces login redirect. | Admin and seller credentials exposed to XSS script access in browser storage. |
| **Mobile Flutter** ([`mobile-app/lib/features/auth/providers/auth_provider.dart`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/mobile-app/lib/features/auth/providers/auth_provider.dart#L13)) | Unencrypted XML `SharedPreferences` (`auth_token`). | None. `ApiClient.globalOnUnauthorized` immediately triggers `logout()`. | Unencrypted tokens vulnerable on rooted devices / physical backups; disruptive logouts on 401. |

---

## 3. Secure JWT & Session Architecture

```
                                  BLUE PANDA SECURE AUTH LIFECYCLE
                                  
  [Client]                                 [Backend / Caddy]                   [PostgreSQL]
     |                                             |                                 |
     |---- 1. POST /auth/login ------------------->|                                 |
     |    (email, password)                        |-- Verify bcrypt hash ---------->|
     |                                             |-- Create user_sessions row ---->|
     |                                             |   (token_hash, session_id)      |
     |<--- 2. Set-Cookie: refresh_token (HttpOnly)-|                                 |
     |    Body: { access_token (15m), user }       |                                 |
     |                                             |                                 |
     |==== 3. API Requests with Bearer AccessToken =================================>|
     |    (Validated in-memory, session_id checked)|                                 |
     |                                             |                                 |
     |--* Access Token Expires (15m) *--           |                                 |
     |                                             |                                 |
     |---- 4. POST /auth/refresh ----------------->|                                 |
     |    (Cookie or Body: refresh_token)          |-- Query session by token_hash ->|
     |                                             |   Check used_at & is_revoked    |
     |                                             |-- ROTATE: Mark old token used-->|
     |                                             |-- Insert new token_hash ------->|
     |<--- 5. New Set-Cookie (rotated refresh) ----|                                 |
     |    Body: { new access_token (15m) }         |                                 |
     |                                             |                                 |
     |---- 6. POST /auth/logout ------------------>|                                 |
     |    (Bearer access_token)                    |-- UPDATE user_sessions -------->|
     |                                             |   SET is_revoked = TRUE         |
     |<--- 7. Clear Cookie & Confirm --------------|                                 |
```

### 3.1 Access Tokens Specification

Access tokens are short-lived, self-contained bearer credentials used for API authorization.

- **Lifespan:** **15 minutes** (`ACCESS_TOKEN_EXPIRE_MINUTES = 15`).
- **Signature Algorithm:** `HS256` using `settings.JWT_SECRET_KEY` (minimum 32 bytes enforced in production).
- **Mandatory Claims Schema:**

| Claim | Type | Description | Verification Rule |
| :--- | :--- | :--- | :--- |
| `sub` | `str` | User ID string (e.g. `"42"`). | Required. Must be convertible to integer matching active user. |
| `type` | `str` | Token type indicator: `"access"`. | Strictly validated: `payload["type"] == "access"`. Rejects refresh tokens sent as access tokens. |
| `jti` | `str` | Unique JWT ID (UUIDv4). | Required. Enables individual token blacklist tracking when needed. |
| `session_id` | `str` | UUIDv4 identifier linking token to active server session. | Required. Verified against active session cache or DB. |
| `role` | `str` | User role (`customer`, `seller`, `admin`, `staff`). | Checked for coarse client routing; backend always verifies DB role for sensitive mutations. |
| `iss` | `str` | Token issuer: `"blue-panda-api"`. | Verified: `verify_iss=True, issuer="blue-panda-api"`. |
| `aud` | `str` | Token audience: `"blue-panda-client"`. | Verified: `verify_aud=True, audience="blue-panda-client"`. |
| `iat` | `int` | Issued-at UTC UNIX timestamp. | Required. Checked: `iat <= now + 5s`. |
| `exp` | `int` | Expiration UTC UNIX timestamp (`iat + 900`). | Strictly verified: `verify_exp=True`. |

### 3.2 Refresh Tokens & Token-Family Rotation

Refresh tokens allow clients to obtain new access tokens without requiring the user to re-enter credentials.

- **Format:** Cryptographically secure 64-character URL-safe random string (`secrets.token_urlsafe(48)` — 384 bits of entropy).
- **Storage Rule:** **RAW REFRESH TOKENS ARE NEVER STORED IN POSTGRESQL.**
- **Cryptographic One-Way Hashing:**
  Raw refresh tokens are high-entropy cryptographic strings (`secrets.token_urlsafe(48)`). The backend calculates and stores strictly the one-way SHA-256 hash:
  $$\text{token\_hash} = \text{SHA256}(\text{raw\_refresh\_token})$$
  **Critical Rule:** Raw refresh tokens are never persisted in PostgreSQL or logs under any circumstance. Because SHA-256 is mathematically irreversible, the server cannot reconstruct or re-issue a previously generated raw token from its hash.
- **Strict Single-Use Rotating Tokens (Zero Insecure Grace Window):**
  When `/api/v1/auth/refresh` is called:
  1. Hash incoming raw token: $H = \text{SHA256}(T_{\text{in}})$.
  2. Inside a database transaction, acquire an exclusive row lock on the token and session:
     ```sql
     SELECT rt.*, us.* 
     FROM refresh_tokens rt
     JOIN user_sessions us ON rt.session_id = us.session_id
     WHERE rt.token_hash = :hash
     FOR UPDATE;
     ```
  3. If token or session not found, session is revoked (`is_revoked == True`), or token is individually revoked (`rt.is_revoked == True`), or expired: Reject with `HTTP 401 Unauthorized`.
  4. **Strict Atomic Consumption Check:**
     - If `rt.used_at IS NOT NULL`:
       - **TOKEN REUSE / REPLAY BREACH DETECTED:** This token has already been consumed.
       - Under pure single-use rotation, an already-consumed token is never accepted again. There is **no insecure grace window**; accepting replayed tokens opens a dangerous attack window where eavesdroppers or malware can replay intercepted tokens.
       - **Action:** Immediately revoke the entire session family:
         ```sql
         UPDATE user_sessions SET is_revoked = TRUE, revoked_reason = 'token_reuse' WHERE session_id = :session_id;
         ```
       - Emit a high-severity security alert log containing client IP and user agent.
       - Reject immediately with `HTTP 401 Unauthorized` (`error_code: "TOKEN_REUSE_DETECTED"`).
  5. If valid (`rt.used_at IS NULL`):
     - Mark current token as consumed: `rt.used_at = now()`.
     - Generate a new cryptographic raw refresh token $T_{\text{new}}$ and access token.
     - Insert a new `refresh_tokens` child record:
       - `token_hash = SHA256(T_{\text{new}})`
       - `parent_token_hash = H` (maintaining cryptographic lineage)
       - `expires_at = now() + 7 days`
     - Update session `last_activity_at = now()`.
     - Commit transaction and return $T_{\text{new}}$ and access token to client.
- **Concurrency & Client-Side Single-Flight Handling:**
  - Legitimate concurrent refresh attempts (e.g. multiple parallel frontend network requests encountering token expiration simultaneously) must **never** compete on the wire.
  - Both web and mobile clients implement single-flight deduplication:
    - **Web (Storefront & Management):** A shared module-scoped Promise memoizes the active `/auth/refresh` flight. Concurrent 401 interceptors await the same in-flight Promise and reuse the rotated access token.
    - **Mobile (Flutter):** An asynchronous mutex lock (`Completer<bool>` in `ApiClient`) serializes 401 recovery; the first request performs the rotation, and queued requests await resolution and replay with the fresh token.
- **Safe Handling of Lost Network Responses (Network Drops):**
  - If a network failure occurs after the backend commits rotation but before the client receives the HTTP response containing $T_{\text{new}}$:
    - The client only has consumed $T_{\text{in}}$, which the server will reject on subsequent presentation.
    - **Safe Standard Recovery:** The client must clear stored local tokens and prompt the user to re-authenticate with primary credentials.
    - Attempting to bypass single-use guarantees or caching unhashed tokens to "recover" from lost responses introduces catastrophic replay vulnerabilities. Re-authentication upon unrecoverable mid-response socket disconnects is the industry-standard security posture (RFC 6749 / RFC 9700).
- **Lifespan Constraints:**
  - Rolling inactivity expiration: **7 days** from last use (`REFRESH_TOKEN_EXPIRE_DAYS = 7`).
  - Absolute session maximum lifetime: **30 days** (`MAX_SESSION_LIFETIME_DAYS = 30`). After 30 days, the user must re-authenticate with primary credentials.
  - Multi-session concurrency: Users can have multiple independent active sessions (e.g. mobile app + desktop browser), each with its own `session_id` and `token_family`.

### 3.3 Password Policy & Cryptographic Upgrades

1. **Complexity Rules:**
   - Minimum length: **8 characters** (10+ recommended in UI).
   - Character classes: Must contain at least 1 uppercase letter (`[A-Z]`), 1 lowercase letter (`[a-z]`), 1 number (`[0-9]`), and 1 special symbol (`[!@#$%^&*(),.?":{}|<>-]`).
   - Validated via Pydantic validator in [`RegisterRequest`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/backend/app/schemas/auth.py#L7), [`UserCreate`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/backend/app/schemas/user.py), and [`ChangePasswordRequest`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/backend/app/schemas/auth.py#L45).
2. **Backward-Compatibility Preservation:**
   - Existing user accounts with simpler passwords remain valid for login.
   - Strict complexity rules apply only upon **new registration** or **password update/reset**.
3. **Session Revocation on Password Change:**
   - When a user successfully changes their password via `PUT /api/v1/auth/change-password`:
     - The backend revokes **all active sessions** (`UPDATE user_sessions SET is_revoked = TRUE, revoked_reason = 'password_changed' WHERE user_id = :uid`).
     - A fresh session is established for the current client, issuing a new token pair.
4. **Account Enumeration & Timing Side-Channel Defense:**
   - In `AuthService.login`: If the user email does not exist in the database, execute a dummy bcrypt hash verification against a constant pre-computed hash:
     ```python
     if not user:
         verify_password(data.password, DUMMY_BCRYPT_HASH)
         raise HTTPException(status_code=401, detail="Invalid email or password.")
     ```
   - This ensures the API response time is identical regardless of whether an email exists, defeating automated user enumeration scripts.

---

## 4. Client-Side Security & Token Lifecycle Architecture

### 4.1 Next.js Web Clients (Storefront & Management)

#### A. The `localStorage` XSS Vulnerability
Tokens in `localStorage` can be accessed by any third-party script, injected tag, or compromised npm dependency running in the browser. Storing refresh tokens in `localStorage` would grant persistent attacker access.

#### B. Dual-Cookie & Memory Architecture
1. **Refresh Token in HttpOnly Cookie:**
   - On successful login or refresh, FastAPI sets an `HttpOnly`, `Secure`, `SameSite=Lax` cookie named `blue_panda_refresh`:
     ```http
     Set-Cookie: blue_panda_refresh=bpr_xxx; Path=/api/v1/auth; HttpOnly; Secure; SameSite=Lax; Max-Age=604800
     ```
   - Browser JavaScript has zero access to this cookie, eliminating XSS token theft.
   - Cross-domain cookie scope:
     - Production: `Domain=.bluepanda.com` allows sharing between `shop.bluepanda.com`, `manage.bluepanda.com`, and `api.bluepanda.com`.
     - Development: Host-only cookie on `localhost` is natively sent across ports (`:3000`, `:3001`, `:8000`).
2. **Access Token in In-Memory Module Scope:**
   - Short-lived access tokens (15 minutes) are held in memory (JavaScript closure or Zustand transient state), not written to `localStorage`.
   - On page refresh or new tab, the application makes a silent POST to `/api/v1/auth/refresh` (which automatically includes the HttpOnly cookie) to restore the in-memory access token.
3. **CSRF Protection on Cookie Endpoints:**
   - Cross-Site Request Forgery (CSRF) is prevented by requiring a custom header on `POST /api/v1/auth/refresh`:
     ```http
     X-Requested-With: XMLHttpRequest
     ```
   - Browsers forbid cross-origin HTML `<form>` or `<img>` requests from attaching custom headers without CORS preflight approval.

### 4.2 Flutter Mobile Client

1. **Native Secure Storage:**
   - Replace unencrypted `SharedPreferences` with `flutter_secure_storage`:
     - iOS: Hardware-backed Keychain with `kSecAttrAccessibleAfterFirstUnlock`.
     - Android: `EncryptedSharedPreferences` backed by Android Keystore.
2. **Thread-Safe Mutex Token Refresh Interceptor:**
   - When any authenticated request in [`ApiClient`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/mobile-app/lib/core/network/api_client.dart#L11) receives an `HTTP 401 Unauthorized`:
     - If the failing request is NOT `/auth/login` or `/auth/refresh`:
       - Acquire an asynchronous lock (`Completer<bool>` mutex) to prevent concurrent refresh races when multiple widgets fetch data simultaneously.
       - If a refresh is already in progress, await the existing future.
       - If first to catch 401:
         - Dispatch `POST /api/v1/auth/refresh` with stored `refresh_token`.
         - On 200 OK: Persist rotated `access_token` and `refresh_token`, update `ApiClient._authToken`, and replay the failed request.
         - On 401/403 Failure: Token family has expired or been revoked. Clear secure storage, invoke `globalOnUnauthorized`, and navigate cleanly to Login.
3. **Cart & Offline State Preservation:**
   - Transparent token refresh ensures checkout flows, cart modifications, and profile updates never fail abruptly due to routine token expiry.

---

## 5. Database Schema & Migration Specification

### 5.1 Parent-Child Architecture: `user_sessions` and `refresh_tokens`

To ensure atomic refresh-token rotation, retain token history for replay detection, and maintain clean separation of device session metadata from cryptographic token hashes, the schema uses a robust parent-child architecture:

1. **`user_sessions` (Parent):** Manages the logical client device session, user ownership, activity timestamps, and instant revocation state across all devices.
2. **`refresh_tokens` (Child):** Tracks the cryptographic lifecycle of individual rotating refresh tokens within that session, recording their SHA-256 hashes, creation, consumption (`used_at`), and parentage.

```sql
-- 1. Parent Table: User Sessions
CREATE TABLE user_sessions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(36) NOT NULL UNIQUE,          -- UUIDv4 session identifier
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_family VARCHAR(36) NOT NULL,               -- Family UUID for rotation/reuse tracking
    ip_address VARCHAR(45) NULL,                     -- Client IP (IPv4 or IPv6)
    user_agent VARCHAR(255) NULL,                    -- Client user-agent string
    device_name VARCHAR(100) NULL,                   -- Human-readable client label (e.g. "Safari on macOS")
    is_revoked BOOLEAN NOT NULL DEFAULT FALSE,       -- Revocation status flag
    revoked_reason VARCHAR(50) NULL,                 -- Reason: logout, reuse, password_change
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,    -- Absolute session expiration
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    last_activity_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

CREATE INDEX ix_user_sessions_session_id ON user_sessions(session_id);
CREATE INDEX ix_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX ix_user_sessions_token_family ON user_sessions(token_family);
CREATE INDEX ix_user_sessions_expires_at ON user_sessions(expires_at);

-- 2. Child Table: Refresh Tokens (Rotation & Replay Detection History)
CREATE TABLE refresh_tokens (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(36) NOT NULL REFERENCES user_sessions(session_id) ON DELETE CASCADE,
    token_hash VARCHAR(64) NOT NULL UNIQUE,          -- SHA-256 hash of active/used refresh token
    parent_token_hash VARCHAR(64) NULL,              -- Token hash that was rotated to produce this one
    is_revoked BOOLEAN NOT NULL DEFAULT FALSE,       -- Individual token revocation flag
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,    -- Expiration timestamp (rolling 7 days)
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    used_at TIMESTAMP WITH TIME ZONE NULL            -- Non-null indicates token has been consumed
);

CREATE INDEX ix_refresh_tokens_session_id ON refresh_tokens(session_id);
CREATE INDEX ix_refresh_tokens_token_hash ON refresh_tokens(token_hash);
CREATE INDEX ix_refresh_tokens_expires_at ON refresh_tokens(expires_at);
```

### 5.2 SQLAlchemy 2 Model Specification

```python
class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_family: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    device_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    revoked_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="sessions")
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken", back_populates="session", cascade="all, delete-orphan"
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("user_sessions.session_id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    parent_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    session: Mapped["UserSession"] = relationship("UserSession", back_populates="refresh_tokens")
```

### 5.3 Automated Session Maintenance & Cleanup
Expired or revoked session rows and old consumed tokens are pruned periodically:
```sql
-- Prune old sessions
DELETE FROM user_sessions 
WHERE expires_at < now() - INTERVAL '30 days' 
   OR (is_revoked = TRUE AND last_activity_at < now() - INTERVAL '7 days');

-- Prune consumed refresh tokens older than 14 days
DELETE FROM refresh_tokens
WHERE used_at IS NOT NULL AND used_at < now() - INTERVAL '14 days';
```

---

## 6. Phase 1B Rate Limiting Integration & Security Dependencies

1. **Throttling on Refresh Endpoint:**
   - The new `POST /api/v1/auth/refresh` endpoint must be protected by the Phase 1B rate limiter:
     - Rate limit: **10 requests/minute per client IP** (`scope="auth:refresh"`).
     - Protects against brute-forcing refresh tokens and denial-of-service rotation floods.
2. **Reverse Proxy Trust Verification:**
   - Both `/auth/login` and `/auth/refresh` rely on [`ClientIpResolver`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/backend/app/core/rate_limit.py#L71) to extract the genuine client IP behind Caddy, ignoring forged `X-Forwarded-For` headers from untrusted direct sockets.
3. **Multi-Worker Production Notice:**
   - Multi-worker production environments (`BACKEND_WORKERS=2`) maintain isolated in-memory stores per worker process.
   - For globally synchronized rate limiting across all workers, Redis storage must be configured via `RATE_LIMIT_STORAGE_URL` prior to public internet exposure.

---

## 7. Compatibility, Deployment & Rollback Strategy

### 7.1 Zero-Downtime Deployment Compatibility
- The `user_sessions` table is an additive schema migration. Existing tables (`users`, `products`, `orders`) are not modified.
- Legacy clients sending old 7-day access tokens will continue to work until their tokens expire, as `decode_access_token` can support backward-compatible validation for tokens lacking `session_id` during a 7-day transition window.
- The `POST /api/v1/auth/login` response maintains backward compatibility:
  ```json
  {
    "success": true,
    "message": "Login successful.",
    "data": {
      "access_token": "eyJhbGciOi...",
      "refresh_token": "bpr_xxx...",
      "token_type": "bearer",
      "user": { ... }
    }
  }
  ```
  Legacy code reading `data.access_token` or `data.token` continues to function seamlessly.

### 7.2 Rollback Procedure
If unexpected issues arise in production:
1. Revert backend code to Phase 1B commit.
2. The `user_sessions` table remains dormant without impacting core application functions.
3. If necessary, execute Alembic downgrade:
   ```bash
   rtk alembic downgrade c4b8d91a2e3f
   ```
   (which safely drops `user_sessions` without touching customer or catalog records).
