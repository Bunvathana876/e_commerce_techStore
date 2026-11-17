#!/bin/sh
set -e

echo "========================================="
echo " Starting FastAPI E-Commerce Backend...  "
echo "========================================="

# [1/2] Wait for database connectivity before launching FastAPI
echo "[1/2] Verifying database connectivity..."
python -c "
import os, sys, time
from sqlalchemy import create_engine, text

url = os.getenv('DATABASE_URL')
if not url:
    print('WARNING: DATABASE_URL is not set. Proceeding without connection check.')
    sys.exit(0)

# Mask credentials for clean and safe logging
masked = url.split('@')[-1] if '@' in url else '***'
print(f'Checking database reachability at: ...@{masked}')

max_retries = int(os.getenv('DB_WAIT_RETRIES', '20'))
retry_interval = int(os.getenv('DB_WAIT_INTERVAL', '2'))

for attempt in range(1, max_retries + 1):
    try:
        engine = create_engine(url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text('SELECT 1'))
        print('Database connection successful.')
        sys.exit(0)
    except Exception as exc:
        print(f'Waiting for database (attempt {attempt}/{max_retries})...')
        time.sleep(retry_interval)

print('ERROR: Unable to connect to database after retries.', file=sys.stderr)
sys.exit(1)
"

# [2/2] Migrations handling:
# Schema migrations must NOT run automatically on regular container startup.
# To execute migrations manually when needed:
#   docker compose run --rm backend alembic upgrade head
if [ "${RUN_MIGRATIONS_ON_STARTUP:-false}" = "true" ]; then
    echo "Notice: RUN_MIGRATIONS_ON_STARTUP=true. Applying database migrations..."
    alembic upgrade head
else
    echo "[2/2] Automatic database migrations and demo seeding are disabled (schema protected)."
fi

# If an operator passes a custom command (e.g. 'alembic current', 'pytest', 'bash'):
if [ $# -gt 0 ] && [ "${1#-}" = "$1" ]; then
    echo "Executing custom command: $*"
    exec "$@"
fi

# Launch Uvicorn ASGI Server with hot-reload enabled for development
echo "Starting Uvicorn ASGI server on port 8000..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload "$@"
