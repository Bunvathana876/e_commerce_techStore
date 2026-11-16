# Phase 1C security blocker investigation and remediation plan

Date: 2026-11-07. **HOLD — preparation only; no production changes authorized.**
This supplements the [release report](PHASE_1C_AUTH_RELEASE_REPORT.md),
[checklist](PHASE_1C_AUTH_RELEASE_CHECKLIST.md), and
[original SQL](PHASE_1C_AUTH_READ_ONLY_CHECKS.sql). Historical findings remain intact.

## 1. Exposure conclusion and evidence limits

**Confirmed: the inspected database permits both `anon` and `authenticated` to
access all three authentication tables without RLS. Internet exploitation is not
confirmed or ruled out. Treat this as a critical release blocker until the hosted
API configuration and target binding are independently verified.**

The [sanitized evidence](phase_1c_security/evidence.json) records the catalog audit
at **2026-11-07 09:36:06 UTC**. No application records, password hashes, token hashes,
bearers, sequence values, or connection secrets were retrieved. No production DDL,
DML, migration, login, deployment, account/password change, commit, or push occurred.

The connection came from the same protected `backend/.env.supabase` used by Phase
1C: Supabase session pooler, port 5432, expected project-reference username format,
database `postgres`, current/session role `postgres`, PostgreSQL **17.11**. The
first application-schema read required exactly revision `a1b2c3d4e5f6`; it matched.
Transactions were repeatable-read/read-only with 10-second statement and 2-second
lock timeouts, and rolled back. Role-switch probes were transaction-local.

This verifies continuity with the previously audited target, **not independent
ownership of that project or Render's live binding**. There is no available
Supabase/Render management connector; browser inventory reported its access host
unavailable. Root `.env` and backend `.env` point at different connection targets
from `.env.supabase`; their values were neither printed nor changed. Do not assume
either local default represents Render production. Before applying anything, the
owner must privately compare the pooler username's project reference with the
Blue Panda dashboard and Render's actual DATABASE_URL/role.

Client-to-pooler TLS is confirmed by libpq `ssl_in_use=true`. Database-side
`pg_stat_ssl` reported false for the pooler's server connection. These measure
different hops; end-to-end TLS is **not** established by this inspection. Privately
verify pooler-to-database protection with Supabase; do not change connection mode
or weaken certificate checks in this task. `sslmode=require` itself does not attest
hostname verification.

## 2. Exact permissions and reachable paths

The following findings apply identically to `public.users`,
`public.user_sessions`, and `public.refresh_tokens`:

| Object / control | Current finding |
| --- | --- |
| Owner | `postgres` |
| RLS / forced RLS / policies | false / false / zero |
| Direct table grantees | `postgres`, `anon`, `authenticated`, `service_role`; grantor `postgres`; no grant options |
| Each table grant | SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER, MAINTAIN (`arwdDxtm`) |
| Column-specific ACLs | None; full-table SELECT includes sensitive columns |
| ID sequences | `users_id_seq`, `user_sessions_id_seq`, `refresh_tokens_id_seq`: USAGE, SELECT, UPDATE for all four roles; owner/grantor `postgres` |
| `public` schema | USAGE for PUBLIC and explicit API roles; API roles have no effective CREATE |
| `graphql_public` schema | USAGE for anon/authenticated/service_role; not proof GraphQL is running |
| Defaults in `public` | For creators `postgres` and `supabase_admin`: all table/sequence privileges and function EXECUTE to API roles |
| Alternate paths inspected | Zero functions in `public`; zero dependent views/materialized views on these tables; zero policies |

`anon` and `authenticated` are NOLOGIN, INHERIT, NOSUPERUSER, NOBYPASSRLS and have
no direct parent memberships. NOLOGIN does not protect the API: `authenticator`
can SET ROLE to both and to `service_role`; its memberships are non-inheriting.
`service_role` has BYPASSRLS. The inspected `postgres` is also BYPASSRLS,
CREATEROLE/CREATEDB and owns the tables; it is not a PostgreSQL superuser.

