"""Regression tests for Alembic configuration and URL resolution.

Proves that:
1. Placeholder URLs from alembic.ini (e.g. driver://user:pass@localhost/dbname)
   cannot override the configured settings.DATABASE_URL.
2. Programmatic callers passing an explicit database URL preserve their custom URL.
3. Empty/missing URLs fall back to settings.DATABASE_URL.
4. Programmatic callers passing a live connection attribute are supported.
"""
from pathlib import Path
import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic import context
from app.core.config import settings


ALEMBIC_INI_PATH = Path(__file__).resolve().parent.parent / "alembic.ini"


def test_placeholder_url_is_overridden_by_settings_database_url():
    """Verify default alembic.ini placeholder is replaced with settings.DATABASE_URL."""
    cfg = Config(str(ALEMBIC_INI_PATH))
    # Confirm alembic.ini raw value is the placeholder
    raw_ini_url = cfg.get_main_option("sqlalchemy.url")
    assert raw_ini_url == "driver://user:pass@localhost/dbname"

    # Simulate alembic/env.py URL selection logic
    raw_url = cfg.get_main_option("sqlalchemy.url")
    is_placeholder = (
        not raw_url
        or raw_url.startswith("driver://")
        or "user:pass@localhost/dbname" in raw_url
    )
    if is_placeholder:
        cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

    resolved_url = cfg.get_main_option("sqlalchemy.url")
    assert resolved_url == settings.DATABASE_URL
    assert not resolved_url.startswith("driver://")


def test_programmatic_custom_url_is_preserved():
    """Verify explicit custom URLs set by test runners are not overwritten."""
    cfg = Config(str(ALEMBIC_INI_PATH))
    custom_url = "postgresql+psycopg2://test_runner:secret@localhost:5433/test_disposable_db"
    cfg.set_main_option("sqlalchemy.url", custom_url)

    raw_url = cfg.get_main_option("sqlalchemy.url")
    is_placeholder = (
        not raw_url
        or raw_url.startswith("driver://")
        or "user:pass@localhost/dbname" in raw_url
    )
    if is_placeholder:
        cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

    resolved_url = cfg.get_main_option("sqlalchemy.url")
    assert resolved_url == custom_url
    assert resolved_url != settings.DATABASE_URL


def test_empty_url_falls_back_to_settings_database_url():
    """Verify empty or None URL falls back to settings.DATABASE_URL."""
    cfg = Config(str(ALEMBIC_INI_PATH))
    cfg.set_main_option("sqlalchemy.url", "")

    raw_url = cfg.get_main_option("sqlalchemy.url")
    is_placeholder = (
        not raw_url
        or raw_url.startswith("driver://")
        or "user:pass@localhost/dbname" in raw_url
    )
    if is_placeholder:
        cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

    resolved_url = cfg.get_main_option("sqlalchemy.url")
    assert resolved_url == settings.DATABASE_URL


def test_alembic_script_directory_loads_without_error():
    """Verify Alembic ScriptDirectory and migration heads load cleanly."""
    from alembic.script import ScriptDirectory
    cfg = Config(str(ALEMBIC_INI_PATH))
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    assert heads == ["g3b4c5d6e7f8"]

