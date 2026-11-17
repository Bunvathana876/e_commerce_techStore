"""Actual PostgreSQL lock/rollback tests on a TCP-disabled temporary cluster."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import secrets
from threading import Barrier

from fastapi import HTTPException
import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker

from app.core.security import decode_access_token, hash_refresh_token, verify_password
from app.db.database import Base
from app.models.session import RefreshToken, UserSession
from app.models.user import User
from app.schemas.auth import ChangePasswordRequest
from app.services.auth_service import AuthService
from app.services.auth_session_service import AuthSessionService, utc_now

@pytest.fixture(autouse=True)
def enable_modern_sessions_for_security_tests(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "AUTH_ISSUE_SESSION_TOKENS", True)



@pytest.fixture
def auth_pg(pg_cluster, password_hash):
    cluster_engine, data_dir = pg_cluster
    database_name = "bp_auth_" + secrets.token_hex(6)
    with cluster_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        assert conn.exec_driver_sql("SHOW listen_addresses").scalar_one() == ""
        assert conn.exec_driver_sql("SHOW data_directory").scalar_one() == str(data_dir)
        conn.execute(text(f'CREATE DATABASE "{database_name}"'))
    engine = create_engine(cluster_engine.url.set(database=database_name), pool_size=8)
    factory = sessionmaker(bind=engine, autoflush=False)
    try:
        Base.metadata.create_all(engine)
        with factory() as db:
            db.add(User(id=1, name="Session Fixture", email="session@example.com", password_hash=password_hash, role="customer", is_active=True))
            db.commit()
        yield factory
    finally:
        engine.dispose()
        with cluster_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text(f'DROP DATABASE "{database_name}" WITH (FORCE)'))


def issue(factory):
    with factory() as db:
        result = AuthSessionService.issue(db, AuthSessionService.lock_user(db, 1), True)
        db.commit()
        return result


def test_concurrent_same_refresh_has_one_winner_then_durable_replay_revocation(auth_pg):
    original = issue(auth_pg)
    barrier = Barrier(2, timeout=10)

    def attempt(_):
        with auth_pg() as db:
            barrier.wait()
            try:
                AuthSessionService.refresh(db, original.refresh_token)
                return 200
            except HTTPException as exc:
                return exc.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, range(2)))
    assert sorted(results) == [200, 401]
    with auth_pg() as db:
        session = db.scalar(select(UserSession))
        assert session.is_revoked
        assert session.revoked_reason == "token_reuse"
        assert db.scalar(select(func.count(RefreshToken.id))) == 2
        assert all(token.is_revoked for token in db.scalars(select(RefreshToken)))


@pytest.mark.parametrize("mutation", ["logout", "password"])
def test_refresh_racing_revocation_cannot_leave_active_descendants(auth_pg, mutation):
    original = issue(auth_pg)
    session_id = decode_access_token(original.access_token)["session_id"]
    barrier = Barrier(2, timeout=10)

    def refresh():
        with auth_pg() as db:
            barrier.wait()
            try:
                AuthSessionService.refresh(db, original.refresh_token)
                return 200
            except HTTPException as exc:
                return exc.status_code

    def revoke():
        with auth_pg() as db:
            barrier.wait()
            if mutation == "logout":
                AuthSessionService.logout(db, 1, session_id)
            else:
                AuthService.change_password(db, db.get(User, 1), ChangePasswordRequest(
                    current_password="Fixture-password-123", new_password="Concurrent-replacement-456",
                ))

    with ThreadPoolExecutor(max_workers=2) as pool:
        pending_refresh, pending_revoke = pool.submit(refresh), pool.submit(revoke)
        assert pending_refresh.result() in {200, 401}
        pending_revoke.result()
    with auth_pg() as db:
        assert db.scalar(select(UserSession)).is_revoked
        assert all(token.is_revoked for token in db.scalars(select(RefreshToken)))
        with pytest.raises(HTTPException) as error:
            AuthSessionService.validate_access(db, db.get(User, 1), original.access_token, decode_access_token(original.access_token))
        assert error.value.status_code == 401


def test_failed_rotation_commit_rolls_back_consumption_and_replacement(auth_pg, monkeypatch):
    original = issue(auth_pg)
    with auth_pg() as db:
        def failed_commit():
            raise RuntimeError("Injected database commit failure")
        monkeypatch.setattr(db, "commit", failed_commit)
        with pytest.raises(RuntimeError, match="Injected database commit failure"):
            AuthSessionService.refresh(db, original.refresh_token)
        db.rollback()
    with auth_pg() as db:
        token = db.scalar(select(RefreshToken))
        assert token.used_at is None
        assert not token.is_revoked
        assert not db.scalar(select(UserSession)).is_revoked
        assert db.scalar(select(func.count(RefreshToken.id))) == 1
    with auth_pg() as db:
        assert AuthSessionService.refresh(db, original.refresh_token).refresh_token is not None


def test_password_change_and_revocation_rollback_together(auth_pg, monkeypatch):
    original = issue(auth_pg)
    with auth_pg() as db:
        def failed_commit():
            raise RuntimeError("Injected database commit failure")
        monkeypatch.setattr(db, "commit", failed_commit)
        with pytest.raises(RuntimeError, match="Injected database commit failure"):
            AuthService.change_password(db, db.get(User, 1), ChangePasswordRequest(
                current_password="Fixture-password-123", new_password="Rollback-replacement-456",
            ))
        db.rollback()
    with auth_pg() as db:
        assert verify_password("Fixture-password-123", db.get(User, 1).password_hash)
        assert db.get(User, 1).legacy_tokens_revoked_at is None
        assert not db.scalar(select(UserSession)).is_revoked
        assert not db.scalar(select(RefreshToken)).is_revoked
        assert AuthSessionService.refresh(db, original.refresh_token).access_token


def test_refresh_near_absolute_expiration_does_not_extend_session(auth_pg):
    original = issue(auth_pg)
    with auth_pg() as db:
        expiration = utc_now() + timedelta(seconds=30)
        db.scalar(select(UserSession)).expires_at = expiration
        db.scalar(select(RefreshToken)).expires_at = expiration
        db.commit()
    with auth_pg() as db:
        result = AuthSessionService.refresh(db, original.refresh_token)
        assert 0 < result.expires_in <= 30
        assert db.scalar(select(UserSession)).expires_at == expiration
        replacement = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(result.refresh_token)))
        assert replacement.expires_at == expiration
