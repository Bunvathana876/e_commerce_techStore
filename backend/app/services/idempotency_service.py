"""Durable per-customer checkout retries.

PostgreSQL transaction locks serialize a key across workers, including absent
rows and abandoned processing records. Acquisition and order completion share
one transaction. Replays resolve the persisted order ID using current ownership
checks. Optional cleanup prunes only completed records older than 24 hours.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.idempotency import IdempotencyRecord

logger = logging.getLogger("uvicorn.error")


class IdempotencyService:
    _ttl_seconds: float = 86400.0  # 24 hours
    _processing_timeout_seconds: float = 60.0  # Recovery age for unlocked processing records

    @classmethod
    def validate_key(cls, key: str | None) -> str | None:
        """Validate and sanitize an idempotency key string."""
        if key is None:
            return None
        cleaned = key.strip()
        if not cleaned:
            return None
        if len(cleaned) > 255:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Idempotency key must not exceed 255 characters.",
            )
        # Prevent control characters or unprintable characters
        if any(ord(ch) < 32 or ord(ch) == 127 for ch in cleaned):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Idempotency key contains invalid control characters.",
            )
        return cleaned

    @classmethod
    def _is_stale(cls, dt: datetime, timeout_seconds: float) -> bool:
        """Check if a timestamp is older than timeout_seconds, handling naive and aware datetimes."""
        if dt.tzinfo is None:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
        else:
            now = datetime.now(timezone.utc)
        return (now - dt).total_seconds() > timeout_seconds

    @classmethod
    def clean_expired(cls, db: Session | None = None) -> None:
        """Prune expired idempotency records older than the TTL."""
        if db is None:
            with SessionLocal() as local_db:
                cls.clean_expired(local_db)
                return

        cutoff = datetime.now(timezone.utc) - timedelta(seconds=cls._ttl_seconds)
        try:
            db.execute(
                delete(IdempotencyRecord).where(
                    IdempotencyRecord.created_at < cutoff,
                    IdempotencyRecord.status == "completed",
                )
            )
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.warning("Failed to prune expired idempotency records: %s", exc)

    @classmethod
    def reset(cls, db: Session | None = None) -> None:
        """Reset all idempotency records in the database (used for test isolation)."""
        if db is None:
            with SessionLocal() as local_db:
                cls.reset(local_db)
                return
        try:
            db.execute(delete(IdempotencyRecord))
            db.commit()
        except Exception:
            db.rollback()
            raise

    @classmethod
    def check_or_acquire(
        cls,
        first_arg: Session | int | None = None,
        second_arg: int | str | None = None,
        third_arg: str | None = None,
        *,
        db: Session | None = None,
        user_id: int | None = None,
        key: str | None = None,
    ) -> tuple[bool, dict[str, Any] | None]:
        """
        Check if an idempotency key has already completed or is currently in-progress.

        Accepts either:
            check_or_acquire(db, user_id, key)
            check_or_acquire(user_id=2, key="...")
            check_or_acquire(user_id, key, db=db)
            check_or_acquire(db=db, user_id=user_id, key=key)

        A supplied session retains the lock until its caller commits or rolls
        back. Without a session this reserves a standalone processing record.

        Returns:
            (is_replay, cached_response_data)
            - If is_replay is True: cached_response_data is the completed order payload.
            - If is_replay is False: key was successfully acquired with 'processing' lock.

        Raises:
            HTTPException 409 Conflict if key is currently in 'processing' state by an active worker.
        """
        actual_db: Session | None = None
        actual_user_id: int | None = None
        actual_key: str | None = None

        if isinstance(first_arg, Session):
            actual_db = first_arg
            if isinstance(second_arg, int):
                actual_user_id = second_arg
            if isinstance(third_arg, str):
                actual_key = third_arg
        elif isinstance(first_arg, int):
            actual_user_id = first_arg
            if isinstance(second_arg, str):
                actual_key = second_arg

        if db is not None:
            actual_db = db
        if user_id is not None:
            actual_user_id = user_id
        if key is not None:
            actual_key = key

        assert actual_user_id is not None, "user_id must be provided"
        assert actual_key is not None, "key must be provided"

        if actual_db is None:
            with SessionLocal() as local_db:
                result = cls._check_or_acquire_impl(local_db, actual_user_id, actual_key)
                local_db.commit()
                return result

        return cls._check_or_acquire_impl(actual_db, actual_user_id, actual_key)

    @classmethod
    def _check_or_acquire_impl(
        cls, db: Session, user_id: int, key: str
    ) -> tuple[bool, dict[str, Any] | None]:
        if db.get_bind().dialect.name == "postgresql":
            # Protect absent rows too, without waiting on a concurrent INSERT.
            # A stable, namespaced digest works across processes and hosts.
            digest = hashlib.sha256(f"checkout:{user_id}:{key}".encode()).digest()
            lock_id = int.from_bytes(digest[:8], "big", signed=True)
            if not db.scalar(select(func.pg_try_advisory_xact_lock(lock_id))):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A checkout request with this idempotency key is currently processing. Please wait.",
                )
        if db.get_bind().dialect.name == "sqlite":
            connection = db.connection()
            if not connection.connection.driver_connection.in_transaction:
                # SQLite's legacy driver does not BEGIN for SELECT/SAVEPOINT.
                # Without an explicit transaction, releasing the insert's
                # savepoint would persist the key even if checkout rolls back.
                connection.exec_driver_sql("BEGIN IMMEDIATE")
        # Keep the row lock until the caller commits the order. A timestamp is
        # not evidence that a worker has died; a live transaction must retain
        # exclusive ownership even after the processing timeout.
        stmt = select(IdempotencyRecord).where(
            IdempotencyRecord.user_id == user_id,
            IdempotencyRecord.key == key,
        ).with_for_update(nowait=True).execution_options(populate_existing=True)

        def locked_record() -> IdempotencyRecord | None:
            try:
                return db.scalar(stmt)
            except OperationalError as exc:
                if getattr(exc.orig, "pgcode", None) != "55P03":
                    raise
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A checkout request with this idempotency key is currently processing. Please wait.",
                ) from exc

        rec = locked_record()
        if rec is None:
            try:
                with db.begin_nested():
                    db.add(IdempotencyRecord(user_id=user_id, key=key, status="processing"))
                    db.flush()
                # No commit here: acquisition and order completion share a
                # transaction, so a crash rolls back both together.
                return False, None
            except IntegrityError:
                # A competing insert may have committed while we waited on
                # the unique constraint. Re-read its result under a row lock.
                rec = locked_record()

        if rec is not None and rec.status == "completed":
            cached_data = json.loads(rec.response_data) if rec.response_data else None
            if cached_data is None and rec.order_id:
                cached_data = {"id": rec.order_id}
            return True, cached_data

        if rec is not None and rec.status == "processing" and cls._is_stale(
            rec.created_at, cls._processing_timeout_seconds
        ):
            now = datetime.now(timezone.utc)
            rec.created_at = now
            rec.updated_at = now
            db.flush()
            return False, None

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A checkout request with this idempotency key is currently processing. Please wait.",
        )

    @classmethod
    def complete(
        cls,
        first_arg: Session | int | None = None,
        second_arg: int | str | None = None,
        third_arg: str | int | None = None,
        fourth_arg: int | dict[str, Any] | None = None,
        fifth_arg: dict[str, Any] | None = None,
        *,
        db: Session | None = None,
        user_id: int | None = None,
        key: str | None = None,
        order_id: int | None = None,
        response_data: dict[str, Any] | None = None,
    ) -> None:
        """
        Mark an idempotency key as successfully completed and cache the order response.

        Accepts either:
            complete(db, user_id, key, order_id, response_data)
            complete(user_id, key, order_id, response_data, db=db)
            complete(user_id=user_id, key=key, order_id=order_id, response_data=response_data)
        """
        actual_db: Session | None = None
        actual_user_id: int | None = None
        actual_key: str | None = None
        actual_order_id: int | None = None
        actual_response_data: dict[str, Any] | None = None

        if isinstance(first_arg, Session):
            actual_db = first_arg
            if isinstance(second_arg, int):
                actual_user_id = second_arg
            if isinstance(third_arg, str):
                actual_key = third_arg
            if isinstance(fourth_arg, int):
                actual_order_id = fourth_arg
            if isinstance(fifth_arg, dict):
                actual_response_data = fifth_arg
        elif isinstance(first_arg, int):
            actual_user_id = first_arg
            if isinstance(second_arg, str):
                actual_key = second_arg
            if isinstance(third_arg, int):
                actual_order_id = third_arg
            if isinstance(fourth_arg, dict):
                actual_response_data = fourth_arg

        if db is not None:
            actual_db = db
        if user_id is not None:
            actual_user_id = user_id
        if key is not None:
            actual_key = key
        if order_id is not None:
            actual_order_id = order_id
        if response_data is not None:
            actual_response_data = response_data

        assert actual_user_id is not None, "user_id must be provided"
        assert actual_key is not None, "key must be provided"
        assert actual_order_id is not None, "order_id must be provided"
        if actual_response_data is None:
            actual_response_data = {}

        if actual_db is None:
            with SessionLocal() as local_db:
                cls._complete_impl(local_db, actual_user_id, actual_key, actual_order_id, actual_response_data)
                return

        cls._complete_impl(actual_db, actual_user_id, actual_key, actual_order_id, actual_response_data)

    @classmethod
    def _complete_impl(
        cls,
        db: Session,
        user_id: int,
        key: str,
        order_id: int,
        response_data: dict[str, Any],
    ) -> None:
        stmt = select(IdempotencyRecord).where(
            IdempotencyRecord.user_id == user_id,
            IdempotencyRecord.key == key,
        )
        rec = db.scalar(stmt)
        if rec is not None:
            rec.status = "completed"
            rec.order_id = order_id
            rec.response_data = json.dumps(response_data, default=str)
            rec.updated_at = datetime.now(timezone.utc)
            db.commit()

    @classmethod
    def release(
        cls,
        first_arg: Session | int | None = None,
        second_arg: int | str | None = None,
        third_arg: str | None = None,
        *,
        db: Session | None = None,
        user_id: int | None = None,
        key: str | None = None,
    ) -> None:
        """
        Release a processing lock if order creation encountered an error so the caller can retry.

        Accepts either:
            release(db, user_id, key)
            release(user_id, key, db=db)
            release(user_id=user_id, key=key)
        """
        actual_db: Session | None = None
        actual_user_id: int | None = None
        actual_key: str | None = None

        if isinstance(first_arg, Session):
            actual_db = first_arg
            if isinstance(second_arg, int):
                actual_user_id = second_arg
            if isinstance(third_arg, str):
                actual_key = third_arg
        elif isinstance(first_arg, int):
            actual_user_id = first_arg
            if isinstance(second_arg, str):
                actual_key = second_arg

        if db is not None:
            actual_db = db
        if user_id is not None:
            actual_user_id = user_id
        if key is not None:
            actual_key = key

        assert actual_user_id is not None, "user_id must be provided"
        assert actual_key is not None, "key must be provided"

        if actual_db is None:
            with SessionLocal() as local_db:
                cls._release_impl(local_db, actual_user_id, actual_key)
                return

        cls._release_impl(actual_db, actual_user_id, actual_key)

    @classmethod
    def _release_impl(cls, db: Session, user_id: int, key: str) -> None:
        stmt = select(IdempotencyRecord).where(
            IdempotencyRecord.user_id == user_id,
            IdempotencyRecord.key == key,
        )
        rec = db.scalar(stmt)
        if rec is not None and rec.status == "processing":
            db.delete(rec)
            db.commit()
