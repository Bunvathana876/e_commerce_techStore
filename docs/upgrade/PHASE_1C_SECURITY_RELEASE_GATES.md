# Phase 1C security release gates — verification record

Date: 2026-11-07. **Decision: HOLD. Production permission changes are not approved.**
Read with the [remediation plan](PHASE_1C_SECURITY_REMEDIATION_PLAN.md).
Phase 1D preparation now continues in the
[secure production runbook](PHASE_1D_SECURE_PRODUCTION_PREPARATION.md).
It adds a synthetic encrypted recovery rehearsal and ordered release checklist;
the original SQL and successful Phase 1C evidence are preserved. The Data API
toggle, real recovery point, Render verification, permissions, marker migration,
credential rotations and deployments remain unexecuted. **Permission SQL must
precede d7e8f9012abc because its existing guard requires a1b2c3d4e5f6.**
This records fresh evidence and exact missing approvals; it does not replace
unverified conditions with assumptions from the earlier local rehearsal.

Previous isolated continuation: the user explicitly approved pulling the official
`postgres:17-alpine` image and isolated disposable testing. PostgreSQL 17.11 SQL
rehearsal passed at 11:24:24 UTC using the unchanged runner with the temporary
copy adapter documented below. This continuation made no production connection,
Render configuration change, deployment, production migration, commit or push.

Previous remaining-gates continuation: the runner's Docker copy issue is fixed and
the direct PostgreSQL 17.11 retest passed at **2026-11-07 12:27:04 UTC**, with
identical reviewed SQL hashes and all nine earlier checks passing. Historical
success is preserved separately. Hosted verification stopped at a device-login
boundary; no live database connection or application-row retrieval occurred.
No production writes, permission changes, migrations, deployments, secret
rotations, commits or pushes were performed.

Latest authorized private dashboard review, **2026-11-07 12:40–12:49 UTC**:
the existing signed-in Supabase session now permits settings review. Dashboard
project binding is verified; Data API/public/three-table exposure is confirmed;
pg_graphql is off; managed backup/recovery options are gated by the Free plan.
Render stops at Sign in, so no running-instance role was verified. All earlier
PostgreSQL success evidence and SQL remain unchanged. New sanitized observations
are in [dashboard_evidence_20261107.json](phase_1c_security/dashboard_evidence_20261107.json).
No production database connection, row query, settings save/toggle, extension
installation, export/restore, credential rotation, deployment or Git write ran.

## Gate results

PASS means the named, bounded claim was verified. FAIL means contrary evidence
was observed. UNVERIFIED means required evidence is missing, not that the system
has been shown vulnerable or safe through that path.

| Gate | Result | Evidence / exact remaining requirement |
| --- | --- | --- |
| Plan and existing permission SQL reviewed | **PASS** | Apply, rollback, guards, assertions, inspection and test runners re-read; existing SQL preserved |
| Connection continuity and expected live revision | **PASS** | Historical read-only audit at 2026-11-07 11:02:38 UTC: same protected target file, database postgres, PostgreSQL 17.11, revision a1b2c3d4e5f6, postgres session; not refreshed in this continuation |
| Independent Blue Panda project identity | **PASS** | Signed-in dashboard: Bunvathana876 / blue-panda-demo / main PRODUCTION; General Project ID equals dashboard URL reference and matches reviewed backend/.env.supabase via private identifier-fingerprint comparison; no reference/URL recorded |
| Authentication-table SQL protection at last live audit | **FAIL** | 11:02:38 UTC snapshot: all three tables had disabled RLS, no policies and all eight table privileges for anon/authenticated/service_role; sequences remained granted; no remediation or fresh live audit performed here |
| Hosted Data API/public-schema exposure established | **PASS** | Dashboard Enable Data API on; selected schemas graphql_public/public; users/user_sessions/refresh_tokens selected in Exposed tables; automatic new-table exposure on; no setting changed |
| Hosted sensitive-table protection | **FAIL** | Verified Data API/public/table exposure plus preserved 11:02:38 UTC grants/no-RLS audit; failure established without retrieving rows; not a fresh valid-role HTTP test |
| Actual running Render target and effective DB role | **UNVERIFIED** | Render dashboard presents Sign in; stopped without entering credentials or continuing authentication; active instance inventory/roles unknown |
| Prepared Render read-only probe reviewed | **PASS** | Unchanged source reread and Python syntax checked; bounded read-only metadata design and operator acceptance limits reviewed below; no live execution claimed |
| Official PostgreSQL 17 image identity/version | **PASS** | Approved pull resolved to docker.io/library/postgres:17-alpine; inspected digest/image ID recorded below; isolated server reported 17.11 |
| Historical PostgreSQL 17 rehearsal evidence preserved | **PASS** | Original adapter-run JSON archived byte-for-byte; reviewed SQL hashes and all nine checks match the direct retest |
| Rehearsal runner Docker copy fix and direct retest | **PASS** | Built-in docker exec stdin transfer verifies SHA-256 for all seven copied files; direct command exited 0 at 12:27:04 UTC without a PATH adapter |
| PostgreSQL 17 isolated apply rehearsal | **PASS** | Unchanged SQL applied to synthetic fixtures on isolated 17.11 in both historical adapter run and fixed direct runner |
| Simulated backend database role retains access | **PASS** | Synthetic non-superuser postgres owner/BYPASSRLS retained the runner's SELECT/UPDATE/DELETE on all three tables and INSERT using users_id_seq; transaction rolled back |
| FastAPI role retains access after changes | **UNVERIFIED** | Must first identify Render's role, then test its ownership/membership/BYPASSRLS/policies and required table/sequence rights on isolated 17; prior owner-role 18.6 test is conditional evidence only |
| Unauthorized API-role SQL denial after changes on 17 | **PASS** | Unchanged verify.sql passed all 45 role/statement cases for anon/authenticated/service_role after apply and reapply; table, column and sequence privilege assertions passed |
| Hosted unauthorized Data API denial | **UNVERIFIED** | Needs independently verified API settings and valid-role controls; no anon key or Supabase authenticated JWT is available; no HTTP row requests were attempted |
| Rollback/reapplication on 17 | **PASS** | Exact fixture ACL/RLS baseline restored; revoked sessions and consumed/revoked refresh fixture history retained; reapplication and denial assertions passed |
| Disposable-container cleanup and preservation | **PASS** | Latest direct-test container removed; same 12 containers and 63 volumes as this continuation's fresh baseline; SQL, historical evidence, configuration and unrelated files preserved |
| GraphQL security model reviewed | **PASS** | Official pg_graphql documentation ties visibility to role privileges/search_path and rows to RLS; disabled introspection does not prove denial |
| Standard hosted pg_graphql path inactive | **PASS** | Dashboard GraphQL offers Install integration; Extensions pg_graphql switch off, available version 1.6.2, with Install extension to use GraphiQL; no installation/toggle/query performed |
| Custom/external GraphQL paths and hosted HTTP denial | **UNVERIFIED** | Standard extension inactivity does not inventory custom resolvers/external services; no valid-role GraphQL request performed |
| Backend-role compatibility comparison criteria | **PASS** | Proposed revocations and policyless RLS reviewed against owner/BYPASSRLS, service_role and ordinary-role cases below |
| Backup/recovery requirements reviewed | **PASS** | Requirements and unsafe legacy shortcuts reviewed below; no export or restore performed |
| Managed scheduled backup/PITR availability | **FAIL** | Dashboard Free plan: no included project backups; PITR is Pro add-on; no usable managed recovery-point evidence available |
| Current managed restore-to-new-project readiness | **FAIL** | Dashboard requires Pro Plan or above and physical backups; prerequisites are not met by current Free-plan project; no upgrade or restore attempted |
| Recoverable backup and isolated restore evidence | **UNVERIFIED** | Need actual recovery point/retention, authorized custodian, verified recovery capability and separately approved restore drill |
| Backup/restore helper suitability for this gate | **FAIL** | Existing helpers expose a URL in argv, omit owner/ACL metadata, allow unencrypted output/pruning and use a name-only restore guard with destructive SQL and no ON_ERROR_STOP; preserved, not executed |
| Credential exposure assessment and rotation plan | **PASS** | Redacted category/equality review and owner-operated checklist prepared; no secret values or secret hashes reproduced in this continuation |
| Previously displayed credential confidentiality | **FAIL** | Local DB password reuse confirmed in root/backend environment configuration; root pgAdmin default and root/backend JWT signing-secret configuration also match earlier displayed literals; production adoption unknown |
| Production credential impact/rotation completion | **UNVERIFIED** | Actual production reuse/consumer inventory unavailable; no rotation authorized or performed |
| External service_role dependencies reviewed | **UNVERIFIED** | Owner must inventory jobs/integrations outside this repository before revoking its three-table access |
| Transport assurance | **UNVERIFIED** | Client-to-pooler TLS confirmed; database-side pg_stat_ssl false for that hop; pooler-to-database protection remains unverified |
| Final DB-owner/security change approval | **UNVERIFIED** | No permission-change window or production migration has been authorized |

