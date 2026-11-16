# Blue Panda Phase 1C — Authentication release preparation

Date: 2026-11-07. **Readiness: HOLD — package prepared; production release is not approved.**

This report follows [Phase 1A](PHASE_1_SECURE_SESSIONS_REPORT.md) and
[Phase 1B](PHASE_1B_AUTH_CLIENT_INTEGRATION_REPORT.md). Use the accompanying
[release checklist](PHASE_1C_AUTH_RELEASE_CHECKLIST.md),
[source/evidence manifest](PHASE_1C_AUTH_RELEASE_MANIFEST.json), and
[read-only SQL checks](PHASE_1C_AUTH_READ_ONLY_CHECKS.sql).
Older deployment guides do not override the verified findings below.

## 1. Decision and blockers

The authentication implementation passes local regression checks, and the inspected
Supabase authentication schema supports the proposed additive migration. Release
must wait for these gates:

| Gate | Finding and required resolution |
| --- | --- |
| Supabase access control — critical | `public.users`, `public.user_sessions`, and `public.refresh_tokens` have RLS and forced RLS disabled, no policies, and effective SELECT/INSERT/UPDATE/DELETE grants to both `anon` and `authenticated`. Verify Data API/exposed-schema and GraphQL settings in the owner's dashboard. If exposed, these grants can bypass FastAPI, disclose account hashes, change roles, or alter revocation records. Approve and test a separate access-control remediation, or demonstrate these tables cannot be reached through exposed APIs. Do not release with exposure unresolved. No permissions were changed here. |
| Recovery evidence | No new production backup/export or restore was performed. Owner must confirm managed backup/PITR availability, approve encrypted export storage, and complete an isolated restore/migration drill. |
| Matching runtime | Live PostgreSQL is **17.11**. This run used Python 3.14.1/PostgreSQL 18.6. Phase 1B previously tested Python 3.12.16/PostgreSQL 16.15. Neither substitutes for a reviewed Python 3.12 release image and PostgreSQL 17 restore/migration/pooler rehearsal. No package/image was installed or pulled. |
| Immutable artifacts and CI | Changes remain uncommitted across separate repositories. No remote CI can attest this working tree. No CI workflow was found in the inspected repositories. Public Storefront/Management GitHub responses contain no Actions runs, check runs, or commit statuses; backend/mobile endpoints returned 404 and their remote CI state is unavailable. Obtain authenticated evidence for reviewed release commits and image/build digests. |
| Production configuration and identity | Render environment, deployed backend SHA, auto-deploy settings, signing configuration, instance/worker count, exact database binding, pool limits and rollback artifacts were not available through connected deployment tools. An operator must verify them privately. Never rotate signing secrets as part of this compatibility rollout. |
| Storefront routing | `https://blue-panda-storefront.vercel.app/` returned **404**, while the linked Vercel project reports a READY production deployment. Verify the intended alias, deployment routing and configured Storefront origin before release. No alias was changed. |
| Manual acceptance | No browser/device E2E or authenticated production smoke test was executed. There are no active seller accounts or seller records in the inspected database. Seller acceptance requires approved isolated staging fixtures; do not create/promote a production seller to complete a checklist. |

