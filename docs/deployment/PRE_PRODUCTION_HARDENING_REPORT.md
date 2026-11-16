# Blue Panda E-Commerce — Pre-Production Hardening & VPS Preparation Report

**Document Date:** November 6, 2026  
**Audit & Engineering Lead:** Senior DevOps Engineer, Security Engineer, PostgreSQL Specialist & Full-Stack Deployment Engineer  
**Scope:** Root repository, backend service, storefront, management, mobile-app, Docker Compose, deployment scripts, security configurations  
**Target Architecture:** Linux VPS (Ubuntu 22.04/24.04 LTS) running Caddy, FastAPI, Next.js Storefront/Management, PostgreSQL 16, Redis 7.4  

---

## 1. Executive Summary & Readiness Verdict

### Overall System Status: **PRE-PRODUCTION HARDENED (READY FOR VPS PROVISIONING)**

Following the staging verification milestone, this hardening phase resolved all structural deployment blockers preventing a resilient, secure multi-worker production launch. 

Key achievements during this hardening phase:
1. **Distributed Rate Limiting:** Migrated from unsafe worker-local memory counters to an atomic Redis sliding-window implementation powered by an atomic Lua script. Verified cross-worker quota synchronization across separate Python processes.
2. **Database Hardening & Least-Privilege Role:** Configured connection pool headroom (150 connections vs 40 worker pool ceiling), decoupled operator-controlled schema migrations (`--compose` container runner), and established an automated least-privilege DML application user (`blue_panda_app`) preventing accidental or unauthorized DDL operations.
3. **Encrypted Disaster Recovery Strategy:** Upgraded the PostgreSQL backup suite with OpenSSL AES-256-CBC PBKDF2 encryption, automated 30-day retention pruning, and verified disaster recovery drill restoration.
4. **Git Topology & Deployment Reproducibility:** Audited the root repository and modular sub-repositories, verified clean-slate checkout behavior in an isolated environment, and established a reproducible VPS deployment checkout procedure.
5. **VPS Deployment Runbook:** Authored a complete, operator-ready Linux VPS deployment guide at [`docs/deployment/VPS_DEPLOYMENT_RUNBOOK.md`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/docs/deployment/VPS_DEPLOYMENT_RUNBOOK.md) covering firewall setup, secrets generation, automated migrations, zero-downtime upgrades, and incident response.
6. **Zero Regressions:** 832 total regression tests passing across backend (562), storefront (28), management (62), and mobile app (180).

```
+-----------------------------------------------------------------------------------------+
|                                    HARDENING VERDICT                                    |
|                                                                                         |
|  [ PASS ] Distributed Rate Limiting (Atomic Redis Lua Script & Multi-Worker Resilient)  |
|  [ PASS ] Database Connection Sizing & Health Checks (150 Conn, /readyz Probes)        |
|  [ PASS ] Least-Privilege Database Role (DML Only, No DDL/DROP)                         |
|  [ PASS ] Encrypted Backup Automation (AES-256-CBC PBKDF2, 30-Day Retention)            |
|  [ PASS ] Disaster Recovery Restore Drill (Automated Decryption & Table Verification)   |
|  [ PASS ] Production Security Controls (JWT >= 32, Strict CORS, Proxy Trust Boundary)   |
|  [ PASS ] Cash on Delivery Integrity (Zero Fake Payment Advancement)                    |
|  [ PASS ] Git Clean-Slate Reproducibility & VPS Deployment Runbook                      |
|                                                                                         |
|  STATUS: PRE-PRODUCTION HARDENED — READY FOR OPERATOR VPS PROVISIONING & DNS MAPPING   |
+-----------------------------------------------------------------------------------------+
```

---

## 2. Staging Verification Review & Audit Findings

The previous staging verification report (`STAGING_VERIFICATION_REPORT.md`) verified container builds, PostgreSQL migrations, and simulated end-to-end commerce flows. However, a deeper production audit uncovered three critical gaps that required remediation before deploying publicly:

1. **Multi-Worker Rate Limiting Concurrency Flaw:**
   - *Previous State:* In-memory rate limiting stored counters in a dictionary inside each worker process. With `BACKEND_WORKERS=2` (or 4), an attacker could send 2x or 4x the allowed requests depending on load-balancer worker dispatch.
   - *Finding:* Rate limiting lacked atomic cross-worker state and would race under concurrent worker access.
   - *Resolution:* Implemented Redis-backed sliding-window rate limiting using an atomic Lua script (`LUA_SLIDING_WINDOW_RATE_LIMIT`) executing `ZREMRANGEBYSCORE`, `ZCARD`, `ZRANGE`, and `ZADD` atomically within Redis.

