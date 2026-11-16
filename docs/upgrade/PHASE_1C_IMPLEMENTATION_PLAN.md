# Blue Panda E-Commerce — Phase 1C: Implementation Plan

**Document ID:** BP-PLAN-PHASE-1C  
**Author:** Senior Authentication Architect & Full-Stack Engineering Team  
**Status:** Implementation Plan Formulated — Awaiting Authorization  
**Target Milestone:** Phase 1C: JWT Revocation, Refresh Tokens & Password Hardening  
**Prerequisites:** Phase 1A, Phase 1A.1, and Phase 1B Complete & Verified  
**Parent Design:** [`docs/upgrade/PHASE_1C_AUTH_SECURITY_DESIGN.md`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/docs/upgrade/PHASE_1C_AUTH_SECURITY_DESIGN.md)

---

## 1. Master Implementation Task Breakdown

To ensure zero downtime, backward compatibility, and rigorous test coverage, Phase 1C is broken down into eight focused, sequential implementation tasks:

```
                                  PHASE 1C EXECUTION ROADMAP
                                  
  +-------------------------------------------------------------------------+
  | Task 1: Backend Session & Token Models (SQLAlchemy & Pydantic Schemas)   |
  +------------------------------------+------------------------------------+
                                       |
  +------------------------------------v------------------------------------+
  | Task 2: Alembic Migration (user_sessions) & Isolated PostgreSQL Tests   |
  +------------------------------------+------------------------------------+
                                       |
  +------------------------------------v------------------------------------+
  | Task 3: Refresh-Token Rotation, Reuse Detection & POST /auth/refresh    |
  +------------------------------------+------------------------------------+
                                       |
  +------------------------------------v------------------------------------+
  | Task 4: Server-Side Revocation on Logout & Password-Change Security     |
  +------------------------------------+------------------------------------+
                                       |
  +------------------------------------v------------------------------------+
  | Task 5: Next.js Storefront HttpOnly Cookie & Silent Refresh Flow        |
  +------------------------------------+------------------------------------+
                                       |
  +------------------------------------v------------------------------------+
  | Task 6: Next.js Management Portal Role-Guard & Silent Refresh Flow      |
  +------------------------------------+------------------------------------+
                                       |
  +------------------------------------v------------------------------------+
  | Task 7: Flutter Mobile App Keychain Storage & Mutex Token Interceptor   |
  +------------------------------------+------------------------------------+
                                       |
  +------------------------------------v------------------------------------+
  | Task 8: End-to-End Authentication Regression & Security Verification    |
  +-------------------------------------------------------------------------+
```

---

## Task 1: Backend Session & Token Models

### Objective
Define the SQLAlchemy 2 `UserSession` model and Pydantic request/response schemas for refresh tokens and password complexity validation.

### Files Involved
- `backend/app/models/session.py` (New Model)
- `backend/app/models/user.py` (Add `sessions` relationship)
- `backend/app/models/__init__.py` (Register `UserSession` for Base metadata)
- `backend/app/schemas/auth.py` (Add `RefreshTokenRequest`, update `TokenResponse`, `RegisterRequest`, `ChangePasswordRequest`)

### Proposed Changes
1. **Model `UserSession`:**
   - Define fields: `id`, `session_id` (UUIDv4), `user_id` (FK `users.id`), `token_hash` (SHA-256 string), `token_family` (UUIDv4), `ip_address`, `user_agent`, `device_name`, `is_revoked`, `revoked_reason`, `expires_at`, `created_at`, `last_used_at`.
   - Setup relationship with `User`: `sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")`.
2. **Schemas:**
   - `RefreshTokenRequest`: `refresh_token: str` (validated non-empty string).
   - `TokenResponse`: Add `refresh_token: str | None = None` and `expires_in: int = 900`.
   - `RegisterRequest` & `ChangePasswordRequest`: Add regex password validator requiring $\ge 8$ chars, $\ge 1$ uppercase, $\ge 1$ lowercase, $\ge 1$ number, $\ge 1$ special character.

### Acceptance Criteria
- [ ] `UserSession` model compiles cleanly under SQLAlchemy 2.
- [ ] Password validation rejects weak passwords (`"short"`, `"password"`, `"12345678"`) with clear validation error messages.
- [ ] Strong passwords (`"SecurePass123!"`) pass schema validation.

### Tests Required
- Unit tests in `backend/tests/test_auth_schemas.py` testing password validation regex boundaries.

### Complexity & Risk
- **Complexity:** Low (0.5 day).
- **Risk:** None. Purely additive models and schemas.

