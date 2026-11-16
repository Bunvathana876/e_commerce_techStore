# Blue Panda Secure Authentication Sessions — Implementation and Rollout Review

**Document Version:** 1.0.0  
**Date:** 2026-11-07  
**Status:** Backend prepared for review; not deployed  
**Target Scope:** `backend/`; client integration and production operations remain separate review steps  
**Phase 1B follow-up (2026-11-07):** Client logout integration and the shipping
issuance default are updated in [the Phase 1B report](PHASE_1B_AUTH_CLIENT_INTEGRATION_REPORT.md).
That report supersedes the original default-enabled rollout wording below.

**Related Documents:** [Original design](PHASE_1C_AUTH_SECURITY_DESIGN.md), [Original plan](PHASE_1C_IMPLEMENTATION_PLAN.md)

## 1. Outcome and inspected architecture

Implemented database-backed access validation, device logout, account-wide logout,
password-change revocation, opaque refresh rotation and replay detection. Both
`/api` and `/api/v1` retain the existing response envelope and login aliases.
No production service, Supabase database, real user account, or real environment
file was changed. No dependencies were added. Migrations ran only in temporary
PostgreSQL databases created by pytest, with TCP connections disabled.

Before this change:

- `security.py` signed JWTs containing `sub` and `exp`.
- `dependencies.py` checked the signature, expiry and current active database user,
  then applied the existing role dependencies. No session lookup occurred.
- `UserSession`, `RefreshToken` and revision `a1b2c3d4e5f6` already existed but were
  not used by login, logout or password changes.
- Logout returned success without revocation. Password changes updated the hash
  without invalidating tokens. No refresh endpoint existed.
- Both web applications retain tokens in localStorage and log out locally.
  Flutter uses SharedPreferences and currently clears its API bearer token before
  attempting remote logout.

## 2. Backend behavior and compatibility

### Access modes

| Request/client | Access lifetime | Refresh token | Server validation |
|---|---|---|---|
| Existing login/register JSON, unchanged | Existing `ACCESS_TOKEN_EXPIRE_MINUTES` | `null` | Active user plus non-revoked, unexpired session owned by that user |
| Login/register with `use_refresh_tokens: true` | `SESSION_ACCESS_TOKEN_EXPIRE_MINUTES`, default 15 | Opaque, rotating | Same session validation, plus strict modern JWT claims |
| Previously issued legacy JWT | Original signed expiration, never extended | None | Lazily adopted into a deterministic per-token session during the compatibility window |

The `access_token`, `token`, `token_type`, `user`, `success`, `message` and `data`
contracts remain available. `expires_in` now reports the lifetime actually issued.
No existing client must implement refresh to keep its current login behavior.
Legacy and bearer-only lifetimes are intentionally retained until a coordinated
client rollout; this phase does not silently shorten all deployed sessions.

Modern JWTs require signature, `sub`, `exp`, `iat`, `jti`, `type=access`,
`session_id`, configured issuer and audience. A missing/revoked/expired session or
session owned by another user is rejected. Roles and ownership still come from
current database records, never from client metadata or JWT role hints. Invalid
credentials cannot downgrade to anonymous access on optional-auth routes.

### Routes

All paths below exist under both prefixes.

| Method/path | Request | Result |
|---|---|---|
| `POST /auth/login` | Existing email/password; optional `use_refresh_tokens` | Existing login response with accurate lifetime; optional refresh credential |
| `POST /auth/register` | Existing registration fields; optional `use_refresh_tokens` | Customer registration and session committed atomically |
| `POST /auth/refresh` | JSON `refresh_token` | New access credential and a replacement refresh credential |
| `POST /auth/logout` | Valid bearer access token | Revokes the associated session and its refresh credentials |
| `POST /auth/logout-all` | Valid bearer access token | Revokes all of the authenticated user's sessions and blocks unseen legacy tokens |
| `PUT /auth/change-password` | Existing current/new password fields and bearer token | Changes password and revokes all sessions, including the caller, in one transaction |

An administrator password reset through the existing user-update endpoint also
revokes the target user's sessions. No account is deleted, reseeded, renamed,
promoted, demoted, or forced to adopt a new password merely by this migration.
Repeated logout using an already-revoked token returns 401; local client cleanup
must still complete. Revocation blocks subsequent requests; it cannot cancel a
business request already authenticated and running before the revocation commits.

### Rotation and replay

- Generate 48 random bytes with the platform cryptographic RNG and URL-safe encoding.
- Store only the SHA-256 digest in `refresh_tokens`; return the raw credential only
  to its authenticated client in the token response.
- Serialize session mutations with PostgreSQL locks in user → session → token order.
  An additional conditional `used_at IS NULL` update enforces single consumption.
