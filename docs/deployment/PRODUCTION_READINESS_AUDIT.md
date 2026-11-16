# Blue Panda Production Readiness Audit

**Audit date:** 2026-11-01  
**Scope:** Read-only Phase 1 audit of the current workspace. No application code, Compose configuration, environment files, database, volumes, migrations, DNS, or deployment infrastructure was changed. Secrets and connection values were not copied into this report.

## Executive assessment

Blue Panda is **not ready for an internet-facing production deployment**. The customer storefront (`storefront/`), management portal (`management/`), FastAPI API, and Flutter client exist as separate applications, and the current backend includes meaningful improvements over the historical project audit: server-side role dependencies, scoped seller operations, upload validation, production validation for JWT/CORS settings, migration tests, and authorization tests.

The current Docker Compose stack remains expressly a development stack. It runs `next dev`, mounts source trees, runs Uvicorn with reload, automatically runs Alembic migrations and demo seeding at container start, publishes all application ports, and exposes pgAdmin. These behaviors must not be used for production.

The most important release gates are: isolate production secrets and state, replace automatic startup migration/seeding with an approved procedure, add a dedicated production Compose/reverse-proxy design, address authentication abuse controls and token storage, prohibit demo/fallback commerce behavior in release builds, establish backup/restore operations, and complete a real payment and fulfillment design before enabling electronic payments.

## Current repository and delivery state

| Area | Observed state | Risk |
|---|---|---|
| Root repository | The root worktree is dirty and has untracked planning/separation documents plus `storefront/` and `management/`. `backend/`, `mobile-app/`, and `web-app/` are tracked as gitlinks, while no usable `.gitmodules` mapping was found. | HIGH |
| Nested repositories | `backend/`, `mobile-app/`, and `web-app/` each contain their own `.git`. The legacy `web-app/` is itself dirty. `storefront/` and `management/` are not root gitlinks. | HIGH |
| Historical documentation | `README.md` calls the system production-ready and lists development defaults/demo credentials. `PROJECT_CONTEXT.md` is useful orientation but predates current authorization/migration work. | MEDIUM |
| Development Compose | PostgreSQL data and pgAdmin data use named volumes. Database binds to loopback, but backend, frontends, and pgAdmin bind to all interfaces. | HIGH |
| Production Compose | No dedicated production Compose file, reverse proxy, restricted production network, backup job, or deployment runbook implementation exists. | CRITICAL |

Before a release pipeline is created, ownership must decide whether this is a true multi-repository layout or a root superproject with properly declared submodules. Do not remove `web-app/`: it is a preserved legacy repository and has uncommitted work.

## Findings by severity

### CRITICAL

| ID | Finding | Evidence and impact | Required release gate |
|---|---|---|---|
| C-01 | Development containers would be deployed if the current Compose file were used. | Storefront and management Dockerfiles run `npm run dev`; backend entrypoint runs Uvicorn with `--reload`; source and build folders are bind-mounted. This is unsuitable for performance, reproducibility, and exposure control. | Create separate production images and production Compose configuration; retain the existing file untouched for local development. |
| C-02 | Database changes and demo data execute automatically at backend startup. | `backend/docker-entrypoint.sh` runs `alembic upgrade head`, database initialization, and seeding before application start. A deployment restart could change data/schema without verified backup or approval. | Remove these actions from production startup. Run an operator-approved migration job only after backup and staging verification; force `AUTO_INIT_DB=false` and `SEED_DEMO_DATA=false`. |
| C-03 | Production secret boundaries are not established. | Development fallback credentials/secrets exist in Compose and templates; `.env` files exist locally; root ignore rules do not clearly ignore all `.env` variants. A production secret manager/process is absent. | Audit tracked history and CI variables without printing values; rotate any values that may have escaped; make production secrets external to Git and fail closed when absent. |
| C-04 | Electronic payment is not production-integrated. | UI/payment states exist, but no gateway SDK/service, provider webhook signature verification, immutable payment ledger, settlement reconciliation, or refund workflow was found. | Keep Cash on Delivery; hide/disable non-COD methods for production until a provider-specific, audited payment implementation is approved. |

### HIGH