## Phase 1D preparation checkpoint

See the [Phase 1D runbook](PHASE_1D_SECURE_PRODUCTION_PREPARATION.md) for source
paths, manual commands, evidence limits and the complete ordered checklist.

| Preparation item | Result | Bounded conclusion |
| --- | --- | --- |
| Data API dependency/source compatibility | **PASS** | Inspected clients use FastAPI; backend uses native PostgreSQL; no Supabase SDK/REST/GraphQL use found in source/manifests |
| External/deployed Data API dependency clearance | **UNVERIFIED** | Owner inventory and effective deployed API origins still required before approved disablement |
| Local production connection role | **PASS** | Parsed postgres/session-pooler configuration; .env.supabase is not automatically loaded by Settings and does not attest Render |
| Encrypted synthetic recovery preparation | **PASS** | PostgreSQL 17.11/CMS AES-256-GCM drill, negative decryption checks and full fixture metadata/history comparisons; no live archive |
| Real application recovery capability | **UNVERIFIED** | No approved live recovery point or real protected restore/media drill; Free-plan managed recovery remains unavailable |
| Marker migration / initial issuance-off checks | **PASS** | Additive migration reviewed; temporary SQLite preservation check and 22 isolated rollout/model tests passed on Python 3.14.1 |
| Explicit initial Render flags / release-image acceptance | **UNVERIFIED** | Runtime unavailable; issuance/legacy flags unset in local production file; Python 3.12 role-specific acceptance still required |
| Live remediation actions | **UNVERIFIED** | Data API toggle, ACL/RLS SQL, marker migration, rotations and every deployment remain separately unapproved/unexecuted |

The permission SQL guard still requires a1b2c3d4e5f6; its approved application
must precede d7e8f9012abc or undergo renewed review/rehearsal. No guard was changed.

The existing SQL-permission defect is confirmed by the preserved audit and
configured hosted exposure is now established. Hosted HTTP denial and actual
Render compatibility remain unverified. Do not approve the
change on the basis of a local owner-role test or an HTTP 401 without a valid key.

## Authorized dashboard observations and current access boundary

The signed-in dashboard now exposes the project settings needed for this review.
The General page identifies organization Bunvathana876, project blue-panda-demo
and branch main PRODUCTION. Its Project ID equals the reference in its dashboard
URL. A 64-bit FNV-1a fingerprint of that non-secret identifier matched one computed
in memory from backend/.env.supabase's pooler-username suffix. Raw identifiers,
connection strings and private URLs were not emitted or saved. This binds the
reviewed target to the visible dashboard project; it does not identify Render's
runtime connection or turn a project named demo into a production-ready service.

