#!/usr/bin/env bash
# ==============================================================================
# Blue Panda E-Commerce — Automated PostgreSQL Backup Script
# Performs logical database backup using pg_dump with gzip compression.
# Secrets and passwords are NEVER printed or logged.
# ==============================================================================
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
TIMESTAMP=$(date -u +"%Y%m%d_%H%M%SZ")
BACKUP_FILE="${BACKUP_DIR}/blue_panda_backup_${TIMESTAMP}.sql.gz"

mkdir -p "${BACKUP_DIR}"

echo "=================================================="
echo " Blue Panda PostgreSQL Logical Backup Pipeline    "
echo " Timestamp (UTC): ${TIMESTAMP}                    "
echo "=================================================="

# Check for pg_dump availability
if ! command -v pg_dump >/dev/null 2>&1; then
    echo "ERROR: pg_dump utility not found in PATH." >&2
    exit 1
fi

# Determine connection mode: DATABASE_URL or individual parameters
if [ -n "${DATABASE_URL:-}" ]; then
    echo "Connecting via configured DATABASE_URL (credentials masked)..."
    pg_dump "${DATABASE_URL}" --format=plain --no-owner --no-privileges | gzip -9 > "${BACKUP_FILE}"
elif [ -n "${POSTGRES_DB:-}" ]; then
    DB_HOST="${POSTGRES_HOST:-localhost}"
    DB_PORT="${POSTGRES_PORT:-5432}"
    DB_USER="${POSTGRES_USER:-ecommerce_user}"
    echo "Connecting to host=${DB_HOST} port=${DB_PORT} dbname=${POSTGRES_DB} user=${DB_USER}..."
    PGPASSWORD="${POSTGRES_PASSWORD:-}" pg_dump -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${POSTGRES_DB}" --format=plain --no-owner --no-privileges | gzip -9 > "${BACKUP_FILE}"
else
    echo "ERROR: Neither DATABASE_URL nor POSTGRES_DB environment variable is set." >&2
    exit 1
fi

# Verify backup artifact exists and is non-empty
if [ ! -s "${BACKUP_FILE}" ]; then
    echo "ERROR: Backup file ${BACKUP_FILE} was not created or is empty." >&2
    rm -f "${BACKUP_FILE}"
    exit 1
fi

# Optional: Apply AES-256-CBC PBKDF2 encryption if key file is configured
ENCRYPTED_FILE=""
if [ -n "${BACKUP_ENCRYPTION_KEY_FILE:-}" ] && [ -f "${BACKUP_ENCRYPTION_KEY_FILE}" ]; then
    echo "Encrypting backup archive with AES-256-CBC (PBKDF2)..."
    ENCRYPTED_FILE="${BACKUP_FILE}.enc"
    openssl enc -aes-256-cbc -salt -pbkdf2 -iter 100000 \
        -in "${BACKUP_FILE}" \
        -out "${ENCRYPTED_FILE}" \
        -pass "file:${BACKUP_ENCRYPTION_KEY_FILE}"
    # Securely remove unencrypted plain archive
    rm -f "${BACKUP_FILE}"
    BACKUP_FILE="${ENCRYPTED_FILE}"
fi

FILE_SIZE=$(ls -lh "${BACKUP_FILE}" | awk '{print $5}')
SHA256=$(sha256sum "${BACKUP_FILE}" 2>/dev/null || shasum -a 256 "${BACKUP_FILE}" | awk '{print $1}')

echo "Backup completed successfully!"
echo "Destination: ${BACKUP_FILE}"
echo "Archive Size: ${FILE_SIZE}"
echo "SHA256 Digest: ${SHA256}"

# Optional: Prune local backups older than retention threshold
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
if [ -n "${RETENTION_DAYS}" ] && [ "${RETENTION_DAYS}" -gt 0 ] 2>/dev/null; then
    echo "Applying retention policy: pruning backups older than ${RETENTION_DAYS} days..."
    find "${BACKUP_DIR}" -type f \( -name "blue_panda_backup_*.sql.gz" -o -name "blue_panda_backup_*.sql.gz.enc" \) -mtime +"${RETENTION_DAYS}" -exec rm -f {} +
fi

# Optional: Sync to offsite/cloud destination if configured
if [ -n "${BACKUP_OFFSITE_DESTINATION:-}" ]; then
    echo "Syncing backup to offsite destination: ${BACKUP_OFFSITE_DESTINATION}..."
    if command -v rclone >/dev/null 2>&1; then
        rclone copy "${BACKUP_FILE}" "${BACKUP_OFFSITE_DESTINATION}"
    elif command -v aws >/dev/null 2>&1; then
        aws s3 cp "${BACKUP_FILE}" "${BACKUP_OFFSITE_DESTINATION}/"
    else
        echo "WARNING: Neither rclone nor aws CLI available; offsite sync skipped." >&2
    fi
fi
echo "=================================================="