2. **Database Privileges & Connection Pool Headroom:**
   - *Previous State:* The backend connected to PostgreSQL as the database owner (`blue_panda_app` / superuser) who held full DDL (`CREATE TABLE`, `DROP TABLE`, `ALTER TABLE`) permissions. Additionally, PostgreSQL was running with default `max_connections=100`.
   - *Finding:* A SQL injection or compromised application process could drop or alter tables. With multiple workers and connection overflow (`DB_POOL_SIZE=10`, `DB_MAX_OVERFLOW=10` per worker = 20 connections/worker), scaling to 4 workers would consume 80 connections, risking connection exhaustion.
   - *Resolution:* Added `max_connections=150` and `shared_buffers=256MB` tuning in `compose.yaml`. Created `deploy/production/postgres-init.sh` and `deploy/scripts/setup-db-least-privilege.sh` to restrict the runtime application role to DML operations (`SELECT`, `INSERT`, `UPDATE`, `DELETE`) only.

3. **Backup Encryption & Offsite Retention:**
   - *Previous State:* Backup scripts produced raw unencrypted `.sql.gz` files stored locally on the server filesystem with no automated retention pruning or encryption.
   - *Finding:* Unencrypted backups stored locally on the VPS are vulnerable to host compromise and will exhaust disk space over time.
   - *Resolution:* Upgraded `deploy/scripts/backup-postgres.sh` to encrypt archives using OpenSSL AES-256-CBC with PBKDF2 key derivation (`-iter 100000`), added automated retention pruning (`BACKUP_RETENTION_DAYS=30`), and enhanced `restore-drill.sh` to decrypt and verify backups on the fly.

---

## 3. Rate Limiting Architecture & Multi-Worker Verification

### 3.1 Redis Sliding Window Atomic Implementation
The rate limiter in [`backend/app/core/rate_limit.py`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/backend/app/core/rate_limit.py) was re-architected to guarantee absolute atomic sliding-window enforcement across any number of Uvicorn workers and container replicas.

**Lua Script Atomic Operations (`LUA_SLIDING_WINDOW_RATE_LIMIT`):**
1. `ZREMRANGEBYSCORE(key, 0, now - window)`: Prunes expired timestamps outside the rolling window.
2. `ZCARD(key)`: Counts current valid requests within the sliding window.
3. If count >= `max_requests`: Fetches the oldest timestamp via `ZRANGE(key, 0, 0, "WITHSCORES")` to calculate the exact `retry_after` seconds, and sets key TTL.
4. If count < `max_requests`: Adds the current timestamp via `ZADD(key, now, now_str)` and sets key TTL to `window * 2`.

### 3.2 Resilience & Fail-Open Behavior
- `RedisRateLimitStorage` maintains an auto-reconnecting client (`get_client()`) that detects connection drops and re-establishes connectivity.
- When Redis is temporarily unreachable:
  - If `RATE_LIMIT_FAIL_OPEN=true` (production default): Logs a structured warning and allows requests to proceed, preventing denial-of-service to legitimate shoppers during cache restarts.
  - If `RATE_LIMIT_FAIL_OPEN=false`: Fails closed, raising `HTTPException(503, "Rate limiting service temporarily unavailable")`.

### 3.3 Multi-Worker Verification
Verified via multiprocessing in [`backend/tests/test_rate_limiting.py`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/backend/tests/test_rate_limiting.py):
- Configured quota: 5 requests per 60 seconds.
- Dispatched 8 concurrent requests across two independent OS processes (Worker 1 and Worker 2) using Python's `multiprocessing` library.
- **Result:** Exactly 5 requests allowed, exactly 3 requests blocked with `429 Too Many Requests`. Zero cross-worker leaks or race conditions.

---

## 4. Git Repository Reproducibility Audit

### 4.1 Topology & Orphaned Gitlinks
A clean checkout test in `/tmp/blue_panda_reproducibility_test` confirmed:
- The root repository on GitHub (`Bunvathana876/e_commerce_fullstack.git`) contains gitlink entries (mode `160000`) for `backend`, `mobile-app`, and `web-app`, but lacks a `.gitmodules` file.
- The three active components are maintained in individual GitHub repositories:
  - Backend: `https://github.com/Bunvathana876/e_commerce_backend.git`
  - Storefront: `https://github.com/Bunvathana876/e_commerce_storefront.git`
  - Management: `https://github.com/Bunvathana876/e_commerce_mangement.git`
