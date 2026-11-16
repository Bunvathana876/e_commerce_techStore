# Blue Panda Deployment & Operational Scripts

This directory contains operator-reviewed scripts for production and staging operations:

## Scripts Overview

| Script | Purpose | Safety Properties |
|---|---|---|
| `backup-postgres.sh` | Performs a logical backup of PostgreSQL via `pg_dump` with gzip compression. | Password masking, non-empty validation, SHA256 integrity checksum. Never runs automatically on container start. |
| `restore-drill.sh` | Performs a non-destructive disaster recovery verification drill into an isolated test database. | **Strict safety guard**: rejects any target database whose name does not contain `drill` or `test`. Never touches live `ecommerce_db`. Cleans up test database upon completion. |
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
