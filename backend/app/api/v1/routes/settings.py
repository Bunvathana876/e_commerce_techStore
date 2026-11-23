from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_roles
from app.db.database import get_db
from app.models.user import User
from app.schemas.settings import StoreSettingsUpdate
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("/public", status_code=status.HTTP_200_OK)
def get_public_store_settings(db: Session = Depends(get_db)):
    data = SettingsService.get_public_settings(db)
    return {
        "success": True,
        "message": "Public store settings retrieved successfully.",
        "data": data.model_dump(),
    }


@router.get("", status_code=status.HTTP_200_OK)
def get_admin_store_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    data = SettingsService.get_admin_settings(db)
    return {
        "success": True,
        "message": "Store settings retrieved successfully.",
        "data": data.model_dump(),
    }


@router.put("", status_code=status.HTTP_200_OK)
def update_admin_store_settings(
    payload: StoreSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    data = SettingsService.update_admin_settings(db, payload, actor=current_user)
    return {
        "success": True,
        "message": "Store settings updated successfully.",
        "data": data.model_dump(),
    }


@router.get("/roles", status_code=status.HTTP_200_OK)
def list_roles_and_permissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    roles = SettingsService.list_roles(db)
    return {
        "success": True,
        "message": "Roles and permissions retrieved successfully.",
        "data": [r.model_dump() for r in roles],
    }
