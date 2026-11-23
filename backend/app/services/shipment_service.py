from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.notification import Notification
from app.models.order import Order, OrderItem
from app.models.shipment import ALLOWED_SHIPMENT_STATUSES, OrderShipment, OrderTrackingEvent
from app.models.user import User
from app.schemas.shipment import (
    OrderShipmentSummary,
    OrderTrackingEventResponse,
    OrderTrackingResponse,
    OrderTrackingUpdateRequest,
)
from app.services.authorization_service import AuthorizationService


DEFAULT_EVENT_TITLES: dict[str, str] = {
    "pending": "Order Placed",
    "label_created": "Shipping Label Created",
    "picked_up": "Package Picked Up by Carrier",
    "in_transit": "Package In Transit",
    "out_for_delivery": "Out for Delivery",
    "processing": "Order Being Prepared",
    "shipped": "Order Shipped",
    "delivered": "Order Delivered",
    "exception": "Delivery Exception Reported",
    "cancelled": "Order Cancelled",
}


class ShipmentService:
    """Real shipment carrier metadata and chronological order tracking events."""

    @staticmethod
    def _validate_tracking_url(url: str | None) -> str | None:
        if url is None:
            return None
        cleaned = url.strip()
        if not cleaned:
            return None
        parsed = urlparse(cleaned)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Tracking URL must start with http:// or https://.",
            )
        return cleaned

    @staticmethod
    def _authorize_read(db: Session, order_id: int, actor: User) -> Order:
        order = db.scalar(
            select(Order)
            .options(
                selectinload(Order.items).selectinload(OrderItem.product),
                selectinload(Order.shipment).selectinload(OrderShipment.events),
            )
            .where(Order.id == order_id)
        )
        if not order:
            raise HTTPException(status_code=404, detail="Order not found.")

        if AuthorizationService.is_admin(actor) or order.user_id == actor.id:
            return order

        if actor.role == "seller":
            seller_ids = set(AuthorizationService.seller_ids(db, actor))
            if seller_ids and any(
                item.product is not None and item.product.seller_id in seller_ids
                for item in order.items
            ):
                return order

        raise HTTPException(status_code=404, detail="Order not found.")

    @staticmethod
    def _authorize_write(db: Session, order_id: int, actor: User) -> Order:
        if not (AuthorizationService.is_admin(actor) or actor.role == "seller"):
            raise HTTPException(status_code=403, detail="Permission denied.")

        order = db.scalar(
            select(Order)
            .options(
                selectinload(Order.items).selectinload(OrderItem.product),
                selectinload(Order.shipment).selectinload(OrderShipment.events),
            )
            .where(Order.id == order_id)
        )
        if not order:
            raise HTTPException(status_code=404, detail="Order not found.")

        if actor.role == "seller" and not AuthorizationService.is_admin(actor):
            seller_ids = set(AuthorizationService.seller_ids(db, actor))
            if not seller_ids:
                raise HTTPException(
                    status_code=403,
                    detail="An active seller account is required.",
                )
            if not order.items or any(
                item.product is None or item.product.seller_id not in seller_ids
                for item in order.items
            ):
                raise HTTPException(
                    status_code=403,
                    detail="Permission denied: order contains items outside your store.",
                )

        return order

    @staticmethod
    def _derive_baseline_events(order: Order) -> list[OrderTrackingEventResponse]:
        status_lower = (order.status or "pending").strip().lower()
        events = [
            OrderTrackingEventResponse(
                id=None,
                status="pending",
                title="Order Placed",
                description="Order received and confirmed in Blue Panda.",
                location=None,
                occurred_at=order.created_at,
            )
        ]
        if status_lower in {"processing", "shipped", "delivered"}:
            events.append(
                OrderTrackingEventResponse(
                    id=None,
                    status="processing",
                    title="Order Being Prepared",
                    description="Your items are being picked and packed for dispatch.",
                    location=None,
                    occurred_at=order.updated_at or order.created_at,
                )
            )
        if status_lower in {"shipped", "delivered"}:
            events.append(
                OrderTrackingEventResponse(
                    id=None,
                    status="shipped",
                    title="Order Dispatched",
                    description="Shipment handed over for delivery.",
                    location=None,
                    occurred_at=order.updated_at or order.created_at,
                )
            )
        if status_lower == "delivered":
            events.append(
                OrderTrackingEventResponse(
                    id=None,
                    status="delivered",
                    title="Order Delivered",
                    description="Package delivered to the recipient address.",
                    location=None,
                    occurred_at=order.updated_at or order.created_at,
                )
            )
        elif status_lower == "cancelled":
            events.append(
                OrderTrackingEventResponse(
                    id=None,
                    status="cancelled",
                    title="Order Cancelled",
                    description="This order was cancelled before completion.",
                    location=None,
                    occurred_at=order.updated_at or order.created_at,
                )
            )
        return events

    @staticmethod
    def _build_response(order: Order) -> OrderTrackingResponse:
        shipment = order.shipment
        if shipment and shipment.events:
            events = [OrderTrackingEventResponse.model_validate(ev) for ev in shipment.events]
        else:
            events = ShipmentService._derive_baseline_events(order)

        return OrderTrackingResponse(
            order_id=order.id,
            order_status=order.status,
            payment_status=order.payment_status,
            shipping_address=order.shipping_address,
            has_shipment_record=shipment is not None,
            shipment=OrderShipmentSummary.model_validate(shipment) if shipment else None,
            events=events,
        )

    @staticmethod
    def get_order_tracking(db: Session, order_id: int, actor: User) -> OrderTrackingResponse:
        order = ShipmentService._authorize_read(db, order_id, actor)
        return ShipmentService._build_response(order)

    @staticmethod
    def upsert_order_tracking(
        db: Session,
        order_id: int,
        payload: OrderTrackingUpdateRequest,
        actor: User,
    ) -> OrderTrackingResponse:
        order = ShipmentService._authorize_write(db, order_id, actor)

        clean_status = payload.status.strip().lower()
        if clean_status not in ALLOWED_SHIPMENT_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Invalid shipment status '{payload.status}'. "
                    f"Allowed: {', '.join(ALLOWED_SHIPMENT_STATUSES)}."
                ),
            )

        clean_carrier = payload.carrier.strip()
        if not clean_carrier:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Carrier name is required.",
            )

        tracking_url = ShipmentService._validate_tracking_url(payload.tracking_url)
        tracking_number = payload.tracking_number.strip() if payload.tracking_number else None
        if tracking_number == "":
            tracking_number = None

        shipment = order.shipment
        now = datetime.now(timezone.utc)
        if shipment is None:
            shipment = OrderShipment(
                order_id=order.id,
                carrier=clean_carrier,
                tracking_number=tracking_number,
                tracking_url=tracking_url,
                status=clean_status,
                estimated_delivery_at=payload.estimated_delivery_at,
                notes=payload.notes.strip() if payload.notes else None,
                updated_by_user_id=actor.id,
            )
            db.add(shipment)
            db.flush()
        else:
            shipment.carrier = clean_carrier
            shipment.tracking_number = tracking_number
            shipment.tracking_url = tracking_url
            shipment.status = clean_status
            if payload.estimated_delivery_at is not None:
                shipment.estimated_delivery_at = payload.estimated_delivery_at
            if payload.notes is not None:
                shipment.notes = payload.notes.strip() or None
            shipment.updated_by_user_id = actor.id

        if clean_status in {"picked_up", "in_transit", "out_for_delivery"} and shipment.shipped_at is None:
            shipment.shipped_at = now
        if clean_status == "delivered" and shipment.delivered_at is None:
            shipment.delivered_at = now

        title = (payload.event_title or "").strip() or DEFAULT_EVENT_TITLES.get(clean_status, clean_status.replace("_", " ").title())
        desc_parts = []
        if payload.event_description and payload.event_description.strip():
            desc_parts.append(payload.event_description.strip())
        if tracking_number:
            desc_parts.append(f"Carrier: {clean_carrier} • Tracking #{tracking_number}")
        description = " — ".join(desc_parts) if desc_parts else f"Shipment updated via {clean_carrier}."

        db.add(
            OrderTrackingEvent(
                shipment_id=shipment.id,
                order_id=order.id,
                status=clean_status,
                title=title,
                description=description,
                location=payload.location.strip() if payload.location and payload.location.strip() else None,
                occurred_at=now,
                created_by_user_id=actor.id,
            )
        )

        db.add(
            Notification(
                user_id=order.user_id,
                type="delivery",
                title=f"Tracking Update: Order #{order.id}",
                message=f"{title}" + (f" ({tracking_number})" if tracking_number else ""),
                link=f"/orders/{order.id}",
                read=False,
            )
        )

        db.commit()
        refreshed = ShipmentService._authorize_read(db, order.id, actor)
        return ShipmentService._build_response(refreshed)

    @staticmethod
    def record_status_event(
        db: Session,
        order: Order,
        status_val: str,
        actor: User | None,
        note: str | None = None,
    ) -> None:
        """Records a real shipment checkpoint when order fulfillment status transitions."""
        clean_status = status_val.strip().lower()
        mapped_shipment_status = {
            "processing": "label_created",
            "shipped": "in_transit",
            "delivered": "delivered",
            "cancelled": "cancelled",
        }.get(clean_status, clean_status)

        shipment = db.scalar(select(OrderShipment).where(OrderShipment.order_id == order.id))
        now = datetime.now(timezone.utc)
        if shipment is None:
            shipment = OrderShipment(
                order_id=order.id,
                carrier="Blue Panda Express",
                status=mapped_shipment_status,
                shipped_at=now if clean_status == "shipped" else None,
                delivered_at=now if clean_status == "delivered" else None,
                updated_by_user_id=actor.id if actor else None,
            )
            db.add(shipment)
            db.flush()
        else:
            shipment.status = mapped_shipment_status
            if clean_status == "shipped" and shipment.shipped_at is None:
                shipment.shipped_at = now
            if clean_status == "delivered" and shipment.delivered_at is None:
                shipment.delivered_at = now
            if actor is not None:
                shipment.updated_by_user_id = actor.id

        db.add(
            OrderTrackingEvent(
                shipment_id=shipment.id,
                order_id=order.id,
                status=mapped_shipment_status,
                title=DEFAULT_EVENT_TITLES.get(clean_status, clean_status.replace("_", " ").title()),
                description=note or f"Order status updated to {clean_status}.",
                occurred_at=now,
                created_by_user_id=actor.id if actor else None,
            )
        )
