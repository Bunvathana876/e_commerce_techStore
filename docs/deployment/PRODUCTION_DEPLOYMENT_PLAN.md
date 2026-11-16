# Blue Panda Production Deployment Plan

**Status:** Design only. This document does not deploy, publish ports, issue certificates, change DNS, run migrations, or modify existing Compose development infrastructure.

## Recommended single-VPS architecture

Use a supported Linux VPS with Docker Engine and Compose. Run a dedicated production Compose project separate from the repository's current development Compose file.

```text
Internet
  |
  +-- TCP 80/443 only --> Caddy (TLS, host routing, limits, access logs)
                              |-- shop.example.com   --> storefront:3000
                              |-- manage.example.com --> management:3001
                              `-- api.example.com    --> backend:8000
                                                              |
                                                     private data network
                                                              |
                                                        PostgreSQL:5432

Operator --> SSH + MFA --> optional short-lived local tunnel --> pgAdmin (never public)
Backup job --> encrypted off-host backup destination --> scheduled restore verification
```

The domains above are illustrative placeholders only. Actual domains belong in deployment secrets/configuration, never source code. Caddy is recommended here because it can manage HTTPS after an operator supplies real DNS and explicitly authorizes deployment; Nginx is an equally viable option if the team already operates it. This plan does not request or generate certificates.

### Network and exposure rules

- The reverse proxy is the only service publishing host ports (80/443 in a future production manifest).
- Storefront, management, backend, and PostgreSQL communicate over internal Docker networks. Do not publish PostgreSQL or backend/frontend application ports on the VPS.
- pgAdmin is excluded from the production Compose profile by default. If temporarily needed, bind it only to loopback and reach it through a named, authenticated SSH tunnel; remove it again after the operation.
- Configure firewall access for SSH only from approved administration addresses and web ports only when deployment is approved. Use provider firewall and host firewall defense in depth.

## Proposed production layout

```text
e-commerce/
  docker-compose.yml                 # unchanged development stack
  compose.production.yml             # future production service definition
  deploy/
    Caddyfile                        # future reverse-proxy policy; no real domain committed
    env/
      production.env.example          # names/placeholders only, never real values
    scripts/
      backup-postgres.sh              # future reviewed backup procedure
      restore-drill.sh                # future non-production verification procedure
      migrate-approved.sh             # future explicit operator-only migration procedure
  storefront/
    Dockerfile.production             # future multi-stage image, or production target
  management/
    Dockerfile.production             # future multi-stage image, or production target
  backend/
    Dockerfile.production             # future non-root runtime image
  PRODUCTION_READINESS_AUDIT.md
  PRODUCTION_DEPLOYMENT_PLAN.md
  PRODUCTION_PROGRESS.md
