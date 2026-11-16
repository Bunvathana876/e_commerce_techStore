# Phase 1D secure production preparation

Date: 2026-11-07. **HOLD — preparation and synthetic testing only.**
Read with the [Phase 1C gates](PHASE_1C_SECURITY_RELEASE_GATES.md),
[permission plan](PHASE_1C_SECURITY_REMEDIATION_PLAN.md), and
[authentication checklist](PHASE_1C_AUTH_RELEASE_CHECKLIST.md).
No live export, restore, configuration change, migration, deployment, rotation,
commit or push is authorized by this document. Existing evidence is historical,
not a new assertion about Render's current runtime.
The [sanitized test record](phase_1d/recovery_evidence.json) retains the final
PostgreSQL 17.11 recovery results and preparation artifact hashes separately from
the earlier evidence.

## Release status

| Gate | Result | Evidence / remaining condition |
| --- | --- | --- |
| In-repository Supabase HTTP/SDK dependency inspection | **PASS** | Storefront, Management, Flutter, FastAPI and legacy web inspected; no direct Supabase SDK/REST/GraphQL dependency found |
| Data API disablement compatible with inspected source | **PASS** | Clients use FastAPI JSON/bearer endpoints; FastAPI uses SQLAlchemy/psycopg2 PostgreSQL; Data API is a separate HTTP surface |
| Globally safe Data API disablement | **UNVERIFIED** | Owner must inventory external jobs/integrations and verify deployed API base URLs; no deployed configuration was read here |
| Data API containment applied | **UNVERIFIED** | Not performed; last dashboard evidence has Data API on and sensitive tables selected |
| Locally configured production login identified | **PASS** | backend/.env.supabase specifies postgres through the session pooler on 5432; no connection or secret output |
| Owner-role SQL compatibility | **PASS** | Preserved catalog and isolated 17.11 owner/BYPASSRLS rehearsal; actual Render role remains separate |
| Actual role/configuration on every Render instance | **UNVERIFIED** | Last access stopped at Sign in; active instance inventory/commit/role unavailable |
| Existing backup helpers suitable for this release | **FAIL** | URL in argv, optional unauthenticated CBC encryption/plaintext intermediate, owner/ACL omission, pruning, unsafe restore guard and no ON_ERROR_STOP |
| Encrypted recovery procedure and synthetic drill | **PASS** | New synthetic-only 17.11 drill passed encrypted archive/metadata recovery, wrong-key/tamper rejection and catalog/history checks; see recorded evidence |
| Actual production recovery point / isolated restore | **UNVERIFIED** | No live export or restore; Free-plan managed options remain unavailable per preserved dashboard evidence |
| Previously exposed credentials still used in local configuration | **FAIL** | Database, pgAdmin and JWT configuration reuse confirmed in Phase 1C; rotation not performed |
| Marker migration source and disposable SQLite check | **PASS** | Exact parent a1b2c3d4e5f6; nullable column/no backfill; fields and an existing marker retained |
| Issuance-off shipping behavior | **PASS** | 22 isolated rollout/model tests passed on Python 3.14.1; default issuance false, legacy acceptance true, null refresh |
| Explicit live issuance-off / initialization-off flags | **UNVERIFIED** | Relevant flags unset in local production file; Render overrides unavailable; require explicit reviewed runtime values |
| Matching PostgreSQL 17 / Python 3.12 migration and application acceptance | **UNVERIFIED** | Recovery drill uses PostgreSQL 17; local application tests use Python 3.14, not the required release image |
| Production change approvals | **UNVERIFIED** | Named scopes/windows/custodian/artifacts/rollback and execution approvals still required |

## Data API recommendation and source evidence

Recommend disabling Data API as separately approved containment **after** the owner
confirms no external consumer depends on it. The inspected applications do not.
This does not repair the underlying database grants or replace permission cleanup.

