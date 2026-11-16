# Blue Panda Backend — Render Free Deployment Guide

**Target Platform:** Render.com (Free Web Service)  
**Database:** Supabase PostgreSQL (Existing schema at Alembic revision `a1b2c3d4e5f6`)  
**Container:** Docker (`backend/Dockerfile.prod` multi-stage, non-root `appuser:10001`)  
**Security Level:** Production  

---

## 1. Render Web Service Settings

Configure the following settings in the **Render Dashboard** when creating a new **Web Service**:

| Setting | Value / Recommended Choice | Notes |
| :--- | :--- | :--- |
| **Name** | `blue-panda-backend` | Will form the default URL: `https://blue-panda-backend.onrender.com` |
| **Repository** | `Bunvathana876/e_commerce_backend` | Or root repository if deploying from monorepo |
| **Root Directory** | `.` (or `backend` if from root repo) | Working directory containing the Dockerfile |
| **Runtime** | **Docker** | Uses the hardened multi-stage production Dockerfile |
| **Dockerfile Path** | `./Dockerfile.prod` (or `backend/Dockerfile.prod`) | Multi-stage image running unprivileged `appuser` |
| **Docker Context** | `.` (or `backend`) | Build context containing `app/`, `alembic/`, `requirements.txt` |
| **Instance Type** | **Free** ($0 / month) | 512 MB RAM, 0.1 shared CPU |
| **Region** | Choose region nearest to Supabase | E.g. `Oregon (US West)` or `Frankfurt (EU)` for low latency |
| **Health Check Path** | `/health` | Lightweight liveness probe returning HTTP 200 without DB query |
| **Auto-Deploy** | `Yes` (or `No` for manual control) | Deploys on git push to the selected branch |

---

## 2. Environment Variables Specification

Set the following variables in the **Environment** tab on Render.  
> [!IMPORTANT]
> Never commit actual passwords or private connection strings to source control. Use the Render Dashboard UI to input production secrets securely.

| Variable Name | Required | Example Format / Value | Description |
| :--- | :---: | :--- | :--- |
| `ENVIRONMENT` | **Yes** | `production` | Enables production security validators and disables debug endpoints |
| `DATABASE_URL` | **Yes** | `postgresql+psycopg2://postgres.<project-id>:<url-encoded-password>@aws-0-<region>.pooler.supabase.com:5432/postgres?sslmode=require` | Supabase Session Pooler URL. Ensure special characters in password are percent-encoded |
| `JWT_SECRET_KEY` | **Yes** | `<AT_LEAST_32_HEX_CHARACTERS>` | Cryptographic secret for signing tokens (generate with `openssl rand -hex 32`) |
| `JWT_ALGORITHM` | No | `HS256` | Default signature algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | `60` | Token expiration lifespan (default 60 minutes) |
| `CORS_ORIGINS` | **Yes** | `https://shop.yourdomain.com,https://manage.yourdomain.com` | Comma-separated or JSON list of authorized frontend browser origins (no trailing slashes) |
| `PORT` | No | `10000` | Render injects this automatically; `Dockerfile.prod` dynamically binds to `${PORT:-8000}` |
| `WORKERS` | No | `1` | **1 worker is optimal for Render Free** (512MB RAM ceiling and unified in-memory rate limiting) |
| `DB_POOL_SIZE` | No | `5` | Keeps total connections well within the Supabase Free 15-connection pooler limit |
| `DB_MAX_OVERFLOW` | No | `5` | Maximum temporary connection burst per worker |
| `DB_POOL_TIMEOUT` | No | `30` | Seconds to wait before timing out if all connections are checked out |
| `DB_POOL_RECYCLE` | No | `1800` | Recycles connections every 30 minutes to drop stale SSL connections |
| `AUTO_INIT_DB` | No | `false` | Strictly disables automatic schema alterations on startup |
| `SEED_DEMO_DATA` | No | `false` | Strictly disables demo data seeding on startup |
| `ENABLE_DOCS_IN_PRODUCTION` | No | `false` | Hides `/docs`, `/redoc`, and `/openapi.json` from public internet |
| `RATE_LIMIT_STORAGE_URL` | No | *(Leave unset/empty on Free tier)* | When unset, utilizes unified in-memory sliding window on the single worker |
| `RATE_LIMIT_FAIL_OPEN` | No | `true` | Allows traffic to flow if rate limiter storage encounters a failure |
| `UPLOAD_DIR` | No | `/var/lib/blue-panda/uploads` | Local upload directory inside the container |