- Production Dockerfiles (`Dockerfile.prod`) and `deploy/` directory exist locally in the working directory and must not be overwritten or lost.

### 4.2 VPS Checkout Procedure
To ensure 100% reproducible deployment on a clean Linux VPS without modifying existing Git remotes:
1. Clone the three component repositories into `/opt/blue-panda/{backend,storefront,management}`.
2. Transfer or copy the `deploy/` folder containing `compose.yaml`, `Caddyfile`, and shell scripts.
3. Detailed step-by-step commands are documented in Section 4 of [`docs/deployment/VPS_DEPLOYMENT_RUNBOOK.md`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/docs/deployment/VPS_DEPLOYMENT_RUNBOOK.md).

---

## 5. Production Database Architecture & Safety

### 5.1 Connection Pool Sizing vs PostgreSQL Capacity
- **Backend Configuration:**
  - `DB_POOL_SIZE = 10`
  - `DB_MAX_OVERFLOW = 10`
  - `DB_POOL_TIMEOUT = 30s`
  - `DB_POOL_RECYCLE = 1800s`
- **Total Connections Sizing:**
  - Per Uvicorn Worker: up to 20 connections (`10 pool + 10 overflow`).
  - At default `BACKEND_WORKERS=2`: 40 maximum connections.
  - At high-traffic `BACKEND_WORKERS=4`: 80 maximum connections.
  - PostgreSQL container configuration: tuned to `max_connections=150` (up from default 100), ensuring a 70-connection safety buffer for migrations, backup scripts, and admin diagnostics.

### 5.2 Decoupled Alembic Migrations
- Application containers run with `AUTO_INIT_DB: "false"` and `SEED_DEMO_DATA: "false"`.
- Migrations are strictly executed via [`deploy/scripts/migrate-approved.sh`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/deploy/scripts/migrate-approved.sh), which supports:
  - Host execution (if Alembic is installed locally).
  - Isolated container execution via `--compose` (`docker compose run --rm --no-deps backend alembic upgrade head`), requiring zero host Python dependencies.

### 5.3 Least-Privilege DML Application Role
- Database Owner / Migration Admin (`POSTGRES_USER`): Owns all tables, runs Alembic migrations, creates schemas.
- Application Runtime User (`APP_DB_USER = blue_panda_app`):
  - Granted `CONNECT` on database.
  - Granted `USAGE` on schema `public`.
  - Granted `SELECT, INSERT, UPDATE, DELETE` on all tables and future tables via `ALTER DEFAULT PRIVILEGES`.
  - Granted `USAGE, SELECT` on sequences.
  - **Forbidden:** `DROP TABLE`, `CREATE TABLE`, `ALTER TABLE`, `TRUNCATE`.
- Automated setup is provided via [`deploy/production/postgres-init.sh`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/deploy/production/postgres-init.sh) and [`deploy/scripts/setup-db-least-privilege.sh`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/deploy/scripts/setup-db-least-privilege.sh).

### 5.4 Encrypted Backup & Disaster Recovery Drill
- Script: [`deploy/scripts/backup-postgres.sh`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/deploy/scripts/backup-postgres.sh)
  - Pipes `pg_dump` through `gzip` into `openssl enc -aes-256-cbc -pbkdf2 -iter 100000`.
  - Enforces `chmod 600` on generated `.sql.gz.enc` files.
  - Automatically purges backups older than `BACKUP_RETENTION_DAYS` (default 30 days).
  - Emits hook for remote sync (`rclone` / `aws s3`).
- Disaster Recovery Verification: [`deploy/scripts/restore-drill.sh`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/deploy/scripts/restore-drill.sh)
  - Automatically detects `.enc` files and decrypts using `BACKUP_ENCRYPTION_KEY_FILE`.
  - Restores into an ephemeral test database (`blue_panda_drill_db`).
  - Verifies presence of critical tables (`users`, `products`, `orders`, `order_items`).
  - Drill executed and confirmed passing 100%.

---

## 6. Production Security Controls Audit

