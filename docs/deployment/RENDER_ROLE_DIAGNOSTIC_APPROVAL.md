# Render role diagnostic: review and approval

Prepared 2026-11-08. **Awaiting user approval; nothing deployed or saved on Render.**
Scope: identify the effective PostgreSQL role needed to restore the existing
administrator login. Keep the existing Supabase project. Permission remediation,
Alembic migrations, account changes and authenticated login tests remain outside
this approval.

The user confirms that the actual production backup and isolated restore
**PASSED**. This supersedes the older runbooks' pending recovery checkpoint for
this continuation; the archive was not reopened or the drill repeated here.

## Read-only findings

Render plugin reads in the confirmed WorkVathana workspace established:

| Item | Observed value |
| --- | --- |
| Workspace | WorkVathana, `tea-dbmmbf2jnfac73atb4kg` |
| Service | blue-panda-api-demo, `srv-dbmof167bikc73bjl1j0` |
| Runtime / plan / instance count | Docker / Free / 1 |
| Source | `Bunvathana876/e_commerce_backend`, branch `main`, repository root |
| Dockerfile / context | `./Dockerfile.prod` / `.` |
| Docker Command override | Empty |
| Current live deployment | `dep-dbo2i5rl550s738imq30` |
| Current live commit | `ad26cefb3dae4d0a24d1b53c8cdb5f494ac602cf` |
| Automatic deploys | Enabled, on commit |
| Render HTTP health-check path | Empty; default platform TCP check |

Sanitized runtime-log inspection confirmed `UndefinedColumn` referencing
`users.legacy_tokens_revoked_at`, including entries after this deployment became
live. No login request was made in this continuation and no SQL parameters,
credentials or account rows were printed. The initial filtered result was
paginated; a subsequent role-only log lookup failed. Neither lookup established
the effective role, and no exhaustive absence claim is made.

The exact committed Dockerfile starts Uvicorn directly, without an ENTRYPOINT or
migration/seed command. The exact committed database factory uses runtime
DATABASE_URL with SQLAlchemy/psycopg2; committed application-source search found
no SET ROLE, search_path changes or SQLAlchemy connection event hooks. A new
connection with the same URL/options therefore provides relevant role evidence,
subject to runtime target/configuration checks. Local `.env.supabase` alone is
not evidence of Render's identity.

