from decimal import Decimal
import hashlib
import hmac
import json
import time
from uuid import uuid4

from fastapi import HTTPException, status
import httpx
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.notification import Notification
from app.models.order import Order
from app.models.payment import PaymentTransaction
from app.models.user import User
from app.schemas.payment import (
    CardPaymentConfirmRequest,
    CardPaymentIntentResponse,
    PaymentConfigResponse,
    PaymentTransactionResponse,
)

SUPPORTED_PAYMENT_METHODS = ["Credit / Debit Card", "Cash on Delivery"]
STRIPE_WEBHOOK_TOLERANCE_SECONDS = 300


class PaymentService:
    """Digital payment configuration, Stripe Card gateway integration, and transaction records."""

    @staticmethod
    def is_stripe_configured() -> bool:
        return bool(settings.STRIPE_SECRET_KEY and settings.STRIPE_SECRET_KEY.strip())

    @staticmethod
    def get_config(db: Session | None = None) -> PaymentConfigResponse:
        enable_card = True
        enable_cod = True
        if db is not None:
            from app.services.settings_service import SettingsService

            store_cfg = SettingsService.get_effective_settings(db)
            enable_card = bool(store_cfg.enable_card_payment)
            enable_cod = bool(store_cfg.enable_cod_payment)

        methods: list[str] = []
        if enable_card:
            methods.append("Credit / Debit Card")
        if enable_cod:
            methods.append("Cash on Delivery")

        configured = PaymentService.is_stripe_configured() and enable_card
        return PaymentConfigResponse(
            supported_methods=methods,
            card_gateway_configured=configured,
            card_provider="stripe" if configured else "none",
            stripe_publishable_key=(
                settings.STRIPE_PUBLISHABLE_KEY.strip()
                if configured and settings.STRIPE_PUBLISHABLE_KEY
                else None
            ),
            currency=settings.PAYMENT_CURRENCY,
            enable_card_payment=enable_card,
            enable_cod_payment=enable_cod,
        )

    @staticmethod
    def create_transaction_for_order(
        db: Session,
        *,
        order: Order,
        provider: str,
        status_val: str = "pending",
        provider_reference: str | None = None,
    ) -> PaymentTransaction:
        tx = PaymentTransaction(
            transaction_ref=f"PAY-{order.id:06d}-{uuid4().hex[:6].upper()}",
            order_id=order.id,
            provider=provider,
            payment_method=order.payment_method,
            amount=Decimal(order.total).quantize(Decimal("0.01")),
            currency=settings.PAYMENT_CURRENCY,
            status=status_val,
            provider_reference=provider_reference,
        )
        db.add(tx)
        db.flush()
        return tx

    @staticmethod
    def _serialize_transaction(tx: PaymentTransaction) -> PaymentTransactionResponse:
        order = tx.order
        user = order.user if order else None
        return PaymentTransactionResponse(
            id=tx.id,
            transaction_ref=tx.transaction_ref,
            order_id=tx.order_id,
            customer_id=user.id if user else (order.user_id if order else None),
            customer_name=user.name if user else None,
            customer_email=user.email if user else None,
            order_status=order.status if order else None,
            provider=tx.provider,
            payment_method=tx.payment_method,
            amount=tx.amount,
            currency=tx.currency,
            status=tx.status,
            provider_reference=tx.provider_reference,
            card_brand=tx.card_brand,
            card_last4=tx.card_last4,
            failure_reason=tx.failure_reason,
            created_at=tx.created_at,
            updated_at=tx.updated_at,
        )

    @staticmethod
    def list_transactions(
        db: Session,
        *,
        status_filter: str | None = None,
        method_filter: str | None = None,
        search: str | None = None,
    ) -> list[PaymentTransactionResponse]:
        query = (
            select(PaymentTransaction)
            .options(selectinload(PaymentTransaction.order).selectinload(Order.user))
            .order_by(PaymentTransaction.created_at.desc(), PaymentTransaction.id.desc())
        )
        if status_filter and status_filter.strip().lower() != "all":
            query = query.where(PaymentTransaction.status == status_filter.strip().lower())
        if method_filter and method_filter.strip().lower() != "all":
            query = query.where(PaymentTransaction.payment_method.ilike(f"%{method_filter.strip()}%"))
        if search and search.strip():
            term = f"%{search.strip()}%"
            user_ids = select(User.id).where(or_(User.name.ilike(term), User.email.ilike(term)))
            order_ids = select(Order.id).where(Order.user_id.in_(user_ids))
            query = query.where(
                or_(
                    PaymentTransaction.transaction_ref.ilike(term),
                    PaymentTransaction.provider_reference.ilike(term),
                    PaymentTransaction.order_id.in_(order_ids),
                )
            )
        rows = list(db.scalars(query).all())
        return [PaymentService._serialize_transaction(tx) for tx in rows]

    @staticmethod
    def get_transaction(db: Session, payment_identifier: str | int) -> PaymentTransactionResponse:
        raw = str(payment_identifier).strip()
        tx: PaymentTransaction | None = None
        base_query = select(PaymentTransaction).options(
            selectinload(PaymentTransaction.order).selectinload(Order.user)
        )
        if raw.isdigit():
            tx = db.scalar(base_query.where(PaymentTransaction.id == int(raw)))
        else:
            upper = raw.upper()
            tx = db.scalar(base_query.where(PaymentTransaction.transaction_ref == upper))
            if tx is None and upper.startswith("PAY-"):
                suffix = upper.replace("PAY-", "", 1)
                if suffix.isdigit():
                    tx = db.scalar(
                        base_query.where(
                            (PaymentTransaction.id == int(suffix))
                            | (PaymentTransaction.order_id == int(suffix))
                        ).order_by(PaymentTransaction.id.desc())
                    )
        if tx is None:
            raise HTTPException(status_code=404, detail=f"Payment transaction '{payment_identifier}' not found.")
        return PaymentService._serialize_transaction(tx)

    @staticmethod
    def create_card_payment_intent(
        db: Session,
        *,
        order_id: int,
        actor: User,
    ) -> CardPaymentIntentResponse:
        from app.services.settings_service import SettingsService

        if not SettingsService.get_effective_settings(db).enable_card_payment:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Credit / Debit Card payments are currently disabled in store settings.",
            )
        if not PaymentService.is_stripe_configured():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Credit / Debit Card gateway (Stripe) is not configured on the server.",
            )

        order = db.scalar(select(Order).where(Order.id == order_id).with_for_update())
        if not order:
            raise HTTPException(status_code=404, detail=f"Order #{order_id} not found.")
        if actor.role != "admin" and order.user_id != actor.id:
            raise HTTPException(status_code=403, detail="Permission denied.")
        if order.payment_method != "Credit / Debit Card":
            raise HTTPException(
                status_code=400,
                detail=f"Order #{order.id} uses '{order.payment_method}', not Credit / Debit Card.",
            )
        if order.payment_status != "pending" or order.status == "cancelled":
            raise HTTPException(
                status_code=409,
                detail=f"Order #{order.id} cannot create a payment intent in status '{order.status}' / '{order.payment_status}'.",
            )

        amount_cents = int((Decimal(order.total) * Decimal("100")).quantize(Decimal("1")))
        if amount_cents <= 0:
            raise HTTPException(status_code=400, detail="Order total must be positive for card capture.")

        tx = db.scalar(
            select(PaymentTransaction)
            .where(PaymentTransaction.order_id == order.id)
            .order_by(PaymentTransaction.id.desc())
        )
        if tx is None:
            tx = PaymentService.create_transaction_for_order(
                db, order=order, provider="stripe", status_val="pending"
            )

        try:
            response = httpx.post(
                f"{settings.STRIPE_API_BASE_URL.rstrip('/')}/payment_intents",
                auth=(settings.STRIPE_SECRET_KEY.strip(), ""),
                data={
                    "amount": str(amount_cents),
                    "currency": settings.PAYMENT_CURRENCY.lower(),
                    "payment_method_types[]": "card",
                    "metadata[order_id]": str(order.id),
                    "metadata[transaction_ref]": tx.transaction_ref,
                },
                headers={"Idempotency-Key": f"pi-order-{order.id}"},
                timeout=15.0,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unable to reach Stripe PaymentIntents API.",
            ) from exc

        if response.status_code >= 300:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Stripe PaymentIntent creation failed.",
            )

        intent = response.json()
        intent_id = intent.get("id")
        client_secret = intent.get("client_secret")
        if not intent_id or not client_secret:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Invalid response received from Stripe PaymentIntents API.",
            )

        tx.provider = "stripe"
        tx.provider_reference = intent_id
        tx.status = "requires_action"
        db.commit()
        db.refresh(tx)

        return CardPaymentIntentResponse(
            payment_id=tx.id,
            transaction_ref=tx.transaction_ref,
            order_id=order.id,
            payment_intent_id=intent_id,
            client_secret=client_secret,
            amount=tx.amount,
            currency=tx.currency,
            publishable_key=settings.STRIPE_PUBLISHABLE_KEY,
        )

    @staticmethod
    def _extract_card_details(intent: dict) -> tuple[str | None, str | None]:
        charges = intent.get("charges", {}).get("data", [])
        if charges and isinstance(charges, list):
            card = charges[0].get("payment_method_details", {}).get("card", {})
            if isinstance(card, dict):
                return card.get("brand"), card.get("last4")
        latest_charge = intent.get("latest_charge")
        if isinstance(latest_charge, dict):
            card = latest_charge.get("payment_method_details", {}).get("card", {})
            if isinstance(card, dict):
                return card.get("brand"), card.get("last4")
        return None, None

    @staticmethod
    def _settle_captured_intent(db: Session, order: Order, intent: dict) -> PaymentTransaction:
        expected_cents = int((Decimal(order.total) * Decimal("100")).quantize(Decimal("1")))
        received_cents = int(intent.get("amount_received") or intent.get("amount") or 0)
        if received_cents < expected_cents:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Captured card amount is less than the authoritative server order total.",
            )

        intent_id = str(intent.get("id") or "")
        tx = db.scalar(
            select(PaymentTransaction)
            .where(
                (PaymentTransaction.order_id == order.id)
                & (
                    (PaymentTransaction.provider_reference == intent_id)
                    | (PaymentTransaction.provider_reference.is_(None))
                )
            )
            .order_by(PaymentTransaction.id.desc())
        )
        if tx is None:
            tx = PaymentService.create_transaction_for_order(
                db, order=order, provider="stripe", status_val="captured", provider_reference=intent_id
            )

        brand, last4 = PaymentService._extract_card_details(intent)
        tx.provider = "stripe"
        tx.provider_reference = intent_id
        tx.status = "captured"
        tx.failure_reason = None
        if brand:
            tx.card_brand = brand[:30]
        if last4:
            tx.card_last4 = last4[:4]

        if order.payment_status != "paid":
            order.payment_status = "paid"
            db.add(
                Notification(
                    user_id=order.user_id,
                    type="order",
                    title=f"Payment Confirmed for Order #{order.id}",
                    message=f"Your Credit / Debit Card payment of ${order.total:.2f} has been verified.",
                    link=f"/orders/{order.id}",
                    read=False,
                )
            )
        return tx

    @staticmethod
    def confirm_card_payment(
        db: Session,
        data: CardPaymentConfirmRequest,
        *,
        actor: User,
    ) -> PaymentTransactionResponse:
        if not PaymentService.is_stripe_configured():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Credit / Debit Card gateway (Stripe) is not configured on the server.",
            )

        order = db.scalar(select(Order).where(Order.id == data.order_id).with_for_update())
        if not order:
            raise HTTPException(status_code=404, detail=f"Order #{data.order_id} not found.")
        if actor.role != "admin" and order.user_id != actor.id:
            raise HTTPException(status_code=403, detail="Permission denied.")
        if order.payment_method != "Credit / Debit Card":
            raise HTTPException(status_code=400, detail="Order is not a Credit / Debit Card order.")

        try:
            response = httpx.get(
                f"{settings.STRIPE_API_BASE_URL.rstrip('/')}/payment_intents/{data.payment_intent_id}",
                auth=(settings.STRIPE_SECRET_KEY.strip(), ""),
                timeout=15.0,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unable to verify card payment with Stripe.",
            ) from exc

        if response.status_code >= 300:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Stripe PaymentIntent lookup failed.",
            )

        intent = response.json()
        metadata_order_id = str(intent.get("metadata", {}).get("order_id") or "")
        if metadata_order_id and metadata_order_id != str(order.id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="PaymentIntent does not match the target order.",
            )

        intent_status = (intent.get("status") or "").strip().lower()
        if intent_status != "succeeded":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Card payment has not succeeded yet (Stripe status: '{intent_status}').",
            )

        tx = PaymentService._settle_captured_intent(db, order, intent)
        db.commit()
        return PaymentService.get_transaction(db, tx.id)

    @staticmethod
    def _verify_stripe_signature(payload: bytes, sig_header: str | None, secret: str) -> None:
        if not sig_header:
            raise HTTPException(status_code=400, detail="Missing Stripe-Signature header.")

        timestamp: int | None = None
        signatures: list[str] = []
        for part in sig_header.split(","):
            key, _, val = part.strip().partition("=")
            if key == "t" and val.isdigit():
                timestamp = int(val)
            elif key == "v1" and val:
                signatures.append(val)

        if timestamp is None or not signatures:
            raise HTTPException(status_code=400, detail="Malformed Stripe-Signature header.")

        if abs(int(time.time()) - timestamp) > STRIPE_WEBHOOK_TOLERANCE_SECONDS:
            raise HTTPException(status_code=400, detail="Stripe webhook timestamp outside tolerance.")

        signed_payload = f"{timestamp}.".encode("utf-8") + payload
        expected_sig = hmac.new(
            secret.encode("utf-8"),
            signed_payload,
            hashlib.sha256,
        ).hexdigest()

        if not any(hmac.compare_digest(expected_sig, sig) for sig in signatures):
            raise HTTPException(status_code=400, detail="Invalid Stripe webhook signature.")

    @staticmethod
    def handle_stripe_webhook(
        db: Session,
        *,
        raw_body: bytes,
        stripe_signature: str | None,
    ) -> dict:
        secret = (settings.STRIPE_WEBHOOK_SECRET or "").strip()
        if not secret:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="STRIPE_WEBHOOK_SECRET is not configured.",
            )

        PaymentService._verify_stripe_signature(raw_body, stripe_signature, secret)

        try:
            event = json.loads(raw_body.decode("utf-8"))
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid webhook JSON payload.") from exc

        event_type = event.get("type", "")
        intent = event.get("data", {}).get("object", {})
        if not isinstance(intent, dict):
            return {"handled": False, "event_type": event_type}

        intent_id = intent.get("id")
        meta_order_id = intent.get("metadata", {}).get("order_id")
        order: Order | None = None
        if meta_order_id and str(meta_order_id).isdigit():
            order = db.scalar(select(Order).where(Order.id == int(meta_order_id)).with_for_update())
        elif intent_id:
            tx_lookup = db.scalar(
                select(PaymentTransaction).where(PaymentTransaction.provider_reference == str(intent_id))
            )
            if tx_lookup:
                order = db.scalar(select(Order).where(Order.id == tx_lookup.order_id).with_for_update())

        if order is None:
            return {"handled": False, "event_type": event_type}

        if event_type == "payment_intent.succeeded":
            PaymentService._settle_captured_intent(db, order, intent)
            db.commit()
            return {"handled": True, "event_type": event_type, "order_id": order.id}

        if event_type == "payment_intent.payment_failed":
            tx = db.scalar(
                select(PaymentTransaction)
                .where(PaymentTransaction.order_id == order.id)
                .order_by(PaymentTransaction.id.desc())
            )
            err_msg = intent.get("last_payment_error", {}).get("message") or "Card authorization failed"
            if tx is not None:
                tx.status = "failed"
                tx.failure_reason = str(err_msg)[:500]
            if order.payment_status == "pending":
                order.payment_status = "failed"
            db.commit()
            return {"handled": True, "event_type": event_type, "order_id": order.id}

        return {"handled": False, "event_type": event_type}