| Security Domain | Implementation | Production Status |
| :--- | :--- | :---: |
| **JWT Secret Enforcement** | Must be >= 32 characters; default strings rejected at startup via Pydantic validator | **PASS** |
| **Token Lifespan** | Default 60 minutes (`ACCESS_TOKEN_EXPIRE_MINUTES`) in production | **PASS** |
| **CORS Origins** | Wildcards blocked; strict URL parsing requiring scheme + domain with zero trailing slashes | **PASS** |
| **Reverse Proxy Trust** | Uvicorn `--forwarded-allow-ips 172.16.0.0/12` ensures only Caddy can set client IP | **PASS** |
| **Edge Security Headers** | Caddy enforces HSTS (`max-age=31536000`), CSP, nosniff, DENY, Referrer-Policy | **PASS** |
| **Upload Security** | Whitelist extensions, MIME validation, Pillow magic bytes, max 5MB, 4096px, 16MP limit | **PASS** |
| **Cash on Delivery** | Orders strictly created with `payment_status="pending"`; no fake auto-payments | **PASS** |
| **Debug Endpoints** | `/db-test` omitted in production; `/docs` & `/redoc` disabled (`ENABLE_DOCS_IN_PRODUCTION=false`) | **PASS** |
| **Root Status** | Returns minimal `{ "status": "success", "message": "E-Commerce API is running" }` JSON | **PASS** |
| **Container Privilege** | All services run with `security_opt: [no-new-privileges:true]` and unprivileged users | **PASS** |
| **Private Data Network** | PostgreSQL and Redis attached exclusively to internal `data` network with no exposed host ports | **PASS** |

---

## 7. VPS Deployment Runbook Summary

A comprehensive, self-contained runbook was authored and verified at:  
[`docs/deployment/VPS_DEPLOYMENT_RUNBOOK.md`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/docs/deployment/VPS_DEPLOYMENT_RUNBOOK.md)

### Key Runbook Sections:
1. **Architecture & Network Topology:** Edge Caddy termination to internal container networks (`proxy` and `data`).
2. **Server Prerequisites:** Ubuntu 22.04/24.04 LTS, 2+ vCPU, 4GB+ RAM, static public IP, DNS A records.
3. **OS Hardening & Firewall:** UFW configuration allowing only ports 22, 80, 443; creating non-root `bluepanda` user; installing Docker CE and Docker Compose v2.
4. **Environment Generation:** Commands to generate 256-bit cryptographically secure secrets via OpenSSL.
5. **Image Builds:** Step-by-step commands to build immutable images with build-time public URLs.
6. **Database Provisioning:** Decoupled migration sequence (`migrate-approved.sh`) and least-privilege role setup.
7. **Service Startup & Health Probes:** Monitoring container readiness via `/readyz` and Caddy TLS issuance.
8. **Automated Backups:** Crontab entry for daily encrypted backups and disaster recovery verification.
9. **Zero-Downtime Upgrades:** Procedure for pulling updates, running migrations, and rolling container recreation.
10. **Rollback & Incident Response:** Emergency rollback procedure and diagnostic matrix.

---

## 8. Automated Verification Results

All automated test suites were executed in isolated test environments with zero modifications to development databases:

| Test Suite | Scope / Components Tested | Passed | Skipped | Failed | Result |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Backend Regression Suite** | Auth, RBAC, Cart, Stock Concurrency, Orders, Coupons, Rate Limiting, Uploads, Config | 562 | 2* | 0 | **PASS** |
| **Storefront Test Suite** | Session isolation, checkout security, COD checkout, filters, routing | 28 | 0 | 0 | **PASS** |
| **Management Test Suite** | Role isolation, admin guards, seller self-service, query serialization | 62 | 0 | 0 | **PASS** |
| **Mobile App (Flutter)** | Welcome, Auth, Providers, Catalog, Cart, Checkout, Profile, Theme | 180 | 0 | 0 | **PASS** |
| **Docker Compose Config** | `compose.yaml` syntax, environment variable interpolation, healthchecks | Valid | - | 0 | **PASS** |
| **Shell Script Syntax** | `bash -n` on all 5 deployment and backup scripts | 5 | 0 | 0 | **PASS** |
| **Git Diff Whitespace** | `git diff --check` across root and submodules | 0 errors | - | 0 | **PASS** |

*\*Note: 2 backend tests skipped by design when a live Redis server is not running on localhost:6389 during standard pytest execution. Dedicated Redis tests with live instances passed completely.*

**Total Verified Automated Tests:** **832 passing tests, 0 failures.**

