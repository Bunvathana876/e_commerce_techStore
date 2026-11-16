#!/usr/bin/env bash
# ==============================================================================
# Blue Panda E-Commerce — Operator Script: Setup Least-Privilege DB User
# Grants least-privilege (DML only, no DDL/DROP) permissions to the application user.
# Can be run against a direct DATABASE_URL or through docker compose.
# ==============================================================================
set -euo pipefail

echo "=================================================="
echo " Blue Panda Least-Privilege Database Role Setup   "
echo " Time (UTC): $(date -u +"%Y-%m-%d %H:%M:%SZ")     "
echo "=================================================="

COMPOSE_FILE="deploy/production/compose.yaml"
ENV_FILE="deploy/production/.env"

if [ -f "${ENV_FILE}" ]; then
    # Load environment variables safely
    set -a
    # shellcheck disable=SC1090
    source "${ENV_FILE}"
    set +a
fi

APP_USER="${APP_DB_USER:-blue_panda_app}"
APP_PASS="${APP_DB_PASSWORD:-}"
DB_NAME="${POSTGRES_DB:-blue_panda_production}"
ADMIN_USER="${POSTGRES_USER:-postgres}"

if [ -z "${APP_PASS}" ]; then
    echo "ERROR: APP_DB_PASSWORD environment variable must be set." >&2
    echo "Usage: APP_DB_PASSWORD='secure_password' $0" >&2
    exit 1
fi

echo "Target Database: ${DB_NAME}"
echo "Admin User:      ${ADMIN_USER}"
echo "App User:        ${APP_USER}"

SQL_COMMANDS=$(cat <<EOF
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '${APP_USER}') THEN
        CREATE ROLE "${APP_USER}" WITH LOGIN PASSWORD '${APP_PASS}';
    ELSE
        ALTER ROLE "${APP_USER}" WITH PASSWORD '${APP_PASS}';
    END IF;
END
\$\$;

GRANT CONNECT ON DATABASE "${DB_NAME}" TO "${APP_USER}";
GRANT USAGE ON SCHEMA public TO "${APP_USER}";

ALTER DEFAULT PRIVILEGES FOR ROLE "${ADMIN_USER}" IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "${APP_USER}";

ALTER DEFAULT PRIVILEGES FOR ROLE "${ADMIN_USER}" IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO "${APP_USER}";

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "${APP_USER}";
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO "${APP_USER}";
EOF
)

if command -v docker >/dev/null 2>&1 && [ -f "${COMPOSE_FILE}" ] && docker compose -f "${COMPOSE_FILE}" ps postgres 2>/dev/null | grep -q "postgres"; then
    echo "Executing via running docker compose postgres service..."
    docker compose -f "${COMPOSE_FILE}" exec -T postgres psql -v ON_ERROR_STOP=1 -U "${ADMIN_USER}" -d "${DB_NAME}" <<< "${SQL_COMMANDS}"
elif command -v psql >/dev/null 2>&1 && [ -n "${DATABASE_URL:-}" ]; then
    echo "Executing via local psql client..."
    psql -v ON_ERROR_STOP=1 "${DATABASE_URL}" <<< "${SQL_COMMANDS}"
else
    echo "ERROR: Neither running postgres docker container nor psql with DATABASE_URL found." >&2
    exit 1
fi

echo "=================================================="
echo " Least-privilege permissions applied successfully!"
echo "=================================================="
