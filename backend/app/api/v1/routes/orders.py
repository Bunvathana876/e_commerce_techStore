from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_roles
from app.db.database import get_db
from app.models.user import User
from app.schemas.order import OrderCreateRequest, OrderStatusUpdateRequest
from app.schemas.shipment import OrderTrackingUpdateRequest
from app.services.authorization_service import AuthorizationService
from app.services.order_service import OrderService
from app.services.shipment_service import ShipmentService

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.get("/all", status_code=status.HTTP_200_OK)
def get_all_orders(
    limit: int | None = Query(None, ge=1, le=500, description="Optional limit of orders to return"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    orders = OrderService.get_all_orders(db, limit=limit)
    return {
        "success": True,
        "message": "All orders retrieved successfully.",
        "data": [o.model_dump() for o in orders],
    }


@router.put("/{order_id}/status", status_code=status.HTTP_200_OK)
def update_order_status(
    order_id: int,
    request: OrderStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "seller")),
):
    updated = OrderService.update_order_status(
        db,
        order_id,
        status_val=request.status,
        payment_status_val=request.payment_status,
        actor=current_user,
        reason=request.reason,
    )
    return {
        "success": True,
        "message": "Order status updated successfully.",
        "data": updated.model_dump(),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_order(
    request: OrderCreateRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_header: str | None = Header(None, alias="Idempotency-Key"),
):
    effective_key = idempotency_header or request.idempotency_key
    order, is_replay = OrderService.create_order(
        db,
        current_user.id,
        request,
        idempotency_key=effective_key,
        return_replay_status=True,
    )
    if is_replay:
        response.status_code = status.HTTP_200_OK
        response.headers["Idempotent-Replayed"] = "true"
    return {
        "success": True,
        "message": (
            "Order retrieved from idempotent submission."
            if is_replay
            else "Order placed successfully."
        ),
        "data": order.model_dump(),
    }


@router.get("", status_code=status.HTTP_200_OK)
def get_user_orders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    orders = OrderService.get_user_orders(db, current_user.id)
    return {
        "success": True,
        "message": "Orders retrieved successfully.",
        "data": [o.model_dump() for o in orders],
    }


@router.get("/{order_id}", status_code=status.HTTP_200_OK)
def get_order_details(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    seller_ids = (
        AuthorizationService.seller_ids(db, current_user)
        if current_user.role == "seller"
        else None
    )
    order = OrderService.get_order_by_id(
        db,
        order_id=order_id,
        user_id=None if AuthorizationService.is_admin(current_user) else current_user.id,
        seller_ids=seller_ids,
    )
    return {
        "success": True,
        "message": "Order details retrieved successfully.",
        "data": order.model_dump(),
    }


@router.get("/{order_id}/tracking", status_code=status.HTTP_200_OK)
def get_order_tracking(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tracking = ShipmentService.get_order_tracking(db, order_id=order_id, actor=current_user)
    return {
        "success": True,
        "message": "Order tracking retrieved successfully.",
        "data": tracking.model_dump(),
    }


@router.put("/{order_id}/tracking", status_code=status.HTTP_200_OK)
def update_order_tracking(
    order_id: int,
    request: OrderTrackingUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "seller")),
):
    tracking = ShipmentService.upsert_order_tracking(
        db,
        order_id=order_id,
        payload=request,
        actor=current_user,
    )
    return {
        "success": True,
        "message": "Order shipment tracking updated successfully.",
        "data": tracking.model_dump(),
    }


@router.delete("/{order_id}", status_code=status.HTTP_200_OK)
def delete_order(
    order_id: int,
    reason: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    cancelled_order = OrderService.cancel_or_archive_order(
        db,
        order_id=order_id,
        actor=current_user,
        reason=reason,
    )
    return {
        "success": True,
        "message": f"Order #{order_id} cancelled and archived successfully.",
        "data": cancelled_order.model_dump(),
    }