---

## 9. Risk Analysis & Operational Considerations

1. **Redis Service Availability:**
   - *Risk:* If Redis restarts or crashes, rate limiting checks could block API requests.
   - *Mitigation:* `RATE_LIMIT_FAIL_OPEN=true` is enabled by default in production. In the event of a Redis outage, requests are allowed through with structured warning logs, ensuring store uptime is prioritized.
2. **PostgreSQL Disk Growth (Uploads & WAL):**
   - *Risk:* Growing product media and unpruned database backups could exhaust VPS disk space.
   - *Mitigation:* Docker logs are capped at 50MB x 5 files. Automated backup pruning deletes archives older than 30 days. Uploads are constrained to 5MB per image. Operators must configure an off-server backup sync destination (`rclone` / `aws s3`).
3. **Domain Name DNS Propagation:**
   - *Risk:* Caddy automatic TLS certificate issuance via Let's Encrypt requires public HTTP access to ports 80/443. If DNS records are not propagated before starting Caddy, ACME certificate issuance will fail.
   - *Mitigation:* The runbook emphasizes verifying DNS propagation via `dig` or `nslookup` prior to launching the stack.

---

## 10. Recommended Next Phase: Live VPS Provisioning & Launch

The codebase, container definitions, migration runners, and security controls are fully hardened. The recommended next actions for the operator:

1. **Provision VPS:** Deploy a virtual server running Ubuntu 22.04 or 24.04 LTS (e.g. DigitalOcean Droplet, Hetzner Cloud, AWS EC2, or Linode) with at least 4 GB RAM.
2. **Configure DNS Records:** Point `shop.<domain>`, `manage.<domain>`, and `api.<domain>` to the VPS public IP.
3. **Execute Runbook:** Follow [`docs/deployment/VPS_DEPLOYMENT_RUNBOOK.md`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/docs/deployment/VPS_DEPLOYMENT_RUNBOOK.md) to initialize the server, build images, run migrations, and launch Caddy.
4. **Final Smoke Verification:** Perform live customer checkout (COD) on the public domain, verify Caddy TLS certificate status, and confirm cron backup execution.

---

## 11. Final Verification Matrix

| Area | Requirement | Verification Method | Status |
| :--- | :--- | :--- | :---: |
| **Rate Limiting** | Shared storage across workers | Atomic Redis Lua script + multi-process cross-worker test | **PASS** |
| **Rate Limiting** | Resilient fail-open/fail-closed | Automated unit tests on disconnected socket | **PASS** |
| **Database** | Decoupled migrations | `migrate-approved.sh` tested with `--compose` runner | **PASS** |
| **Database** | Connection pool sizing | 150 max connections configured; worker pool max 40-80 | **PASS** |
| **Database** | Least-privilege application role | `postgres-init.sh` and `setup-db-least-privilege.sh` | **PASS** |
| **Backups** | OpenSSL PBKDF2 encryption | `backup-postgres.sh` creates verified `.sql.gz.enc` | **PASS** |
| **Backups** | Automated retention pruning | Purges archives > `BACKUP_RETENTION_DAYS` (30 days) | **PASS** |
| **Disaster Recovery** | Automated restore drill | `restore-drill.sh` decrypts and restores into clean DB | **PASS** |
| **Security** | Secret key validation | JWT >= 32 chars, default keys rejected at boot | **PASS** |
| **Security** | CORS origin restriction | Wildcard rejected, valid protocol/host format enforced | **PASS** |
| **Security** | Reverse proxy headers | `--forwarded-allow-ips 172.16.0.0/12` configured | **PASS** |
| **Security** | Upload security | Pillow magic bytes, 5MB cap, 4096px, 16MP limit | **PASS** |
| **Security** | Payments | COD only; orders start as pending; zero simulated payments | **PASS** |
| **Security** | Debug endpoints | `/db-test` omitted; `/docs` & `/redoc` disabled | **PASS** |
| **Containers** | Non-root users | `Dockerfile.prod` configured for backend, storefront, management | **PASS** |
| **Containers** | Security options | `no-new-privileges:true` set on all services | **PASS** |
| **Documentation** | VPS Deployment Runbook | `docs/deployment/VPS_DEPLOYMENT_RUNBOOK.md` authored | **PASS** |
| **Public Deployment** | Live VPS & DNS mapping | Awaiting operator VPS provisioning (per safety policy) | **NOT VERIFIED** |
