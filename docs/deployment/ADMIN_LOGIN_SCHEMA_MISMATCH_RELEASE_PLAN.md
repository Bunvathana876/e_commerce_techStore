# Admin login schema mismatch release plan

Date: 2026-11-08. **HOLD — preparation only; stop before production changes.**
No production connection, permission change, migration, backup/export/restore,
configuration change, authenticated smoke, deployment, commit or push was performed.

Read with the [login investigation](MANAGEMENT_LOGIN_CORS_REPORT.md),
[Phase 1C permission plan](../upgrade/PHASE_1C_SECURITY_REMEDIATION_PLAN.md),
[security gates](../upgrade/PHASE_1C_SECURITY_RELEASE_GATES.md),
[Phase 1D recovery/release plan](../upgrade/PHASE_1D_SECURE_PRODUCTION_PREPARATION.md)
and [authentication acceptance checklist](../upgrade/PHASE_1C_AUTH_RELEASE_CHECKLIST.md).
This plan narrows the immediate goal to restoring existing administrator login;
it does not authorize the broader client rollout described in those documents.

## Confirmed evidence and unresolved attribution

| Finding | Evidence and limit |
| --- | --- |
| Production revision is `a1b2c3d4e5f6`, `user_sessions` exists, marker column is absent | Confirmed by the user's production Supabase results; not independently refreshed in this task |
| Live valid-shaped login returns 500; production preflight and readiness work | Prior login report and user's confirmation; readiness tests connectivity rather than ORM/schema compatibility |
| Current local code requires the marker during login | `AuthService.login` executes `select(User)` before checking account existence/password; `User` maps `legacy_tokens_revoked_at` |
| Local committed backend `ad26cefb3dae4d0a24d1b53c8cdb5f494ac602cf` has this requirement | Read exact committed model/service/migration using Git; not inferred from dirty working-tree files |
| Historical manifest backend `ee3f547295687a0a1e9612eb90cf0a50b2787d70` lacks the marker mapping and migration | Exact committed files compared; the manifest records a repository head, not a verified current Render deployment |
| Render deployed commit | User confirms `ad26cef`, which resolves locally to `ad26cefb3dae4d0a24d1b53c8cdb5f494ac602cf`; its committed model and login service were rechecked |
| Effective Render DB role and per-instance target binding | **UNVERIFIED**; current runtime evidence not supplied |
| Precise live database exception | **UNVERIFIED**; sanitized traceback not supplied |

Against the confirmed schema, the user-confirmed deployed commit's login query
references a nonexistent column. The query fails before password verification,
even when no matching user exists, when connected to that database/schema.
The expected PostgreSQL error is UndefinedColumn, SQLSTATE `42703`. This is a
sufficient explanation for this code/schema combination; the specific live 500
has now been tied to the user-confirmed source commit. Actual runtime database
binding/role and the raw exception remain unverified. No sanitized Render
traceback was found in the reviewed reports. Do not claim that a schema repair
rules out other errors.

Current backup check: no encrypted archive candidate was found under workspace
`backups/`; the existing Phase 1D recovery evidence is synthetic-only with zero
production connections. This does not rule out a backup held elsewhere, but no
recoverable production archive is verified. The prepared Phase 1D export recipe
must receive approval for encrypted public-schema/metadata export, protected
destination, approved recipient certificate/key custody and isolated restore
before use. Permission/migration execution remains a later separate approval,
conditional on recoverability and actual Render-role compatibility.

## Migration and security ordering

