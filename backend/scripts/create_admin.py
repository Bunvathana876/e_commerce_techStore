"""Admin user creation and password management CLI.

Usage examples:
  Interactive:
    cd backend && python3 -m scripts.create_admin

  Direct arguments:
    cd backend && python3 -m scripts.create_admin --email admin@example.com --password "MySecurePassword123!" --name "Main Admin"

  Reset password / promote existing account:
    cd backend && python3 -m scripts.create_admin --email admin@example.com --password "NewPassword123!" --update
"""

import argparse
from datetime import datetime, timezone
import getpass
import os
from pathlib import Path
import sys

# Ensure backend root is in sys.path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from dotenv import dotenv_values
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.password_policy import validate_password_strength
from app.core.security import hash_password
from app.models.user import User


def get_db_session() -> Session:
    """Resolve database URL and initialize SQLAlchemy session."""
    env_file = backend_root / ".env"
    db_url = os.environ.get("DATABASE_URL")
    if not db_url and env_file.exists():
        env_config = dotenv_values(env_file)
        db_url = env_config.get("DATABASE_URL")

    if not db_url:
        root_env = backend_root.parent / ".env"
        if root_env.exists():
            root_config = dotenv_values(root_env)
            db_url = root_config.get("DATABASE_URL")

    if not db_url:
        raise RuntimeError("DATABASE_URL not found in environment or .env files.")

    engine = create_engine(db_url, pool_pre_ping=True)
    SessionFactory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return SessionFactory()


def create_or_update_admin(
    db: Session,
    email: str,
    password: str,
    name: str = "Admin User",
    phone: str | None = None,
    allow_weak: bool = False,
    update_existing: bool = False,
) -> tuple[User, str]:
    """Create a new admin user or update existing user to admin.

    Returns:
        tuple[User, str]: (User instance, action taken description)
    """
    clean_email = email.lower().strip()
    if not clean_email or "@" not in clean_email or "." not in clean_email:
        raise ValueError(f"Invalid email address: '{email}'")

    if not password:
        raise ValueError("Password cannot be empty.")

    if not allow_weak:
        is_valid, error_msg = validate_password_strength(password)
        if not is_valid:
            raise ValueError(
                f"Password does not meet security requirements: {error_msg} "
                "(use --allow-weak to bypass in development)"
            )

    pwd_hash = hash_password(password)
    now = datetime.now(timezone.utc)

    existing_user = db.scalar(select(User).where(User.email == clean_email))

    if existing_user:
        if not update_existing:
            raise ValueError(
                f"User with email '{clean_email}' already exists with role='{existing_user.role}'. "
                "Use --update flag to reset password and promote/ensure admin role."
            )

        existing_user.password_hash = pwd_hash
        existing_user.role = "admin"
        existing_user.is_active = True
        existing_user.legacy_tokens_revoked_at = now
        if name and name != "Admin User":
            existing_user.name = name.strip()
        if phone:
            existing_user.phone = phone.strip()

        db.commit()
        db.refresh(existing_user)
        return existing_user, "updated"

    new_user = User(
        name=name.strip() if name else "Admin User",
        email=clean_email,
        password_hash=pwd_hash,
        phone=phone.strip() if phone else None,
        role="admin",
        is_active=True,
        legacy_tokens_revoked_at=now,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user, "created"


def main():
    parser = argparse.ArgumentParser(description="Create or update an admin user for the management website.")
    parser.add_argument("--email", "-e", help="Admin email address")
    parser.add_argument("--password", "-p", help="Admin password (leave blank to be prompted securely)")
    parser.add_argument("--name", "-n", default="Admin User", help="Admin full name (default: 'Admin User')")
    parser.add_argument("--phone", help="Admin phone number (optional)")
    parser.add_argument(
        "--update", "-u", action="store_true", help="Update password/role if user already exists"
    )
    parser.add_argument(
        "--allow-weak", action="store_true", help="Allow passwords that do not pass NIST strength checks"
    )

    args = parser.parse_args()

    email = args.email
    password = args.password
    name = args.name
    phone = args.phone
    update = args.update
    allow_weak = args.allow_weak

    # Interactive prompts if required arguments are missing
    if not email:
        try:
            email = input("Admin Email: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            sys.exit(1)

    if not password:
        try:
            password = getpass.getpass("Admin Password: ")
            confirm = getpass.getpass("Confirm Password: ")
            if password != confirm:
                print("Error: Passwords do not match.")
                sys.exit(1)
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            sys.exit(1)

    try:
        db = get_db_session()
        user, action = create_or_update_admin(
            db=db,
            email=email,
            password=password,
            name=name,
            phone=phone,
            allow_weak=allow_weak,
            update_existing=update,
        )

        print("\n" + "=" * 60)
        print(f"SUCCESS: Admin account successfully {action}!")
        print("=" * 60)
        print(f"  Name:   {user.name}")
        print(f"  Email:  {user.email}")
        print(f"  Role:   {user.role}")
        print(f"  Status: {'Active' if user.is_active else 'Inactive'}")
        print("=" * 60)
        print("You can now log in to the Blue Panda Management Website:")
        print("  Management URL: http://localhost:3001")
        print("  Admin Portal:   http://localhost:3001/admin/dashboard")
        print("  Login Page:     http://localhost:3001/login")
        print("=" * 60 + "\n")
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
