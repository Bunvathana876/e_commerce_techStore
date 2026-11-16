#!/usr/bin/env bash
# ==============================================================================
# Blue Panda E-Commerce — Approved Migration Runner
# Executes database schema migrations in a controlled, operator-verified manner.
# Migrations are NEVER run on regular application startup.
# ==============================================================================
set -euo pipefail

AUTO_APPROVE=false
USE_COMPOSE=false
for arg in "$@"; do
    case "$arg" in
        -y|--yes) AUTO_APPROVE=true ;;
        --compose) USE_COMPOSE=true ;;
    esac
done

echo "=================================================="
echo " Blue Panda Production Schema Migration Tool      "
echo " Time (UTC): $(date -u +"%Y-%m-%d %H:%M:%SZ")     "
echo "=================================================="

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="${ROOT_DIR}/deploy/production/compose.yaml"

# Check for alembic (prefer project virtualenv over system python)
ALEMBIC_BIN=""
if [ "${USE_COMPOSE}" != "true" ]; then
    if [ -f "${ROOT_DIR}/backend/.venv/bin/alembic" ]; then
        ALEMBIC_BIN="${ROOT_DIR}/backend/.venv/bin/alembic"
    elif [ -f "${ROOT_DIR}/.venv/bin/alembic" ]; then
        ALEMBIC_BIN="${ROOT_DIR}/.venv/bin/alembic"
    elif command -v alembic >/dev/null 2>&1; then
        ALEMBIC_BIN="alembic"
    fi
fi

if [ -z "${ALEMBIC_BIN}" ]; then
    if command -v docker >/dev/null 2>&1 && [ -f "${COMPOSE_FILE}" ]; then
        echo "Note: Local alembic not found. Using Docker Compose container runner..."
        USE_COMPOSE=true
    else
        echo "ERROR: alembic executable not found locally and Docker Compose is unavailable." >&2
        exit 1
    fi
fi

if [ "${USE_COMPOSE}" = "true" ]; then
    echo "Migration Mode: Docker Compose (container-isolated)"
    echo "[1/3] Checking current migration revision via container..."
    docker compose -f "${COMPOSE_FILE}" run --rm --no-deps backend alembic current || true

    echo "[2/3] Verification confirmation:"
    if [ "${AUTO_APPROVE}" != "true" ]; then
        read -r -p "Proceed with 'alembic upgrade head' in backend container? [y/N] " response
        case "$response" in
            [yY][eE][sS]|[yY]) ;;
            *)
                echo "Migration cancelled by operator."
                exit 0
                ;;
        esac
    fi

    echo "[3/3] Executing 'alembic upgrade head' inside backend container..."
    docker compose -f "${COMPOSE_FILE}" run --rm --no-deps backend alembic upgrade head

    echo "Post-migration revision:"
    docker compose -f "${COMPOSE_FILE}" run --rm --no-deps backend alembic current
    echo "=================================================="
    echo " Schema migration executed successfully.          "
    echo "=================================================="
    exit 0
fi

if [ -z "${DATABASE_URL:-}" ]; then
    echo "ERROR: DATABASE_URL environment variable must be set." >&2
    exit 1
fi

# Mask credentials for logging
MASKED_URL=$(echo "${DATABASE_URL}" | sed -E 's|://([^:]+):([^@]+)@|://\1:***@|')
echo "Target Database: ${MASKED_URL}"

# Determine alembic working directory
if [ -f "backend/alembic.ini" ]; then
    MIGRATE_DIR="backend"
elif [ -f "alembic.ini" ]; then
    MIGRATE_DIR="."
else
    echo "ERROR: alembic.ini not found in current directory or backend/." >&2
    exit 1
fi

echo "[1/3] Checking current migration revision..."
CURRENT_REV=$(cd "${MIGRATE_DIR}" && "${ALEMBIC_BIN}" current 2>&1 || true)
echo "Current Revision: ${CURRENT_REV}"

echo "[2/3] Verification confirmation:"
if [ "${AUTO_APPROVE}" != "true" ]; then
    read -r -p "Proceed with 'alembic upgrade head'? [y/N] " response
    case "$response" in
        [yY][eE][sS]|[yY]) ;;
        *)
            echo "Migration cancelled by operator."
            exit 0
            ;;
    esac
fi

echo "[3/3] Executing 'alembic upgrade head'..."
(cd "${MIGRATE_DIR}" && "${ALEMBIC_BIN}" upgrade head)

NEW_REV=$(cd "${MIGRATE_DIR}" && "${ALEMBIC_BIN}" current)
echo "Post-migration revision: ${NEW_REV}"
echo "=================================================="
echo " Schema migration executed successfully.          "
echo "=================================================="