At 12:45 UTC, **Integrations → Data API → Overview** showed Enable Data API on.
In Settings, Select schemas showed selected graphql_public/public. Select tables
showed selected public.users, public.user_sessions and public.refresh_tokens
among the listed public tables. Automatically expose new tables was on; Extra
search path showed public/extensions. Only selectors were opened to read metadata;
no selection was changed and Save remained disabled after inspection. No API key,
Table Editor, authentication records, request playground or row response was used.

GraphQL's integration page offered Install integration and named pg_graphql as
required. **Database → Extensions** showed pg_graphql off, available version 1.6.2,
and Install extension to use GraphiQL at 12:47:56 UTC. The standard extension path
is inactive. graphql_public being selected as an exposed schema does not activate
the absent extension. Custom/external GraphQL services and valid-role HTTP denial
remain unverified; no GraphiQL query or extension installation was attempted.

**Database → Backups** showed Free-plan restrictions: Scheduled backups says the
Free plan does not include project backups; Point in time offers a Pro add-on;
Restore to new project requires Pro or above and physical backups. No backup ID,
retention window or PITR recovery range was available through these pages. This
fails managed-recovery readiness, while offsite/manual backup existence remains
UNVERIFIED. Nothing was downloaded, restored, enabled or upgraded.

Render's dashboard opened a Sign in page. Per the user's restriction, inspection
stopped without typing credentials, choosing an identity provider, registering an
SSH key or proceeding through authentication. Supabase dashboard access does not
grant Render access. Each Render instance's role/target/commit remains UNVERIFIED.

The existing [Render probe](phase_1c_security/render_identity_probe.py) was reread
and syntax-checked, not edited or executed. Its safe operator procedure and
limitations are documented below. The earlier rehearsal was not repeated because
no runner or SQL behavior changed; both successful evidence files and hashes were
verified instead.

## Previous access boundary and evidence still required

The following records the earlier blocked continuation. The latest Supabase
dashboard observations above supersede its Supabase identity/settings/backup
availability gaps; Render remains blocked.

Supabase and Render plugin discovery again returned `installed: false`; both were
already suggested earlier, so no duplicate suggestion or connection was made.
No Supabase/Render management CLI or management token was present in the process
or named project environment files. Only key names/presence booleans were emitted;
no credentials, browser credential stores or unrelated files were searched.
The browser-control host was unavailable. Native Chrome navigation to the public
Supabase dashboard entry redirected to GitHub device verification. No code was
entered, resent or retrieved, no additional sign-in step was taken, and no project
dashboard metadata was reached. Remote access attempts stopped at that boundary.
Render instance count, plan, project binding and runtime role therefore remain
unknown; no Render shell/probe execution is claimed.

The owner can close these read-only evidence gaps using the procedures below,
after handling private access themselves or providing an authorized connection:

| Required sanitized evidence | Current result | Minimum record |
| --- | --- | --- |
| Supabase project identity | **UNVERIFIED** | Operator/UTC, intended organization/project confirmed, dashboard Reference ID matches reviewed private connection: yes/no |
| REST/Data API exposure | **UNVERIFIED** | Enable Data API, public in exposed schemas, users/user_sessions/refresh_tokens exposure, automatic exposure state; metadata only |
| GraphQL | **UNVERIFIED** | GraphQL integration state, pg_graphql status/version, relevant role search_path and schema/table grants, existing schema visibility evidence without selecting collections |
| Every active Render API instance | **UNVERIFIED** | Service/live commit, active-instance inventory and one prepared read-only probe output per selected running instance; no invented instance count |
| Backup/PITR | **UNVERIFIED** | Available recovery-point IDs/timestamps/status, retention, earliest/latest PITR times/timezone, plan and restore-target capabilities |

Do not paste secrets, full URLs, authentication rows or screenshots containing
keys into this record. Retain the private identifier binding with the owner and
record only sanitized results. If metadata is inaccessible, leave UNVERIFIED;
do not infer safety from login redirects, missing keys or disabled introspection.

## Backend compatibility comparison

Source review of `backend/app/db/database.py` confirms direct SQLAlchemy
connections using the configured URL; no SET ROLE was found there or in the
reviewed auth service/dependency modules. This is local source evidence, not the
deployed commit. The prepared Render probe is unchanged and syntax-valid; it
reads revision and role/privilege metadata in a bounded read-only transaction,
does not import application startup and does not query authentication rows.
Its instance-ID-present boolean does not enumerate or independently bind every
instance: retain the Shell instance selection and active inventory separately.

| Effective running role, once verified | Expected effect of proposed SQL | Compatibility result now |
| --- | --- | --- |
| postgres owner/BYPASSRLS, matching isolated fixture | Owner rights retained; non-FORCE RLS bypassed; fixture CRUD succeeded | **PASS** for simulated role only; actual Render role **UNVERIFIED** |
| Other owner-equivalent role with effective inherited ownership | Could retain access, subject to actual membership/inheritance and schema/sequence rights | **UNVERIFIED**; reproduce exact role on isolated 17 |
| service_role or role relying on its revoked grants | BYPASSRLS does not grant table/sequence privileges; proposed SQL removes its access | **FAIL** if this is the required backend capability path; actual use **UNVERIFIED** |
| Non-owner/NOBYPASSRLS ordinary role | Policyless RLS blocks row access even with otherwise sufficient table grants | **FAIL** if required to serve auth operations; actual use **UNVERIFIED** |
| Separate BYPASSRLS role with retained independent grants | Requires schema USAGE, required CRUD and sequence rights after revocation | **UNVERIFIED** until exact-role isolated acceptance |

For each verified running role, compare the probe's SELECT/INSERT/UPDATE/DELETE,
sequence USAGE, schema USAGE, ownership/membership and BYPASSRLS evidence with the
post-change state. Reproduce attributes/grants/membership in disposable 17 and
complete approved Python 3.12 application acceptance using synthetic accounts.
Current simulated CRUD includes SELECT/UPDATE/DELETE on all three tables and an
INSERT/sequence use on users; it is not full login/session/refresh acceptance.
Keep the separately reviewed legacy-marker migration outside this permission-only
test. Do not restore browser-facing grants or grant BYPASSRLS as an ad hoc fix.

