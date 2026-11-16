# Phase 1C credential exposure assessment and rotation checklist

Date: 2026-11-07. **Assessment only. No secrets rotated or configuration changed.**
Read with the [release gates](../PHASE_1C_SECURITY_RELEASE_GATES.md).

## Verified exposure scope

An earlier unfiltered `git diff` displayed credential literals already present
in unrelated repository changes. This assessment captured the relevant diff in
memory and emitted only categories, file names and equality booleans. Values,
full URLs and secret fingerprints are deliberately omitted.

| Credential category | Result | Evidence and boundary |
| --- | --- | --- |
| PostgreSQL password literals | **FAIL** | Two distinct literals were displayed in removed/added docker-compose.yml configuration, including the embedded DATABASE_URL password; run.sh's removed password line also appeared |
| Reuse in current local database configuration | **FAIL** | The password in each of .env and backend/.env matches an exposed literal; no connection was attempted |
| Reuse in local pgAdmin configuration | **FAIL** | Private-review continuation confirmed .env PGADMIN_DEFAULT_PASSWORD matches a displayed literal; adoption by an existing persisted pgAdmin account is UNVERIFIED |
| Reuse in local JWT configuration | **FAIL** | Private-review continuation confirmed JWT_SECRET_KEY in both .env and backend/.env matches a displayed literal; actual Render runtime reuse is UNVERIFIED |
| Same-password reuse in reviewed Supabase file | **PASS** | backend/.env.supabase's parsed database password differs from both exposed literals; this is only a local equality check, not proof of production safety |
| pgAdmin default password | **FAIL** | PGADMIN_DEFAULT_PASSWORD literals appeared in the earlier docker-compose.yml diff |
| Development JWT signing secret | **FAIL** | JWT_SECRET_KEY literals appeared in the earlier docker-compose.yml diff |
| Actual production use/reuse of any exposed value | **UNVERIFIED** | No running Render environment, owner secret inventory or trusted runtime binding was available |
| Broader disclosure or misuse | **UNVERIFIED** | Chat/output readership, retained copies, repository history outside the inspected diff and authentication audit trails were not investigated |
| Automatic rotation | **PASS** | None performed; files and running services were preserved |

No Supabase API key, production database password or Render management token was
identified in the inspected earlier diff. This does not rule out exposure through
other channels or production reuse of the development values. Treat displayed
values as disclosed wherever they remain valid. Do not test them against a live
service to establish reuse.

The 2026-11-07 private review repeated equality checks entirely in memory.
Root .env DATABASE_URL/POSTGRES_PASSWORD, PGADMIN_DEFAULT_PASSWORD and
JWT_SECRET_KEY matched the relevant earlier exposed literals; backend/.env
DATABASE_URL and JWT_SECRET_KEY also matched. The reviewed Supabase connection's
password did not match either displayed database-password literal. No secret
values, secret hashes, full URLs or live authentication attempts were emitted.
These are confirmed configuration reuses; running-service adoption still needs
owner evidence. Supabase dashboard access verified project settings, not its
password or Render's credential binding.

## Approval and preparation — complete before any rotation

- [ ] Name the incident/credential owner, approving service owner and operator.
  Restrict access to the affected transcript/output and any shared exports. Request
  supported redaction or removal through the owner; removal cannot undo disclosure.
  Preserve only a sanitized incident record with source locations and UTC times.
- [ ] Privately map each exposed value to its credential record and consumers:
  local PostgreSQL roles, Docker/Compose configuration, local environment files,
  pgAdmin, background jobs, CI and the actual Render service/environment groups.
  Check reuse through owner-controlled comparison; record yes/no without values.
  Include Supabase only if its actual credential is affected or reused.
- [ ] Agree on the rotation window, service restart/deployment actions, expected
  downtime, observer, recovery point and safe forward-recovery plan. Do not restore
  a disclosed credential as a rollback strategy.
- [ ] Obtain separate explicit approval for each password/signing-secret change,
  consumer configuration update, restart/deployment and any session revocation.
  Approval for this assessment or SQL rehearsal does not authorize these actions.

## Owner-operated execution plan — not executed here

Sequence: contain the output disclosure and map consumers first; rotate affected
database logins with their consumer cutover; handle the actual pgAdmin account
and saved connection secrets separately; coordinate the JWT signing-secret
cutover across all verified instances; then validate adoption and retire old
versions. Apply only to owner-confirmed consumers after the separate approvals
below. A local configuration match does not authorize a production rotation.

1. Generate a unique replacement in the approved password manager/secret store.
   Use its protected entry mechanism. Keep secret material out of chat, source
   code, shell history, process arguments, screenshots and diagnostic output.
   Do not place temporary plaintext credential files in the repository.
2. For an affected **database login**, use the service owner's supported password
   workflow. Coordinate every approved consumer update and connection-pool refresh
   within the agreed window. Never change an unaffected Supabase credential merely
   because a local development password was disclosed. Verify the new binding with
   the prepared metadata-only probe once runtime access is authorized.
3. For **pgAdmin**, rotate the actual account credential if it uses the exposed
   default; update any affected saved database connection secret separately.
   Changing an image's default environment variable is not evidence that an existing
   persisted pgAdmin account password changed. Verify through the owner workflow.
4. For the **JWT signing secret**, first determine where the exposed development
   secret is actually used. Approve a coordinated replacement across every signing
   and verification instance. Plan for existing-token invalidation and re-login;
   handle refresh/session revocation through separately approved application
   procedures. Test signature rejection and successful authentication only with
   synthetic staging accounts; do not read or mutate production account rows here.
5. Update the approved consumers through protected configuration entry. Render
   distinguishes Save only from deployment: saved environment changes do not reach
   an existing runtime until its next deploy. Any deployment/restart needs separate
   approval. Never print the environment to prove the update.
   [Render environment-variable behavior](https://render.com/docs/configure-environment-variables)
6. After the authorized cutover, have the owner validate replacement usage and
   retire old credentials through the provider's supported mechanism. Review
   connection/authentication metadata for misuse without retrieving account,
   session or password-hash rows. Record completion and remaining consumers by
   identifier and UTC time only.
7. Separately review removing hardcoded defaults, unsafe password-printing paths
   and retained secret material from repository/history/output. Prepare a scoped
   patch for approval; do not rewrite history, delete evidence, commit or push as
   part of this assessment. Preserve unrelated user work.

## Completion evidence to request

For each category: owner, approved scope/window, affected-consumer identifiers,
replacement version/reference (no secret or secret hash), cutover time, runtime
adoption evidence, old-credential retirement and any remaining exception. Until
this is available, rotation completion and production impact remain **UNVERIFIED**.
