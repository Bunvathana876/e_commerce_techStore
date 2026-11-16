# Blue Panda Phase 1B — Auth Client Integration and Staging Readiness

Date: 2026-11-07  
Status: Implemented and tested locally; no deployment authorized or performed.

## Outcome and scope

Storefront and Management deliberate sign-out controls now submit an authenticated
`POST /auth/logout` using the captured bearer before immediate local cleanup.
Flutter sends the captured token before clearing its shared API client and saved
session. Network failure, HTTP 401/500 and delayed responses cannot restore the old
session or erase a later login. Logout does not retry, send refresh credentials,
or claim successful server revocation when offline.

Modern login/register issuance now defaults to **disabled**:
`AUTH_ISSUE_SESSION_TOKENS=false`. Legacy acceptance remains enabled. Existing
bearer-only login lifetimes and response aliases are retained. This flag does not
turn off database validation/revocation: compatibility credentials are still
pre-registered as sessions. Modern security tests explicitly opt in.

No refresh storage, refresh interceptor, cookie/BFF architecture, dependency,
database migration, role/password change to real accounts, deployment, commit or
push was performed. Tests change only generated fixture accounts in disposable
databases. No live Supabase connection or production migration was attempted.
Existing unrelated staged, unstaged and untracked work was preserved. The retired
combined `web-app/` was not modified; the active apps are `storefront/` and
`management/`.

This report supersedes conflicting proposals in the Phase 1C design/plan and the
original Phase 1 report's default-enabled issuance statement. In particular, the
current backend accepts refresh **JSON**, sets no auth cookie, uses configured
issuer/audience values from code, applies an absolute session expiry, revokes the
password-changing caller too, and must not be rolled back by dropping revocation
history. Proposed shared-domain cookies, automatic cleanup, password-policy changes
and transparent rollback to a stateless decoder are not implemented guarantees.

## Completed client integration

### Storefront

- Account and navbar sign-out start a bounded five-second backend request with the
  original bearer. Local auth, private persisted data and registered store cleanup
  handlers run synchronously before awaiting the response. Existing guest shopping,
  neutral preferences, management session keys and commerce isolation are preserved.
- The revocation request is non-cacheable, omits ambient cookies, rejects redirects,
  and uses keepalive across navigation. It bypasses the generic 401 interceptor so
  an old logout cannot affect a newer login. Its boolean result indicates whether
  the server acknowledged success; the UI states only local browser sign-out.
- Ordinary and upload 401 handling now checks the request's token and session epoch.
  An old account's response cannot log out the next account.
- Successful password change clears the requesting local session because the
  backend has revoked it. Copy tells the customer to sign in again. A late success
  cannot clear a newer session.
- Logout handler exceptions use fixed log messages rather than exception objects.

### Management Dashboard

- Admin and seller sidebar sign-out uses the same authenticated FastAPI logout and
  immediate local cleanup pattern, retaining `mgmt_` storage isolation and private
  cashier/notification cache cleanup.
- Existing `validateManagementSession()` resolves active identity and admin/seller
  role from `/auth/me`, discards stale responses, and fails closed on rejection or
  network failure. Existing layouts withhold dashboard children until verification;
  customers cannot acquire dashboard access by editing cached browser roles.
- Existing 401 handling rejects expired/revoked sessions and guards account switches.
  Backend dependencies continue to enforce live database roles and seller ownership.
- Password-change helper clears the revoked caller, guarded by session generation.

“Server-side logout” here means authenticated **FastAPI session revocation**. The
Next.js apps still use client identity guards and expose a public loading shell;
this is not cookie-based Next.js SSR authentication. No private server-rendered
payload was added. Any future server data access or Server Action must independently
authenticate and authorize; a layout guard is not an API security boundary.

### Flutter

- Provider → auth service → API service passes an explicit captured bearer to logout.
  The service no longer clears a shared client when its response finishes.
- Provider identity and shared bearer clear immediately; preferences, private caches
  and cleanup listeners complete independently of the remote response. Existing
  navigation listeners are notified before awaiting remote completion. The remote
  request has a five-second bound and its error is consumed without logging secrets.
- The local logout guard releases after local cleanup, so a later login can itself
  log out while an older revocation response is still pending.
- API requests capture an auth generation, preventing an older protected request's
  401 from invalidating a newer bearer. Logout exclusion uses the original request
  path, including when a transport/test response lacks request metadata.
- Auth restore/save/cleanup diagnostics use fixed messages, avoiding credential or
  malformed private JSON leakage through exception strings.

## Backend and migration review