| Component | Inspected files / behavior |
| --- | --- |
| Storefront | src/lib/api.ts, src/lib/auth.ts, package.json: NEXT_PUBLIC_API_URL, fetch, FastAPI bearer/envelope contracts |
| Management | src/lib/api.ts, src/lib/config.ts, src/lib/auth.ts, package.json: FastAPI API base and bearer requests |
| Flutter | lib/core/constants/api_endpoints.dart, lib/core/network/api_client.dart, feature services, pubspec.yaml: http client and /api/v1 paths; API_URL/runtime host override |
| FastAPI | app/db/database.py, requirements.txt: synchronous SQLAlchemy/psycopg2 native PostgreSQL; no Supabase SDK or HTTP Data API transport |
| Legacy web-app | src/lib/api.ts and package.json: same backend HTTP pattern; included to avoid overlooking the legacy client |

Scans covered application source and dependency manifests. Backend maintenance
scripts mentioning Supabase use PostgreSQL SQLAlchemy connections/host validation,
not Data API calls. No inspected package manifest declares Supabase/PostgREST or
GraphQL clients. This is source evidence, not proof that a deployed environment
has the intended API_URL/NEXT_PUBLIC_API_URL. Check effective deployed origins,
external automation, API keys' consumers, custom domains and installed integrations
privately before changing the shared project's setting.

