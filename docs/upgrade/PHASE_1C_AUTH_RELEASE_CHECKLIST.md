# Phase 1C authentication release checklist

**Status: HOLD. Preparation only. No production operation is authorized here.**
Use with the [release report](PHASE_1C_AUTH_RELEASE_REPORT.md) and
[manifest](PHASE_1C_AUTH_RELEASE_MANIFEST.json). A checked preparation item is evidence,
not permission to deploy. Record approver, UTC time, exact commit/build/target and
sanitized evidence for each future gate. Never record credentials or request bodies.

Phase 1D adds prerequisite containment, recovery and permission gates in the
[secure production preparation](PHASE_1D_SECURE_PRODUCTION_PREPARATION.md).
Complete those before the ordered authentication rollout below. The existing
permission SQL is guarded at a1b2c3d4e5f6 and must precede d7e8f9012abc unless it
is separately re-reviewed/rehearsed. No production action is authorized by either
checklist; modern issuance remains OFF for the initial backend release.

## Preparation completed

- [x] Review uncommitted backend, Storefront, Management and Flutter auth changes.
- [x] Preserve unrelated work, Git indexes and real environment files.
- [x] Read live revision first; it matches expected `a1b2c3d4e5f6`.
- [x] Inspect auth columns, indexes, FKs, grants, RLS and aggregate counts read-only.
- [x] Confirm required path is only `a1b2c3d4e5f6 -> d7e8f9012abc`.
- [x] Confirm code default `AUTH_ISSUE_SESSION_TOKENS=false` and legacy acceptance.
- [x] Re-run local regression, lint, builds and Flutter analysis.
- [x] Prepare recovery procedure and smoke tests without executing them in production.

## Gates before any commit/push or production window

- [ ] **Owner/security approval:** resolve the observed grants-without-RLS exposure
  risk. Verify hosted REST/GraphQL/exposed-schema settings privately; review any
  remediation as a separate change. Do not change account roles or reset passwords.
- [ ] **Code review approval:** approve the auth file manifest; separate bootstrap,
  seed, infrastructure and unrelated mobile/UI changes. No blanket staging/commit.
  Approve exact commits in each independent repository; this task made none.
- [ ] **Release-control approval:** verify Render/Vercel auto-deploy behavior,
  production branches, project/team/root-directory, API origins and intended aliases
  before any push. Resolve Storefront 404. Commit/push needs its own review/approval
  and must not silently deploy through Git integration.
- [ ] **CI/artifact approval:** obtain authenticated backend/mobile CI evidence;
  run missing checks on exact reviewed commits. Storefront/Management currently
  have no reported checks/runs. Record tested immutable backend digest, client build
  identifiers and Flutter signing/distribution route. Local tests do not attest
  future builds or the dirty working tree through remote CI.
- [ ] **Database-owner approval:** confirm exact production database binding,
  live revision, expected schema, PostgreSQL 17, TLS, pooler/direct connection mode,
  least privilege, connection budget, timeouts and monitoring. If revision is
  unexpected, **stop**; no stamp, downgrade or alternative sequence without review.
- [ ] **Backup/data-custodian approval:** authorize encrypted export location,
  access, retention, key custody, RPO/RTO and separate media backup. Verify managed
  recovery availability. No production data export has been taken by this task.
- [ ] **Staging approval:** restore a protected backup in independently verified,
  isolated PostgreSQL 17; rehearse the migration with the Python 3.12 release image.
  Verify credential/role/store-link equality privately and all session-history
  constraints. Complete browser/device acceptance below using staging fixtures.
- [ ] **Rollback approval:** identify and test a session-aware fallback artifact
  before the first backend cutover. Do not designate the stateless live build as
  the rollback floor. Approve pause/forward-fix procedure if no healthy fallback.
- [ ] **Configuration approval:** privately verify signing key/algorithm and actual
  access lifetime are preserved; issuance explicitly false; legacy acceptance true;
  cutoff unset/approved future; production mode; initialization/seeding false;
  HTTPS/CORS/proxy settings and every worker's settings consistent.
- [ ] **Operations approval:** name release operator, observer and incident owner;
  approve maintenance/cutover window, rollback trigger thresholds and observation
  duration. No unexplained 5xx, role/ownership bypass, successful revoked-token use
  or failed backup/schema check may be waived by a healthy `/health` response.

## Ordered production gates — separate explicit approvals

1. [ ] **Migration approval:** approve reviewed artifact + database + exact
   `a1b2c3d4e5f6 -> d7e8f9012abc` + bounded lock timeout + verified recovery point.
   Operator applies only that migration, then verifies column/revision and account
   preservation. This package does not run it.
2. [ ] **Backend deployment approval:** release session-aware backend with issuance
   OFF; verify schema separately from SELECT 1 readiness; complete cutover/drain of
   old workers. No modern issuance or refresh enablement.
3. [ ] **Production smoke approval:** permit only agreed login/session operations
   by account owners after backend cutover; these operations write session records.
   Never paste credentials into chat or capture HAR/auth headers/bodies. Password
   changes, account provisioning and role changes remain prohibited in this task.
4. [ ] **Management release approval:** release reviewed client, test admin/customer
   denial and keyboard sign-out; seller acceptance is pending without an existing
   approved seller account. Retain staging seller evidence and record this gap.