## GraphQL exposure review

The preserved 11:02:38 UTC catalog evidence lists pgcrypto but no pg_graphql,
public functions or dependent views. It is historical and tied to the connection
whose independent Blue Panda project identity was then UNVERIFIED. The latest
dashboard review now verifies that target binding and pg_graphql off. The
historical snapshot alone did not establish the hosted configuration. No GraphQL row request,
introspection request or authentication collection query was issued here.

Supabase documents GraphQL schema visibility through PostgreSQL permissions and
search_path; SELECT/INSERT/UPDATE/DELETE privileges affect exposed operations.
RLS governs rows. Disabling introspection does not disable queries or mutations.
Therefore the proposed grant revocations would remove these tables' GraphQL
entrypoints for those roles, assuming the verified target and standard pg_graphql
path. This is a documented inference, not observed hosted denial.
[GraphQL visibility](https://supabase.com/docs/guides/graphql),
[GraphQL security](https://supabase.com/docs/guides/graphql/security).

The owner should inspect integration/extension and existing schema metadata
without enabling extensions or introspection. Check all three sensitive table
names and role-specific paths, including wrappers/custom resolvers if present.
An empty schema explorer with introspection disabled is insufficient evidence.
Any further valid-role metadata/zero-row HTTP acceptance needs verified project
identity and authorized credentials; do not reuse the FastAPI JWT or service key.

## Fresh investigation and evidence boundaries

This section preserves the earlier 11:02:38 UTC audit; it is not a new live audit
from the remaining-gates continuation.

[release_gate_evidence.json](phase_1c_security/release_gate_evidence.json) preserves
the new catalog snapshot separately from historical evidence. The audit used
repeatable-read/read-only transactions, default read-only connection settings,
10-second statement and 2-second lock timeouts, then rollback. Its first
application-schema read checked the revision. Six role-switched SELECT 1 LIMIT 0
probes succeeded with no application rows returned. No user, password-hash,
refresh-hash, bearer, or sequence-value query was issued.

Owner postgres is non-superuser/BYPASSRLS and owns these objects. Both anon and
authenticated have effective SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES,
TRIGGER and MAINTAIN. Their sequence ACLs include USAGE, SELECT and UPDATE. No
column-specific ACLs or policies were found, no functions exist in public, and
no dependent views/materialized views were found. The inspected PostgREST schema
settings are unset in the SQL-visible locations; its process environment is not
visible from that connection. pg_graphql is not installed.

Fresh keyless HEAD requests to REST and GraphQL each returned 401. These reached
the gateway and did not establish that either API is enabled or exposes public.
No network request selected even a zero-row authentication-table response via HTTP.

Supabase and Render integrations were discovered but are **not installed or
connected** in this session. Browser inventory again reported its access host
unavailable. No relevant Render/Supabase management tokens or CLI executables
were available in the inspected environment. A safe configuration-key inventory
found no such credentials in the existing project environment files. No browser
credential store, unrelated user files or backup contents were searched.

Root/backend default environment files are different connection targets from
backend/.env.supabase. Values remain private and unchanged. This reinforces why
neither local defaults nor the fresh owner connection can attest Render's binding.

## Exact safe Supabase UI steps

Use the owner's existing signed-in Supabase dashboard. Do not change a toggle,
save settings, reveal keys, open authentication users/table rows, or run migrations.

1. Select the organization and production project intended for Blue Panda.
   Open **Project Settings → General → Project Settings → Reference ID**.
   Privately compare it to the suffix of the username in backend/.env.supabase's
   session-pooler URL. Also compare it to the project reference shown by the
   dashboard project URL. Record only `organization/project confirmed: yes/no`
   and `reference matches reviewed connection: yes/no`, plus operator and UTC time.
   [Supabase project-reference location](https://supabase.com/docs/guides/graphql)
2. Open **Integrations → Data API → Overview**. Read **Enable Data API** without
   toggling it. If the layout routes settings through **Project Settings → API /
   Data API**, follow that settings link. Read **Exposed schemas** and whether
   public is included. Inspect **Exposed tables** metadata for users, user_sessions
   and refresh_tokens; do not use Table Editor or any request/playground action.
   Record enabled yes/no, public exposed yes/no, and the three names' listed state.
   Do not infer safety from an empty UI list if settings or permissions are unclear.
   [Data API controls](https://supabase.com/docs/guides/api/securing-your-api),
   [exposed-schema setting](https://supabase.com/docs/guides/api/using-custom-schemas)
3. Read **Automatically expose new tables**, if present. Record its state; do not
   change it. Check the GraphQL integration status separately. No pg_graphql
   extension was observed, but that does not verify the hosted configuration.
4. If Data API is enabled, public is exposed, and the three tables are listed,
   mark hosted access-control protection **FAIL** given the confirmed grants/no
   RLS. This conclusion requires no sensitive row retrieval. If the API is off or
   public is absent, record the bounded route exclusion as verified; the database
   grant defect still requires remediation and must not be reported fixed.

Settings names can vary across dashboard layouts; the documented Data API
integration is the destination. Do not substitute Supabase Auth settings for
Data API schema exposure.

## Exact safe Render UI/runtime steps

1. Open the intended Render workspace, production environment and **Blue Panda
   backend** service. Confirm the service's public origin, repository/root and
   currently live deployment commit, not merely the latest successful build.
   Privately record the service ID and active instance selection for audit.
2. Open **Environment**. Privately compare the effective DATABASE_URL project
   reference/connection mode with the independently verified Supabase project.
   Include linked environment groups and secret-file or start-command overrides
   in the review. Do not copy the URL into chat, logs, command arguments or this
   report. Do not edit, save, restart, redeploy or select a deploy action.
   [Render environment configuration](https://render.com/docs/configure-environment-variables)
3. Open **Shell** for an existing running instance. If scaled, choose each active
   instance in the **Instance** dropdown. Do not create an ephemeral instance,
   upgrade the plan, install packages or deploy a diagnostic endpoint. Free web
   services do not provide Shell/SSH; if unavailable, keep runtime proof
   UNVERIFIED and obtain equivalent existing operational evidence through the owner.
   [Render Shell access and plan support](https://render.com/docs/ssh)
4. Inspect the prepared [render_identity_probe.py](phase_1c_security/render_identity_probe.py).
   In the running Shell, execute its complete source through Python stdin:

   ```sh
   python - --expected-project-ref EXPECTED_PROJECT_REF --expected-service-id EXPECTED_SERVICE_ID <<'PY'
   # Paste the complete contents of render_identity_probe.py here.
   PY
   ```

   Replace the two placeholders with the privately verified non-secret identifiers.
   No password/token/connection string is pasted into this command. This code uses
   runtime DATABASE_URL in memory, imports no application/settings/startup module,
   refuses a mismatched service/project or URL routing override, enforces a read-only
   bounded connection, checks revision first, and rolls back. Run it once per
   active instance. It does not change a user's record or password. No dependency
   installation is necessary if the deployed runtime matches the reviewed stack.
5. Retain only sanitized output: matching booleans, deployed commit, effective
   current_user/session_user, role flags, owner memberships, required table and
   sequence privileges, version and TLS boolean. Never run printenv, echo the
   URL, enable shell tracing, import app.main or use a live login to identify the
   role. Compare the output commit against the selected live deployment and
   inspect that deployed source for connection hooks/SET ROLE changes.

Before execution, have the owner privately review libpq routing inputs such as
PGHOSTADDR, PGSERVICE, PGSERVICEFILE and PGOPTIONS, and any effective environment
group/secret-file overrides. The probe guards URL query overrides but does not
audit every inherited libpq environment input. Do not print their values, silently
clear them or change runtime configuration; unresolved routing requires a stop.
The TLS default is require, which establishes encrypted transport, not independent
certificate/project attestation. Retain the dashboard/project binding and service
provenance as separate evidence.

Require each successful probe result to have expected project/service matches,
the selected live deployment commit, instance_id_present true, read_only on,
REPEATABLE READ, expected revision a1b2c3d4e5f6, expected server major, TLS true and
exactly three table records. Check every required schema/CRUD/sequence flag and
owner/membership/BYPASSRLS condition, not just a successful connection. Missing,
null or mismatched fields keep the gate UNVERIFIED; stop on revision/target drift.
Do not retry with weaker TLS, run migrations or use a production login to repair
a failing probe.

The probe creates a new connection from that instance's DATABASE_URL. It does
not inspect an already pooled FastAPI connection or execute application connection
hooks. Compare the actual deployed engine/session code for SET ROLE/hooks before
treating that result as the application's effective role. Its instance-ID boolean
is insufficient to establish coverage: privately label the selected Shell instance
for each sanitized result and reconcile against the full active-instance list.
If the owner cannot provide an existing supported Shell/SSH session, leave live
role proof UNVERIFIED; do not deploy a diagnostic, create an instance, add access
keys or upgrade a service under this request.

Current result: Render Sign in is the authentication blocker. The owner must
complete private authentication themselves or supply an already authorized
read-only session/sanitized per-instance evidence. The current user request
already authorizes the bounded read-only probe once that access exists; it does
not authorize expanding account access or altering the service.

The probe is prepared and locally validated for early target rejection, **not
executed on Render**. Source review shows FastAPI connects directly with
SQLAlchemy/psycopg2 and does not SET ROLE per customer. A matching effective
postgres owner/BYPASSRLS role is expected to retain the needed capabilities, but
that expectation does not close the live-role or role-specific staging gate.

## Historical PostgreSQL 17 isolated rehearsal results

The user explicitly approved the official image pull and disposable testing in
this continuation, satisfying the dependency rule in [AGENTS.md](../../AGENTS.md).
No application dependency was installed or upgraded. The executed pull and first
runner invocation were:

```sh
rtk docker pull postgres:17-alpine
rtk proxy python3 docs/upgrade/phase_1c_security/rehearse_postgres17.py
```

Identity evidence from pull and `docker image inspect`:

- Official registry/repository: `docker.io/library/postgres:17-alpine` (pull output:
  `Pulling from library/postgres`).
- RepoDigest: `postgres@sha256:3540c0362c809df084ffac0ae69fe794515f9de92692f02178bcdce0ef0302ac`.
- Inspected local image ID, also used to start the runner's container:
  `sha256:3540c0362c809df084ffac0ae69fe794515f9de92692f02178bcdce0ef0302ac`.
- Platform: `linux/arm64`. The isolated SQL server reported `17.11`; its
  `server_version_num` passed the runner's major-17 assertion. This verifies the
  pulled repository/digest and running version, not a separate signature audit.

The first direct invocation **FAIL**ed at `docker cp`: the daemon reported
`Could not find the file /tmp/security` despite the directory having been made
inside the container's tmpfs. It had already passed readiness, isolation, cluster
identity, data-directory, disabled-TCP and major-version checks; no fixture or
permission SQL had yet run. Its finally block removed container
`bp-security-pg17-b0719c6aee3a`.

To preserve repository files, the retry used a temporary Docker CLI adapter under
the host temporary directory. Only copies of the six reviewed SQL filenames and
the runner's temporary `apply_failure.sql` to its uniquely named test container's
`/tmp/security/` were adapted. Each source's unchanged bytes were sent over stdin
to `docker exec -i CONTAINER sh -c 'cat > "$1"' -- /tmp/security/FILE.sql`.
All other Docker commands passed through to the real CLI. The original Python
runner was invoked unchanged with the adapter first on PATH; its source, SQL and
production guards were not edited. The adapter was removed automatically.
Direct-runner Docker-copy portability was **FAIL** in this historical run;
the completed SQL assertions below were **PASS** through this documented adapter.
The fixed direct retest below now closes that portability failure.

The retry exited 0 at **2026-11-07 11:24:24.372932 UTC**. Independent live
inspection of container `bp-security-pg17-41aa9f84ddf1` confirmed network `none`,
read-only root, auto-remove, no published ports/bind mounts/volume mounts, and
tmpfs at `/var/lib/postgresql/data`, `/var/run/postgresql` and `/tmp`. The runner
also verified its unique cluster name, expected data directory and disabled TCP.
Only synthetic tables/rows at revision `a1b2c3d4e5f6` were used; no production URL,
environment file, real account, password hash or token was consumed.

| Test | Result | Observed evidence |
| --- | --- | --- |
| Official image pull, identity and major version | **PASS** | Registry/digest/image identity above; server 17.11 |
| Container isolation | **PASS** | Network none, TCP disabled, no host mounts/ports/persistent volumes; tmpfs data |
| Historical direct runner SQL-copy portability | **FAIL** | Initial docker cp failed before fixture setup; adapter enabled historical retry; fixed direct retest below supersedes current portability status |
| Missing approval refusal | **PASS** | Apply rejected; ACL/RLS snapshot unchanged |
| Revision-drift refusal | **PASS** | Unexpected synthetic revision rejected; ACL/RLS unchanged |
| Lock-contention failure | **PASS** | Script configured 2s lock timeout; SQLSTATE 55P03; ACL/RLS unchanged |
| Failure after ACL/RLS changes | **PASS** | Temporary injected division-by-zero yielded 22012; complete transaction rolled back |
| Unchanged apply and API-role denial | **PASS** | 45 cases: three roles × three tables × SELECT/EXPLAIN SELECT/INSERT/UPDATE/DELETE; writes only planned, not executed |
| Effective privileges and RLS flags | **PASS** | All eight table, four column and three sequence privilege types denied for each API role/object; RLS enabled without FORCE |
| Defense after accidental SELECT regrant | **PASS** | anon saw zero rows from populated users fixture; SELECT regrant then removed |
| Simulated backend owner access | **PASS** | Non-superuser postgres owner/BYPASSRLS SELECT/UPDATE/DELETE on all three tables and users INSERT/sequence use succeeded inside rolled-back transaction |
| Repeated apply safety | **PASS** | Applying to already-remediated state rejected; ACL/RLS unchanged |
| SQL rollback | **PASS** | Exact table/sequence ACL and table RLS flags restored to fixture baseline |
| Fixture history retention | **PASS** | Revoked session and consumed/revoked refresh-token fixture rows retained after rollback and reapply |
| Reapplication | **PASS** | Apply, privilege assertions and all 45 denial cases passed again |
| Container cleanup | **PASS** | Both uniquely named test containers absent after execution; no test containers remain |
| Existing data/resource preservation | **PASS** | Same 13 existing containers and 63 volumes; 609 workspace-file hashes unchanged before this report edit; 20 protected SQL/runner/migration/configuration hashes unchanged |
| Actual Render role and application authentication | **UNVERIFIED** | Synthetic owner SQL capability only; no running Render probe or Python 3.12 FastAPI acceptance |
| Hosted Supabase exposure/HTTP denial | **UNVERIFIED** | No hosted connection/request or dashboard access in this continuation |
| Backup recovery | **UNVERIFIED** | No backup/export/restore executed |

Preservation compares container IDs, images, running states and mount sets (mount
order normalized), plus volume names; it does not read/hash live database contents.
Existing databases were never addressed by the test commands. The approved image
remains cached; no existing image, container, volume or file was removed. After
the report update, this document is the only intended changed repository file.

The runner recorded these reviewed artifact SHA-256 values:

```text
apply.sql            81f98bb0e9223a52d5b33204e3e21af70f0ee51e3d7b28d020a21e761de499f7
rollback.sql         a300599bfa3172ca605efb69b34468f5b9ae3d3a4b44fcc7cd6ac487e5c1f1dc
target_guard.sql     5c0100eff4164531734eda5f6be985e8deb034dfe1cddb79825571d3c197b54a
deny_assertions.sql  3b51662a64ad2576f949b8feaf1ba18f8c21b7724149fa506eb6a0ff08143aec
verify.sql           24e400f01a7c81a9b7afaaf1c4892c89c8d5ee8e019e22698268dd5b27073400
inspect.sql          21753a1f611bee31fa7bab3bb53a504e75795a7d5157bbc38a77adde234e43bd
```

This successful run proves engine/SQL behavior for its fixture role only.
It does not prove Render's actual role or FastAPI login/session functionality.
After runtime identity is verified, reproduce that role's relevant attributes,
memberships/grants/policies on independently isolated 17 and run the approved
Python 3.12 application acceptance. If it is a non-owner/NOBYPASSRLS role with no
applicable policy, the proposed policyless RLS blocks it: stop and review a
backend-only policy rather than restoring browser-role grants. The current
session-aware code also requires the separately reviewed legacy-marker migration;
do not silently add that migration to this permission-only rehearsal or production.

No new login/password mutation tests were run. The earlier 412-test/18.6 results
remain historical evidence. Any future account-mutating acceptance must use
disposable synthetic fixtures under its own authorized scope; current production
accounts and passwords remain untouched.

## Fixed direct PostgreSQL 17 retest

The original successful output is preserved byte-for-byte in
[postgres17_20261107_adapter_evidence.json](phase_1c_security/postgres17_20261107_adapter_evidence.json).
The new output is separate:
[postgres17_20261107_direct_evidence.json](phase_1c_security/postgres17_20261107_direct_evidence.json).
Existing catalog/historical JSON and all six SQL artifacts remain unchanged.

The focused runner change replaces both Docker archive-copy calls with stdin
writes through exec into the existing isolated tmpfs directory. It checks each
destination SHA-256 against its source bytes, including the temporary injected
failure file. Fixture SQL, reviewed SQL files, SQL transactions/guards, role
assertions, isolation settings and cleanup behavior were not changed.

Reproduction from the repository root (cached approved image required; no pull):

```sh
rtk proxy python3 docs/upgrade/phase_1c_security/rehearse_postgres17.py
rtk docker ps -a --filter name=bp-security-pg17- --format '{{.Names}}'
```

Require exit 0, server 17.11/major 17, the seven copied files in
`sql_files_verified`, all nine checks and matching historical SQL hashes. The
second command should return no names when no other rehearsal is active.
Executed directly without any PATH adapter: exit 0 at 12:27:04.712899 UTC;
same official image ID/digest and same nine successful checks as the historical
run, including all 45 role/statement denials after apply and reapply.
No new image was pulled. The test container was auto-removed; this continuation's
12 pre-existing container identities/images/running states/mount sets and all 63
volume names were unchanged. The earlier run's 13-container inventory remains
historical and was not substituted for the new baseline.

## Hosted denial acceptance

The existing [HTTP test runner](phase_1c_security/data_api_negative_tests.py) remains
unchanged. A future owner-approved valid-role test must use a verified public
project origin, publishable/anon key and an existing Supabase authenticated
credential, never a FastAPI JWT or service key. Metadata controls must establish
valid credentials first. Table probes use select=id&limit=0 and never return rows.
Require the permission-denied or hidden-table statuses/codes specified in the
remediation plan. A 401 from a missing/invalid key is not a passing negative test.

With the current unremediated grants, an authorized zero-row probe may succeed;
that is a failed protection gate and must not be escalated to a row read. Do not
run POST/PATCH/DELETE/TRUNCATE against production for negative coverage. SQL-role
denial on isolated 17 and hosted HTTP denial are different evidence requirements.

## Backup and recovery review

Current dashboard result: **FAIL** for managed backup/PITR and managed
restore-to-new-project readiness on this Free-plan project. The three backup tabs
show the paid-plan/physical-backup prerequisites described above, with no usable
managed recovery point. **UNVERIFIED** remains the result for an independently
recoverable offsite/manual backup and any actual isolated restore acceptance.
The procedures below describe the evidence to obtain after the owner chooses
and separately approves a recovery path; they are not a claim that one exists.

Read-only owner UI steps: open **Database → Backups** in the verified Supabase
project. Record actual available backup IDs/timestamps/status, retention and
whether PITR is enabled; if enabled, read the earliest/latest recovery points
and timezone. Do not enable/disable PITR, download/export or click Restore/Start
a restore. Confirm plan capabilities rather than assuming them. Database backups
exclude Storage object payloads; custom-role password recovery also needs a
separate procedure. [Supabase backup documentation](https://supabase.com/docs/guides/platform/backups)

Approval requires: a recoverable point immediately before the window; acceptable
RPO/RTO and measured restore evidence; named data custodian; encrypted storage,
key custody/access/retention; separate media recovery; preserved owner/ACL/policy/
role/default-grant metadata; and a separately approved isolated restore target.
No backup was read or exported here and no managed restore capability was verified.

The existing backup helper passes DATABASE_URL in argv, makes encryption optional,
omits ownership/privileges and prunes older files. The restore helper uses a
name-only guard, DROP/CREATE and psql without ON_ERROR_STOP. Both were inspected,
preserved and **not executed**. They are not approved shortcuts for this window.

Fresh source review confirms these helper limitations. The restore helper also
uses application-table counts rather than establishing ACL/RLS/role recovery;
it was not run, and no backup was decoded or restored. The synthetic permission
rollback rehearsal is not evidence that an actual backup can be restored.

An isolated restore is technically a future option, not yet approved or proven
available for this project. Supabase's documented Restore to a New Project
requires a paid plan and physical backups, creates a separately billed project,
and copies the database while leaving service/media configuration to review.
Its binary restore can start copied external jobs immediately; a new project
alone does not establish safe isolation. Review jobs, wrappers and outbound
effects before approving that path. A controlled logical restore to a separately
isolated target may be appropriate where its limitations are accepted.
[Restore-to-new-project capabilities and limits](https://supabase.com/docs/guides/platform/clone-project).

Before a real recovery drill, the owner must approve sensitive backup handling
and the exact target/budget, encryption/key custody, network isolation and blocked
outbound integrations, plus metadata-only validation scope. Record measured
recovery time and a demonstrated recovery point; compare revision, schema,
ownership/ACL/RLS/policies, roles/default grants and required indexes/constraints
without retrieving authentication rows. Include media recovery and custom-role
credential recovery separately. Do not create, restore or delete a project,
download an export, run the legacy helper or inspect authentication rows under
this verification request. Backup readiness remains **UNVERIFIED**.

Prefer transaction rollback before commit or a targeted forward fix after commit.
The prepared SQL rollback reopens the observed vulnerability: isolate externally
exposed APIs and obtain separate DB-owner/security approval first. It only applies
at the exact reviewed revision/state; never restore an old database merely to undo
permissions, because that can discard newer revocations and refresh replay history.

## Final approval checklist — exact remaining blockers

- [x] Signed-in dashboard identifies the reviewed Supabase organization/project
  and matching reference binding; raw reference/private URLs omitted.
- [x] Data API/public/three-table exposure, automatic exposure and standard
  GraphQL integration/extension states recorded from the verified dashboard.
- [ ] Every active Render instance is tied to its live commit and effective DB
  role/project; role-specific PostgreSQL 17/Python 3.12 acceptance demonstrates
  required application access after the permission change.
- [x] Official PostgreSQL 17 test-image pull approved; isolated apply, denial,
  timeout/failure rollback, exact ACL/RLS restoration and reapply passed on 17.11
  historically with an adapter and now directly with the fixed runner. This is
  not backup-recovery proof.
- [x] Preserve historical rehearsal evidence, fix Docker copy without changing
  SQL behavior and retest directly with copied-byte verification.
- [x] Verify current standard GraphQL configuration: pg_graphql off and integration
  not installed; no denial claim relies on disabled introspection.
- [ ] Inventory custom/external GraphQL and service_role consumers before assuming
  the standard extension state covers every access path.
- [ ] Hosted valid-role zero-row tests have trusted controls; planned post-change
  denial acceptance is agreed. No missing-key response is counted as proof.
- [ ] External service_role consumers are inventoried and found compatible with
  its scoped grant removal; no browser-facing role receives an exception.
- [ ] Managed backup/PITR and required protected restore evidence satisfy RPO/RTO;
  custodian, metadata/media recovery and separate restore authorization are named.
- [ ] Supabase pooler-to-database transport assurance is privately resolved.
- [x] Identify earlier output's exposed credential categories and prepare the
  [safe rotation checklist](phase_1c_security/CREDENTIAL_ROTATION_CHECKLIST.md).
- [ ] Owner verifies actual credential consumers/production reuse and separately
  approves any required secret rotation, runtime configuration and deployment/
  restart/session-revocation actions; none are authorized by this report.
- [ ] DB-owner/security approvers approve exact reviewed SQL/artifact hashes,
  target, window, bounded lock budget, observer, rollback/forward-fix criteria
  and verification. Runtime/default-ACL/API configuration changes remain separate.

## Exact approvals still needed before production remediation

No production-remediation permission follows from this evidence review. The
Supabase read-only review is complete within its stated scope; Render private
authentication must be completed by the owner before the already-authorized
bounded probe can run.

1. **Recovery:** owner/custodian approves the exact recovery source and recovery
   target, sensitive-data handling, encryption/key custody, RPO/RTO, isolation,
   outbound-job controls and restore validation. An export or restore is a separate
   action. Any paid-plan/PITR/new-project purchase also needs explicit cost approval;
   a Free-plan upsell is not approval and no upgrade was made here.
2. **Permissions:** after per-instance role-specific isolated acceptance and
   recoverability evidence, DB owner/security approvers authorize the exact
   reviewed SQL hashes, verified target, table/sequence scope, window, observer,
   lock budget, success checks and rollback/forward-fix criteria. Emergency rollback
   reopens the vulnerability and needs its own approval and exposure controls.
3. **API configuration:** any disabling of Data API, schema/table exposure change,
   default-grant change, GraphQL installation/toggle or backend-only policy design
   is separately scoped and approved. None was changed in this review.
4. **Credentials/runtime:** approve affected consumer IDs, each credential category,
   protected rotation mechanism and cutover window. Separately approve configuration
   updates, pool refresh/restart/deployment and JWT/session invalidation as required.
   Confirmed local configuration reuse does not authorize changes on Supabase/Render.
   Follow the [rotation sequence](phase_1c_security/CREDENTIAL_ROTATION_CHECKLIST.md).
5. **Other changes:** any production migration, deployment, commit or push remains
   prohibited until explicitly requested and separately reviewed. The current
   permission-only plan does not authorize the legacy-marker migration.

**Do not apply permissions, migrations, deployments, account changes or Git
operations on the basis of this report. FAIL/UNVERIFIED gates remain open.**

## Files and checks from the previous runner-fix continuation

| File | Why changed |
| --- | --- |
| PHASE_1C_SECURITY_RELEASE_GATES.md | Current gate results, explicit private-access boundary, compatibility/GraphQL/recovery review and approval requirements |
| phase_1c_security/rehearse_postgres17.py | Replace Docker archive copy with exec/stdin transfer and verify copied bytes; no SQL behavior change |
| phase_1c_security/postgres17_20261107_adapter_evidence.json | Preserve the earlier successful output byte-for-byte |
| phase_1c_security/postgres17_20261107_direct_evidence.json | Record the successful fixed direct run separately |
| phase_1c_security/CREDENTIAL_ROTATION_CHECKLIST.md | Redacted exposure assessment and unexecuted owner-operated rotation plan |

Direct PostgreSQL 17.11 execution passed all nine checks and copied-file hashes;
Python syntax and preservation checks passed. Final verification checks report
and runner diffs, whitespace, local links, evidence consistency, unchanged SQL and
unrelated files, existing Docker inventory and test-container cleanup. Diff
inspection is limited to intended files or captured without emitting unrelated
configuration; no credential values are reproduced in this continuation.
Application/backend/web/mobile suites were not run because application code did
not change. No production account/session/password-hash rows were retrieved.
The hosted probe and restore drill were not run: private access, owner metadata
and separate restore authorization are missing. The access stop follows the
user's explicit restriction, not an inferred requirement from a skill.
No production remediation is authorized by these results.

## Files and checks from this private review

- `PHASE_1C_SECURITY_RELEASE_GATES.md`: current dashboard results, probe review,
  access boundary, remaining compatibility/recovery gates and exact approvals.
- `phase_1c_security/dashboard_evidence_20261107.json`: new sanitized settings and
  plan observations; no private URL, reference, key, password, token or row payload.
- `phase_1c_security/CREDENTIAL_ROTATION_CHECKLIST.md`: confirmed local pgAdmin/JWT
  configuration reuse and ordered owner-operated rotation sequence.

All existing SQL, probe/runner code, successful PostgreSQL JSON, migrations and
environment files were preserved. No runtime test was repeated because behavior
did not change. Evidence/SQL hashes, probe syntax, intended diffs, Markdown links,
whitespace and unchanged-file checks are verified at handoff. Application suites,
Render probe, production SQL and backup/restore execution were not run: application
code is unchanged and the remaining private-access/recovery conditions are unmet.
No credentials or private URLs were printed in this review. Read-only dashboard
navigation, metadata-only local comparisons and documentation updates exhaust
the actions taken; no settings, data, containers, volumes or services were modified.
