from app.core.config import settings
from app.core.dependencies import require_roles
from app.core.rate_limit import RateLimiter
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.services.auth_session_service import AuthSessionService

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", status_code=status.HTTP_200_OK)
def list_users(
    role: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    query = select(User)
    if role:
        query = query.where(User.role == role)
    query = query.order_by(User.id.desc())

    users = list(db.scalars(query).all())
    return {
        "success": True,
        "message": "Users retrieved successfully.",
        "data": [UserResponse.model_validate(u).model_dump() for u in users],
    }


@router.get("/{user_id}", status_code=status.HTTP_200_OK)
def get_user_by_id(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    user = db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    return {
        "success": True,
        "message": "User retrieved successfully.",
        "data": UserResponse.model_validate(user).model_dump(),
    }


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RateLimiter(times=settings.RATE_LIMIT_SENSITIVE_MUTATIONS, seconds=60, scope="users:create", user_scoped=True))],
)
def create_user(
    request: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    from app.core.security import hash_password

    existing = db.scalar(select(User).where(User.email == request.email.lower().strip()))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists.",
        )

    user = User(
        name=request.name.strip(),
        email=request.email.lower().strip(),
        password_hash=hash_password(request.password),
        phone=request.phone.strip() if request.phone else None,
        avatar=request.avatar.strip() if request.avatar else None,
        role=request.role or "customer",
        is_active=request.is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "success": True,
        "message": f"User {user.name} created successfully.",
        "data": UserResponse.model_validate(user).model_dump(),
    }


@router.put(
    "/{user_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RateLimiter(times=settings.RATE_LIMIT_SENSITIVE_MUTATIONS, seconds=60, scope="users:update", user_scoped=True))],
)
def update_user(
    user_id: int,
    request: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    from app.core.security import hash_password

    user = db.scalar(select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    if request.name is not None:
        user.name = request.name.strip()
    if request.email is not None:
        conflict = db.scalar(
            select(User).where(
                User.email == request.email.lower().strip(),
                User.id != user_id,
            )
        )
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is already used by another user.",
            )
        user.email = request.email.lower().strip()
    if request.phone is not None:
        user.phone = request.phone.strip() if request.phone.strip() else None
    if request.avatar is not None:
        user.avatar = request.avatar.strip() if request.avatar.strip() else None
    if request.role is not None:
        user.role = request.role.strip()
    if request.is_active is not None:
        user.is_active = request.is_active
    if request.password is not None and len(request.password.strip()) >= 6:
        user.password_hash = hash_password(request.password.strip())
        AuthSessionService.revoke_all(db, user, "password_changed")

    db.commit()
    db.refresh(user)

    return {
        "success": True,
        "message": f"User #{user.id} updated successfully.",
        "data": UserResponse.model_validate(user).model_dump(),
    }


@router.delete("/{user_id}", status_code=status.HTTP_200_OK)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    user = db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    
    db.delete(user)
    db.commit()

    return {
        "success": True,
        "message": f"User #{user_id} deleted successfully.",
        "data": None,
    }