The existing FastAPI connection remains protocol-compatible when Data API is off:
it uses the PostgreSQL socket/pooler, not PostgREST. No DATABASE_URL, SQL role,
TCP endpoint or table grants need to change for that toggle. Actual availability
still depends on Render's real target, role, TLS and connection configuration.
Supabase documents disabling Data API for applications that do not use its data
endpoints. [Official Data API controls](https://supabase.com/docs/guides/api/securing-your-api)

### Exact future dashboard change and rollback

1. Obtain owner approval for the verified project, Data API-only scope, external
   consumer inventory, observer, window and rollback criteria. Privately verify
   the dashboard Project ID against the reviewed binding. Record metadata only.
2. Record current state: Data API on, selected schemas graphql_public/public,
   selected sensitive tables, automatic exposure on, GraphQL extension off.
   Do not reveal keys or visit authentication/table rows.
3. In **Integrations → Data API → Overview**, set **Enable Data API** off and
   select **Save**. If Project Settings → Data API redirects there, follow it.
   Do not select Harden Data API, change schemas/grants/default exposure or install
   GraphQL in the same action. **These steps are not executed by this preparation.**
4. Re-read the persisted switch state. Owner-approved status-only routing checks
   should confirm unavailable REST endpoints; no authentication-row retrieval.
   A keyless 401 alone is inconclusive. Verify existing FastAPI readiness, anonymous
   denials and staging flows; production login/logout writes need separate consent.
5. If an approved, inventoried consumer breaks, stop progression and investigate
   the exact dependency. A rollback is **Overview → Enable Data API on → Save**,
   followed by a persisted-state and approved consumer check. This restores the
   previous exposure and can reopen access to vulnerable tables. It requires
   separate owner/security approval and agreed external containment; do not
   automatically re-enable an insecure API merely because a generic check fails.
   Do not undo grants, restore a database, or enable pg_graphql as toggle rollback.

## Backend role and initial configuration

The local production connection is configured as `postgres` through Supabase's
session pooler, database postgres. This was parsed in memory without importing
settings/startup or opening a connection. Root/backend default environment files
are different targets; neither attests Render. The preserved live audit identifies
postgres as non-superuser, owner and BYPASSRLS. The prepared SQL revokes PUBLIC,
anon, authenticated and service_role rights on only the three auth tables/sequences
and enables non-FORCE, policyless RLS. It preserves owner rights; the matching
synthetic role passed. BYPASSRLS alone never supplies missing table privileges.

Settings automatically reads `.env`, not `.env.supabase`. The latter is a reviewed
connection file, not proof that a normally launched FastAPI process uses it. Root
.env declares development with initialization/seeding/startup migrations false;
backend/.env and backend/.env.supabase do not declare ENVIRONMENT. Before any
future job/import using the production connection, the owner must supply and
verify explicit production settings through the approved runtime mechanism.

If Render instead uses service_role-derived grants, the revocation breaks that
path. A non-owner/NOBYPASSRLS role is blocked by policyless RLS even with table
rights. Stop and review backend-only access/policies rather than restore browser
grants or grant BYPASSRLS without review.

Have the owner complete private Render sign-in. Use the unchanged
[read-only probe](phase_1c_security/render_identity_probe.py) and
[per-instance procedure](PHASE_1C_SECURITY_RELEASE_GATES.md#exact-safe-render-uiruntime-steps).
Record each existing instance, live commit, target match, effective role,
ownership/membership, schema/table/sequence privileges, TLS and revision. Review
deployed engine hooks and inherited libpq routing: the probe opens a new connection
from runtime configuration, not an existing FastAPI pool connection. Do not add
SSH keys, install dependencies, deploy a diagnostic or change runtime flags here.

Shipping code defaults: AUTH_ISSUE_SESSION_TOKENS=false,
AUTH_ACCEPT_LEGACY_TOKENS=true, AUTH_LEGACY_ACCEPT_UNTIL unset. These fields and
AUTO_INIT_DB/SEED_DEMO_DATA/RUN_MIGRATIONS_ON_STARTUP are **unset** in the inspected
local production file. Missing flags are not explicit production evidence:
AUTO_INIT_DB and SEED_DEMO_DATA have permissive code defaults, while the shell
entrypoint defaults migration-on-startup to false. main.py bypasses create_all
and demo seeding when production mode is actually set; an unset environment is
not that assurance. Require explicit initial
runtime configuration: production mode; issuance false; legacy acceptance true;
cutoff unset or separately approved future; initialization/seeding/startup
migrations false. Preserve the approved access lifetime/key unless a separately
approved credential incident response requires a coordinated change.

## Encrypted application recovery on Supabase Free

The legacy backup/restore helpers were reviewed and preserved, not executed.
Use a separately approved operator procedure below. It is an application-public
schema backup, **not a complete Supabase platform clone**. Blue Panda's own auth
tables are in public. Supabase-managed auth/storage payloads, other custom schemas,
settings/secrets, media/uploads and external integrations require a separate
scope/inventory and recovery plan. A schema-filtered dump may omit dependencies;
the exact reviewed artifact must restore successfully before release.
[pg_dump scope and metadata](https://www.postgresql.org/docs/17/app-pgdump.html),
[Supabase recovery caveats](https://supabase.com/docs/guides/platform/migrating-within-supabase/backup-restore)

Before any live export, approve: custodian; public-schema scope and dependencies;
recovery point/RPO/RTO; protected destination outside **all** Git checkouts/cloud
sync; retention/access; separate media backup; encryption recipient fingerprint
and offline private-key custody; source/target identity and restore authorization.
This task generated only disposable synthetic test keys. Real recovery key
creation/custody is an owner action, not an application-signing-key reuse.

Use an existing approved OpenSSL CMS implementation supporting AES-256-GCM. The
drill tested OpenSSL 4.0.3. Public-certificate recipient encryption lets the backup
host hold no decryption key. The private key and any key passphrase stay in the
custodian's protected store, separate from ciphertext; never put passphrases in
argv, environment values, logs, chat or Git. Pin/verify the recipient certificate's
public SHA-256 fingerprint through the owner. No new packages were installed.
[OpenSSL CMS](https://docs.openssl.org/3.6/man1/openssl-cms/)

Use PostgreSQL 17 native clients for the reviewed 17 source and restore target.
Prepare owner-only (0600) libpq service/pass files outside the repository, using
protected entry. Use a verified direct endpoint where available; an independently
verified session pooler on 5432 is the fallback when direct connectivity is
unavailable. Do not use transaction pooler 6543. Review TLS trust/hostname
validation and libpq overrides; never copy a SQLAlchemy URL into shell arguments.
Test native-client connection identity/revision read-only before export approval.

After those approvals, the operator sets non-secret file paths/service alias and
the reviewed revision privately. The following is a **prepared recipe, not an
executed production command**. Run in an approved shell with tracing off:

```sh
rtk proxy bash <<'SH'
set -euo pipefail
set +x
umask 077
: "${BP_RECOVERY_DIR:?existing protected directory outside all Git checkouts}"
: "${BP_RECIPIENT_CERT:?approved public recipient certificate path}"
: "${PGSERVICEFILE:?owner-only reviewed service file path}"
: "${PGPASSFILE:?owner-only password file path}"
: "${PGSERVICE:?reviewed backup service alias}"
: "${BP_EXPECTED_REVISION:?reviewed pre-window revision}"
test -d "$BP_RECOVERY_DIR"
if git -C "$BP_RECOVERY_DIR" rev-parse --show-toplevel >/dev/null 2>&1; then exit 2; fi
test -z "${PGHOSTADDR+x}" && test -z "${PGPASSWORD+x}"
python3 - <<'PY'
import os
from pathlib import Path
import stat
for name, directory in [("BP_RECOVERY_DIR", True), ("PGSERVICEFILE", False), ("PGPASSFILE", False)]:
    info = Path(os.environ[name]).lstat()
    valid_type = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    if info.st_uid != os.getuid() or info.st_mode & 0o077 or not valid_type:
        raise SystemExit("STOP: recovery path ownership/type/permissions need owner review")
PY
pg_dump --version | grep -Eq 'PostgreSQL\) 17\.'
psql --version | grep -Eq 'PostgreSQL\) 17\.'
export PGOPTIONS='-c default_transaction_read_only=on -c statement_timeout=600000 -c lock_timeout=2000'
export PGCONNECT_TIMEOUT=10 PGAPPNAME=blue-panda-approved-backup
stamp=$(date -u +%Y%m%dT%H%M%SZ)
archive="$BP_RECOVERY_DIR/public-$stamp.dump.cms"
metadata="$BP_RECOVERY_DIR/metadata-$stamp.json.cms"
test ! -e "$archive" && test ! -e "$archive.partial"
test ! -e "$metadata" && test ! -e "$metadata.partial"
psql --dbname="service=$PGSERVICE" --no-password -X -qAt -v ON_ERROR_STOP=1 \
  -v expected_revision="$BP_EXPECTED_REVISION" \
  -f docs/upgrade/phase_1d/backup_metadata.sql \
  2>"$BP_RECOVERY_DIR/metadata-$stamp.log" |
  openssl cms -encrypt -binary -stream -aes-256-gcm -outform DER \
    -out "$metadata.partial" "$BP_RECIPIENT_CERT" \
    2>"$BP_RECOVERY_DIR/metadata-encrypt-$stamp.log"
pg_dump --dbname="service=$PGSERVICE" --no-password --format=custom \
  --schema=public --strict-names --lock-wait-timeout=2s \
  2>"$BP_RECOVERY_DIR/dump-$stamp.log" |
  openssl cms -encrypt -binary -stream -aes-256-gcm -outform DER \
    -out "$archive.partial" "$BP_RECIPIENT_CERT" \
    2>"$BP_RECOVERY_DIR/encrypt-$stamp.log"
test -s "$archive.partial" && test -s "$metadata.partial"
mv "$archive.partial" "$archive"
mv "$metadata.partial" "$metadata"
openssl dgst -sha256 "$archive" "$metadata" >"$BP_RECOVERY_DIR/manifest-$stamp.txt"
SH
```

Export the path/service-alias variables into the approved operator shell before
the recipe; no secret values belong in those variables. The path checks reject
symlinks, non-owner access and group/world permissions. Unexpected inherited
PGHOSTADDR/PGPASSWORD inputs cause refusal, not silent runtime modification.
The metadata pipeline verifies major/revision before pg_dump starts.
Only encrypted archive/metadata bytes are persisted; no plaintext dump intermediate.
Each pipeline must succeed (pipefail) before publication. A failure leaves protected
partial ciphertext/logs for operator review; never label it recoverable. Native
diagnostics may contain private target identifiers, so do not print/share logs.
No owner/privilege suppression flags are used. The metadata file contains role
attributes/memberships/default privileges without password hashes; it is encrypted
too. Role passwords need separately approved recovery. Freeze role/schema DDL in
the approved export window or capture/review before/after metadata: these separate
connections do not share a single snapshot. pg_dump itself is transaction-consistent.
Do not silently prune, upload, or send archives to GitHub. Offsite encrypted copy
and recovery-key redundancy require named approved destinations/custodians.

### Isolated restore acceptance

The [synthetic-only runner](phase_1d/rehearse_recovery.py) accepts no live URL or
input archive. It uses the cached official 17 image, two unique network-none,
read-only-root/tmpfs containers, synthetic fixtures from the existing reviewed
runner, and disposable test encryption keys. Run only its synthetic test now:

```sh
rtk proxy python3 docs/upgrade/phase_1d/rehearse_recovery.py
```

For a **future separately approved real archive drill**, the operator must verify
the new target's image/cluster/data directory, no ports/network/binds/volumes,
blocked outbound jobs and resource budget before placing any sensitive data there.
Authenticate/decrypt the entire CMS file successfully **before** pg_restore.
Plaintext may be staged only in that verified target's bounded tmpfs, not a host
checkout/disk. A decrypt-to-tmpfs pipeline must finish successfully before the
restore command; never pipe unauthenticated streaming plaintext straight into SQL.
Review encrypted roles/membership/extension metadata privately and bootstrap only
approved compatible roles in the isolated target; do not blindly recreate managed
Supabase roles or carry production passwords. Restore with pg_restore
`--exit-on-error --single-transaction` into a new empty disposable database; do not
use --clean or a name-only guard against an existing database.
Retain the fresh cluster's initdb-created public schema and its default ACLs;
do not drop/recreate that namespace before restore. The expanded synthetic check
caught loss of its PUBLIC USAGE baseline when that namespace was recreated.
If the archive contains CREATE SCHEMA public, first independently match the
target namespace owner/ACL against the encrypted source metadata, then review a
pg_restore table-of-contents list that omits **only** that already-satisfied SCHEMA
creation entry. Keep schema ACL/comment and every other entry, owners and grants.
Use --use-list with that reviewed list. If the namespace does not match, stop for
approved bootstrap design; do not suppress all owners/privileges or ignore errors.

Require schema/column/index/FK/unique/default/owner/ACL/RLS/policy/extension and
revision comparisons plus retained revocation/consumption history. Owner-only
explicit ACLs may become equivalent NULL defaults during pg_dump recovery; compare
normalized effective rights, not only ACL text. The synthetic drill caught that
normalization distinction before passing. Real history validation must follow the
custodian-approved privacy scope without printing records, hashes or tokens.
Measure restore time and recoverable point; check media separately. Cleanup may
remove only the verified drill containers/tmpfs after approved validation. Synthetic
success does not prove production export permissions, dependencies, RPO/RTO or
Python 3.12 compatibility.

## Marker migration and ordered release plan

Reviewed d7e8f9012abc adds nullable users.legacy_tokens_revoked_at (timestamptz),
with no default/backfill. Its parent is a1b2c3d4e5f6. Existing columns are skipped
by name only, so independently verify type/nullability on drift; do not stamp past
an incompatible column. Downgrade drops the barrier and can revive old JWTs:
retain schema/history and use a reviewed session-aware fallback/forward fix.
Its inspector needs an online connection; offline --sql is not validated here.

The exact future order, each step separately authorized:

1. Close Render identity/role/configuration and external-consumer gaps; approve
   containment, recovery, immutable artifacts, observer/window and incident plan.
   Complete required PostgreSQL 17/Python 3.12 and client acceptance first.
2. Apply approved **Data API off** containment, then verify persisted state and
   unaffected PostgreSQL/FastAPI paths. Leave GraphQL off. No schema/grant change
   is implied by this toggle.
3. Obtain an approved encrypted pre-window recovery point and successful protected
   isolated restore with media/metadata coverage. Handle confirmed affected secrets
   under the separate coordinated rotation plan below before releasing new code;
   do not preserve a compromised signing key solely for backward compatibility.
4. At exactly a1b2c3d4e5f6, apply the separately approved permission-only SQL and
   verify scoped denial/owner access. **Existing target_guard.sql requires a1b2c3d4e5f6.**
   Do this before d7e8f9012abc or stop for renewed SQL review/rehearsal; never edit
   the expected revision casually or run the guarded script after marker migration.
5. Apply only the separately approved marker migration to d7e8f9012abc with the
   migration job's bounded lock/statement budgets and target verification. Do not
   use upgrade head, auto-init, seed, earlier migrations or stamping as shortcuts.
6. Deploy the reviewed session-aware backend with modern issuance explicitly OFF,
   legacy acceptance ON, approved cutoff/lifetime and startup writes disabled.
   Drain old workers, verify marker/schema independently from readiness, and run
   only separately authorized session smoke. Preserve revoked/consumed history.
7. Release Management, then Storefront to its confirmed working alias, then Flutter
   signed artifact/device acceptance, each with its own approval. Do not enable
   modern issuance/refresh or change storage dependencies as part of this rollout.
8. Observe both /api and /api/v1, denials, errors/latency and revocation persistence;
   close only with owner sign-off. Keep a tested session-aware backend fallback;
   no stateless rollback, schema downgrade or old database restore as permission undo.

## Credential sequence and restart requirements

Follow the [redacted rotation checklist](phase_1c_security/CREDENTIAL_ROTATION_CHECKLIST.md).
Confirmed affected **configuration**: root/backend DB password, root pgAdmin
default, root/backend JWT signing key. The reviewed Supabase password differs
from the displayed DB literals; actual Render reuse/other consumers are unknown.
Do not rotate an unaffected Supabase credential merely because local values leaked.

Order: contain retained output → inventory/reuse review → owner-approved fresh
separate recovery encryption key/certificate custody → affected database logins
and every consumer's synchronized configuration/pool cutover → actual pgAdmin
account and saved DB secrets → coordinated JWT signing/verification key cutover
across all affected workers → adoption verification and old-version retirement.
If active compromise requires urgent containment, the incident owner chooses the
window/order; do not delay response solely to preserve sessions.

Database password changes require owner-approved consumer connection refresh;
existing pooled connections are not evidence that new credentials work. Changing
Compose defaults does not rotate an existing database or persisted pgAdmin account.
JWT cutover requires coordinated worker replacement and an approved forced-login/
session plan; mixed keys cause inconsistent acceptance. Render Save only does not
update an existing runtime: deploy/restart actions need separate approval. Never
roll back to a disclosed secret. No secret was rotated by this preparation.

## Manual production approval checklist

- [ ] Owner confirms external Data API/GraphQL/service_role consumers and deployed
  client origins; authorizes the exact Data API toggle and conditional rollback.
- [ ] Owner provides existing Render access and per-instance probe evidence; exact
  role-specific post-remediation application acceptance passes on 17/Python 3.12.
- [ ] Custodian approves encrypted export scope/location/retention/key/media custody
  and isolated restore; measured recovery point/RPO/RTO and dependency coverage pass.
- [ ] Incident/service owner identifies every affected credential consumer and
  approves rotations, forced-login behavior and each runtime restart/deploy window.
- [ ] DB owner/security approvers authorize unchanged permission SQL hashes at
  a1b2c3d4e5f6, then the separately reviewed marker migration to d7e8f9012abc;
  stop on revision drift and review rollback feasibility across that boundary.
- [ ] Release owner approves exact reviewed commits/build digests, CI evidence,
  canonical origins/CORS, auto-deploy controls, session-aware fallback and observation.
- [ ] Explicit production flags are privately confirmed on **every** instance;
  issuance remains false and no initialization/seeding/automatic migration runs.
- [ ] Separate consent covers production session-writing smoke and each backend/
  Management/Storefront/Flutter deployment. No account/role/password mutation is
  implicitly authorized. Commit/push and paid-service changes remain prohibited.

## Checks and limits

Focused backend command: `rtk .venv/bin/python -m pytest -q
tests/test_auth_rollout_defaults.py tests/test_session_models.py` from backend:
**22 PASS**, two dependency deprecation warnings; no packages changed. Isolation
was verified in conftest before execution. Actual marker upgrade/repeat check
passed on temporary SQLite without importing application settings. This is not
PostgreSQL lock/release-runtime acceptance. Successful recovery output is retained
separately; earlier Phase 1C evidence/SQL/runner and all existing scripts preserved.
No web/mobile code changed, so their lint/build/device suites were not rerun.
A source inspection reprinted an already-disclosed development JWT default.
Its value is omitted from this runbook and remains covered by the replacement
requirement; subsequent configuration/diff review used redacted or captured output.

Changed-file inventory: this runbook records the procedure and checklist;
phase_1d/backup_metadata.sql supplies read-only password-free metadata capture;
phase_1d/rehearse_recovery.py is the synthetic-only isolated drill;
phase_1d/recovery_evidence.json records its successful result;
PHASE_1C_SECURITY_RELEASE_GATES.md adds the Phase 1D status checkpoint; and
PHASE_1C_AUTH_RELEASE_CHECKLIST.md links the prerequisite ordering. No existing
application, migration, recovery helper, real environment file or earlier SQL/
evidence artifact was changed.