| ID | Finding | Evidence and impact | Required release gate |
|---|---|---|---|
| H-01 | pgAdmin is enabled and published by default. | Current Compose maps pgAdmin port 5050 and sets development-oriented pgAdmin configuration. | Omit pgAdmin from production Compose. Use SSH tunneling or a separate, tightly controlled administrative workflow when needed. |
| H-02 | API and frontends are directly published instead of being private upstream services. | Compose exposes 8000, 3000, and 3001 directly; no Caddy/Nginx/TLS service exists. | Publish only ports 80/443 on the reverse proxy; place API/frontends/DB on private Compose networks. |
| H-03 | Login and registration lack observed rate limiting and abuse defenses. | Auth routes issue/validate access tokens but no limiter was found. | Add a reverse-proxy and/or API rate-limit design for login, registration, password change, uploads, and sensitive administration before launch. |
| H-04 | JWT access tokens are browser `localStorage` values. | Both new Next.js apps read/write bearer tokens through `localStorage`; this increases the impact of XSS. Logout does not revoke an already-issued JWT. | Perform an auth-session design review: CSP/XSS protections, short-lived tokens, refresh/revocation behavior, and ideally secure HttpOnly cookie/BFF architecture. This is a planned security change, not an automatic migration. |
| H-05 | Frontend remote-image policy is overly permissive. | Both Next.js configs allow `http` and `https` images from wildcard hostnames. | Replace wildcard remote patterns with explicit trusted image origins; serve uploaded media through the production API/media host only. |
| H-06 | Upload persistence is local container filesystem state. | API writes validated raster images beneath `uploads/`; current backend source bind mount happens to preserve them in development, but a production image/redeploy would not. | Use a dedicated persistent volume with backup/restore coverage as an interim solution, or object storage in a separately approved phase; add retention, ownership, and media-serving rules. |
| H-07 | Mobile defaults are local HTTP endpoints. | Flutter defaults to localhost/emulator endpoints unless `API_URL` is passed at build/run time. | Produce explicit release flavors/build commands requiring an HTTPS production API origin; prevent a release artifact from silently using localhost. |
| H-08 | Production observability and recovery have not been implemented. | Health is liveness-only (`/health`); no readiness DB check, structured logging, monitoring, alerting, backup automation, or restore runbook was found. | Add readiness/health separation, sanitized structured logs, service metrics/alerts, encrypted backups, and a restore drill. |
| H-09 | Seller scoping and payment/order authority need deployment-grade regression verification. | Current routes use `require_roles`; the repository contains authorization, POS, seller, stock-concurrency, order-state, and upload-security tests. These are not evidence of a production PostgreSQL deployment. | Run and gate relevant tests in CI, including PostgreSQL migration/concurrency tests in an isolated disposable database; review every privileged route as release work. |

### MEDIUM

| ID | Finding | Evidence and impact | Required release gate |
|---|---|---|---|
| M-01 | Uvicorn proxy trust, host validation, security headers, and request-wide body limits are not configured. | No trusted-forwarded-header/host middleware was found. Upload service itself enforces type, byte, dimension, and pixel limits. | Define trusted proxy IP/network handling, host allowlist, proxy security headers, request-size limits, and header policy at Caddy/Nginx and API layers. |
| M-02 | Connection pool policy is implicit. | SQLAlchemy uses `pool_pre_ping=True`; pool size, overflow, timeout, recycle, and observability are not configured. | Size pools for VPS capacity and worker count; document database connection budget. |
| M-03 | API documentation is disabled by default in production, but production defaults are not yet deployed/tested. | Settings correctly controls docs/OpenAPI in production. | Verify production environment validation and restrict docs to an authenticated/internal path only if operations require them. |
| M-04 | No distinct readiness endpoint. | `/health` returns a static healthy response without database dependency verification. | Add a guarded `/readyz` DB query and have orchestration use readiness separately from liveness. |
| M-05 | Development/demo presentation can be misleading during outages. | Storefront has showcase catalog fallbacks; mobile contains explicitly opt-in mock auth code plus fallback reviews/notifications/coupons. | Establish production build policy: no silent fake products/orders/payment success; demos must be visibly labeled and unavailable in production configurations. |
| M-06 | The API is available under both `/api` and `/api/v1`. | Both routers are registered for web/mobile compatibility. | Keep compatibility during migration, document canonical versioning, and add deprecation/monitoring before any removal. |
| M-07 | Password policy is weak by production standards. | Password change enforces only a six-character minimum; login/register have no observed throttling/reset/email-verification service. | Define password policy, password reset verification, credential stuffing controls, and account recovery operations. |
| M-08 | Persistent database volume exists, but backup and restore are absent. | `postgres_data` is named; no automated dumps, encrypted off-host copy, retention, or restore test was found. | Implement backup schedule/retention/encryption and conduct a documented restore test before production. |