Render Free has no Shell/SSH or one-off jobs. The connected Render plugin can
read the service and logs but has no tool for updating Docker Command. The
reviewed fallback is the existing service's Dashboard setting, after approval.
See the current [Free service limitations](https://render.com/docs/free#other-limitations)
and [Docker Command override](https://render.com/docs/docker#building-from-a-dockerfile).

## Exact proposed change

Set this service's **Settings → Docker Command** to the complete, single-line
contents of [render_identity_docker_command.txt](../upgrade/phase_1c_security/render_identity_docker_command.txt).
It is 11,034 bytes excluding its final newline. The command embeds the unchanged
[reviewed probe](../upgrade/phase_1c_security/render_identity_probe.py) and the
[readable launcher](../upgrade/phase_1c_security/render_identity_diagnostic_launcher.py).
The offline test verifies the decoded command equals those exact sources.

| Artifact | SHA-256 |
| --- | --- |
| Original probe, unchanged | `3fe1b1237b74ea401ae1ba6ec1aa6d2d0e3391c7652b18836a64decb0f4cdd73` |
| Diagnostic launcher | `ba7d251de247db068274ddba6b2efa898689c96bf174c518e6f726ddb2aef433` |
| Docker Command file, including final newline | `3c93199ab6cf93eb7a36d617ea952e5692ff0c4e7f4d962c15fc4bbf9afda665` |

Before saving, recheck the workspace/service, live deployment, source branch SHA,
pending deploys and configuration drift. Privately check linked environment
groups and pending settings so an unrelated saved change is not activated.
Stop if the source or configuration differs from this review. No environment
variable, secret file, key, plan, repository, Dockerfile, health-check setting or
automatic-deploy setting is to be changed under this approval. Coordinate no
concurrent source push during the short diagnostic/removal window. If the UI
cannot accept this command or cannot apply it to the reviewed source, stop and
prepare another review; do not substitute a diagnostic endpoint or new service.

Saving a command can initiate deployment. Approval must therefore precede the
save itself. Deploy only the reviewed full SHA above; capture the resulting
deployment ID and commit and verify `live`. Do not use "latest commit" if the
branch has moved. A config deploy may rebuild that same source, so this proposal
does **not** promise a byte-identical retained image. Do not clear build cache or
upgrade dependencies. If the available flow requires changing automatic-deploy
settings or another configuration field, stop for a revised review.

The launcher does the following on each container start while enabled:

1. Before importing the app, require the expected Render service, commit,
   instance presence, production environment, disabled auto-init/seed and no
   startup migration flag. Mismatch logs only an UNVERIFIED reason and exits;
   it does not start a candidate with unreviewed startup behavior.
2. Reject inherited nonempty PG* variables rather than changing or ignoring
   libpq routing/options. Match the runtime Supabase project against a SHA-256
   fingerprint of the independently dashboard-verified project identifier from
   the prior review. No project reference or connection credential is embedded.
3. Run the original probe using runtime DATABASE_URL only in memory. Preserve
   its runtime URL options, including role options; refuse URL routing overrides
   and weak TLS. Enforce read-only transactions, 10-second connection/statement
   limits and a 2-second lock timeout. Add a 45-second alarm around the diagnostic.
4. Check parent revision `a1b2c3d4e5f6`, PostgreSQL 17, TLS, repeatable-read and
   exactly the three auth-table metadata records. Read only catalog/role/privilege
   metadata and Alembic revision; never select authentication/account rows.
   Roll back and close the diagnostic connection.
5. Emit one `READ_ONLY_ROLE_PROBE` JSON line containing provenance, hashed
   instance identity, current_user/session_user/configured role, role flags,
   owners/memberships, schema/CRUD/sequence permissions and TLS/version checks.
   Errors emit only UNVERIFIED, exception type and SQLSTATE; exception text and
   SQL parameters are suppressed. Query failure keeps the role gate open and
   proceeds to the unchanged app command, without retrying or repairing anything.
6. Replace the launcher process with the exact committed startup command:

   ```sh
   exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WORKERS:-1} --proxy-headers
   ```

There is no source commit/push, application endpoint, package installation,
permission SQL, migration, account change or authenticated request in this plan.
Normal application traffic continues under the current runtime behavior; the
read-only guarantee concerns the separate diagnostic connection. Startup is
delayed by the bounded probe, and Free-plan restarts can rerun it until removal.

## Required observation and removal

After the diagnostic deploy is live, collect only the sanitized marker line from
that deploy/instance. Require service/project match, the reviewed commit, instance
presence, expected parent revision, PostgreSQL 17, TLS true, read_only on and
repeatable read. Review every required schema/table/sequence privilege and role
ownership/membership/BYPASSRLS field. A ROLE_OBSERVED line establishes identity;
it is not automatic approval of post-remediation compatibility. Missing fields,
drift or a failed probe leave the role gate UNVERIFIED. Never retry with weaker
TLS, another identity or automatic migration.

Removal is part of the requested diagnostic approval:

1. Once one usable result or a terminal diagnostic failure is recorded, restore
   **Docker Command to its original empty value** and apply a cleanup deploy of
   the same reviewed source SHA. Capture its deployment ID and `live` status.
   If the diagnostic candidate fails preflight, still remove the saved override;
   an older live instance does not by itself clear service configuration.
2. Confirm via service readback that dockerCommand is empty, commit is unchanged,
   and the cleanup instance produces no new diagnostic marker. Retain historical
   sanitized logs for audit; do not delete logs or database data.
3. Check credential-free GET `/health` and `/readyz` return 200 after both deploys.
   Do not attempt administrator login yet: the missing-column repair has not
   been approved. If startup or cleanup fails, report it and stop; do not roll
   back to an older application commit, change credentials or touch schema.

Both deploys replace Free-plan ephemeral storage. The production backup/restore
is owner-confirmed passed, but that does not independently prove media coverage.
Privately confirm no required uploads exist only on the current instance before
starting this approved window; do not copy or delete them under this plan.
See [Render deployment filesystem behavior](https://render.com/docs/deploys#ephemeral-filesystem).

## Separate permission-remediation gate

After identity is verified and the diagnostic is removed, compare the observed
role against the unchanged reviewed [apply.sql](../upgrade/phase_1c_security/apply.sql).
It revokes the three internal auth tables/sequences from PUBLIC, anon,
authenticated and service_role and enables policyless, non-FORCE RLS. An ordinary
non-owner role may lose access; BYPASSRLS alone does not grant table privileges.
Do not switch the application to an owner, add BYPASSRLS or invent an RLS policy
to make the gate pass. Resolve incompatible evidence through a new review.

Present a **separate permission execution approval** with the effective role,
role-specific isolated acceptance, current target/revision/ACL/RLS guard results,
unchanged SQL hashes, recovery checkpoint and approved window. Unresolved gates
in the [administrator login plan](ADMIN_LOGIN_SCHEMA_MISMATCH_RELEASE_PLAN.md)
remain explicit; this diagnostic does not close them. Do not execute permission
SQL before that approval. The single marker migration and later existing-admin
login verification retain their own approval gates. Nothing here approves
`alembic upgrade head`, automatic migrations, role/password changes or a client
release.

## Verification completed before requesting approval

- Seven offline tests passed, with synthetic environment/metadata and mocked
  probe/process execution: successful handoff, service/commit/startup rejection,
  inherited libpq rejection, wrong-target rejection, error/timeout sanitization,
  TLS/version/isolation/evidence drift and exact source-to-command parity.
- The command passed `sh -n`; the embedded Python compiled without execution.
- The original probe hash was checked; permission SQL/migrations were not edited.
- Tests ran on existing local Python 3.14.1 dependencies. No Python 3.12 Render
  execution, production DB query, full application test suite or browser login
  was run; only diagnostic preparation changed. Runtime acceptance awaits approval.

Reproduce the offline checks from the repository root:

```sh
rtk proxy backend/.venv/bin/python -B -m unittest discover -s docs/upgrade/phase_1c_security -p test_render_identity_diagnostic.py
rtk proxy sh -n docs/upgrade/phase_1c_security/render_identity_docker_command.txt
```

**Requested approval:** temporarily set this exact Docker Command and deploy the
reviewed commit on blue-panda-api-demo, collect sanitized read-only role evidence,
then restore the empty command and deploy the same commit to remove it. No
permission SQL or migration is included.