```

This is a target structure, not a request to create these operational files yet. It deliberately keeps `docker-compose.yml`, `web-app/`, and every existing local workflow intact.

## Service design

| Service | Production responsibility | Key controls |
|---|---|---|
| Caddy | TLS termination, HTTPS redirect, host routing, request limits, security headers, access logs | Only public service; explicit hosts; no database/admin proxy route. |
| Storefront | Customer Next.js application | `next build` then `next start` or standalone Node server; non-root user; private upstream network; public API URL compiled intentionally. |
| Management | Admin/seller Next.js application | Same production build model; separate host; administrative session and CSP hardening review. |
| Backend | FastAPI REST API | Non-reload multi-worker process, trusted proxy configuration restricted to Caddy, role/ownership enforcement, rate limits, liveness/readiness, sanitized logs. |
| PostgreSQL | Private durable relational database | No published port; named volume; least-privilege app user; backup/restore discipline; direct access only through approved operations. |
| pgAdmin | Optional break-glass tool | Disabled by default; never public; separate operator authentication and SSH tunnel only. |

## Environment-variable and secret strategy

1. Keep development `.env` behavior separate from production. Never copy development defaults into a VPS production environment.
2. Store production secrets in a deployment secret mechanism with restricted operator/CI access. A root-owned environment file readable only by the deployment account is an acceptable initial VPS solution; a managed secret store is preferred when available.
3. Keep only variable names and non-sensitive example values in Git. `NEXT_PUBLIC_*` values are public browser configuration and must never contain passwords, JWT keys, database URLs, provider secrets, or internal credentials.
4. Use distinct strong PostgreSQL credentials and a distinct, high-entropy JWT signing key per environment. Rotate any secret suspected to have been committed or shared.
5. Explicitly set production values, including `ENVIRONMENT=production`, `AUTO_INIT_DB=false`, `SEED_DEMO_DATA=false`, an HTTPS-only CORS allowlist, and documentation disabled. The backend must fail rather than silently use a development default.
6. Build-time public URLs must be set separately for storefront and management. Server-only backend values must resolve through the internal network only where the code path is server-side.

## Build and runtime preparation

### Next.js

- Use a current supported Node LTS image selected and pinned during implementation; Node 20 is presently used but should be confirmed against the Next.js release support policy at implementation time.
- Create multi-stage builds using lockfile-enforced installation (`npm ci` when lockfiles are present), compile with `next build`, and run only the minimal production output.
- Evaluate `output: "standalone"` against current custom SVG webpack behavior. Use it if build/runtime tests show compatibility; otherwise use a minimal `next start` runtime image.
- Run as an unprivileged user, copy only runtime artifacts, disable telemetry, and do not bind mount source or `.next` in production.
- Replace wildcard Next image remote patterns with explicit trusted API/media hosts. Preserve image optimization only after proxy/media headers and cache rules are verified.
- Establish production-safe error behavior and structured server logs. Do not expose API internals in customer-facing errors.

### FastAPI

- Run a non-reload production command such as a managed Gunicorn/Uvicorn-worker or Uvicorn process sized to available CPU/memory. Choose and load-test the exact command during implementation; do not add a process manager blindly.
- Configure forwarded headers only from the reverse proxy network, allowed host headers, request IDs, sanitized structured logging, and security headers in the proxy/API design.
- Keep docs/OpenAPI disabled publicly. Add separate liveness and DB-backed readiness checks.
- Tune SQLAlchemy pool size/overflow/recycle/timeouts relative to the number of API workers and PostgreSQL `max_connections`.
- Rate-limit auth, password changes, uploads, POS/admin mutations, and resource-intensive searches. Include a shared storage design if multiple backend replicas are introduced later.
- Keep backend RBAC and seller ownership checks authoritative. Client navigation guards are never authorization.

### Files and images

Initial safe VPS option: mount a dedicated named volume for backend uploads, back it up with the database metadata, serve it only through the API/proxy, and enforce ownership/permissions. Longer term: object storage with private write credentials, signed/admin upload policy, lifecycle rules, and CDN only after a dedicated design review. Do not keep product media solely in a disposable image layer.

## Database safety and migration procedure

1. Test every migration from an empty and representative restored PostgreSQL copy in staging.
2. Before any production schema change: place the application in an approved maintenance/release mode if needed, take a timestamped encrypted backup, verify the backup completed, record current Alembic revision, and obtain explicit operator approval.
3. Run the migration once through a dedicated, logged migration job—not application startup. Abort on failure; do not retry blindly.
4. Run readiness checks and focused smoke tests. Retain the previous application image and the backup until release acceptance.
5. Database rollback is not assumed safe. Roll forward with a reviewed corrective migration unless a tested rollback procedure and restored copy are approved.
6. Do not seed demo users, catalog, notifications, or accounts in staging/production except via separately reviewed, clearly labeled fixtures.

## Backup, restore, and recovery

- Create encrypted PostgreSQL logical backups at least daily; choose frequency/RPO based on order volume before launch. Store off-host with retention and access logging.
- Back up uploads consistently with database metadata. Document whether backups are crash-consistent and how they are restored together.
- Test restores at least quarterly and before major schema changes in an isolated environment. Record restore duration (RTO), data point (RPO), revision, and verification results.
- Define incident contacts, credential rotation steps, service log retention, and order/payment reconciliation after restore.

## CI/CD and release flow

1. **Repository hygiene first:** resolve root/nested-repository ownership, submodule policy, branch protection, review policy, and secret scanning. Do not delete the legacy `web-app/`.
2. **Pull request CI:** run backend tests (including an isolated PostgreSQL migration suite), storefront/management lint/build/test commands, Flutter analysis/tests, image build checks, and dependency/security scans. Do not auto-upgrade dependencies as part of this plan.
3. **Staging:** deploy immutable tagged images and separate non-production secrets; exercise login, role denial, product upload, checkout/COD, order transitions, media delivery, migration rehearsal, backup, and restore.
4. **Production release:** confirm a current verified backup; approve migration if any; deploy versioned images; run the migration job only if approved; bring up services; run HTTPS/host/readiness checks and critical smoke tests.
5. **Rollback:** stop routing traffic to unhealthy app image, redeploy previous image tag, preserve logs, and decide database recovery using the documented migration/restore plan. Never delete volumes as rollback.
6. **Monitor:** uptime/readiness, reverse-proxy 4xx/5xx and latency, API error rates, auth rate-limit events, DB disk/connection/backup failures, container restarts, TLS expiry, and order/payment operational exceptions. Route alerts to named on-call owners.

## Prioritized implementation roadmap

| Phase | Goal | Approval gate |
|---|---|---|
| 0 | Resolve repository topology, secret exposure review, and correct production-readiness claims. | Owner confirms Git/submodule strategy and secret-rotation scope. |
| 1 | Add non-production deployment artifacts: separate production Compose skeleton, network policy, `.env` examples, and image hardening without altering development Compose. | Review architecture and domain/secret ownership. |
| 2 | Harden API perimeter/auth: rate limiting, readiness, proxy/host policy, pool settings, logging, upload persistence, and release-specific demo disablement. | Security review and backward-compatibility test plan. |
| 3 | Implement frontend production builds and runtime configuration; restrict image sources; complete browser token/session security decision. | End-to-end staging validation. |
| 4 | Establish backups, restore drill, migration job, CI pipeline, staging deployment, and monitoring. | Backup/restore evidence and operational sign-off. |
| 5 | Integrate real electronic payments only as a separate provider-specific project. Preserve COD throughout. | Finance/security/legal/provider approval and webhook/reconciliation testing. |

## First safe implementation task

**Create a separate, non-running production deployment skeleton and a root Git/secret hygiene policy—without touching `docker-compose.yml`, any runtime `.env`, Docker volumes, or application code.**

The task should include only placeholder production environment examples, a documented private-network service design, and checks that prevent production configuration from accepting the known development defaults. It should be reviewed alongside a decision about the three nested Git repositories before any CI or deployment automation is added.