5. [ ] **Storefront release approval:** release to confirmed working origin; test
   customer account, logout and private cache cleanup at phone/desktop widths.
6. [ ] **Flutter release approval:** approve signed artifact/distribution, then test
   existing customer login/logout on a device, both themes and text scaling.
7. [ ] **Observation acceptance:** record both-prefix status checks, latency/error
   metrics and revocation persistence; close window only with owner sign-off.

## Smoke tests to execute after the relevant approval

Use an approved masked REST client/browser/device. Repeat API assertions under
**both `/api` and `/api/v1`**. Record expected/actual HTTP status and pass/fail only.
Do not use production users for mutation tests merely to make a row green.

| ID / behavior | Exact steps and expected result | Allowed future environment |
| --- | --- | --- |
| S1: infrastructure and denials | GET `/health` -> 200; `/readyz` -> 200. Independently inspect revision/marker. GET `/auth/me` and `/users` without bearer and with an invalid bearer -> 401. No credential or database error details in output/logs. | Production after approved cutover; unauthenticated probes already passed in preparation |
| S2: existing legacy credential | Account owner retains a valid pre-cutover session in a protected client, without exporting it. After backend rollout GET `/auth/me` -> 200, correct identity/role; original expiry unchanged; exactly one deterministic adoption. Repeat -> no duplicate adoption. Do not re-login first. No secret values recorded. | Staging first; production only with session-write approval and private signing/config verification |
| S3: administrator | Owner signs into Management with an existing approved admin. POST `/auth/login` -> 200; both `token` aliases match; refresh null; original configured lifetime. GET `/auth/me` -> correct active admin; GET `/users` -> 200, inspect status without exporting user list. Dashboard opens only after identity verification. | Existing production admin only after approval; fixtures in staging |
| S4: seller authorization | Existing seller signs in; `/auth/me` -> seller; GET `/seller/me` -> own store; GET `/users` -> 403. Customer bearer GET `/seller/me` -> 403. In staging only, attempt update of another seller's product -> 404 and unchanged record; own allowed update succeeds and is verified. Editing cached browser role must not grant admin data. | Staging required. Production seller test **blocked: 0 active sellers/0 stores**. No account creation or promotion authorized |
| S5: customer | Existing customer signs in through Storefront and Flutter separately; login -> 200, `/auth/me` -> same active customer; `/users` -> 403; `/seller/me` -> 403. Cart/orders are scoped to that customer. Management rejects customer even if cached role is edited. No order or payment mutation is needed. | Staging first, then existing consenting production customer after approval |
| S6: online device logout | Establish devices A/B for the same consenting account. Use each deliberate logout control: Storefront navbar/account, Management admin/seller sidebar, Flutter profile. One bounded POST `/auth/logout` uses A's captured bearer; local identity/private caches clear immediately. Reusing A for `/auth/me` -> 401; B still -> 200. Repeated A logout -> 401. Browser Back must not expose private content. | Staging all roles; approved production session-only test on existing admin/customer; seller remains pending |
| S7: offline/race cleanup | In staging, disable networking before logout: local sign-out still completes; no claimed remote success. Delay A's logout/401 response, sign into B, release A response: B survives. Test load/empty/failure/retry states, keyboard focus, narrow/wide web, Flutter light/dark, small screen, scalable text and Back. | Isolated staging/device testing; avoid delaying or fault-injecting production |
| S8: password revocation | On a disposable staging fixture only, create two sessions plus one unseen pre-session JWT. Wrong current password -> 400, no password/session change. Valid change -> 200; caller and all prior/unseen credentials -> 401; fresh login with new password -> 200 and same role/store link. Storefront clears current auth and requests sign-in. Admin reset of a staging seller revokes only target. Verify database rollback failure paths using isolated tests. | Staging only. **No production password change is authorized**. Positive production password smoke remains blocked until a separate future instruction explicitly permits that account/password action |
| S9: rollback/history | On isolated staging, revoke A, switch to reviewed session-aware fallback with database retained: A -> 401, B -> 200. Marker and consumed/revoked rows remain. Rehearse client fallback with the session-aware backend. | Staging before release; approved incident procedure only in production |
| S10: modern/refresh guard | Shipping login returns null refresh and does not request opt-in/refresh. In isolated modern-mode regression only, rotate once, replay parent -> TOKEN_REUSE_DETECTED; family access fails, independent device survives. | Automated/staging only; modern issuance and refresh clients stay OFF in production |

A completed production subset must explicitly list S4 and S8 as pending rather than
claiming seller/password production acceptance. Current user instructions prohibit
creating accounts, changing roles/passwords, migrations and deployment in this task.

## Explicit approvals outside this package

- [ ] Any Supabase grants/RLS/API-exposure change or schema change beyond the marker.
- [ ] Backup/export, restore drill environment and future production migration.
- [ ] Reviewed commits/pushes and each backend/client deployment or rollback.
- [ ] Production authenticated smoke operations and their account-owner consent.
- [ ] Any future production password operation, user provisioning or role change
  (not allowed by the current task; no such action is scheduled here).
- [ ] Modern issuance, secure refresh storage/BFF/CSRF, mobile storage dependency,
  legacy cutoff/lifetime change, session cleanup/retention implementation or shared
  rate-limit infrastructure.
- [ ] Emergency key rotation, forced login, stateless recovery or database restoration.
