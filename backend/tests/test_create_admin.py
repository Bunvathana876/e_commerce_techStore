"""Unit tests for backend/scripts/create_admin.py."""

import pytest
from sqlalchemy import select

from app.core.security import verify_password
from app.db.database import SessionLocal
from app.models.user import User
from scripts.create_admin import create_or_update_admin


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_create_admin_success(db_session):
    email = "new_admin@example.com"
    password = "SuperSecurePassword2026!"
    name = "Test Admin"

    user, action = create_or_update_admin(
        db=db_session,
        email=email,
        password=password,
        name=name,
        allow_weak=False,
        update_existing=False,
    )

    assert action == "created"
    assert user.id is not None
    assert user.email == email
    assert user.name == name
    assert user.role == "admin"
    assert user.is_active is True
    assert verify_password(password, user.password_hash)


def test_create_admin_rejects_invalid_email(db_session):
    with pytest.raises(ValueError, match="Invalid email address"):
        create_or_update_admin(
            db=db_session,
            email="invalid-email",
            password="SuperSecurePassword2026!",
        )


def test_create_admin_rejects_weak_password_without_flag(db_session):
    with pytest.raises(ValueError, match="Password does not meet security requirements"):
        create_or_update_admin(
            db=db_session,
            email="weak_admin@example.com",
            password="123",
            allow_weak=False,
        )


def test_create_admin_allows_weak_password_with_flag(db_session):
    user, action = create_or_update_admin(
        db=db_session,
        email="dev_admin@example.com",
        password="devpass",
        allow_weak=True,
    )
    assert action == "created"
    assert user.role == "admin"
    assert verify_password("devpass", user.password_hash)


def test_create_admin_duplicate_without_update_fails(db_session):
    email = "existing_admin@example.com"
    create_or_update_admin(
        db=db_session,
        email=email,
        password="SuperSecurePassword2026!",
    )

    with pytest.raises(ValueError, match="already exists"):
        create_or_update_admin(
            db=db_session,
            email=email,
            password="AnotherSecurePassword2026!",
            update_existing=False,
        )


def test_create_admin_promote_and_update_existing_user(db_session):
    # Create standard customer first
    email = "customer_to_promote@example.com"
    customer = User(
        name="Regular Customer",
        email=email,
        password_hash="old_hash",
        role="customer",
        is_active=True,
    )
    db_session.add(customer)
    db_session.commit()

    # Promote to admin and update password
    new_password = "PromotedAdminPassword2026!"
    updated_user, action = create_or_update_admin(
        db=db_session,
        email=email,
        password=new_password,
        name="Promoted Admin",
        update_existing=True,
    )

    assert action == "updated"
    assert updated_user.id == customer.id
    assert updated_user.role == "admin"
    assert updated_user.name == "Promoted Admin"
    assert updated_user.legacy_tokens_revoked_at is not None
    assert verify_password(new_password, updated_user.password_hash)