Reviewed `auth_session_service.py`, login/register/password services, auth routes,
JWT decoding, role dependencies, existing session models and migration
`d7e8f9012abc` following `a1b2c3d4e5f6`.

Verified behavior through the backend suites:

- Both `/api` and `/api/v1` retain success/message/data, token/access_token aliases,
  token_type, user and existing bearer-only lifetime. Default rollout credentials
  remain compatible with old JWT decoders without an audience claim.
- Login/register commits session issuance atomically; refresh opt-in is rejected
  while modern login issuance is disabled. Failed registration leaves no account.
- Access checks require an active database user and valid non-revoked session.
  Missing/invalid credentials fail closed, including optional-auth routes.
- Logout revokes one device; logout-all and password change revoke all of that
  user's sessions, including the caller, plus unseen pre-session legacy tokens.
- Refresh is single-use with user → session → token PostgreSQL locks and a guarded
  consumption update. Replay commits family revocation before returning 401 with
  `TOKEN_REUSE_DETECTED`; unrelated devices remain valid. Stored refresh values are
  hashes, never raw credentials. Expiry is absolute and rotation does not extend it.
- Admin APIs remain denied to customers/sellers as appropriate; seller writes stay
  scoped to their own stores, including after refresh. Current roles and active
  status come from database records.

Revision `d7e8f9012abc` adds nullable `users.legacy_tokens_revoked_at` without a
backfill or changes to account hashes, roles or seller relationships. Fifteen
migration tests verify fresh and populated upgrades, failure rollback, constraints,
indexes, session-table creation, downgrade/re-upgrade and preservation of fixture
administrator/seller hashes, ownership and session records. No migration changed in
this phase. Downgrade success on throwaway data is not approval to erase production
revocation history.

## Automated verification results

| Check | Result |
| --- | --- |
| Full backend, local Python 3.14.1 / PostgreSQL 18.6 | 676 passed, 2 skipped; 2 existing deprecation warnings |
| Backend in Python 3.12.16 / PostgreSQL 16.15 containers | 674 passed, 3 skipped, 1 deselected; 2 existing deprecation warnings |
| PostgreSQL migration suite | All 15 passed on both PostgreSQL versions |
| Storefront tests, Node 24.19.0 | 46 passed |
| Management tests, Node 24.19.0 | 86 passed |
| Storefront production build, Node 24.19.0 | Passed |
| Management production build, Node 24.19.0 | Passed |
| Storefront lint | Passed, 0 errors / 1 existing navigation warning |
| Management lint | Passed, 0 errors / 18 existing warnings |
| Flutter full suite | 188 passed |
| Flutter analysis | No issues found |
| Whitespace/diff checks | Passed in root and all four affected repositories |

The two local skips are Redis integration tests requiring port 6389. Container
skips are those Redis tests plus a coupon concurrency fixture which separately
requires local initdb/pg_ctl binaries. That coupon test passed on the host.
The Git-ignore check was verified on the actual host repositories before being
deselected in the runtime container, which has no Git executable or repository
metadata. No session or migration test was skipped. Existing Node module-type and
storefront test-storage warnings remain; they are not test failures.

Reproduction (commands run from the indicated application directory):

```bash
# backend
rtk .venv/bin/python -m pytest -q -rs
rtk .venv/bin/python scripts/verify_auth_staging.py
# storefront and management; ensure node --version is v24.x first
rtk npm test
rtk npm run lint
rtk npm run build
# mobile-app
rtk flutter test
rtk flutter analyze
```

The shell's npm shim initially selected Node 25 despite `node` resolving to 24.
Final web tests/lint/builds explicitly prepended the installed Node 24 bin directory
to PATH. No dependency changed. Storefront build used a closed loopback test API URL;
Management build used reserved `https://api.example.invalid/api` and
`https://shop.example.invalid` placeholders to satisfy its production URL checks.
Builds never used live API destinations. These local artifacts are test artifacts,
not deployable production configuration.

The staging harness uses existing cached images (`blue-panda-backend:staging` and
`postgres:16-alpine`), an allowlisted source snapshot without .env files, network-none
containers, tmpfs database data, a unique disposable socket volume and a verified
cluster identity. It overrides only the snapshot's PostgreSQL fixture, checks TCP
is disabled and the server is PostgreSQL 16, and removes only its own generated
resources in finally. It never runs the normal backend entrypoint. Cached runtime
dependencies were used, not rebuilt from requirements; an approved reproducible
release-image build remains a staging gate.

