from fastapi import APIRouter, Depends, Header, Query, Request, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_roles
from app.db.database import get_db
from app.models.user import User
from app.schemas.payment import CardPaymentConfirmRequest, CardPaymentIntentRequest
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.get("/config", status_code=status.HTTP_200_OK)
def get_payment_config(db: Session = Depends(get_db)):
    config = PaymentService.get_config(db)
    return {
        "success": True,
        "message": "Payment configuration retrieved successfully.",
        "data": config.model_dump(),
    }


@router.post("/card/intent", status_code=status.HTTP_201_CREATED)
def create_card_payment_intent(
    payload: CardPaymentIntentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    intent = PaymentService.create_card_payment_intent(
        db, order_id=payload.order_id, actor=current_user
    )
    return {
        "success": True,
        "message": "Card payment intent created successfully.",
        "data": intent.model_dump(),
    }


@router.post("/card/confirm", status_code=status.HTTP_200_OK)
def confirm_card_payment(
    payload: CardPaymentConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tx = PaymentService.confirm_card_payment(db, payload, actor=current_user)
    return {
        "success": True,
        "message": "Card payment verified and captured.",
        "data": tx.model_dump(),
    }


@router.post("/webhooks/stripe", status_code=status.HTTP_200_OK)
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(None, alias="Stripe-Signature"),
    db: Session = Depends(get_db),
):
    raw_body = await request.body()
    result = PaymentService.handle_stripe_webhook(
        db,
        raw_body=raw_body,
        stripe_signature=stripe_signature,
    )
    return {
        "success": True,
        "message": "Webhook processed.",
        "data": result,
    }


@router.get("", status_code=status.HTTP_200_OK)
def list_payments(
    status_filter: str | None = Query(None, alias="status"),
    method: str | None = Query(None),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    rows = PaymentService.list_transactions(
        db,
        status_filter=status_filter,
        method_filter=method,
        search=search,
    )
    return {
        "success": True,
        "message": "Payment transactions retrieved successfully.",
        "data": [row.model_dump() for row in rows],
    }


@router.get("/{payment_identifier}", status_code=status.HTTP_200_OK)
def get_payment(
    payment_identifier: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    row = PaymentService.get_transaction(db, payment_identifier)
    return {
        "success": True,
        "message": "Payment transaction retrieved successfully.",
        "data": row.model_dump(),
    }