---

## 3. Architecture & Operational Verification

### 3.1 Single Uvicorn Worker on Render Free
- **Memory Footprint:** FastAPI with SQLAlchemy, Pydantic, and bcrypt uses ~110–130 MB RAM at baseline.
- **Resource Constraints:** Render Free provides a strict **512 MB RAM** limit. Running 2 workers (~260+ MB) under concurrent request allocations risks triggering the kernel Out-Of-Memory (OOM) killer.
- **CPU:** Render Free allocates 0.1 shared vCPU core. Multiple workers cause context-switching overhead without multi-core benefits.
- **Rate Limiting:** With 1 worker, in-memory rate limiting is 100% unified without requiring an external Redis service.
- **Recommendation:** Use `WORKERS=1` for Render Free. Scale to `WORKERS=2` or `WORKERS=4` only on paid plans with 2GB+ RAM.

### 3.2 Supabase PostgreSQL SSL & Connection Limits
- **SSL Enforcement:** Supabase requires SSL encryption. `backend/app/db/database.py` automatically enforces `sslmode=require` for Supabase hosts, and normalizes legacy `postgres://` URLs to `postgresql+psycopg2://`.
- **Pool Sizing:**
  - Supabase Free Tier pooler limit: **15 concurrent connections**.
  - Blue Panda configuration: `DB_POOL_SIZE=5` + `DB_MAX_OVERFLOW=5` = **10 maximum connections**.
  - Leaves 5 connection slots available for Alembic migrations, database maintenance, and Supabase Studio queries.
- **Port Selection:**
  - Port `5432`: Session pooler (recommended for standard Web applications).
  - Port `6543`: Transaction pooler (for short-lived serverless functions).

### 3.3 Health & Readiness Endpoints
- **Liveness (`/health`):** Returns HTTP 200 `{"status": "healthy"}` immediately without querying PostgreSQL. Configure this as Render's **Health Check Path** so container startup is recognized instantly.
- **Readiness (`/readyz`):** Executes `SELECT 1` through SQLAlchemy. Returns HTTP 200 `{"status": "ready", "database": "connected"}` or HTTP 503 if the database is unreachable.

### 3.4 Zero Startup Migrations / Seeding
- `AUTO_INIT_DB=false` and `SEED_DEMO_DATA=false` are set as container defaults.
- `app/main.py` hard-bypasses `create_all()` and `seed_database()` whenever `is_production` is `True`.
- Supabase schema is already up-to-date at revision `a1b2c3d4e5f6`.

---

## 4. Product Uploads & Storage Strategy

### 4.1 Render Free Ephemeral Filesystem
On the Render Free tier, container filesystems are **ephemeral**:
- Any uploaded product images stored in `/var/lib/blue-panda/uploads` will persist while the container is running.
- When Render spins down the service after 15 minutes of inactivity or when a new version deploys, locally stored images will be lost.

### 4.2 Recommended Cloud Storage Options (Future Milestone)
For persistent production media storage, integrate external object storage:
1. **Supabase Storage (Recommended):** Since PostgreSQL is already on Supabase, use Supabase Storage (1 GB free storage, S3-compatible API, public CDN URLs).
2. **Cloudflare R2:** S3-compatible, 10 GB free tier with zero egress fees.
3. **AWS S3:** Industry standard object storage.

*Note: For initial demo evaluation on Render Free, local uploads function normally during active user sessions.*

---

## 5. Render Free Cold Start Behavior

- Render Free web services automatically spin down into a sleep state after **15 minutes of inactivity**.
- The first HTTP request after sleeping will trigger a cold start, taking approximately **30 to 50 seconds** to boot the container.
- Subsequent requests will be served immediately with sub-50ms latency.
- To keep the service awake during demo presentations, configure a free external ping service (e.g. [UptimeRobot](https://uptimerobot.com) or [Cron-Job.org](https://cron-job.org)) to hit `https://<your-service>.onrender.com/health` every 10 minutes.