---

## Task 2: Alembic Migration & Isolated PostgreSQL Tests

### Objective
Create an Alembic migration script to create the `user_sessions` table with indexes, and write migration tests against an isolated database.

### Files Involved
- `backend/alembic/versions/<revision>_add_user_sessions_table.py` (New Migration)
- `backend/tests/test_migrations_postgres.py` (Add `user_sessions` schema checks)

### Proposed Changes
1. **Alembic Migration Script:**
   - Use defensive inspector checks: `if 'user_sessions' not in existing_tables:`.
   - Create table with foreign key `ondelete="CASCADE"`.
   - Create indexes on `session_id`, `user_id`, `token_hash`, and `expires_at`.
   - Define `downgrade()`: `op.drop_table('user_sessions')`.
2. **Migration Verification:**
   - Test upgrade from current head `c4b8d91a2e3f` to new revision.
   - Verify rollback from new revision back to `c4b8d91a2e3f`.

### Acceptance Criteria
- [ ] Migration runs idempotently on fresh and pre-existing databases.
- [ ] All 4 indexes are successfully created in PostgreSQL.
- [ ] Downgrade cleanly drops `user_sessions` without impacting `users` table.

### Tests Required
- `backend/tests/test_migrations_postgres.py` upgrade and downgrade test steps.

### Complexity & Risk
- **Complexity:** Low (0.5 day).
- **Risk:** Low. Table is purely additive; no existing tables are altered.

---

## Task 3: Refresh-Token Rotation, Reuse Detection & POST /auth/refresh

### Objective
Implement secure token generation, SHA-256 hashed storage, rotation on use, automatic token reuse breach detection, and the `POST /api/v1/auth/refresh` endpoint.

### Files Involved
- `backend/app/core/security.py` (Update `create_access_token`, add `generate_refresh_token`, `hash_refresh_token`)
- `backend/app/services/auth_service.py` (Add `refresh_token()`, update `login()`, `register()`)
- `backend/app/api/v1/routes/auth.py` (Add `POST /refresh` with Phase 1B rate limiting)

### Proposed Changes
1. **Security Functions:**
   - `create_access_token(data, session_id, role, expires_delta=None)`: Injects `type: "access"`, `jti`, `session_id`, `iss`, `aud`, `iat`, `exp` (15 minutes).
   - `generate_refresh_token()`: Returns 64-character URL-safe string.
   - `hash_refresh_token(raw_token)`: Returns SHA-256 hex digest.
2. **Refresh Logic in `AuthService.refresh_token`:**
   - Execute under database transaction with row-level lock (`SELECT ... FOR UPDATE`).
   - Look up child `RefreshToken` joined with `UserSession` by SHA-256 token hash.
   - Check if revoked or expired.
   - Strict reuse detection: If `used_at IS NOT NULL`, a breach/replay is detected &mdash; immediately revoke the entire session (`is_revoked = True, revoked_reason = 'token_reuse'`), log high-severity security alert, and reject with `HTTP 401 Unauthorized` (`error_code: "TOKEN_REUSE_DETECTED"`). No insecure grace window is permitted.
   - If `used_at IS NULL`: mark `used_at = now()`, insert new `RefreshToken` record with `parent_token_hash`, update session `last_activity_at = now()`, and issue rotated access token + new raw refresh token.
3. **Route Mounting:**
   - Mount `POST /auth/refresh` on both `/api` and `/api/v1`.
   - Rate limit to 10 req/min via `Depends(RateLimiter(times=10, seconds=60, scope="auth:refresh"))`.
   - Support dual-mode input: reads refresh token from `HttpOnly` cookie or JSON body.

### Acceptance Criteria
- [ ] `POST /api/v1/auth/refresh` returns 200 with new access token and rotated refresh token when given a valid token.
- [ ] Presenting an expired refresh token returns `HTTP 401 Unauthorized`.
- [ ] Presenting an already-used refresh token revokes all family sessions and returns `HTTP 401 Unauthorized` (`error_code: "TOKEN_REUSE_DETECTED"`).
- [ ] Exceeding 10 refresh requests in 1 minute triggers `HTTP 429 Too Many Requests`.

### Tests Required
- `backend/tests/test_token_rotation.py`: Valid rotation, expired token, reuse breach detection, transaction concurrency locks, rate limiting.

### Complexity & Risk
- **Complexity:** Medium (1.5 days).
- **Risk:** Low-Medium. Client-side single-flight deduplication prevents wire race conditions, while atomic row-level locks protect backend state integrity. Lost network responses are safely resolved via clean reauthentication without compromising single-use token security.

