from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy import func, or_, select, update, delete
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.models.notification import Notification
from app.schemas.notification import (
    NotificationCreate,
    NotificationResponse,
    NotificationUpdate,
)


class NotificationService:
    _has_seeded = False

    @staticmethod
    def _recipient_filter(user_id: int | None, include_shared: bool = False) -> ColumnElement[bool]:
        """Require a recipient; shared rows are only added to read-only feeds."""
        if user_id is None:
            raise ValueError("A notification recipient is required.")
        own = Notification.user_id == user_id
        return or_(own, Notification.user_id.is_(None)) if include_shared else own

    @staticmethod
    def seed_sample_notifications_if_empty(db: Session) -> None:
        if NotificationService._has_seeded:
            return
        NotificationService._has_seeded = True

        count = db.scalar(select(func.count(Notification.id))) or 0
        if count == 0:
            samples = [
                Notification(
                    type="delivery",
                    title="Order #104 Shipped! 📦",
                    message="Your package is on its way with express courier tracking #BP-88921.",
                    link="/orders/104",
                    read=False,
                ),
                Notification(
                    type="promo",
                    title="Weekend Flash Sale ⚡",
                    message="Enjoy up to 40% OFF all premium wireless gear and accessories this weekend!",
                    link="/categories/electronics",
                    read=False,
                ),
                Notification(
                    type="order",
                    title="Payment Confirmed",
                    message="Payment of $199.99 for Order #104 has been successfully processed.",
                    link="/orders/104",
                    read=False,
                ),
                Notification(
                    type="review",
                    title="New 5-Star Review Received ⭐",
                    message="Alex Chen rated Sony WH-1000XM5 with 5 stars: 'Best headphones ever!'",
                    link="/admin/reviews",
                    read=True,
                ),
                Notification(
                    type="stock",
                    title="Low Stock Alert ⚠️",
                    message="Nike Air Max 270 inventory is below threshold (only 3 units left in warehouse).",
                    link="/admin/products",
                    read=True,
                ),
                Notification(
                    type="system",
                    title="Welcome to Blue Panda Store 🐼",
                    message="Thank you for joining Blue Panda. Discover daily curated deals and lightning fast checkout.",
                    link=None,
                    read=True,
                ),
            ]
            db.add_all(samples)
            db.commit()

    @staticmethod
    def list_notifications(
        db: Session,
        user_id: int,
        type_filter: Optional[str] = None,
        unread_only: bool = False,
        skip: int = 0,
        limit: int = 50,
        include_shared: bool = False,
    ) -> list[NotificationResponse]:
        query = select(Notification).where(
            NotificationService._recipient_filter(user_id, include_shared)
        )

        if type_filter and type_filter.lower() != "all":
            query = query.where(Notification.type == type_filter.lower())

        if unread_only:
            query = query.where(Notification.read.is_(False))
            if include_shared:
                query = query.where(Notification.user_id == user_id)

        query = query.order_by(Notification.created_at.desc()).offset(skip).limit(limit)

        notifications = list(db.scalars(query).all())
        return [NotificationResponse.model_validate(n) for n in notifications]

    @staticmethod
    def get_unread_count(db: Session, user_id: int) -> int:
        query = select(func.count(Notification.id)).where(
            Notification.read.is_(False),
            NotificationService._recipient_filter(user_id),
        )

        count = db.scalar(query)
        return int(count or 0)

    @staticmethod
    def create_notification(
        db: Session,
        data: NotificationCreate,
    ) -> NotificationResponse:
        notif = Notification(
            user_id=data.user_id,
            type=data.type,
            title=data.title,
            message=data.message,
            link=data.link,
            read=False,
        )
        db.add(notif)
        db.commit()
        db.refresh(notif)
        return NotificationResponse.model_validate(notif)

    @staticmethod
    def mark_as_read(
        db: Session, notification_id: int, user_id: int
    ) -> NotificationResponse:
        query = select(Notification).where(
            Notification.id == notification_id,
            NotificationService._recipient_filter(user_id),
        )
        notif = db.scalar(query)
        if not notif:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Notification #{notification_id} not found",
            )
        notif.read = True
        db.commit()
        db.refresh(notif)
        return NotificationResponse.model_validate(notif)

    @staticmethod
    def mark_all_read(db: Session, user_id: int) -> int:
        query = update(Notification).where(
            Notification.read.is_(False),
            NotificationService._recipient_filter(user_id),
        )
        result = db.execute(query.values(read=True))
        db.commit()
        return result.rowcount

    @staticmethod
    def delete_notification(
        db: Session, notification_id: int, user_id: int
    ) -> bool:
        query = select(Notification).where(
            Notification.id == notification_id,
            NotificationService._recipient_filter(user_id),
        )
        notif = db.scalar(query)
        if not notif:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Notification #{notification_id} not found",
            )
        db.delete(notif)
        db.commit()
        return True

    @staticmethod
    def clear_all(db: Session, user_id: int) -> int:
        query = delete(Notification).where(
            NotificationService._recipient_filter(user_id)
        )
        result = db.execute(query)
        db.commit()
        return result.rowcount

