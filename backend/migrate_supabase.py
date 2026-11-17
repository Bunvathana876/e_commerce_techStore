
import os
import subprocess

from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

database_url = dotenv_values(".env.supabase").get("DATABASE_URL")

if not database_url:
    raise SystemExit("STOP: Supabase DATABASE_URL missing")

url = make_url(database_url)

# Protect the local ecommerce_db database.
if not (
    url.host
    and url.host.endswith(".pooler.supabase.com")
    and url.database == "postgres"
    and url.port == 5432
    and url.username
    and url.username.startswith("postgres.")
):
    raise SystemExit("STOP: Unexpected database target")

# Verify the actual database connection.
engine = create_engine(
    url,
    connect_args={"connect_timeout": 10},
)

with engine.connect() as connection:
    identity = connection.execute(
        text("SELECT current_database(), current_user")
    ).one()

    existing_tables = connection.execute(
        text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
    ).scalars().all()

engine.dispose()

print("Verified Supabase host:", url.host)
print("Database:", identity[0])
print("Username:", identity[1])
print("Existing public tables:", existing_tables)

if existing_tables:
    raise SystemExit(
        "STOP: Public schema already contains tables. "
        "Review before applying migrations."
    )

# Explicit confirmation.
confirmation = input(
    "\nType MIGRATE SUPABASE to create the tables: "
)

if confirmation != "MIGRATE SUPABASE":
    raise SystemExit("Migration cancelled")

env = os.environ.copy()
env["DATABASE_URL"] = database_url

# Apply migrations only after verification and confirmation.
subprocess.run(
    ["alembic", "upgrade", "head"],
    env=env,
    check=True,
)

print("\nSupabase migration completed!")