Browser acceptance was attempted using a local test-only API, but browser control
reported “The browser access host is unavailable”; native-browser fallback timed
out. No browser flow is claimed verified. Temporary local servers were stopped.
No physical mobile device/simulator or live staging service was tested. The React
review found the edited controls retain button semantics and immediate navigation,
with no added effects, hooks, UI layout changes or dependencies. Automated tests
cover cleanup, commerce/session isolation, denial, expiry, delayed responses and
credential-safe logout logging; visual/keyboard acceptance remains below.

## Refresh readiness — architecture proposal, not enabled

### Browser storage

Current access tokens remain in separately namespaced localStorage for deployed
client compatibility. They are script-readable and remain an XSS exposure. Do not
put refresh credentials there, in sessionStorage, URLs, analytics or logs.

Proposed follow-up: separate same-origin BFF sessions for Storefront and Management.
Keep refresh credentials in a server session store and give the browser an opaque,
HttpOnly, Secure, host-only SameSite cookie (prefer a valid `__Host-` prefix).
Keep short-lived browser access tokens in memory if the browser still calls the API
directly, or keep both token types server-side when all private calls use the BFF.
Use separate cookie names/origins and backend sessions per application. Cookies are
not port-isolated on localhost; avoid shared parent-domain cookies and configure
local testing deliberately. HttpOnly reduces script access, not all effects of XSS.
Cookie semantics are documented in the [Set-Cookie reference](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie).

Approve the BFF/session-store design first. No existing server session store or
browser-cookie backend contract is available. Backend refresh currently accepts
JSON only, so merely adding `credentials: include` cannot implement refresh. Cookie
endpoints require explicit allowed-Origin validation and CSRF protection, suitable
SameSite policy, no-store responses, session fixation controls and logout cookie
clearing. SSR loaders/actions must validate the backend identity and role.

### Rotation, retries, replay and expiry

Use one refresh operation per session generation, shared across concurrent calls.
If browser tabs share a BFF session, serialize refresh across tabs/workers at the
session owner; a per-tab Promise alone cannot prevent replay races. Flutter can
use a shared Future/Completer without another mutex package. Commit replacement
credentials before releasing queued callers, and check the generation before
updating state or persistence.

Retry at most once after a definite authentication rejection and successful refresh.
Exclude login, registration, logout and refresh from recursion. Do not automatically
replay checkout/payment or other non-idempotent writes after an ambiguous transport
failure. Business mutations need an approved idempotency contract before retries.
A lost successful refresh response makes the old credential unsafe to retry: clear
the session and ask for login. A timeout/429 does not justify a refresh retry loop.
Respect Retry-After for permitted operations without reusing ambiguously consumed
tokens. Preserve only explicitly safe draft/guest state across reauthentication.

