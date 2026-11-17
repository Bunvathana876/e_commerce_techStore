# Blue Panda Deployment & Operational Scripts

This directory contains operator-reviewed scripts for production and staging operations:

## Scripts Overview

| Script | Purpose | Safety Properties |
|---|---|---|
| `backup-postgres.sh` | Performs a logical backup of PostgreSQL via `pg_dump` with gzip compression. | Password masking, non-empty validation, SHA256 integrity checksum. Never runs automatically on container start. |
| `restore-drill.sh` | Performs a non-destructive disaster recovery verification drill into an isolated test database. | **Strict safety guard**: rejects any target database whose name does not contain `drill` or `test`. Never touches live `ecommerce_db`. Cleans up test database upon completion. |
| `verify-local-runtime.py` | Checks a local production backend image, migrations, auth, checkout, retries, cancellation, stock, and CORS. | Creates a fresh temporary PostgreSQL container and random loopback API port; reads no existing `.env` or database and stops its resources on exit. |
| `migrate-approved.sh` | Runs `alembic upgrade head` in a controlled, logged manner. | Inspects current revision, prompts operator for confirmation (or `--yes`), logs post-migration revision. |

## Usage Examples

### 1. Create a logical database backup
```bash
export DATABASE_URL="postgresql+psycopg2://user:password@localhost:5432/blue_panda"
./deploy/scripts/backup-postgres.sh
```

### 2. Run a non-destructive restore drill
```bash
export POSTGRES_PASSWORD="password"
export DRILL_DB_NAME="blue_panda_restore_drill"
./deploy/scripts/restore-drill.sh ./backups/blue_panda_backup_20261106_120000Z.sql.gz
```

### 3. Run approved database migrations
```bash
export DATABASE_URL="postgresql+psycopg2://user:password@localhost:5432/blue_panda"
./deploy/scripts/migrate-approved.sh
```

### 4. Verify a production image locally

This checks the image against a fresh, disposable PostgreSQL 16 database. It is
not a production migration or a backup/restore drill. Docker must be running and
`postgres:16-alpine` must already be available locally. No live credentials are
required. Run from the repository root:

```bash
rtk docker build -f backend/Dockerfile.prod -t blue-panda-backend:local-check backend
rtk proxy python3 deploy/scripts/verify-local-runtime.py --backend-image blue-panda-backend:local-check
```

Expected output includes `PASS production image migrations on empty PostgreSQL 16`
and a pass for the production API flow. The script checks both API prefixes,
HTTP 409 on repeated cancellation, one order per retry key, and restored stock.
It runs as the image's unprivileged user with a read-only root filesystem.
Rate limiting is disabled for this bounded commerce smoke test; verify Redis
quotas separately through `backend/tests/test_rate_limiting.py`.
