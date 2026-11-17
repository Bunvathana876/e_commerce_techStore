
from getpass import getpass

from sqlalchemy import create_engine, text # pyright: ignore[reportMissingImports]
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError

print("Blue Panda — Supabase Connection Test")

host = input("Supabase Session Pooler Host: ").strip()
port = int(input("Port [5432]: ").strip() or "5432")
username = input("Database Username: ").strip()
password = getpass("Database Password: ")

url = URL.create(
    "postgresql+psycopg2",
    username=username,
    password=password,
    host=host,
    port=port,
    database="postgres",
    query={"sslmode": "require"},
)

try:
    engine = create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 10},
    )

    with engine.connect() as connection:
        result = connection.execute(
            text("SELECT current_database(), current_user")
        ).one()

        print("Connected successfully!")
        print("Database:", result[0])
        print("Username:", result[1])

    engine.dispose()

except SQLAlchemyError as exc:
    print("Connection failed:", type(exc).__name__)
    print("Check the host, username, password and network.")
    print("Error details:", str(exc).splitlines()[0])
