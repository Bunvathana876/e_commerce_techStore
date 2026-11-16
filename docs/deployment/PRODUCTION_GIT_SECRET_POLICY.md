# Blue Panda Production Git and Secret Policy

## Purpose

This policy prevents development credentials, production secrets, deployment state, and private customer/commerce data from entering source control or build artifacts.

## Current findings

- Root `.env` and application-local `.env` files exist in the workspace but were not read during this task.
- The current root ignore policy excludes `.env` and `.env.*` while explicitly allowing `.env.example`. Backend and Next.js ignore rules also exclude private environment files.
- The production skeleton adds a local defense-in-depth ignore rule for `deploy/production/.env` and permits only `.env.example`.
- In the repositories inspected, only an environment example filename was tracked; no live `.env`/`.env.local` filename was identified as tracked. The root `.env.example` and new production template are examples, not secret stores.
- Tracked development configuration/documentation contains known demo/default credential values and an insecure development JWT fallback. These are unsafe defaults for production even if they are not real production secrets.
- `.DS_Store` is already tracked in the root and currently modified. This is repository noise, not a secret, and should be removed from tracking only in a separately reviewed cleanup.
- Because there are orphaned gitlinks and independent nested histories, secret scanning must cover the root plus `backend`, `mobile-app`, and `web-app` histories separately until the monorepo migration is complete.

Static filename inspection cannot prove that no secret has ever been committed. Historical and remote scanning remains required before production.

## Classification

### Never commit

- Database passwords or complete production connection strings
- JWT signing keys, OAuth/client secrets, payment-provider keys, webhook secrets, SMTP credentials, or backup encryption keys
- Real `.env`, `.env.local`, secret YAML/JSON, private keys, certificates with private material, database dumps, or production logs
- Customer personal data, access tokens, refresh tokens, payment data, uploaded private documents, or live backups
- Registry credentials, VPS SSH private keys, cloud credentials, or CI runner tokens

### Safe to commit with review

- `.env.example` files containing variable names and unmistakably unusable placeholders
- Public example domains under `example.com`/`.invalid`
- Non-sensitive operational defaults such as port numbers, byte limits, and retention examples
- `NEXT_PUBLIC_*` values only when everyone understands they are intentionally public browser configuration

## Required controls

1. Store production secrets in the deployment platform/CI secret store or a root-owned host file outside Git with least-privilege permissions.
2. Inject secrets only at runtime unless a provider explicitly requires a build secret. Never use Docker `ARG`/`ENV` for private build secrets because image history and layers can retain them.
3. Supply `NEXT_PUBLIC_*` values during Next.js builds, record them as public build metadata, and produce immutable environment-specific image tags. Never place private values in a `NEXT_PUBLIC_*` variable.
4. Protect production environments with branch protection, required review, restricted deployment identities, short-lived credentials where possible, and audited manual approval.
5. Configure secret scanning for current files, commits, pull requests, container build context, and all independent repository histories.
6. Keep database dumps/backups and upload archives outside the repository. Encrypt them, restrict access, define retention, and test restoration.
7. Sanitize application/CI logs. Never echo environment files, expanded Compose configurations, authorization headers, tokens, database URLs, or secret-bearing command lines.

## Remediation for a suspected or discovered secret

1. Treat it as compromised; restrict access and notify the responsible owner without copying the value into an issue or chat.
2. Revoke/rotate it at the provider or service first. History rewriting alone does not invalidate a secret.
3. Determine exposure across root and nested repositories, forks, CI logs/artifacts, container registries, backups, and deployed hosts.
4. Replace the value through the approved secret store and verify dependent services.
5. Decide on history cleanup only with repository-owner approval and a coordinated clone/fork plan. Never force-push automatically.
6. Document the incident using redacted identifiers, dates, scope, and corrective controls.

## Pre-production checklist

- [ ] Scan every current and historical repository independently.
- [ ] Confirm no live environment or credential file is tracked.
- [ ] Replace every development/demo/default credential with a unique production secret outside Git.
- [ ] Confirm production startup fails when required secrets are missing.
- [ ] Confirm container images and CI artifacts contain no private build inputs.
- [ ] Confirm Compose rendering and logs are not uploaded with expanded secrets.
- [ ] Review access to the registry, VPS, database backups, DNS, and CI deployment environment.
- [ ] Record owners and rotation procedures for every secret class.
