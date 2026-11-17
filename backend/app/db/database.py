from collections.abc import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

def _create_engine():
    url = settings.DATABASE_URL
    # SQLite (used in test isolation) does not accept QueuePool parameters
    if url.startswith("sqlite"):
        return create_engine(url, pool_pre_ping=True)

    # Normalize legacy postgres:// scheme to postgresql+psycopg2:// for SQLAlchemy 2 compatibility
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgresql://") and not url.startswith("postgresql+"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)

    connect_args: dict = {"connect_timeout": 10}
    # If connecting to Supabase or managed cloud PostgreSQL, enforce SSL if not in URL
    if ("supabase.co" in url or "supabase.com" in url) and "sslmode" not in url:
        connect_args["sslmode"] = "require"

    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT,
        pool_recycle=settings.DB_POOL_RECYCLE,
        connect_args=connect_args,
    )

engine = _create_engine()

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)

class Base(DeclarativeBase):
    pass

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    
    try:
        yield db
    finally:
        db.close()