Six `SET LOCAL ROLE` probes ran `SELECT 1 FROM public.<table> LIMIT 0` under the
two untrusted API roles. All succeeded and returned zero rows. With no RLS or
policies this confirms a SQL authorization defect without fetching any record.
Effective privilege checks also confirmed every permission listed above.

REST `/rest/v1/` and GraphQL `/graphql/v1` HEAD requests without API keys each
returned 401. **These prove only gateway reachability.** No valid publishable/anon
key or Supabase authenticated JWT was available for a safe table HTTP probe.
Database/session `pgrst.db_schemas` and `pgrst.db_anon_role` were unset and no such
role/database overrides were found; process environment settings remain invisible.
`pg_graphql` is not installed. Its absence narrows that extension path but does not
prove gateway configuration. Data API enabled/disabled and exposed `public` remain
**unverified**, rather than inferred from Supabase defaults or these 401s.

Owner evidence required: matching project reference, Data API toggle, exact
Exposed schemas, automatic exposure/default-grant controls, GraphQL status, and
any custom API domain/routing. Record sanitized settings only. Public tables with
grants and no RLS are unsafe when exposed; grants and RLS are separate controls.
[Supabase API security guidance](https://supabase.com/docs/guides/api/securing-your-api)

## 3. Severity and impact

**Critical if public-schema Data API exposure is enabled; confirmed dangerous
database permissions regardless of current gateway configuration.** A usable
public application key is not a per-user authorization boundary. Supabase API
roles are distinct from Blue Panda's application `users.role` strings.

Potential reads include account PII and bcrypt hashes, session/device metadata,
and refresh-token hashes/history. Hashes are not plaintext passwords or raw
refresh tokens, and disclosure does not by itself prove token forgery. Potential
writes include password-hash replacement, administrator role assignment, account
disablement/deletion, revocation/history tampering and session disruption. These
paths bypass FastAPI authorization if accessible through the Data API. TRUNCATE,
TRIGGER and MAINTAIN are SQL-role capabilities; their grants do **not** imply that
PostgREST exposes arbitrary SQL for executing them. No exploitation was attempted.

Enabling RLS alone is insufficient: BYPASSRLS roles bypass it, and whole-table
operations such as TRUNCATE are outside RLS. Do not add a public read policy or
an `auth.uid()` policy to make custom FastAPI authentication work.
[PostgreSQL 17 RLS semantics](https://www.postgresql.org/docs/17/ddl-rowsecurity.html)

## 4. Recommended remediation and FastAPI compatibility

Approve a focused, atomic change for these internal authentication tables:

1. Revoke ALL table privileges from PUBLIC, anon, authenticated and service_role.
2. Revoke ALL privileges on their three ID sequences from the same roles.
3. Enable RLS on each table, with no API policies. Leave FORCE RLS off and preserve
   ownership and backend privileges. No user rows or auth schema columns change.
4. Verify effective privileges, including inherited/column grants, not only ACL text.

Including service_role removes an unused direct path that bypasses RLS; approval
requires checking for external jobs, integrations and administrative consumers
that were not visible in this repository. If one exists, stop and redesign its
explicit permission requirements rather than silently exempting it. Supabase
secret/service keys use this privileged role and must not be used to simulate an
anonymous denial test.
[Supabase key roles](https://supabase.com/docs/guides/getting-started/api-keys)

Do not revoke `public` schema USAGE globally: unrelated APIs may depend on it and
it is not needed for this containment. Do not change other tables, relocate the
schema, create runtime roles, change passwords, rotate signing keys, or alter
FastAPI authorization as part of this patch.

`backend/app/db/database.py` creates synchronous SQLAlchemy/psycopg2 connections
using DATABASE_URL; it does not use the Supabase Data API, forward client JWTs to
PostgREST, or SET ROLE per customer. `AuthService.login` reads/locks the user and
verifies bcrypt in Python. Dependencies load the current user/role from the DB;
session services insert/update/lock auth records and preserve revocation history.

**For the inspected postgres owner/BYPASSRLS connection, these changes preserve
login, bcrypt verification, administrator authorization and session CRUD.** No
API-role policy is needed by that connection. This is a conditional compatibility
assessment, not a claim that Render's actual role has been proven. A restricted
non-owner/NOBYPASSRLS backend would be blocked by policyless RLS even with table
grants. If Render uses such a role, stop and prepare a dedicated backend-only
policy before applying; do not grant privileges back to browser API roles.

Future minimum-privilege runtime role, as a separate reviewed change:

| Role | Minimum intended access |
| --- | --- |
| anon / authenticated / PUBLIC / unused service_role | No auth-table or sequence access; no applicable policies |
| Dedicated FastAPI role | LOGIN, NOSUPERUSER, NOCREATEROLE, NOCREATEDB, NOBYPASSRLS, no ownership or API-role membership; database CONNECT and schema USAGE |
| FastAPI auth objects | users SELECT/INSERT/UPDATE/DELETE for existing user operations; sessions and refresh SELECT/INSERT/UPDATE; sequence USAGE for inserts; backend-role-only ALL policy USING true / WITH CHECK true |
| Migration role | Owns objects and performs reviewed DDL; unavailable to clients and routine application requests |

The runtime role still needs an inventory of commerce-table privileges; do not
switch Render to an auth-only role. Session/refresh DELETE needs a separately
reviewed cleanup use case; do not discard revocation or replay history. The policy
permits the trusted backend to serve all accounts while existing FastAPI checks
enforce per-user authorization; authenticator must not be able to assume that role.

Default ACLs would expose future recreated tables. Review creator-specific table,
sequence and function defaults separately, including `supabase_admin` authority
and PostgreSQL's global PUBLIC function EXECUTE default. Avoid a blanket default
change without dependency review. Every future auth migration must preserve RLS
and denied grants. If the owner confirms Data API is entirely unused, separately
approve disabling it and verify GraphQL/other dependencies independently. That
does not replace database privilege containment.

## 5. Prepared SQL and rollback

All scripts are **draft artifacts**, outside Alembic; none were run in production.
They do not change the Alembic stamp. Register the approved permission change in
the project's reviewed migration process before an eventual application.

| Added file | Purpose |
| --- | --- |
| `PHASE_1C_SECURITY_REMEDIATION_PLAN.md` | Findings, limits, decision and approval gates |
| `phase_1c_security/evidence.json` | Sanitized read-only catalog and HTTP evidence |
| `phase_1c_security/inspect.sql` | Reproducible revision-first, bounded metadata-only preflight |
| `phase_1c_security/target_guard.sql` | Shared approval/version/revision/ownership/dependency guard |
| `phase_1c_security/apply.sql` | Atomic narrow revocations and RLS enablement |
| `phase_1c_security/rollback.sql` | Exact observed grants/RLS restoration, separately approved emergency use |
| `phase_1c_security/deny_assertions.sql` | Effective table, column and sequence denial assertions |
| `phase_1c_security/verify.sql` | Read-only SQL role tests; DML planning only, never execution |
| `phase_1c_security/data_api_negative_tests.py` | Future HTTP valid-role controls and zero-row denial tests |
| `phase_1c_security/rehearse_local.py` | Isolated Unix-socket fixture rehearsal with target guards |

Only after explicit approval, use a protected, independently verified libpq service
and `psql -X`, not a web SQL editor. The planned apply invocation is:

```sh
rtk proxy env PGSERVICE=blue_panda_security_approved psql -X -v ON_ERROR_STOP=1 -v approval=APPROVED_AUTH_TABLE_ACL_WINDOW -v expected_server_major=17 -f docs/upgrade/phase_1c_security/apply.sql
```

The approval string is an accidental-execution guard, **not authorization or
independent project verification**. The service/pass files must be restricted and
configured outside Git; no connection URL/password in argv. Exact revision,
owners, ACLs, RLS, columns, sequences and inspected dependencies must match. An
unexpected revision, repeated apply, inherited residual grant or lock timeout
aborts the transaction. The table lock is ACCESS EXCLUSIVE, bounded to two seconds;
there may be brief blocking. Rehearse lock contention on PostgreSQL 17 first.

Before COMMIT, failure rolls back the entire ACL/RLS change. After COMMIT, prefer
a forward fix of the verified backend role. `rollback.sql` restores only the
observed table/sequence grants and disabled RLS, with no data or default-ACL
changes. **It reopens the vulnerability**: isolate externally exposed API access
first, obtain separate security/DB-owner approval, and replace only the filename
in the planned command. It refuses changed revision/ACL/policy state. If the auth
marker migration has already advanced the revision, renew review; never downgrade
session history or use database restoration to undo a permission-only failure.

## 6. Verification and negative tests

Completed during this investigation:

- Read-only production catalogs and six zero-row role probes: grants defect
  confirmed. Production writes and authenticated account operations: zero.
- `rtk proxy .venv/bin/python -m pytest tests/test_auth_sessions.py tests/test_authorization.py tests/test_auth_session_concurrency.py -q`
  from backend: **412 passed**, two existing deprecation warnings, 50.38 seconds.
  Tests configure temporary SQLite/uploads and an independently checked temporary
  PostgreSQL cluster before importing the app. No production URL is consumed.
- Local SQL rehearsal: PostgreSQL **18.6**, TCP disabled, exact temporary data
  directory checked, non-superuser postgres owner/BYPASSRLS fixture. Apply,
  effective privilege checks, 45 SELECT/EXPLAIN denial cases across three roles,
  preserved owner CRUD, repeat-apply refusal, missing-approval/revision-drift
  refusal, exact ACL/RLS rollback and reapply passed. RLS also hid a populated
  fixture after an accidental SELECT regrant. No production connection.
  This is not matching PostgreSQL 17/Python 3.12 staging acceptance.
- HTTP test runner parsed successfully. Actual valid-key HTTP tests were **not
  executed** because the verified project settings and role credentials are absent.
- Root `git diff --check`, diff/status review, and individual no-index whitespace
  checks for all ten added artifacts passed. Existing unrelated work was preserved;
  no Git index changes were made.

Required future acceptance, in order:

1. Owner verifies project, Render binding/role and API settings. On independently
   isolated PostgreSQL 17/Python 3.12 staging, capture ACL/RLS metadata and run apply.
   Exercise two-second lock timeout and a deliberate statement failure; assert
   transaction rollback leaves ACLs, data and revocation history unchanged.
2. Run `rtk proxy psql -X -v ON_ERROR_STOP=1 -f docs/upgrade/phase_1c_security/verify.sql`
   through the verified protected service. Every API role must lack all eight
   table privileges, four column privilege classes, and all sequence privileges.
   Under each role SELECT LIMIT 0 and EXPLAIN SELECT/INSERT/UPDATE/DELETE must
   fail specifically with SQLSTATE 42501. No TRUNCATE or DML is executed.
3. With Data API enabled in staging, provide the HTTP runner an owned 0600 JSON
   file outside Git: `project_url`, `publishable_key`, an existing Supabase Auth
   fixture `authenticated_jwt`, and `target_verified: true`. Never paste these
   values into chat. Run:

   ```sh
   rtk proxy python3 docs/upgrade/phase_1c_security/data_api_negative_tests.py /secure/blue-panda-staging-api-tests.json
   ```

   For anon and authenticated independently, the metadata control must return 200
   with valid credentials. GET each `/rest/v1/<table>?select=id&limit=0` with
   `Accept-Profile: public` must return 401/403 plus code 42501, or 404/PGRST205
   for a hidden relation. Any 200, including `[]`, fails this grants-removal test.
   Invalid/expired JWTs, invalid keys, unrelated 404s, timeouts and 5xx prove
   nothing. Record role/table/status/code only. No service key substitution,
   forged JWT, row read, or production POST/PATCH/DELETE test is permitted.
   If API/public exposure is disabled, record that setting and verify disabled
   routing separately; the runner's failed control is inconclusive, not a pass.
4. With disposable staging fixtures only, test HTTP INSERT/UPDATE/DELETE and
   GraphQL queries/mutations if GraphQL is enabled. Target populated fixtures,
   require permission denial and privately verify they remain unchanged. A
   well-formed valid credential control is required. Do not infer write safety
   from an invalid-body 400 or test writes on production records.
5. With the **actual deployed backend role/settings** in staging, test both
   `/api` and `/api/v1`: correct login 200; wrong password 401; inactive fixture
   403; admin users access 200; customer access 403; no/invalid bearer 401.
   Verify bcrypt valid/wrong/malformed hashes on generated fixtures only. Verify
   token aliases/lifetime, issuance-off/null refresh, device A logout -> 401 while
   B stays 200, legacy adoption once, password-change/replay/revocation rollback
   tests on disposable fixtures. Existing automated tests cover these behaviors;
   the role-specific PostgreSQL 17 staging run remains required.
6. After separate production permission-change approval, rerun metadata/SQL and
   zero-row HTTP denial checks, and compare protected account/role/credential
   equality and counts without exporting values. Production login/session smoke
   requires separate owner consent because it writes sessions. No password or
   account changes are authorized. Never claim live positive auth acceptance
   based only on this local suite or a healthy SELECT 1 readiness endpoint.

Web/mobile builds, lint and browser/device auth E2E were not rerun: application
code was unchanged. PostgreSQL 17 staging, actual Render role, managed recovery,
hosted API controls and approved production positive auth smoke remain gates.

## 7. Storefront 404 — separate confirmed cause

The report's expected `https://blue-panda-storefront.vercel.app/` returns 404 with
`x-vercel-error: DEPLOYMENT_NOT_FOUND`; authenticated Vercel inspect cannot resolve
it under the verified linked project/team. The project's READY production build
is `dpl_4ta3coNCJLQss3jJTT2SRNjeybye`, source SHA
`04dacabfd6297d133a5e3246fdd5a0ff6f213ab1`. Its assigned aliases are:

- `https://blue-panda-storefront-iota.vercel.app/` — HEAD **200**.
- `https://blue-panda-storefront-vathanabun934-2100s-projects.vercel.app/`.

**Cause: the reported URL is not an assigned alias for that production deployment.**
The production build includes the root route; this evidence places the reported
404 at Vercel alias resolution. Why the shorter name was not assigned is not
proven. Root/Management local Storefront settings did not match the unassigned
hostname; deployed environment values were not retrieved.

Obtain release-owner agreement on the canonical origin. Either use the existing
working alias consistently in deployment docs, client origins and backend CORS,
or separately approve assigning an available intended alias. Inspect deployed
origins/CORS and test redirects/links before future release. No alias, setting,
source file or deployment was changed. This issue does not explain or mitigate
the Supabase permissions blocker. Vercel investigation used the
[vercel-cli skill](/Users/bunvathana/.codex/plugins/cache/openai-curated-remote/vercel/0.54.1/skills/vercel-cli/SKILL.md).

## 8. Required approval and stop point

Before application, obtain named DB-owner/security approval for the exact project,
actual Render role, three tables/sequences, removal of service_role dependencies,
reviewed immutable SQL, recovery point, matching staging results, bounded lock
window, observer and forward-fix/rollback procedure. Independently authorize any
Data API/default-ACL/runtime-role or alias/CORS change; these are outside the narrow
draft migration. Production positive session smoke and any later commit/push or
deployment require their own approvals. Accounts/passwords remain untouched.

**Stop here. This package prepares a remediation; it does not establish that the
hosted API is safe, close the release blocker, or authorize execution.**
