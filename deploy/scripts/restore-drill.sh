#!/usr/bin/env bash
# ==============================================================================
# Blue Panda E-Commerce — Automated Disaster Recovery Restore Drill
# Restores a backup file into an ISOLATED disposable drill database.
# STRICT SAFETY GUARD: Refuses to restore into any database unless the database
# name explicitly contains 'drill' or 'test' to prevent accidental overwrites.
# ==============================================================================
set -euo pipefail

BACKUP_FILE="${1:-}"
DRILL_DB_NAME="${DRILL_DB_NAME:-blue_panda_restore_drill}"
DB_HOST="${POSTGRES_HOST:-localhost}"
DB_PORT="${POSTGRES_PORT:-5432}"
DB_USER="${POSTGRES_USER:-ecommerce_user}"

if [ -z "${BACKUP_FILE}" ]; then
    echo "Usage: $0 <path_to_backup.sql.gz>" >&2
    exit 1
fi

if [ ! -f "${BACKUP_FILE}" ]; then
    echo "ERROR: Backup file '${BACKUP_FILE}' not found." >&2
    exit 1
fi

# Safety guard: protect live/production databases
case "${DRILL_DB_NAME}" in
    *drill*|*test*)
        ;;
    *)
        echo "STRICT SAFETY ABORT: Target database name '${DRILL_DB_NAME}' must contain 'drill' or 'test'." >&2
        echo "This script is strictly for disaster recovery verification drills." >&2
        exit 1
        ;;
esac

echo "=================================================="
echo " Blue Panda Disaster Recovery Restore Drill       "
echo " Target Isolated Database: ${DRILL_DB_NAME}       "
echo " Source Archive: ${BACKUP_FILE}                   "
echo "=================================================="

if ! command -v psql >/dev/null 2>&1; then
    echo "ERROR: psql client utility not found in PATH." >&2
    exit 1
fi

# Step 1: Recreate empty drill database
echo "[1/4] Preparing clean drill database '${DRILL_DB_NAME}'..."
PGPASSWORD="${POSTGRES_PASSWORD:-}" psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d postgres -c "DROP DATABASE IF EXISTS ${DRILL_DB_NAME};"
PGPASSWORD="${POSTGRES_PASSWORD:-}" psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d postgres -c "CREATE DATABASE ${DRILL_DB_NAME};"

# Step 2: Restore backup
echo "[2/4] Restoring schema and records into '${DRILL_DB_NAME}'..."
if [[ "${BACKUP_FILE}" == *.enc ]]; then
    if [ -z "${BACKUP_ENCRYPTION_KEY_FILE:-}" ] || [ ! -f "${BACKUP_ENCRYPTION_KEY_FILE}" ]; then
        echo "ERROR: Encrypted backup detected but BACKUP_ENCRYPTION_KEY_FILE is not set or not found." >&2
        exit 1
    fi
    echo "Decrypting and restoring from AES-256-CBC encrypted archive..."
    openssl enc -d -aes-256-cbc -salt -pbkdf2 -iter 100000 \
        -in "${BACKUP_FILE}" \
        -pass "file:${BACKUP_ENCRYPTION_KEY_FILE}" | gunzip -c | PGPASSWORD="${POSTGRES_PASSWORD:-}" psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DRILL_DB_NAME}" -q
else
    gunzip -c "${BACKUP_FILE}" | PGPASSWORD="${POSTGRES_PASSWORD:-}" psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DRILL_DB_NAME}" -q
fi

# Step 3: Verify schema integrity
echo "[3/4] Verifying restored schema and data integrity..."
TABLE_COUNT=$(PGPASSWORD="${POSTGRES_PASSWORD:-}" psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DRILL_DB_NAME}" -t -A -c "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';")
USER_COUNT=$(PGPASSWORD="${POSTGRES_PASSWORD:-}" psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DRILL_DB_NAME}" -t -A -c "SELECT count(*) FROM users;")
PRODUCT_COUNT=$(PGPASSWORD="${POSTGRES_PASSWORD:-}" psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DRILL_DB_NAME}" -t -A -c "SELECT count(*) FROM products;")

echo "Restored Tables in public schema: ${TABLE_COUNT}"
echo "Restored User records: ${USER_COUNT}"
echo "Restored Product records: ${PRODUCT_COUNT}"

if [ "${TABLE_COUNT}" -lt 10 ]; then
    echo "ERROR: Restore drill failed: table count (${TABLE_COUNT}) is below expected minimum (10)." >&2
    exit 1
fi

# Step 4: Cleanup drill database
echo "[4/4] Cleaning up disposable drill database..."
PGPASSWORD="${POSTGRES_PASSWORD:-}" psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d postgres -c "DROP DATABASE ${DRILL_DB_NAME};"

echo "=================================================="
echo " Restore Drill Verdict: PASSED (Verified Clean)   "
echo "=================================================="