- Mark the presented token used and insert its replacement in the same transaction.
  Retain parent hashes to preserve rotation history.
- Reusing a consumed token revokes its entire token family and all family refresh
  credentials. Commit the revocation before returning 401 with
  `error_code=TOKEN_REUSE_DETECTED`. Other device families remain valid.
- Session/refresh expiry is absolute, default 30 days for refresh-enabled sessions.
  Rotation never extends it; access expiry is capped by the remaining session life.
- Refresh quotas use the existing limiter: 10/minute by default, shared across
  `/api` and `/api/v1`. No bearer token is required to refresh an expired access token.
- Unknown, expired, revoked and unavailable-account refresh requests fail closed.
  Request validation omits credential input. Auth responses carry `no-store`.
  Security logs record the replay event without token, password or secret values.

There is deliberately no replay grace window. Concurrent use, multi-tab races, and
retrying after a lost successful refresh response can revoke that device family.
Clients must use single-flight rotation and ask for fresh login when recovery is
ambiguous. Rotation follows the replay-detection pattern in
[RFC 9700 section 4.14](https://www.rfc-editor.org/rfc/rfc9700.html#section-4.14).
Claim requirements use the existing PyJWT dependency's
[required-claim validation](https://pyjwt.readthedocs.io/en/stable/usage.html).

## 3. Prepared migration and legacy-token strategy

New revision: `d7e8f9012abc`, following `a1b2c3d4e5f6`.

The revision adds one nullable `users.legacy_tokens_revoked_at` timestamp without
a default, backfill, credential update, role update, or seller relationship change.
Existing session models/tables and indexes are reused. Old API code tolerates the
additional nullable column. The new backend requires this revision before serving.

Old tokens have no `iat`, so a timestamp comparison cannot distinguish tokens
issued before a password change. The marker therefore prevents adoption of **all
unregistered legacy tokens** after password change or logout-all. Already-adopted
legacy sessions are explicitly revoked in the same transaction. Fresh logins issue
modern session tokens; during the validation-only rollout they can instead issue
pre-registered legacy credentials following successful password verification.

Legacy adoption uses a deterministic UUID derived from the bearer digest. It never
stores the raw bearer credential, never extends its original expiration, and never
replaces a revoked row with an active one. The current user row is locked before
first adoption so a password change cannot race adoption into bypassing revocation.

No automatic legacy cutoff is imposed in code, to preserve deployed clients.
Approve a cutoff explicitly using `AUTH_LEGACY_ACCEPT_UNTIL` (UTC ISO timestamp),
or disable acceptance with `AUTH_ACCEPT_LEGACY_TOKENS=false` after the old-token
drain period. Keep the existing signing secret and algorithm stable during this
rollout. Rotating signing keys would force existing clients to log in again.

Do not delete revoked legacy session rows before their original expiry or the
approved legacy cutoff: doing so could allow individual logged-out legacy tokens
to be adopted again. Retain used refresh history until its family has expired.
No session-history cleanup job is introduced in this phase.

## 4. Deployment order requiring review and operational approval

1. **Review the code and migration.** Confirm the actual schema/revision in the
   target environment through an approved operator procedure. This task did not
   connect to Supabase or determine its applied revisions. Do not blindly stamp
   Alembic or rerun seed scripts to reconcile drift.
2. **Verify recovery and staging.** Take an approved backup, confirm restore
   procedures, and rehearse the reviewed migration chain on an isolated staging
   database. Preserve administrator/seller identities and relationship counts.
3. **Apply schema before code**, using the approved migration runner only. If the
   session-table revision is not applied, review the full path through that
   revision as well. No migration runs from an auth request or this implementation.
4. **First backend pass: validation-only issuance.** Configure
   `AUTH_ISSUE_SESSION_TOKENS=false` and `AUTH_ACCEPT_LEGACY_TOKENS=true`; keep the
   existing access lifetime. Leave the legacy cutoff unset or in the future.
   Complete the rollout to every API worker. This pass emits old-worker-compatible
   JWTs without an audience claim. Old workers do not enforce revocation, so this
   mixed-worker interval is transitional and cannot be called fully secured.
5. **Second backend pass: enable session-token issuance.** Only after all old API
   workers are drained, set `AUTH_ISSUE_SESSION_TOKENS=true` on every worker. Modern
   JWTs contain an audience that the original decoder would reject. Do not issue
   them while old workers are still receiving traffic. The Phase 1B follow-up changes the shipping default to disabled. Keep it
   explicitly disabled for the first pass; do not skip it.
6. **Verify current deployed clients** using the checklist below with no refresh
   opt-in. Confirm their token lifetime did not change. Verify account-wide password
   revocation intentionally requires a fresh sign-in.
7. **Release reviewed clients**, one at a time. Add remote logout first, then secure
   refresh storage/single-flight behavior and opt-in. Do not switch a client to
   15-minute access tokens before its refresh/recovery implementation is ready.
8. **Approve and schedule legacy retirement** after the last old-worker token can
   expire under the largest previously configured access lifetime. This includes
   tokens issued during the first rollout pass. Monitor sanitized 401/replay/429
   counts and database latency; never record request credential bodies or headers.

Do not downgrade the database for an ordinary application rollback: that destroys
revocation history. Prefer a forward fix or rollback to a tested session-aware
build with matching issuer/audience and schema. Returning to the original decoder
would reject modern tokens and ignore revocation; it is not a safe transparent
rollback. A forced-login/key-rotation recovery plan needs separate approval.

## 5. Required client changes (identified, not implemented)

### Storefront and Management

Relevant files in each app are `src/lib/auth.ts`, `src/lib/api.ts`, and their
account/navigation logout actions. The Management app also has
`src/lib/management-session.ts` and seller role guards.

- Add an asynchronous remote logout action: capture the bearer credential, call
  `/auth/logout`, then synchronously clear existing private state. Always complete
  local cleanup on failure, but do not claim server revocation succeeded offline.
  Current web logout functions do not call the API.
- For refresh opt-in, add the optional login/register field and response types
  (`token`, `expires_in`, `refresh_token`), retaining the existing session epoch
  protection for delayed responses and account switches.
- Design and review a server/BFF-owned HttpOnly, Secure, SameSite cookie flow with
  CSRF/Origin protection and per-application cookie isolation. This backend phase
  accepts refresh **JSON only**, does not set cookies, and does not silently enable
  ambient-cookie auth. Do not store a long-lived refresh credential in localStorage
  as a shortcut. A BFF can call this JSON endpoint while keeping refresh secrets
  server-side. Direct API-cookie support needs a coordinated follow-up contract.
- Keep access tokens in memory in the upgraded architecture. Add single-flight
  refresh, guarded one-time retry, and session-epoch checks so old responses cannot
  restore a logged-out/switched account. Coordinate refresh across browser tabs if
  they share a refresh cookie. Avoid blind retries of non-idempotent mutations or
  ambiguous network failures.
- After password change or logout-all, clear all local auth/private caches and
  require sign-in. Both revoke the current session too.
- Validate backend identity/role after refresh; preserve existing seller/admin
  separation and backend role enforcement.

### Flutter

Relevant files: `lib/features/auth/providers/auth_provider.dart`,
`lib/features/auth/services/auth_api_service.dart`,
`lib/features/auth/services/auth_service.dart`,
`lib/core/network/api_client.dart`, and
`lib/core/constants/api_endpoints.dart`.

- Fix logout ordering: the provider currently clears `ApiClient`'s token before
  its service calls the logout endpoint. Capture/send the old token for revocation
  before clearing it, while retaining immediate local session invalidation and
  private-state cleanup. Prevent a delayed logout response from affecting a new user.
- Add refresh/logout-all endpoints and response parsing, then explicit refresh opt-in.
- Store refresh credentials in native Keychain/Keystore-backed storage. Any new
  secure-storage dependency requires approval; none was added here.
- Replace immediate 401 logout with a single-flight refresh attempt and a guarded
  single retry when the server definitely rejected authentication. Never refresh
  recursively on refresh/logout errors. On replay/revocation, clear secure and
  in-memory state and require login.
- Keep the existing host-only `API_URL` convention; endpoint constants include
  `/api/v1`. Preserve cart/order/notification session-isolation listeners.

## 6. Verification and manual acceptance

Final full-suite command, run from `backend/`:

```bash
rtk .venv/bin/python -m pytest -q -rs
```

**Result: 669 passed, 2 skipped, 2 warnings in 80.58 seconds.** The two skips are
existing Redis integration tests that require a test Redis server on port 6389.
The warnings are existing Starlette/httpx and AnyIO deprecations. No dependency
installation or upgrade was performed to suppress them.

The run includes access expiry and required claims, compatible customer/admin/seller
login, registration, device/account logout, password-change/reset revocation,
unseen legacy-token denial, sequential rotation/replay, cross-prefix rate limiting,
secret-safe validation, and PostgreSQL concurrent rotation/revocation/rollback tests.
All 15 migration tests ran against temporary PostgreSQL, including preservation of
administrator/seller hashes, roles, store ownership and existing session records.
Root/backend `git diff --check` passed. New Python files passed syntax/whitespace
checks; the changed-file manifest and referenced design/plan paths were verified.

The suite's SQLite database/uploads are temporary. Shared PostgreSQL fixtures start a fresh
cluster under `/tmp`, verify its data directory and disabled TCP listener, and
never read a configured `TEST_POSTGRES_URL`. Migration tests no longer probe port
5433 or an external database at collection time.

Local runtime: Python 3.14.1 and Homebrew PostgreSQL 18.6. The documented deployment
uses Python 3.12 and PostgreSQL 16, so matching-version staging tests remain a
release gate; local PostgreSQL coverage is not proof of live Supabase compatibility.

Staging acceptance steps, using a REST client with secret-value masking:

1. Sign in with existing customer, administrator and seller accounts from each
   deployed client. Confirm user identity, role, seller link, token aliases, original
   access lifetime, cart and order access remain correct.
2. Obtain two device sessions. Logout one via the API. Reuse its access token for
   `/auth/me` and its refresh token at `/auth/refresh`: both must return 401. The
   other device must still work. Current UI logout needs the client fixes above.
3. Opt in to refresh. Rotate once; verify the new access token works. Reuse the old
   refresh credential; require `TOKEN_REUSE_DETECTED` and rejection of both the old
   and new family access credentials. An independent device must remain valid.
4. Let an access token expire while its session remains active. Protected requests
   return 401; the current refresh token still rotates. Expire/revoke the session:
   both access and refresh must fail.
5. Change the password while multiple devices are active. All old devices and a
   previously unused pre-session JWT must fail. New-password login must work with
   unchanged role/ownership. Repeat for an administrator resetting a seller password.
6. Try customer/seller access to administrative APIs and seller writes to another
   seller's products before and after refresh. Existing 403/404 denials must remain.
7. Exercise both API prefixes, invalid/oversized refresh input, refresh rate limits,
   lost responses, offline logout, and account switching. Verify credential bodies,
   bearer headers, passwords and secret settings never appear in logs or telemetry.

No browser/device E2E, live Supabase schema check, production migration, or deployed
runtime verification was performed. These remain explicit release gates.

## 7. Approval boundaries

Still requiring approval: applying any staging/live migration; production rollout
and its feature flags; legacy cutoff/lifetime policy; web BFF/cookie/CSRF architecture;
Flutter secure-storage dependency and client release; session-history retention/
cleanup policy; any forced reauthentication or signing-key rotation recovery action.
The user has authorized this backend implementation and disposable-database tests;
no further approval was required to prepare these reviewable artifacts.

## 8. Changed-file manifest

Paths below are relative to the workspace root. Existing unrelated working-tree
changes and untracked Supabase/helper scripts were left untouched.

| File | Purpose |
|---|---|
| `backend/app/core/config.py` | Compatibility/issuance flags, issuer/audience, refresh lifetime and quota configuration |
| `backend/app/core/security.py` | Strict modern claim validation, compatible legacy decoding and secure refresh generation/hashing |
| `backend/app/core/auth_errors.py` | Sanitized auth validation/errors, stable replay error code and non-cacheable responses |
| `backend/app/core/dependencies.py` | Require a database session in addition to the existing identity/role checks |
| `backend/app/models/user.py` | Add the nullable legacy-token revocation marker |
| `backend/app/schemas/auth.py` | Optional refresh opt-in, bounded masked refresh input, credential-safe object representations |
| `backend/app/services/auth_session_service.py` | Session issuance/adoption/validation, rotation, replay handling and revocation transactions |
| `backend/app/services/auth_service.py` | Issue sessions from login/register and revoke them atomically after password change |
| `backend/app/api/v1/routes/auth.py` | Refresh/logout-all endpoints and real server logout; preserve both mounted prefixes |
| `backend/app/api/v1/routes/users.py` | Serialize administrator password resets with auth mutations and revoke target sessions |
| `backend/alembic/versions/d7e8f9012abc_add_legacy_token_revocation.py` | Prepared additive marker migration; no production execution |
| `backend/tests/conftest.py` | Share the verified temporary TCP-disabled PostgreSQL fixture |
| `backend/tests/test_auth_sessions.py` | HTTP compatibility, claim/expiry/revocation/replay, ownership, privacy and quota regression tests |
| `backend/tests/test_auth_session_concurrency.py` | Real PostgreSQL rotation/revocation races and transactional rollback tests |
| `backend/tests/test_alembic_config.py` | Expect the new single migration head |
| `backend/tests/test_migrations_postgres.py` | Eliminate configured-server access and verify migration/account/session preservation |
| `backend/tests/test_session_models.py` | Verify masked refresh request input retains its actual secret value internally |
| `backend/tests/test_stock_concurrency.py` | Reuse the shared isolated cluster fixture without changing inventory assertions |
| `docs/upgrade/PHASE_1_SECURE_SESSIONS_REPORT.md` | This audit, migration/rollout order, client work, acceptance checklist and approval boundaries |