### LOW

| ID | Finding | Evidence and impact | Required release gate |
|---|---|---|---|
| L-01 | Image builds are larger and less repeatable than necessary. | Dockerfiles use `npm install`, single-stage Node images, root runtime, and development tooling. Backend includes broad build/client packages. | Introduce lockfile-based, multi-stage, non-root production images after functionality/security gates. |
| L-02 | README terminology and topology are stale. | It describes one `web-app/` portal and claims production readiness, while current root Compose uses `storefront/` and `management/`. | Update documentation only after repository topology and deployment design are approved. |
| L-03 | Container image tags are not fully pinned. | pgAdmin uses `latest`; base images are major-version tags. | Pin validated versions/digests in production manifests and use an update policy. |

## Component audit

### Frontends

- `storefront/` and `management/` use Next.js 16.3.4 / React 19.2.8 with Node 20 Alpine Dockerfiles. Package scripts already include `build`, `start`, `lint`, and tests.
- Both Dockerfiles are development-only: one stage, root user, dependency installation with `npm install`, no lockfile enforcement, no standalone output, and `next dev` command.
- Both configurations use permissive remote image patterns. Their API fallback is a localhost HTTP URL when `NEXT_PUBLIC_API_URL` is absent. Public variables are compiled into browser bundles; they must contain no secrets and need controlled build-time values.
- Browser tokens in localStorage and console logging need a security/logging review. API authorization remains the authoritative control and must not be replaced by UI route guards.
- `web-app/` remains preserved legacy code in a separate nested Git repository. It was inspected only for Docker/configuration orientation and must be excluded from any deletion/cleanup proposal.

### FastAPI and authentication

- The backend has environment-aware production validation for JWT secret strength and explicit CORS origins. Production docs are disabled by default. This is good baseline behavior.
- JWTs use HS256 and a seven-day default expiry. There is no refresh/revocation/deny-list lifecycle; logout is client-side token disposal plus a success response.
- Route dependencies now enforce roles in reviewed route modules. This is a material improvement; route-by-route ownership and seller-scope regression tests still belong in the release gate.
- CORS is explicit/configurable, not wildcard by default. Production values must contain only the actual HTTPS storefront and management origins.
- Validated raster uploads reject path tricks, mismatched media types, oversized input, oversized dimensions/pixels, and markup/SVG; nevertheless, ingress limits, durable storage, malware/operational policy, and generated URL host handling remain production concerns.
- The current engine performs pre-ping but has no explicit production pool tuning. The health check does not prove database readiness.

### Data, orders, and payments

- Alembic has an initial migration and a later consolidation migration. Do not infer safety from static inspection: run the migration suite against a disposable PostgreSQL instance and take/verify a backup before any real migration.
- The backend code includes order-state and stock-concurrency tests. Actual production capacity, isolation behavior, and operational rollback need staging validation.
- Cash on Delivery can remain available subject to order-state authorization and fulfillment procedures. Non-COD labels/states are not evidence of a payment integration.
- No backup, retention, point-in-time recovery, restore verification, migration approval runbook, or database access-control process was found.

### Tests inspected

| Area | Available evidence | Audit action |
|---|---|---|
| Backend | API, authorization, CORS/config, coupon, Alembic/PostgreSQL, order-state, POS, seller, stock concurrency, and upload-security test modules | Inspected; not run because this Phase 1 request is read-only and the suite writes isolated test DB/upload state. |
| Storefront | Node tests for checkout security, session isolation, and routing | Inspected; not run. |
| Management | Test command exists; no test files were identified in the inspected test path. | Not run. |
| Mobile | Unit/widget coverage across auth, cart/checkout, network, orders, products, reviews, UI, and settings | Inspected; not run. |

## Production release decision

**Do not deploy publicly.** A production candidate may be prepared only after all CRITICAL findings and applicable HIGH findings are closed, staging proves the deployment/migration/restore path, and business owners approve payment and order-state behavior. The existing development Compose workflow should remain available and unchanged throughout that work.