The Supabase exposure conclusion is conditional on hosted API configuration; SQL
grants and disabled RLS were directly observed. Supabase explains that grants and
RLS are separate access-control layers and documents disabling the Data API when
unused: [Securing your API](https://supabase.com/docs/guides/api/securing-your-api).
This package does not broaden the approved auth migration into an unreviewed
permissions/schema change.

## 2. Scope and preservation

Reviewed staged/unstaged/untracked state in the root and `backend/`, `storefront/`,
`management/`, `mobile-app/`, and retired `web-app/` repositories. The active web
clients are **Storefront and Management**. Do not deploy retired `web-app/`.

Reviewed the backend auth routes, admin password reset, security/configuration,
identity/role dependencies, user/session models, response schemas, session and
password services, migrations and isolation/concurrency tests; both web clients'
auth/API helpers, deliberate logout controls, management identity guard and logout
tests; and Flutter networking, auth provider/services, profile logout caller and
logout tests. No application source fix was required by this review.

The existing changes preserve response aliases, both API prefixes, current database
role/ownership checks, device revocation, password/account-wide revocation, refresh
replay history, immediate local cleanup and protection against delayed responses
clearing a subsequent login. Auth/session writes commit through the service layer.
Refresh credentials are not added to client persistence or automatically requested.

The manifest identifies the reviewed auth files by SHA-256 and records all dirty
paths in each active repository. It also identifies helper/bootstrap/demo scripts
and production Dockerfiles as separately reviewed release inputs, not automatic
authorization to execute or include them. Root deployment/docs/configuration,
backups, graph output, retired web changes, Flutter visual/catalog/cart/iOS changes,
lockfiles and other unrelated work were preserved. Do not use a blanket `git add`.

A private local baseline compared 719 existing files, including real environment
files, without publishing their contents or secret-derived checksums. **All baseline
file contents remained unchanged.** Real root/backend/Supabase/Storefront/Management/
retired-web environment files remain untracked and ignored. Their values were not
copied into this package. No Git index, branch, remote, commit or push was changed.
Builds regenerated only their normal ignored artifacts.

Files added by Phase 1C:

| File | Purpose |
| --- | --- |
| `docs/upgrade/PHASE_1C_AUTH_RELEASE_REPORT.md` | Findings, compatibility, verification, recovery and rollout procedure |
| `docs/upgrade/PHASE_1C_AUTH_RELEASE_CHECKLIST.md` | Ordered go/no-go gates, approvals and exact smoke steps |
| `docs/upgrade/PHASE_1C_AUTH_RELEASE_MANIFEST.json` | Source hashes, repository revisions, dirty-file separation and sanitized live/CI evidence |
| `docs/upgrade/PHASE_1C_AUTH_READ_ONLY_CHECKS.sql` | Revision-first, bounded read-only audit for an approved psql session |

## 3. Verified Supabase revision and migration compatibility

Inspection at **2026-11-07 08:18:26 UTC** used the existing verified connection in
`backend/.env.supabase`. The target was validated as PostgreSQL database `postgres`
through the Supabase owner session pooler, port 5432. Host/project/account identifiers
and credentials are deliberately omitted. TLS was in use. The connection enforced
`default_transaction_read_only=on`, a repeatable-read read-only transaction,
10-second statement timeout and 2-second lock timeout, and ended with rollback.
No application startup, Alembic command, seed or bootstrap was invoked on production.

The **first application-schema query** read `public.alembic_version` and required
exactly one row, `a1b2c3d4e5f6`, before any further schema/data inspection. It matched.
If a subsequent check differs, stop production work and obtain a new review; do not
stamp, downgrade, replay older migrations or infer schema correctness from the stamp.

```text
f904b613102f -> c4b8d91a2e3f -> a1b2c3d4e5f6 [LIVE]
                                         -> d7e8f9012abc [LOCAL HEAD]
```

**Only `a1b2c3d4e5f6 -> d7e8f9012abc` is required for the inspected target.**
Both prior consolidation and session-table migrations are already recorded. A local
Alembic ScriptDirectory inspection confirmed one head and this forward sequence
without loading the migration environment or connecting to a database.

| Inspected object | Result |
| --- | --- |
| `users` | Expected pre-migration columns/types/nullability; integer ID primary key, unique valid email index and sequence default; marker absent |
| `user_sessions` | Expected 12 columns; valid unique `session_id` index; valid user/family/expiry indexes; validated user FK with ON DELETE CASCADE |
| `refresh_tokens` | Expected 8 columns; valid unique 64-character hash index; valid session/expiry indexes; validated session FK with ON DELETE CASCADE |
| Auth hooks/security | No custom triggers/rules/policies on the three auth tables; owner connection has required inspection/write privileges; RLS/grants blocker above |
| `sellers` | Existing nullable user relationship, validated FK with ON DELETE SET NULL and valid user index; no relationship change proposed |
| Aggregate data | 2 users: 1 active admin and 1 active customer; 0 active sellers; 0 seller records; 0 sessions, revoked sessions or refresh rows; 0 orphan session/refresh rows |

Counts are a point-in-time baseline, not an immutable approval token. No names,
emails, password hashes, bearer values or refresh hashes were selected. This is an
authentication-schema audit, not a complete schema/data audit of the marketplace.

Revision `d7e8f9012abc` adds **nullable TIMESTAMP WITH TIME ZONE
`users.legacy_tokens_revoked_at`**, without a default, backfill, credential change,
role edit, user creation or seller relinking. The existing-column guard skips an
existing name without validating its type, so a newly present/incompatible column
requires review. It currently is absent. Old backend code tolerates the extra
nullable column; new ORM user reads require it before any session-aware code serves.
Adding a column still acquires a table lock: rehearse and use bounded lock/statement
timeouts in the approved window. No claim of zero blocking is made.

Do not use `alembic upgrade ... --sql` as a validated rehearsal: this migration's
inspection needs a live connection. Use an isolated restored database instead.

## 4. JWT compatibility and initial configuration

**Confirmed in code and regression tests:**

- `Settings.AUTH_ISSUE_SESSION_TOKENS` defaults to **False**; the backend example
  explicitly sets false. `AUTH_ACCEPT_LEGACY_TOKENS` defaults to True; the cutoff
  defaults to unset. These are code defaults, not proof of Render overrides.
- Existing signed `sub`/`exp` JWTs remain eligible until their original expiration
  with the same signing key/algorithm and permitted legacy policy. Adoption records
  a deterministic session derived from the token digest and does not extend expiry.
  Revoked records cannot be replaced by fresh active adoption.
- A pre-existing JWT can be adopted on its first authenticated request. **Even a
  GET `/auth/me` with such a token writes a session.** Consequently this read-only
  task did not obtain, replay or validate a real live JWT against candidate code.
  Live compatibility remains conditional on private signing/settings verification
  and an approved staging/rollout acceptance test. No real login was performed.
- With issuance disabled, successful login still creates a revocable session and
  returns an old-decoder-compatible JWT with a nonce and no audience/session claims.
  It retains the configured existing access lifetime and token/access_token aliases;
  refresh is null and refresh opt-in is rejected. The actual code lifetime default
  is **10080 minutes (7 days)**, not the stale Render guide's 60 minutes. Preserve
  the actual deployed setting; do not adopt an assumed duration from documentation.
- Logout revokes the one token/device. Logout-all/password change revoke adopted
  sessions and block all unseen old JWTs using the per-user marker. A fresh verified
  login remains possible. The password-changing caller must sign in again.
- Modern tokens have strict issuer/audience/session claims and require session
  lookup. Original decoders reject audience-bearing tokens; modern issuance must
  stay off throughout this release. Turning issuance off later does not revoke
  existing modern tokens or stop existing refresh families from rotating.

Privately verify and explicitly configure on every worker:

| Setting | Initial release requirement |
| --- | --- |
| `AUTH_ISSUE_SESSION_TOKENS` | `false` |
| `AUTH_ACCEPT_LEGACY_TOKENS` | `true` |
| `AUTH_LEGACY_ACCEPT_UNTIL` | Unset, or a separately approved future UTC cutoff |
| `JWT_SECRET_KEY`, `JWT_ALGORITHM` | Preserve the current deployed values; never print them |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Preserve the real deployed duration |
| `JWT_ISSUER`, `JWT_AUDIENCE` | Stable consistent configuration, including rollback candidate |
| `ENVIRONMENT`, `AUTO_INIT_DB`, `SEED_DEMO_DATA` | `production`, `false`, `false` |
| Client refresh | No opt-in; no refresh storage/interceptor release |

## 5. Backup and isolated restoration plan — NOT EXECUTED

The owner must approve backup location, encryption/key custody, authorized access,
retention, recovery point objective (RPO), recovery time objective (RTO), and the
restore environment. Do not assume this Supabase project's plan includes daily
backups or PITR. Confirm the most recent recoverable timestamp and backup ID
privately. Supabase documents plan-dependent backup availability, recommends
off-site exports for free projects, and notes that database backups exclude Storage
objects: [Database backups](https://supabase.com/docs/guides/platform/backups).

1. Confirm the exact project/database against the reviewed connection, current
   revision, server major version and schema. Resolve the exposure blocker first.
   Record counts plus a protected equality check of user IDs/password hashes/roles/
   active state and seller links for the restore drill; never print hash values.
2. Arrange a verified direct database connection for native backup/migration tools
   where available. The inspected application connection is a session pooler, not
   the direct endpoint. Supabase recommends direct connections for migrations and
   native dump/restore: [Connection guidance](https://supabase.com/docs/guides/database/connecting-to-postgres).
   If direct access is unavailable, rehearse the approved session-mode alternative;
   do not silently switch to the transaction pooler or invent another target.
3. Use a reviewed PostgreSQL **17** client/runtime for the baseline and drill.
   This machine currently has pg_dump/pg_restore 18.6; they were version-checked
   only and not used for a backup. Do not assume a dump produced by a newer major
   is a tested restore into 17.
4. Keep connection credentials in restricted libpq service/pass files or the
   approved secret manager, outside Git and release artifacts. Files/directories
   must restrict access (0600/0700). No URL/password in process arguments, command
   history, logs or reports. Do not pass the SQLAlchemy `postgresql+psycopg2` URL
   directly to native PostgreSQL tools.
5. After approval, export a consistent custom-format `public` schema/data snapshot
   including `alembic_version`, users, seller relationships, session records,
   consumed refresh history and the legacy marker if present. The conceptual
   operator command below requires preconfigured, independently verified libpq
   services and a unique protected output path. **It was not executed.**

   ```sh
   rtk proxy env PGSERVICE=blue_panda_backup PGSERVICEFILE=/secure/pg_service.conf PGPASSFILE=/secure/pgpass pg_dump --format=custom --schema=public --no-owner --no-privileges --lock-wait-timeout=5s --file=/secure/backup/blue-panda-before-auth.dump
   ```

   The archive contains private account hashes and is sensitive even without raw
   passwords. Use encrypted storage/off-site copies and separately controlled keys.
   Record SHA-256, tool/server versions, revision, timestamp and archive verification.
   Preserve a separate reviewed schema-grant/role/policy/extension inventory because
   `--no-owner --no-privileges` omits ownership/ACL restoration. This scoped archive
   is not a full Supabase platform backup. Preserve uploads/Storage objects separately.
6. Inspect `pg_restore --list` and restore into a **new isolated PostgreSQL 17**
   instance with verified non-production host identity, disabled outbound access,
   restricted access and no production credentials. A name containing `test` alone
   is not a sufficient safety check. Do not drop/recreate a database on Supabase.
   Against the independently verified empty service, the proposed command is:

   ```sh
   rtk proxy env PGSERVICE=blue_panda_auth_restore_drill PGSERVICEFILE=/secure/drill_service.conf PGPASSFILE=/secure/drill_pgpass pg_restore --exit-on-error --single-transaction --no-owner --no-privileges --dbname=service=blue_panda_auth_restore_drill /secure/backup/blue-panda-before-auth.dump
   ```

7. Verify before/after row counts, private credential/role/link equality, sequences,
   constraints/indexes and revision. Rehearse exactly `a1b2c3d4e5f6 -> d7e8f9012abc`
   on the restored copy, verify the marker's type/nullability/default, then run
   fixture-only auth/revocation/authorization tests. Exercise lock timeout/failure
   rollback and measure elapsed backup/restore/rehearsal times against RPO/RTO.
   Production user rows must not be used for password-changing drills.
8. Retain both the pre-change archive and an approved post-migration/current
   recovery point. As sessions/revocations accumulate, an old pre-release backup
   alone is insufficient: restoring it would lose subsequent revocations.

Existing operational scripts are **not approved shortcuts**. `backup-postgres.sh`
passes DATABASE_URL in argv, optionally leaves unencrypted output, and prunes old
backups; `restore-drill.sh` performs DROP/CREATE, relies on a name-only target guard
and does not use psql ON_ERROR_STOP. `migrate-approved.sh` ignores failed revision
reads and upgrades floating `head`. `backend/migrate_supabase.py`, bootstrap and
seed helpers must not run for this release preparation. These files were preserved,
not executed or modified.

## 6. Exact controlled deployment order — approval required

1. **Freeze reviewed artifacts and controls.** Resolve blockers, obtain exact
   per-repository commits/digests and green CI/equivalent reviewed evidence; verify
   intended projects, production origins, database identity, private settings and
   a session-aware rollback build. Arrange human-controlled auto-deploy settings
   before any future push; pushing may itself trigger a deployment. No push is
   authorized by this package. Complete backup and isolated restore rehearsal.
2. **Database first.** Re-run the read-only audit immediately before the window.
   Require exactly `a1b2c3d4e5f6` and the reviewed schema; stop if unexpected. In the
   separately approved migration job, use the reviewed release artifact and an
   explicit target, not floating head:

   ```sh
   # FUTURE APPROVED JOB ONLY; run from backend with approved secret injection.
   rtk .venv/bin/python -m alembic upgrade d7e8f9012abc
   ```

   Use approved bounded DDL timeouts, verify the resulting revision/column and
   unchanged accounts/roles/links. Do not stamp, seed or run create_all. If already
   at the target on a later attempt, stop for verification/review rather than
   reusing the pre-migration audit script unchanged.
3. **Session-aware backend second.** Deploy the reviewed Python 3.12 artifact to
   Render only after schema verification, with issuance explicitly false and
   legacy acceptance true. Preserve signing settings and duration. Validate health,
   schema separately, both prefixes and approved auth smoke checks. Drain every
   old worker/instance before treating revocation as effective. Use a controlled
   traffic pause/cutover if supported; mixed old workers ignore revocations.
4. **Frontend clients third, individually.** Proposed review order: Management,
   Storefront, then Flutter. Validate each against the fully session-aware backend
   before proceeding. Verify client build-time API origins, CORS and HTTPS;
   web bases include `/api` (or `/api/v1`), Flutter API_URL is host-only because
   constants already contain `/api/v1`. Keep refresh disabled. Select and approve
   the Flutter distribution/signing mechanism separately; none was verified here.
5. **Observe and hold.** Execute the checklist and record sanitized results; stop
   progression for migration drift, failed role/ownership checks, successful use of
   revoked tokens, unexpected opt-in/refresh, elevated 5xx/401/429, database lock
   timeouts, or unacceptable latency versus the agreed baseline. Name an operator,
   observation interval and numeric latency/error thresholds before the window.
6. Modern issuance, refresh clients, legacy retirement and history cleanup require
   separate review/approval. Do not enable them as a convenience during this release.

## 7. Application rollback without losing revocation history

- Stop further release stages, preserve traffic/data for diagnosis, and prefer a
  forward fix or a **tested session-aware** backend compatible with the retained
  schema/signing/issuer/audience/legacy settings. Capture current deployment IDs
  and database recovery point before the future rollout. There is no verified
  previously deployed session-aware rollback artifact today: preparing one is a gate.
- Keep `d7e8f9012abc`, `users.legacy_tokens_revoked_at`, `user_sessions`, and
  `refresh_tokens`, including revoked/consumed records. Do not run Alembic downgrade,
  clear markers, delete revocations or reset sessions as an application rollback.
  Retain legacy revocation rows at least through their original expiry/approved
  cutoff and refresh history through family expiry; no cleanup is approved here.
- Client rollback can precede/occur independently of backend rollback while retaining
  the session-aware backend. Old clients lose remote logout, a temporary security
  regression that needs explicit incident acceptance; recorded revocations still hold.
  Verify their baked-in API origins and response compatibility before traffic returns.
- The original stateless backend is **not** a safe rollback floor, even while modern
  issuance is off: it ignores stored revocations and revives logged-out tokens.
  If no session-aware artifact is healthy, pause service and fix forward. Emergency
  stateless recovery/key rotation/forced reauthentication needs separate incident
  approval; disabling issuance alone cannot make it safe.
- Never restore an old database backup as routine application rollback. Disaster
  recovery must address sessions and password/role changes after the restore point.
  Preserve a current revocation journal/recovery point or obtain approval for
  forced reauthentication and a reviewed recovery design; do not invent a SQL merge
  of session histories during an incident.
- Render dashboard rollback reuses a retained build; its target environment settings
  must also be checked. Dashboard rollback disables auto-deploy, whereas API rollback
  does not. Verify signing keys/flags have not reverted before allowing traffic:
  [Render rollbacks](https://render.com/docs/rollbacks).
- Vercel Instant Rollback restores a previous build and its original build-time
  configuration; confirm API origins and eligible retained deployment first:
  [Vercel Instant Rollback](https://vercel.com/docs/instant-rollback).
  Neither platform action rolls back external Supabase safely by itself.
- Re-run health, role/ownership, old-token adoption, logout/reuse and staging
  password-revocation checks before restoring normal traffic. Only record status,
  timing and pass/fail; never headers, auth bodies, hashes or credentials.

## 8. Verification results and operational mechanisms

All results below were obtained in this Phase 1C review unless marked historical.

| Check | Result |
| --- | --- |
| Backend `rtk .venv/bin/python -m pytest -q -rs` | **676 passed, 2 skipped**, 97.92 s; 2 existing Starlette/AnyIO deprecation warnings |
| PostgreSQL migration coverage within full suite | All **15** migration tests ran; no auth/session/concurrency/migration skips |
| Storefront `npm test` / Management `npm test` | **46 / 86 passed**, Node 24.19.0; existing module-type and Storefront test-storage warnings |
| Storefront / Management `npm run lint` | **0 errors**, respectively 1 / 18 existing warnings |
| Storefront / Management `npm run build` | Passed with Next.js **16.4.5**, Node 24.19.0; non-live API placeholders explicitly overrode real environment destinations |
| Flutter `rtk flutter test` / `rtk flutter analyze` | **188 passed** / no issues found |
| New read-only SQL artifact, disposable PostgreSQL 18.6 | Expected-revision execution passed; unexpected revision stopped before subsequent inspection; attempted write in read-only transaction rejected; no production connection |
| Root and four active repos, staged and unstaged `git diff --check` | Passed |
| Retired web staged `git diff --check` | Existing blank line at EOF in `src/lib/__tests__/ts-resolver.mjs`; preserved and excluded from release |
| Prior Python 3.12/PostgreSQL 16 container rehearsal | Historical Phase 1B: 674 passed, 3 skipped, 1 deselected; not rerun here because it does not match live PostgreSQL 17 |

The backend's two skips require test Redis on port 6389. No Redis service was
started or installed. Tests use temporary SQLite/uploads and a fresh PostgreSQL
18.6 cluster under `/tmp`, verify cluster identity and disabled TCP, and do not use
the production URL. Password/role test changes affect only generated fixture data.

For web checks, PATH explicitly selected installed Node 24.19.0. Storefront build
used `http://127.0.0.1:9/api`; Management used `https://api.example.invalid/api`
and `https://shop.example.invalid`. These are verification artifacts, **not release
builds**. No dependencies or lockfiles were changed.

Read-only hosted probes:

| Probe | Observed result |
| --- | --- |
| Render API `/health` | 200, healthy |
| Render API `/readyz` | 200, database connected |
| `/api/auth/me`, `/api/v1/auth/me`, `/api/users`, `/api/v1/users`, no bearer | 401 |
| Both `/auth/me` prefixes with a fixed invalid probe bearer | 401; no live JWT used |
| Management `/login` | 200 |
| Expected Storefront production origin `/` | 404; routing gate above |

The current `/readyz` runs only SELECT 1: it proves connectivity, not migration
readiness, identity of the database or session-schema compatibility. Its failure
path currently includes the database exception text; review/sanitize this existing
diagnostic before relying on it as a public failure probe. Failure bodies were not
requested through fault injection or copied into this report.

Available mechanisms verified: existing backend `Dockerfile.prod` runs unprivileged
Python 3.12/Uvicorn without startup migrations or seeds; documented Render Docker/Git
deployment and dashboard rollback; installed authenticated Vercel CLI with local
project links for both active web apps; and existing VPS Compose/Caddy templates.
The Compose path includes separate infrastructure and is not approval to switch the
current hosting architecture. No Render CLI or gh CLI is installed. No sufficient
Render/Supabase management connector was available; PostgreSQL and public HTTP were
the read-only fallbacks. Vercel **list only** confirmed READY production builds at
the current committed web HEADs (see manifest); it did not verify aliases, private
environment values, plan limits or release protection.

Not performed: production backup/export/restore, DDL/DML, real authentication,
password/role changes, user creation/seeding, browser/device acceptance, matching
PostgreSQL 17 rehearsal, image rebuild, CI setup/dispatch, deploy/promotion/rollback,
Git commit/push. The checklist defines the manual steps and approvals still needed.

## 9. Residual limitations to accept explicitly

Browser access tokens remain script-readable in localStorage and Flutter uses
SharedPreferences. Offline logout cannot guarantee remote revocation. Already
authenticated in-flight business operations can finish after revocation. Legacy
acceptance has no automatic retirement; schedule it only after the actual maximum
old-token duration from the last old/validation-only worker. Per-worker in-memory
rate limits do not provide a shared multi-instance quota. Existing login lacks dummy
bcrypt work for unknown users. These are recorded limitations, not new production
integrations or claims that the marketplace is production-ready.
