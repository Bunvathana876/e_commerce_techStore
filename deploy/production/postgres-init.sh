#!/usr/bin/env bash
# ==============================================================================
# Blue Panda E-Commerce — PostgreSQL Initialization Script
# Executed automatically by PostgreSQL container when creating a fresh database.
# Configures a least-privilege application role (DML only, no DDL/DROP).
# ==============================================================================
set -euo pipefail

APP_USER="${APP_DB_USER:-blue_panda_app}"
APP_PASS="${APP_DB_PASSWORD:-}"
DB_NAME="${POSTGRES_DB:-blue_panda_production}"
ADMIN_USER="${POSTGRES_USER:-postgres}"

if [ -n "${APP_PASS}" ]; then
    echo ">> [postgres-init] Provisioning least-privilege application role: '${APP_USER}' on database '${DB_NAME}'..."
    psql -v ON_ERROR_STOP=1 --username "${ADMIN_USER}" --dbname "${DB_NAME}" <<-EOSQL
        -- Create application role if it does not already exist
        DO \$\$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '${APP_USER}') THEN
                CREATE ROLE "${APP_USER}" WITH LOGIN PASSWORD '${APP_PASS}';
            ELSE
                ALTER ROLE "${APP_USER}" WITH PASSWORD '${APP_PASS}';
            END IF;
        END
        \$\$;

        -- Database & Schema connection and usage
        GRANT CONNECT ON DATABASE "${DB_NAME}" TO "${APP_USER}";
        GRANT USAGE ON SCHEMA public TO "${APP_USER}";

        -- Default privileges: Automatically grant DML (SELECT, INSERT, UPDATE, DELETE)
        -- on future tables and sequences created by the migration owner (${ADMIN_USER})
        ALTER DEFAULT PRIVILEGES FOR ROLE "${ADMIN_USER}" IN SCHEMA public
            GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "${APP_USER}";

        ALTER DEFAULT PRIVILEGES FOR ROLE "${ADMIN_USER}" IN SCHEMA public
            GRANT USAGE, SELECT ON SEQUENCES TO "${APP_USER}";

        -- Grant on existing objects if already created
        GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "${APP_USER}";
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO "${APP_USER}";
EOSQL
    echo ">> [postgres-init] Role '${APP_USER}' successfully configured with least-privilege permissions."
else
    echo ">> [postgres-init] Note: APP_DB_PASSWORD not set; skipping automatic creation of '${APP_USER}'."
fi