[d7e8f9012abc](../../backend/alembic/versions/d7e8f9012abc_add_legacy_token_revocation.py)
has parent `a1b2c3d4e5f6`. It adds nullable
`public.users.legacy_tokens_revoked_at` as timestamp with time zone, without a
default or backfill. It does not change passwords, roles, seller links or session
rows. The existing-name check does not validate type/nullability; drift requires
review. Its inspector needs an online connection; offline SQL output is not an
accepted rehearsal. ALTER TABLE requires a lock, so the job needs bounded lock
and statement timeouts and an approved window. See [PostgreSQL ALTER TABLE](https://www.postgresql.org/docs/17/sql-altertable.html).

The existing [permission apply SQL](../upgrade/phase_1c_security/apply.sql) must run
**before** this migration under the reviewed release procedure. Its
[target guard](../upgrade/phase_1c_security/target_guard.sql) requires exactly
`a1b2c3d4e5f6`, the expected PostgreSQL major, owner session/BYPASSRLS, owners,
dependencies and sequence bindings. Apply also requires the exact reviewed ACL/RLS
baseline. It revokes table/sequence access from PUBLIC, anon, authenticated and
service_role on the three auth tables and enables non-FORCE, policyless RLS.
It does not advance Alembic. A changed baseline or already-applied remediation
requires fresh review rather than blind reapplication or weakening guards.

This ordering preserves the reviewed guard and closes historically documented
auth-table exposure before adding the revocation marker. It is a requirement of
this release package, not a PostgreSQL dependency of ADD COLUMN itself.
Disabling Data API alone does not repair SQL grants. Historical exposure findings
must be refreshed; current hosted containment is not established by this review.

Actual Render access must survive remediation. An owner normally bypasses
non-FORCE RLS; BYPASSRLS does not substitute for SQL privileges. An ordinary
non-owner role without policies is denied even when granted table access.
A service_role-derived connection can lose its grants. Verify the real role;
do not switch to an owner, grant BYPASSRLS or restore browser-role access as an
unreviewed workaround. See [PostgreSQL RLS behavior](https://www.postgresql.org/docs/17/ddl-rowsecurity.html).

## Ordered manual production checklist

Every change below requires its named approval; this document grants none.
Record operator/approver, UTC time, artifact hashes, target-match booleans and
status-only evidence. Keep credentials, SQL parameters and account/session rows
out of chat, logs and Git.

1. **Bind deployed code to the failure — release owner, read-only evidence.**
   In Render, select the backend service and currently live deployment, not just
   the newest build. Record its full commit SHA, artifact identity, active-instance
   inventory and effective start command. Compare that exact commit's
   `app/models/user.py`, `app/services/auth_service.py`, `app/db/database.py` and
   `app/services/auth_session_service.py` with the reviewed code. Check connection
   hooks/SET ROLE/search_path and whether it requires the marker. Obtain the login
   exception type, SQLSTATE and application stack location with secrets/parameters
   removed. If the deployed code does not select the missing column, stop and
   diagnose its actual exception; do not migrate based on this hypothesis alone.
2. **Verify every Render runtime — DB owner/release operator, read-only evidence.**
   Follow the existing [per-instance procedure](../upgrade/PHASE_1C_SECURITY_RELEASE_GATES.md#exact-safe-render-uiruntime-steps)
   using [render_identity_probe.py](../upgrade/phase_1c_security/render_identity_probe.py)
   through Python stdin on an existing runtime, with privately verified project
   and service identifiers. Record effective current_user/session_user, owner
   membership, role flags, public schema USAGE, required auth-table/sequence
   privileges, PostgreSQL version, TLS, connection mode and commit match. Inspect
   linked environment groups, routing overrides and search_path privately. The
   probe requires the parent revision and is not a post-migration probe. If the
   service tier has no Shell/SSH, obtain equivalent existing owner-operated
   evidence; do not claim the local production file proves Render's role.
3. **Close exposure/configuration/credential gates — owner/security approvals.**
   Inventory external Data API, GraphQL and service_role consumers. Refresh hosted
   API settings/grants metadata. If confirmed unused, separately approve and apply
   Integrations -> Data API -> Overview -> Enable Data API off, save and recheck;
   retain GraphQL off. If external consumers exist, stop for reviewed containment
   design. Follow the [credential assessment](../upgrade/phase_1c_security/CREDENTIAL_ROTATION_CHECKLIST.md):
   privately establish actual Render reuse of disclosed values and coordinate
   separately approved rotations/cutovers if affected. No unaffected Supabase
   password rotation is implied. Do not preserve a compromised key for compatibility.
4. **Establish recoverability — custodian/export/restore approvals.**
   Follow the Phase 1D encrypted recovery procedure, not the legacy backup helpers.
   Capture a verified pre-change recovery point with protected owner/ACL/RLS,
   role/membership/default-privilege/revision metadata and separate media coverage.
   Use approved PostgreSQL 17 clients, a verified direct connection or session
   pooler on 5432, protected libpq service/pass files, authenticated encryption and
   separate key custody outside Git/cloud sync. Restore and validate the actual
   archive on an independently isolated target; record RPO/RTO. Historical
   synthetic drills do not prove this recovery point. Last evidence showed no
   Free-plan managed backup/PITR; verify current recovery capability privately.
5. **Rehearse the exact release — staging/data-custodian approval.**
   On isolated PostgreSQL 17 with the Python 3.12 release image and the real
   runtime role semantics, test permissions -> marker migration -> application.
   Confirm account/hash/role/store-link preservation privately, new-session writes,
   legacy JWT acceptance, logout/revocation and RBAC denials under both prefixes.
   Verify API-role denial, lock-timeout transaction rollback, history retention and
   the session-aware fallback. Run auth and full backend suites on the exact
   candidate. No production fixture users, password changes or failure injection.
6. **Apply permissions first — explicit DB-owner/security execution approval.**
   Recheck the reviewed project, revision `a1b2c3d4e5f6`, ACL/RLS/ownership state and
   approved unchanged hashes immediately before the window. Use the plan's
   protected service and psql invocation from the workspace root:

   ```sh
   rtk proxy env PGSERVICE=blue_panda_security_approved psql -X -v ON_ERROR_STOP=1 -v approval=APPROVED_AUTH_TABLE_ACL_WINDOW -v expected_server_major=17 -f docs/upgrade/phase_1c_security/apply.sql
   rtk proxy env PGSERVICE=blue_panda_security_approved psql -X -v ON_ERROR_STOP=1 -f docs/upgrade/phase_1c_security/verify.sql
   ```

   The approval string is only a guard, not authorization. The service must already
   be independently bound to the approved target outside Git. Apply takes bounded
   ACCESS EXCLUSIVE locks (2-second lock/10-second statement limits). Stop on any
   guard/verification failure. Verify required backend access separately: the
   denial verifier does not prove login works. Keep hosted containment in place.
7. **Apply only the marker — separate migration execution approval.**
   Use the exact reviewed backend artifact in a dedicated Python 3.12 migration
   job, working directory `backend/`, with privately supplied, independently
   verified production DATABASE_URL and DDL-capable migration identity. Enforce
   2-second lock and 10-second statement budgets on the actual connection; review
   URL/libpq options so they cannot override those budgets. Recheck the parent
   revision, public search_path, target and security baseline. The exact Alembic
   operation is:

   ```sh
   rtk proxy python -m alembic upgrade d7e8f9012abc
   ```

   Do not run `upgrade head`, stamp, downgrade, replay earlier migrations, use
   automatic init/seed or the existing upgrade-head helper. Verify revision is
   exactly `d7e8f9012abc`; the public.users marker is nullable timestamptz with no
   default; ACL/RLS and account/history metadata remain preserved. The migration
   itself does not enforce this release's target, permission or timeout gates.
8. **Confirm/runtime cutover only as needed — separate release/config approval.**
   On every worker, explicitly verify `ENVIRONMENT=production`,
   `AUTO_INIT_DB=false`, `SEED_DEMO_DATA=false`,
   `RUN_MIGRATIONS_ON_STARTUP=false`, `AUTH_ISSUE_SESSION_TOKENS=false`,
   `AUTH_ACCEPT_LEGACY_TOKENS=true`, and unset/approved future legacy cutoff.
   Preserve uncompromised signing settings, actual access lifetime and consistent
   issuer/audience; retain explicit trusted CORS origins, TLS and reviewed proxy
   trust/pool budgets. Settings reads `.env`, not `.env.supabase` automatically.
   If the exact current backend is already the approved session-aware artifact,
   first assess recovery after the additive migration: login restoration need not
   require an unrelated client release or backend deployment. If code/configuration
   cutover is required, approve the exact tested artifact, drain old workers and
   verify every instance. Release the local CORS masking fix separately if desired;
   it cannot substitute for the schema repair. Never enable modern issuance/refresh
   or rotate an unaffected signing key as part of this compatibility fix.
9. **Verify existing admin login — separate account-owner/session-write consent.**
   Check `/health` and `/readyz` 200, schema/revision independently, production
   Management OPTIONS 200 and empty-body login 422. The existing admin privately
   signs into Management: POST login 200, GET `/auth/me` shows the same active
   admin, dashboard loads and an authorized admin request succeeds. Record status
   only; do not export customer lists, tokens, passwords or HAR files. Verify
   anonymous/invalid-bearer requests return 401 and an existing consenting customer
   gets 403 on admin APIs; repeat relevant checks under `/api` and `/api/v1`.
   Login, legacy adoption and logout can write sessions even with issuance OFF.
   Test revocation with approved staging fixtures or separately approved session
   smoke; do not create/promote production users, alter passwords or run load tests.
   Observe 5xx/latency and logs for the agreed window before owner sign-off.

## Rollback limits and minimum restoration scope

- Before permission COMMIT, failures roll back its transaction. After COMMIT,
  prefer a reviewed forward fix. Existing rollback.sql restores vulnerable grants
  and disables RLS: it needs separate emergency security approval and containment.
- Both apply and rollback guards require `a1b2c3d4e5f6`. After the marker advances
  Alembic, the old permission rollback cannot run unchanged. **Do not downgrade
  to satisfy its guard**; renew forward-recovery review instead.
- Marker downgrade removes the legacy-token revocation barrier. Retain the column,
  revoked/consumed session history and security controls. No stateless backend
  fallback, blind historical-commit rollback or old database restoration to undo
  permissions. A pre-window restore may lose later writes/revocations and revive
  access; actual disaster recovery needs separate approval and reconciliation.
- Minimum safe scope, once code/schema attribution and gates pass: approved
  containment/recovery -> compatible permission remediation at parent revision ->
  the single additive marker migration -> verify the current approved runtime ->
  existing-admin session smoke. No new table, user, role promotion, JWT format
  change, frontend rebuild or broad application rollout is intrinsically needed.
  A required credential incident response or runtime-role redesign remains a
  separate blocker, not an excuse to skip security requirements.

## Verification and handoff

This task changed only this plan. No application/SQL/migration/configuration file
was edited, and no application tests or migration rehearsals were executed.
Existing SQL/guard/assertion, recovery runner/metadata and marker migration hashes
match the Phase 1D record. Local exact-commit file comparison, relative-link checks,
whitespace and Git preservation checks were performed.

The earlier backend result was 702 passed, 2 Redis-dependent skips on the local
environment; it is not new release-image acceptance. Historical PostgreSQL 17.11
permission/recovery drills and Python 3.14/SQLite marker checks remain valid only
for their stated synthetic scope. Current Render role/configuration, sanitized
exception, real recovery point, PostgreSQL 17/Python 3.12 application acceptance,
current exposure/credential status and all production execution approvals remain
open. No production change is authorized by completing this checklist.