`TOKEN_REUSE_DETECTED`, revoked/expired refresh or unavailable account must clear
all device credentials/private caches and require login. The backend retains token
history, revokes the replayed family and intentionally offers no replay grace
window, following the [RFC 9700 rotation model](https://www.rfc-editor.org/rfc/rfc9700.html#section-4.14).
Its default refresh session expires absolutely after 30 days. Its opt-in access
lifetime is 15 minutes, capped by remaining session life; bearer-only clients keep
the existing configured access lifetime. Password change/logout-all also require
fresh login. Refresh must never silently downgrade to a guest success.

The issuance flag gates login/register opt-in, not existing refresh families. Turning
it off later is not an emergency revoke-all switch and does not stop already-issued
refresh credentials from rotating. Plan existing-family draining/revocation separately.

### Flutter storage and dependencies

SharedPreferences remains the current persistence layer and is unsuitable for
long-lived secrets; its publisher also cautions against storing critical data in
it ([SharedPreferences documentation](https://pub.dev/packages/shared_preferences)).
Propose an approved secure-storage dependency or carefully reviewed native platform
channels: iOS Keychain and Android Keystore-backed encryption. Review lock-state
accessibility, device backup/restore exclusions, reinstall behavior, atomic pair
replacement, storage failure and migration of existing access credentials.

The current [flutter_secure_storage publisher documentation](https://pub.dev/packages/flutter_secure_storage)
describes Keychain and Android RSA-OAEP/AES-GCM defaults; it warns that its older
EncryptedSharedPreferences approach is no longer recommended. Do not blindly copy
the earlier Phase 1C proposal or add a version without checking Android/iOS minimums,
backup settings, key invalidation and platform tests. Flutter web requires the browser
architecture, not an assumption of native Keychain security. No package was added.
Browser AbortController/AbortSignal, Fetch and existing Node test tools suffice for
this phase. Future BFF persistence is a separate architecture/dependency approval;
future Flutter secure storage is a separate package/platform approval.

## Safe staging and deployment order — requires operator approval

1. Review this diff, snapshot the exact code/image identifiers and approve the
   migration path for the actual target revision. An authorized operator must audit
   schema drift/session tables and validate backup restore in an isolated copy.
   Do not blindly stamp Alembic or use create_all/seed to reconcile drift.
2. Rebuild approved Python 3.12, Node 24 and mobile artifacts with reviewed dependencies
   and sanitized environment settings. Explicitly set AUTO_INIT_DB=false and
   SEED_DEMO_DATA=false. Keep signing key/algorithm, issuer/audience, access lifetime
   and legacy acceptance compatible. Verify proxy/CORS/TLS, database permissions and
   connection-pool behavior in staging, including the Supabase connection mode if used.
3. Apply reviewed schema before serving session-aware code, using an approved runner.
   Confirm `d7e8f9012abc` and prerequisite revisions, retained accounts/roles/ownership,
   indexes and session lookup latency. No live schema/revision was inspected here.
4. Roll the backend out to all workers with AUTH_ISSUE_SESSION_TOKENS=false and
   AUTH_ACCEPT_LEGACY_TOKENS=true. Keep the legacy cutoff unset or approved for a
   future date. Drain every old worker before considering modern tokens. During a
   mixed rollout, old workers cannot enforce new revocations; minimize that interval.
5. Release Storefront, Management and Flutter logout integrations in a controlled
   order after backend availability. Run all acceptance steps below against staging
   and then approved production smoke checks. Monitor sanitized 401/403/429/replay
   counts and database latency; never collect auth headers/bodies or refresh values.
6. Hold modern issuance and all client refresh opt-in OFF for this phase. A later
   explicit approval may enable modern bearer tokens only after all workers support
   their audience/claims. Refresh client release additionally requires the storage,
   CSRF, single-flight, lost-response and platform acceptance gates above.
7. Approve legacy retirement separately after the longest old-token lifetime issued
   by the last old/validation-only worker has drained. Preserve revoked legacy rows
   until original expiry/cutoff; deleting them sooner can allow re-adoption. Retain
   consumed refresh history until its family expires. No cleanup job was added.

## Rollback procedure

1. Stop the rollout and keep modern issuance disabled. Preserve database and session
   history. Prefer a forward fix or the last tested session-aware backend with
   compatible schema, signing settings, issuer/audience and legacy policy.
2. Client rollback preserves current bearer-only compatibility. Rolling clients
   back loses remote logout and must be treated as a temporary security regression;
   the backend continues to enforce revocations already recorded.
3. Do not downgrade the production database as an ordinary app rollback. Dropping
   session tables or the legacy barrier loses revocations. Do not restore an older
   database snapshot into service while old signed tokens remain valid without an
   approved forced-reauthentication plan.
4. Do not transparently return to the original stateless decoder: it ignores
   revocation and rejects modern audience-bearing tokens. If recovery requires it,
   obtain explicit incident approval for key rotation/forced login, worker draining,
   device-session revocation and communication. Disabling issuance alone does not
   invalidate existing modern credentials or refresh families.
5. Re-run role/ownership, both-prefix compatibility, logout and password-revocation
   checks before restoring traffic. Schema downgrade is tested only on disposable
   PostgreSQL and requires a separate reviewed data-loss/recovery decision elsewhere.

## Required acceptance steps and remaining risks

Use fixture-only accounts in approved staging, not real accounts/passwords. Mask
headers and bodies in any REST client; record only status codes and sanitized events.

1. Storefront: at phone and desktop widths, sign in, populate cart/wishlist, visit
   account/checkout, then sign out from navbar and account button independently.
   Confirm the request is POST with a bearer (do not copy its value); local identity
   and private cart/wishlist/order caches clear and neutral preferences remain.
   With networking disabled, repeat: local sign-out must still finish promptly and
   no UI should claim acknowledged remote revocation. Guest shopping must still work.
2. Management: use admin and seller fixtures separately. Confirm their own landing
   pages render only after backend identity verification. Visit the other role's
   path and try a customer token plus edited cached admin metadata: protected data
   must not render. Test keyboard sign-out in both sidebars and browser Back.
   Reuse a logged-out credential in a masked REST client: `/auth/me` returns 401;
   an independent device stays valid. Expired/revoked sessions must lead to login.
3. Flutter: check both themes, small screen/text scaling, back navigation and profile
   sign-out. Confirm remote bearer attachment, immediate local identity/cache cleanup,
   login navigation and no private data on Back, including offline and server 401.
   Delay logout response, sign in as another fixture, then release it: the new login
   must survive. Repeat with a delayed protected request returning 401.
4. Password revocation: change only a disposable fixture password in staging, with
   two devices active. Both old devices must receive 401; Storefront clears its
   current session immediately and tells the user to log in. Verify new-password
   login keeps the same role/store link. Do not change real user passwords for testing.
5. In isolated modern-mode tests only, rotate once, replay the parent and verify
   TOKEN_REUSE_DETECTED plus rejection of all family credentials; another device
   remains valid. Check a lost response/concurrent calls require clean recovery.
6. Repeat API compatibility and admin/seller/ownership denial through both `/api`
   and `/api/v1`. Verify failure/empty/retry/loading UI states, focus/touch targets,
   no credentials in logs and no accidental refresh requests from shipping clients.

Remaining risks: browser localStorage XSS and mobile SharedPreferences exposure;
offline logout cannot guarantee remote revocation and leaves a stolen token usable
until expiry/revocation; backend requests authenticated before revocation can finish;
legacy acceptance has no automatic cutoff; mixed old workers ignore revocation;
per-worker in-memory rate limits are not a shared multi-worker quota. Existing login
still lacks dummy bcrypt verification for a nonexistent user, so the original design's
timing-equality claim is not an implemented guarantee. These were not broadened into
unrequested architecture/password-policy changes. Real schema drift, release-image
rebuild, browser/device behavior and hosted proxy/pooler behavior remain unverified.

Production approvals required: actual schema/revision audit, backup/restore and
migration execution; release artifacts/environment/proxy settings and backend/client
rollout; any modern issuance flag change; legacy expiry/retirement and history
retention policy; BFF/cookie/session-store/CSRF architecture; mobile secure-storage
dependency/platform release; shared rate-limit infrastructure if needed; and any
forced logout, key rotation or destructive rollback. This task grants none of these
production approvals. No deployment command was run.

## Changed-file manifest

Only changes made for this phase are listed; previous Phase 1 and unrelated dirty
files are not claimed as new work.

| File | Reason |
| --- | --- |
| `backend/app/core/config.py` | Default modern issuance off |
| `backend/.env.example` | Explicit validation-only rollout flags |
| `backend/tests/test_auth_sessions.py` | Explicit modern-mode fixture for existing security coverage |
| `backend/tests/test_auth_session_concurrency.py` | Explicit modern-mode fixture for PostgreSQL races |
| `backend/tests/test_auth_rollout_defaults.py` | Default flags and both-prefix role-compatible login/logout regressions |
| `backend/scripts/verify_auth_staging.py` | Disposable Python 3.12/PostgreSQL 16 verification harness |
| `storefront/src/lib/auth.ts` | Captured-bearer remote logout and safe cleanup diagnostics |
| `storefront/src/lib/api.ts` | Generation-guarded 401 handling and password-change cleanup |
| `storefront/src/components/store/StoreNavbar.tsx` | Wire remote logout and truthful browser-only message |
| `storefront/src/app/(store)/account/page.tsx` | Wire remote logout and re-login copy after password change |
| `storefront/src/lib/__tests__/server-logout.test.mjs` | Logout, expiry, failure, race, password and logging regressions |
| `management/src/lib/auth.ts` | Captured-bearer remote logout and safe cleanup diagnostics |
| `management/src/lib/api.ts` | Password-change cleanup for revoked caller |
| `management/src/components/layout/Sidebar.tsx` | Wire administrator logout |
| `management/src/components/seller/SellerSidebar.tsx` | Wire seller logout |
| `management/src/lib/__tests__/server-logout.test.mjs` | Logout, expiry, failure, race, password and logging regressions |
| `mobile-app/lib/core/network/api_client.dart` | Auth-generation guard and reliable logout-path handling |
| `mobile-app/lib/features/auth/providers/auth_provider.dart` | Correct dispatch/cleanup order and sanitized diagnostics |
| `mobile-app/lib/features/auth/services/auth_service.dart` | Pass explicit logout bearer |
| `mobile-app/lib/features/auth/services/auth_api_service.dart` | Send captured bearer with timeout; avoid delayed client clearing |
| `mobile-app/test/features/auth/server_logout_test.dart` | Logout/failure/race/cache/logging tests |
| `docs/upgrade/PHASE_1_SECURE_SESSIONS_REPORT.md` | Link this follow-up and correct shipping-default wording |
| `docs/upgrade/PHASE_1B_AUTH_CLIENT_INTEGRATION_REPORT.md` | Verification evidence, refresh readiness, rollout, rollback and approvals |