---

## Task 4: Server-Side Revocation on Logout & Password-Change Security

### Objective
Modernize `POST /auth/logout` and `PUT /auth/change-password` to enforce server-side session revocation.

### Files Involved
- `backend/app/core/dependencies.py` (Check `session_id` against `user_sessions` revocation state)
- `backend/app/services/auth_service.py` (Update `logout()`, `change_password()`)
- `backend/app/api/v1/routes/auth.py` (Update `/logout`, add `POST /logout-all`)

### Proposed Changes
1. **`get_current_user` Dependency Update:**
   - After validating JWT signature and `exp`, verify `payload.get("type") == "access"`.
   - Check `session_id`: Query DB (or Redis if enabled) to ensure `is_revoked == False`.
   - If session revoked: Raise `HTTP 401 Unauthorized` (`"Session has been revoked"`).
2. **Logout Endpoint Update:**
   - Extract `session_id` from bearer token.
   - Mark session `is_revoked = True, revoked_reason = 'logout'`.
   - Clear refresh token cookie in response (`Max-Age=0`).
3. **`POST /logout-all` Endpoint:**
   - Revokes all sessions for `current_user.id`.
4. **Password Change Security Update:**
   - Revoke all other sessions for the user upon password change.
   - Equalize timing on failed password verifications with dummy hashes.

### Acceptance Criteria
- [ ] Calling `POST /auth/logout` immediately invalidates the token; subsequent API requests with that token return `401 Unauthorized`.
- [ ] Changing a password invalidates other active device sessions.
- [ ] Access tokens lacking a valid session fail authorization.

### Tests Required
- `backend/tests/test_auth_revocation.py`: Logout single device, logout all devices, password change revocation, dummy-hash timing verification.

### Complexity & Risk
- **Complexity:** Medium (1 day).
- **Risk:** Low. Database queries on `session_id` are indexed (`ix_user_sessions_session_id`).

---

## Task 5: Next.js Storefront Integration

### Objective
Migrate the Storefront customer portal from `localStorage` token storage to in-memory access tokens backed by `HttpOnly` refresh cookies with transparent silent refresh.

### Files Involved
- `storefront/src/lib/auth.ts`
- `storefront/src/lib/api.ts`
- `storefront/src/app/(auth)/login/page.tsx`

### Proposed Changes
1. **Auth Storage Modernization (`storefront/src/lib/auth.ts`):**
   - Store access token in an in-memory variable `let inMemoryAccessToken: string | null = null;`.
   - Store public user metadata in `localStorage` for UI hydration, but remove access token from persistent storage.
   - Implement `silentRefresh()`: Calls `POST /api/v1/auth/refresh` (browser sends HttpOnly cookie automatically).
2. **API Client Request Interceptor (`storefront/src/lib/api.ts`):**
   - If a request returns `401 Unauthorized`:
     - Avoid immediately calling `logout()`.
     - Attempt `silentRefresh()`.
     - On success: Retry the original request with the new access token.
     - On failure: Call `logout()` and redirect to `/login?expired=true`.
3. **Logout:**
   - Dispatches `POST /api/v1/auth/logout` to clear server session and remove cookie.

### Acceptance Criteria
- [ ] Access tokens are never written to `localStorage`.
- [ ] Expired access tokens automatically refresh in the background without UI interruption.
- [ ] Clicking Logout revokes the server session and clears client state.
- [ ] Existing cart, favorites, and checkout flows continue to function seamlessly.

### Tests Required
- Storefront unit tests in `storefront/src/lib/__tests__/auth-refresh.test.ts`.

### Complexity & Risk
- **Complexity:** Medium (1 day).
- **Risk:** Low. Fallback to `/login` is preserved if refresh fails.

---

## Task 6: Management Portal Integration

### Objective
Update the Management portal (Admin and Seller roles) with the identical in-memory + HttpOnly cookie architecture, preserving role routing and session isolation.

### Files Involved
- `management/src/lib/auth.ts`
- `management/src/lib/api.ts`
- `management/src/app/(auth)/login/page.tsx`

### Proposed Changes
1. Mirror Storefront's in-memory access token and silent refresh pattern while preserving `mgmt_` namespacing.
2. Ensure admin and seller role guards continue to clamp users strictly to `/admin/dashboard` or `/seller`.
3. Clear server sessions and HttpOnly cookies on logout.

