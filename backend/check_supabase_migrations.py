
import os
import subprocess

from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

config = dotenv_values(".env.supabase")
database_url = config.get("DATABASE_URL")

if not database_url:
    raise SystemExit("DATABASE_URL missing in .env.supabase")

url = make_url(database_url)

if (
    url.database != "postgres"
    or not (url.host or "").endswith(".pooler.supabase.com")
    or not (url.username or "").startswith("postgres.")
):
    raise SystemExit("Stopped: unexpected database target")

print("Host:", url.host)
print("Database:", url.database)

engine = create_engine(
    url,
    connect_args={"connect_timeout": 10},
)

with engine.connect() as connection:
    database = connection.execute(
        text("SELECT current_database()")
    ).scalar_one()

    tables = connection.execute(
        text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
    ).scalars().all()

    print("Connected database:", database)
    print("Existing public tables:", tables)

engine.dispose()

env = os.environ.copy()
env["DATABASE_URL"] = database_url

print("\nLocal migration head:")
subprocess.run(
    ["alembic", "heads"],
    env=env,
    check=True,
)

print("\nCurrent Supabase migration:")
subprocess.run(
    ["alembic", "current"],
    env=env,
    check=True,
)
