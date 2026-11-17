from typing import Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_roles
from app.db.database import get_db
from app.models.user import User
from app.schemas.notification import (
    NotificationCreate,
)
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", status_code=status.HTTP_200_OK)
def list_notifications(
    type: Optional[str] = None,
    unread_only: bool = False,
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notifications = NotificationService.list_notifications(
        db,
        user_id=current_user.id,
        type_filter=type,
        unread_only=unread_only,
        skip=skip,
        limit=limit,
    )
    unread_count = NotificationService.get_unread_count(db, user_id=current_user.id)
    return {
        "success": True,
        "message": "Notifications retrieved successfully.",
        "data": [n.model_dump() for n in notifications],
        "unread_count": unread_count,
    }


@router.get("/unread-count", status_code=status.HTTP_200_OK)
def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    unread_count = NotificationService.get_unread_count(db, user_id=current_user.id)
    return {
        "success": True,
        "unread_count": unread_count,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_notification(
    data: NotificationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    created = NotificationService.create_notification(db, data=data)
    return {
        "success": True,
        "message": "Notification created successfully.",
        "data": created.model_dump(),
    }


@router.get("/admin", status_code=status.HTTP_200_OK)
def list_admin_notifications(
    type: Optional[str] = None,
    unread_only: bool = False,
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    notifications = NotificationService.list_notifications(
        db, current_user.id, type_filter=type, unread_only=unread_only,
        skip=skip, limit=limit, include_shared=True,
    )
    unread_count = NotificationService.get_unread_count(db, current_user.id)
    return {
        "success": True,
        "message": "Notifications retrieved successfully.",
        "data": [n.model_dump() for n in notifications],
        "unread_count": unread_count,
    }


@router.get("/admin/unread-count", status_code=status.HTTP_200_OK)
def get_admin_unread_count(
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    unread_count = NotificationService.get_unread_count(db, current_user.id)
    return {"success": True, "unread_count": unread_count}


@router.patch("/admin/{notification_id}/read", status_code=status.HTTP_200_OK)
def mark_admin_notification_as_read(
    notification_id: int,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    updated = NotificationService.mark_as_read(
        db, notification_id, current_user.id
    )
    return {
        "success": True,
        "message": "Notification marked as read.",
        "data": updated.model_dump(),
    }


@router.post("/admin/read-all", status_code=status.HTTP_200_OK)
def mark_all_admin_notifications_as_read(
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    count = NotificationService.mark_all_read(
        db, current_user.id
    )
    return {
        "success": True,
        "message": "All notifications marked as read.",
        "updated_count": count,
    }


@router.delete("/admin/{notification_id}", status_code=status.HTTP_200_OK)
def delete_admin_notification(
    notification_id: int,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    NotificationService.delete_notification(
        db, notification_id, current_user.id
    )
    return {
        "success": True,
        "message": f"Notification #{notification_id} deleted successfully.",
    }


@router.delete("/admin", status_code=status.HTTP_200_OK)
def clear_all_admin_notifications(
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    count = NotificationService.clear_all(
        db, current_user.id
    )
    return {
        "success": True,
        "message": "All notifications cleared.",
        "deleted_count": count,
    }


@router.patch("/{notification_id}/read", status_code=status.HTTP_200_OK)
def mark_as_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    updated = NotificationService.mark_as_read(
        db, notification_id=notification_id,
        user_id=current_user.id,
    )
    return {
        "success": True,
        "message": "Notification marked as read.",
        "data": updated.model_dump(),
    }


@router.post("/read-all", status_code=status.HTTP_200_OK)
def mark_all_as_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    count = NotificationService.mark_all_read(db, user_id=current_user.id)
    return {
        "success": True,
        "message": "All notifications marked as read.",
        "updated_count": count,
    }


@router.delete("/{notification_id}", status_code=status.HTTP_200_OK)
def delete_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    NotificationService.delete_notification(
        db, notification_id=notification_id,
        user_id=current_user.id,
    )
    return {
        "success": True,
        "message": f"Notification #{notification_id} deleted successfully.",
    }


@router.delete("", status_code=status.HTTP_200_OK)
def clear_all_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    count = NotificationService.clear_all(db, user_id=current_user.id)
    return {
        "success": True,
        "message": "All notifications cleared.",
        "deleted_count": count,
    }