### Acceptance Criteria
- [ ] Admin and seller access tokens are kept in memory only.
- [ ] Long-running dashboard sessions refresh smoothly without logging the user out.
- [ ] Role routing guards enforce permissions identically.

### Tests Required
- `management/src/lib/__tests__/role-routing.test.mjs` and new auth refresh tests.

### Complexity & Risk
- **Complexity:** Medium (1 day).
- **Risk:** Low.

---

## Task 7: Flutter Mobile App Integration

### Objective
Migrate mobile auth from plain `SharedPreferences` to `flutter_secure_storage`, and add a mutex-protected token refresh interceptor in `ApiClient`.

### Files Involved
- `mobile-app/pubspec.yaml` (Add `flutter_secure_storage`)
- `mobile-app/lib/core/network/api_client.dart`
- `mobile-app/lib/features/auth/services/auth_api_service.dart`
- `mobile-app/lib/features/auth/providers/auth_provider.dart`

### Proposed Changes
1. **Secure Storage Service:**
   - Encrypt `access_token` and `refresh_token` in Keychain / Keystore.
2. **`ApiClient` Mutex Refresh Interceptor:**
   - Wrap 401 handling in an asynchronous lock (`Completer<bool>`).
   - If access token expires, dispatch `POST /api/v1/auth/refresh` using stored `refresh_token`.
   - Update stored tokens and replay original request.
   - If refresh fails, execute `globalOnUnauthorized` and wipe local state.

### Acceptance Criteria
- [ ] Mobile access and refresh tokens are encrypted in secure storage.
- [ ] Simultaneous in-flight requests that hit 401 trigger only **one** refresh network request.
- [ ] The app automatically recovers from token expiry without ejecting the user from checkout.

### Tests Required
- `mobile-app/test/core/network/api_network_test.dart` and `auth_provider_test.dart`.

### Complexity & Risk
- **Complexity:** Medium (1.5 days).
- **Risk:** Medium. Requires careful async synchronization to avoid race conditions.

---

## Task 8: End-to-End Authentication Regression & Security Verification

### Objective
Execute comprehensive automated security verification across backend, web, and mobile to confirm complete abuse defense and regression-free operation.

### Test Suites to Run
1. `backend/tests/test_rate_limiting.py` (Phase 1B verification)
2. `backend/tests/test_token_rotation.py` (New Phase 1C verification)
3. `backend/tests/test_auth_revocation.py` (New Phase 1C verification)
4. Full backend test suite (`pytest -k "not postgres"`)
5. Storefront test suite (`npm test`)
6. Management test suite (`npm test`)
7. Flutter test suite (`flutter test` and `flutter analyze`)

### Acceptance Criteria
- [ ] 100% of tests pass across backend, storefront, management, and mobile.
- [ ] `flutter analyze` reports 0 issues.
- [ ] Stolen tokens are verified to fail after logout or password change.
- [ ] Replayed refresh tokens trigger immediate breach revocation.

---

## 2. Summary Timeline & Recommended First Task

| Task | Estimated Effort | Primary Subsystem |
| :--- | :--- | :--- |
| **Task 1: Backend Session & Token Models** | **0.5 day** | FastAPI / SQLAlchemy / Pydantic |
| **Task 2: Alembic Migration & Isolated DB Tests** | **0.5 day** | Alembic / PostgreSQL |
| **Task 3: Refresh-Token Rotation & POST /auth/refresh** | **1.5 days** | FastAPI / Security Core |
| **Task 4: Server-Side Revocation on Logout & Passwords** | **1.0 day** | FastAPI / Auth Routes |
| **Task 5: Next.js Storefront Integration** | **1.0 day** | Next.js / TypeScript |
| **Task 6: Next.js Management Portal Integration** | **1.0 day** | Next.js / TypeScript |
| **Task 7: Flutter Mobile App Integration** | **1.5 days** | Flutter / Dart |
| **Task 8: End-to-End Authentication Regression** | **1.0 day** | Full Monorepo |
| **Total Estimated Effort** | **8.0 days** | Full-Stack Multi-Client |

### Recommended First Implementation Task
When authorized, start with **Task 1: Backend Session & Token Models**:
1. Implement the `UserSession` model in [`backend/app/models/session.py`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/backend/app/models/) and wire it to [`User`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/backend/app/models/user.py#L17).
2. Update [`backend/app/schemas/auth.py`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/backend/app/schemas/auth.py) with `RefreshTokenRequest` and password complexity validators.
3. Add isolated unit tests validating schema boundaries before executing any database changes.
