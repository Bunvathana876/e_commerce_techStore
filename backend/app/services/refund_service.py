from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException, status
import httpx
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.notification import Notification
from app.models.order import Order, OrderItem
from app.models.payment import PaymentTransaction
from app.models.refund import Refund, RefundLedgerEntry
from app.models.user import User
from app.schemas.refund import (
    RefundAccountBalance,
    RefundApproveRequest,
    RefundCreateRequest,
    RefundLedgerEntryResponse,
    RefundLedgerListResponse,
    RefundLedgerTrialBalance,
    RefundProcessRequest,
    RefundRejectRequest,
    RefundResponse,
)
from app.services.inventory_service import InventoryService

ACCOUNTS = {
    "4100": "Sales Returns & Allowances",
    "2100": "Customer Refunds Payable",
    "1010": "Cash / COD Clearing",
    "1020": "Card Processor Clearing",
}

ALLOWED_REFUND_METHODS = {
    "credit / debit card": "Credit / Debit Card",
    "credit or debit card": "Credit / Debit Card",
    "credit/debit card": "Credit / Debit Card",
    "credit card": "Credit / Debit Card",
    "debit card": "Credit / Debit Card",
    "card": "Credit / Debit Card",
    "cash on delivery": "Cash on Delivery",
    "cash on delivery (cod)": "Cash on Delivery",
    "cod": "Cash on Delivery",
    "cash": "Cash",
}


class RefundService:
    """Dedicated refund lifecycle and immutable double-entry refund accounting ledger."""

    @staticmethod
    def _new_ref(prefix: str) -> str:
        return f"{prefix}-{uuid4().hex[:12].upper()}"

    @staticmethod
    def _normalize_refund_method(raw_method: str | None, fallback: str = "Cash on Delivery") -> str:
        raw = (raw_method or fallback).strip()
        canonical = ALLOWED_REFUND_METHODS.get(raw.lower())
        if canonical is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Unsupported refund method '{raw}'. "
                    "Supported refund methods are Credit / Debit Card, Cash on Delivery, and Cash."
                ),
            )
        return canonical

    @staticmethod
    def _clearing_account_for_method(refund_method: str) -> tuple[str, str]:
        if "card" in refund_method.lower():
            return "1020", ACCOUNTS["1020"]
        return "1010", ACCOUNTS["1010"]

    @staticmethod
    def _post_balanced_entries(
        db: Session,
        *,
        refund: Refund,
        entry_type: str,
        lines: list[tuple[str, Decimal, Decimal]],
        memo: str,
        actor_user_id: int | None,
    ) -> list[RefundLedgerEntry]:
        total_debit = sum((d for _, d, _ in lines), Decimal("0.00"))
        total_credit = sum((c for _, _, c in lines), Decimal("0.00"))
        if total_debit <= Decimal("0.00") or total_debit != total_credit:
            raise ValueError(
                f"Unbalanced refund ledger entry: debit={total_debit}, credit={total_credit}"
            )

        journal_ref = RefundService._new_ref("RJL")
        created: list[RefundLedgerEntry] = []
        for account_code, debit, credit in lines:
            row = RefundLedgerEntry(
                journal_ref=journal_ref,
                refund_id=refund.id,
                order_id=refund.order_id,
                entry_type=entry_type,
                account_code=account_code,
                account_name=ACCOUNTS[account_code],
                debit_amount=debit.quantize(Decimal("0.01")),
                credit_amount=credit.quantize(Decimal("0.01")),
                currency=refund.currency,
                memo=memo[:500] if memo else None,
                created_by_user_id=actor_user_id,
            )
            db.add(row)
            created.append(row)
        db.flush()
        return created

    @staticmethod
    def _serialize_refund(db: Session, refund_id: int) -> RefundResponse:
        refund = db.scalar(
            select(Refund)
            .options(
                selectinload(Refund.order).selectinload(Order.user),
                selectinload(Refund.ledger_entries),
            )
            .where(Refund.id == refund_id)
        )
        if not refund:
            raise HTTPException(status_code=404, detail=f"Refund #{refund_id} not found.")

        order = refund.order
        customer = order.user if order else None
        return RefundResponse(
            id=refund.id,
            refund_number=refund.refund_number,
            order_id=refund.order_id,
            customer_id=refund.customer_id,
            customer_name=customer.name if customer else None,
            customer_email=customer.email if customer else None,
            order_total=order.total if order else None,
            order_status=order.status if order else None,
            order_payment_status=order.payment_status if order else None,
            amount=refund.amount,
            currency=refund.currency,
            refund_method=refund.refund_method,
            status=refund.status,
            reason=refund.reason,
            notes=refund.notes,
            restock_items=refund.restock_items,
            restocked=refund.restocked,
            warehouse_id=refund.warehouse_id,
            external_reference=refund.external_reference,
            requested_at=refund.requested_at,
            approved_at=refund.approved_at,
            processed_at=refund.processed_at,
            created_at=refund.created_at,
            updated_at=refund.updated_at,
            ledger_entries=[
                RefundLedgerEntryResponse(
                    id=le.id,
                    journal_ref=le.journal_ref,
                    refund_id=le.refund_id,
                    order_id=le.order_id,
                    entry_type=le.entry_type,
                    account_code=le.account_code,
                    account_name=le.account_name,
                    debit_amount=le.debit_amount,
                    credit_amount=le.credit_amount,
                    currency=le.currency,
                    memo=le.memo,
                    created_by_user_id=le.created_by_user_id,
                    created_at=le.created_at,
                )
                for le in sorted(refund.ledger_entries, key=lambda item: item.id)
            ],
        )

    @staticmethod
    def _resolve_refund_lookup(db: Session, refund_identifier: str | int) -> Refund:
        raw = str(refund_identifier).strip()
        if raw.isdigit():
            refund = db.scalar(select(Refund).where(Refund.id == int(raw)))
        else:
            upper = raw.upper()
            refund = db.scalar(select(Refund).where(Refund.refund_number == upper))
            if refund is None and upper.startswith("REF-"):
                suffix = upper.replace("REF-", "", 1)
                if suffix.isdigit():
                    refund = db.scalar(select(Refund).where(Refund.id == int(suffix)))
        if not refund:
            raise HTTPException(status_code=404, detail=f"Refund '{refund_identifier}' not found.")
        return refund

    @staticmethod
    def list_refunds(
        db: Session,
        *,
        status_filter: str | None = None,
        search: str | None = None,
        order_id: int | None = None,
    ) -> list[RefundResponse]:
        query = select(Refund).order_by(Refund.created_at.desc(), Refund.id.desc())
        if status_filter and status_filter.strip().lower() != "all":
            query = query.where(Refund.status == status_filter.strip().lower())
        if order_id is not None:
            query = query.where(Refund.order_id == order_id)
        if search and search.strip():
            term = f"%{search.strip()}%"
            user_ids = select(User.id).where(
                or_(User.name.ilike(term), User.email.ilike(term))
            )
            query = query.where(
                or_(
                    Refund.refund_number.ilike(term),
                    Refund.reason.ilike(term),
                    Refund.customer_id.in_(user_ids),
                )
            )
        rows = list(db.scalars(query).all())
        return [RefundService._serialize_refund(db, r.id) for r in rows]

    @staticmethod
    def get_refund(db: Session, refund_identifier: str | int) -> RefundResponse:
        refund = RefundService._resolve_refund_lookup(db, refund_identifier)
        return RefundService._serialize_refund(db, refund.id)

    @staticmethod
    def _cumulative_active_refund_amount(db: Session, order_id: int, exclude_refund_id: int | None = None) -> Decimal:
        query = select(func.coalesce(func.sum(Refund.amount), Decimal("0.00"))).where(
            Refund.order_id == order_id,
            Refund.status.in_(["requested", "approved", "processed"]),
        )
        if exclude_refund_id is not None:
            query = query.where(Refund.id != exclude_refund_id)
        return Decimal(db.scalar(query) or 0)

    @staticmethod
    def create_refund(
        db: Session,
        data: RefundCreateRequest,
        *,
        actor: User,
    ) -> RefundResponse:
        order = db.scalar(select(Order).where(Order.id == data.order_id).with_for_update())
        if not order:
            raise HTTPException(status_code=404, detail=f"Order #{data.order_id} not found.")

        if actor.role != "admin" and order.user_id != actor.id:
            raise HTTPException(status_code=403, detail="Permission denied.")

        if (order.payment_status or "").strip().lower() not in {"paid", "refunded"}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Order #{order.id} cannot be refunded because payment_status is '{order.payment_status}'.",
            )

        if data.restock_items and (order.status or "").lower() == "cancelled":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Stock for cancelled orders has already been restored.",
            )

        already_claimed = RefundService._cumulative_active_refund_amount(db, order.id)
        remaining_refundable = (Decimal(order.total) - already_claimed).quantize(Decimal("0.01"))
        if remaining_refundable <= Decimal("0.00"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Order #{order.id} has already been fully refunded or claimed by active refund requests.",
            )

        refund_amount = (
            Decimal(data.amount).quantize(Decimal("0.01"))
            if data.amount is not None
            else remaining_refundable
        )
        if refund_amount <= Decimal("0.00"):
            raise HTTPException(status_code=400, detail="Refund amount must be greater than zero.")
        if refund_amount > remaining_refundable:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Refund amount (${refund_amount:.2f}) exceeds remaining refundable balance "
                    f"(${remaining_refundable:.2f}) on Order #{order.id}."
                ),
            )

        canonical_method = RefundService._normalize_refund_method(
            data.refund_method,
            fallback=order.payment_method or "Cash on Delivery",
        )

        refund = Refund(
            refund_number=RefundService._new_ref("REF"),
            order_id=order.id,
            customer_id=order.user_id,
            requested_by_user_id=actor.id,
            amount=refund_amount,
            currency=settings.PAYMENT_CURRENCY,
            refund_method=canonical_method,
            status="requested",
            reason=data.reason.strip(),
            notes=data.notes.strip() if data.notes else None,
            restock_items=data.restock_items,
            restocked=False,
            warehouse_id=data.warehouse_id,
        )
        db.add(refund)
        db.commit()
        return RefundService._serialize_refund(db, refund.id)

    @staticmethod
    def approve_refund(
        db: Session,
        refund_identifier: str | int,
        data: RefundApproveRequest,
        *,
        actor: User,
    ) -> RefundResponse:
        target = RefundService._resolve_refund_lookup(db, refund_identifier)
        refund = db.scalar(select(Refund).where(Refund.id == target.id).with_for_update())
        assert refund is not None
        if refund.status != "requested":
            raise HTTPException(
                status_code=409,
                detail=f"Refund {refund.refund_number} in '{refund.status}' status cannot be approved.",
            )

        now = datetime.now(timezone.utc)
        refund.status = "approved"
        refund.approved_at = now
        if data.notes:
            refund.notes = f"{refund.notes} | {data.notes.strip()}".strip(" |") if refund.notes else data.notes.strip()

        RefundService._post_balanced_entries(
            db,
            refund=refund,
            entry_type="refund_accrual",
            lines=[
                ("4100", refund.amount, Decimal("0.00")),
                ("2100", Decimal("0.00"), refund.amount),
            ],
            memo=f"Accrued refund {refund.refund_number} for Order #{refund.order_id}: {refund.reason}",
            actor_user_id=actor.id,
        )
        db.commit()
        return RefundService._serialize_refund(db, refund.id)

    @staticmethod
    def _execute_stripe_refund_if_applicable(
        db: Session,
        refund: Refund,
    ) -> str | None:
        if "card" not in refund.refund_method.lower():
            return None
        if not (settings.STRIPE_SECRET_KEY and settings.STRIPE_SECRET_KEY.strip()):
            return None

        tx = db.scalar(
            select(PaymentTransaction)
            .where(
                PaymentTransaction.order_id == refund.order_id,
                PaymentTransaction.provider == "stripe",
                PaymentTransaction.status == "captured",
                PaymentTransaction.provider_reference.is_not(None),
            )
            .order_by(PaymentTransaction.id.desc())
        )
        if tx is None or not tx.provider_reference:
            return None

        amount_cents = int((refund.amount * Decimal("100")).quantize(Decimal("1")))
        try:
            resp = httpx.post(
                f"{settings.STRIPE_API_BASE_URL.rstrip('/')}/refunds",
                auth=(settings.STRIPE_SECRET_KEY.strip(), ""),
                data={
                    "payment_intent": tx.provider_reference,
                    "amount": str(amount_cents),
                    "reason": "requested_by_customer",
                    "metadata[refund_number]": refund.refund_number,
                    "metadata[order_id]": str(refund.order_id),
                },
                headers={"Idempotency-Key": f"refund-{refund.refund_number}"},
                timeout=15.0,
            )
            if resp.status_code >= 300:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Stripe card refund execution failed.",
                )
            body = resp.json()
            return body.get("id")
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unable to reach Stripe to process card refund.",
            ) from exc

    @staticmethod
    def process_refund(
        db: Session,
        refund_identifier: str | int,
        data: RefundProcessRequest,
        *,
        actor: User,
    ) -> RefundResponse:
        target = RefundService._resolve_refund_lookup(db, refund_identifier)
        refund = db.scalar(select(Refund).where(Refund.id == target.id).with_for_update())
        assert refund is not None
        if refund.status not in {"requested", "approved"}:
            raise HTTPException(
                status_code=409,
                detail=f"Refund {refund.refund_number} in '{refund.status}' status cannot be processed.",
            )

        order = db.scalar(
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.id == refund.order_id)
            .with_for_update()
        )
        assert order is not None

        now = datetime.now(timezone.utc)
        if refund.status == "requested":
            refund.approved_at = now
            RefundService._post_balanced_entries(
                db,
                refund=refund,
                entry_type="refund_accrual",
                lines=[
                    ("4100", refund.amount, Decimal("0.00")),
                    ("2100", Decimal("0.00"), refund.amount),
                ],
                memo=f"Accrued refund {refund.refund_number} for Order #{refund.order_id}: {refund.reason}",
                actor_user_id=actor.id,
            )

        ext_ref = data.external_reference.strip() if data.external_reference else None
        if not ext_ref:
            ext_ref = RefundService._execute_stripe_refund_if_applicable(db, refund)

        clearing_code, _ = RefundService._clearing_account_for_method(refund.refund_method)
        RefundService._post_balanced_entries(
            db,
            refund=refund,
            entry_type="refund_settlement",
            lines=[
                ("2100", refund.amount, Decimal("0.00")),
                (clearing_code, Decimal("0.00"), refund.amount),
            ],
            memo=(
                f"Settled refund {refund.refund_number} via {refund.refund_method}"
                + (f" ({ext_ref})" if ext_ref else "")
            ),
            actor_user_id=actor.id,
        )

        effective_restock = data.restock_items if data.restock_items is not None else refund.restock_items
        effective_wh_id = data.warehouse_id or refund.warehouse_id
        if effective_restock and not refund.restocked and (order.status or "").lower() != "cancelled":
            items_to_restore = [
                (item.product_id, item.quantity)
                for item in order.items
                if item.product_id is not None
            ]
            if items_to_restore:
                InventoryService.restore_stock(
                    db,
                    items_to_restore,
                    warehouse_id=effective_wh_id,
                    entry_type="refund_restock",
                    reference_type="refund",
                    reference_id=refund.id,
                    reason=f"Restocked via {refund.refund_number}",
                    actor_user_id=actor.id,
                )
                refund.restocked = True
                refund.restock_items = True
                refund.warehouse_id = effective_wh_id

        refund.status = "processed"
        refund.processed_at = now
        refund.processed_by_user_id = actor.id
        if ext_ref:
            refund.external_reference = ext_ref
        if data.notes:
            refund.notes = f"{refund.notes} | {data.notes.strip()}".strip(" |") if refund.notes else data.notes.strip()

        total_processed = (
            db.scalar(
                select(func.coalesce(func.sum(Refund.amount), Decimal("0.00"))).where(
                    Refund.order_id == order.id,
                    Refund.status == "processed",
                )
            )
            or Decimal("0.00")
        )
        # Flush first so SUM includes current refund
        db.flush()
        total_processed = (
            db.scalar(
                select(func.coalesce(func.sum(Refund.amount), Decimal("0.00"))).where(
                    Refund.order_id == order.id,
                    Refund.status == "processed",
                )
            )
            or Decimal("0.00")
        )
        if Decimal(total_processed) >= Decimal(order.total):
            order.payment_status = "refunded"
            for tx in db.scalars(
                select(PaymentTransaction).where(
                    PaymentTransaction.order_id == order.id,
                    PaymentTransaction.status == "captured",
                )
            ).all():
                tx.status = "refunded"

        db.add(
            Notification(
                user_id=order.user_id,
                type="order",
                title=f"Refund {refund.refund_number} Processed",
                message=f"A refund of ${refund.amount:.2f} for Order #{order.id} has been settled ({refund.refund_method}).",
                link=f"/orders/{order.id}",
                read=False,
            )
        )
        db.commit()
        return RefundService._serialize_refund(db, refund.id)

    @staticmethod
    def reject_refund(
        db: Session,
        refund_identifier: str | int,
        data: RefundRejectRequest,
        *,
        actor: User,
    ) -> RefundResponse:
        target = RefundService._resolve_refund_lookup(db, refund_identifier)
        refund = db.scalar(select(Refund).where(Refund.id == target.id).with_for_update())
        assert refund is not None
        if refund.status not in {"requested", "approved"}:
            raise HTTPException(
                status_code=409,
                detail=f"Refund {refund.refund_number} in '{refund.status}' status cannot be rejected.",
            )

        was_approved = refund.status == "approved"
        refund.status = "rejected"
        refund.processed_by_user_id = actor.id
        rejection_note = f"Rejected: {data.reason.strip()}"
        refund.notes = f"{refund.notes} | {rejection_note}".strip(" |") if refund.notes else rejection_note

        if was_approved:
            # Reverse the previously posted accrual
            RefundService._post_balanced_entries(
                db,
                refund=refund,
                entry_type="refund_reversal",
                lines=[
                    ("2100", refund.amount, Decimal("0.00")),
                    ("4100", Decimal("0.00"), refund.amount),
                ],
                memo=f"Reversed approved refund {refund.refund_number}: {data.reason.strip()}",
                actor_user_id=actor.id,
            )

        db.commit()
        return RefundService._serialize_refund(db, refund.id)

    @staticmethod
    def record_order_refund_inline(
        db: Session,
        *,
        order: Order,
        actor: User | None,
        reason: str,
    ) -> Refund:
        """Record a real Refund + balanced accrual & settlement entries inside an order refund commit."""
        already_processed = (
            db.scalar(
                select(func.coalesce(func.sum(Refund.amount), Decimal("0.00"))).where(
                    Refund.order_id == order.id,
                    Refund.status == "processed",
                )
            )
            or Decimal("0.00")
        )
        amount_to_record = (Decimal(order.total) - Decimal(already_processed)).quantize(Decimal("0.01"))
        if amount_to_record <= Decimal("0.00"):
            existing = db.scalar(
                select(Refund).where(Refund.order_id == order.id).order_by(Refund.id.desc())
            )
            if existing is not None:
                return existing
            amount_to_record = Decimal(order.total).quantize(Decimal("0.01"))

        canonical_method = RefundService._normalize_refund_method(
            order.payment_method,
            fallback="Cash on Delivery",
        )
        now = datetime.now(timezone.utc)
        refund = Refund(
            refund_number=RefundService._new_ref("REF"),
            order_id=order.id,
            customer_id=order.user_id,
            requested_by_user_id=actor.id if actor else None,
            processed_by_user_id=actor.id if actor else None,
            amount=amount_to_record,
            currency=settings.PAYMENT_CURRENCY,
            refund_method=canonical_method,
            status="processed",
            reason=reason.strip(),
            restock_items=False,
            restocked=False,
            requested_at=now,
            approved_at=now,
            processed_at=now,
        )
        db.add(refund)
        db.flush()

        actor_id = actor.id if actor else None
        RefundService._post_balanced_entries(
            db,
            refund=refund,
            entry_type="refund_accrual",
            lines=[
                ("4100", amount_to_record, Decimal("0.00")),
                ("2100", Decimal("0.00"), amount_to_record),
            ],
            memo=f"Accrued refund {refund.refund_number} via order status update: {reason.strip()}",
            actor_user_id=actor_id,
        )
        clearing_code, _ = RefundService._clearing_account_for_method(canonical_method)
        RefundService._post_balanced_entries(
            db,
            refund=refund,
            entry_type="refund_settlement",
            lines=[
                ("2100", amount_to_record, Decimal("0.00")),
                (clearing_code, Decimal("0.00"), amount_to_record),
            ],
            memo=f"Settled refund {refund.refund_number} via {canonical_method}",
            actor_user_id=actor_id,
        )
        for tx in db.scalars(
            select(PaymentTransaction).where(
                PaymentTransaction.order_id == order.id,
                PaymentTransaction.status == "captured",
            )
        ).all():
            tx.status = "refunded"
        return refund

    @staticmethod
    def list_ledger(
        db: Session,
        *,
        refund_id: int | None = None,
        account_code: str | None = None,
        page: int = 1,
        limit: int = 50,
    ) -> RefundLedgerListResponse:
        page = max(1, page)
        limit = max(1, min(100, limit))
        query = select(RefundLedgerEntry)
        if refund_id is not None:
            query = query.where(RefundLedgerEntry.refund_id == refund_id)
        if account_code and account_code.strip().lower() != "all":
            query = query.where(RefundLedgerEntry.account_code == account_code.strip())

        total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
        offset = (page - 1) * limit
        entries = list(
            db.scalars(
                query.order_by(RefundLedgerEntry.created_at.desc(), RefundLedgerEntry.id.desc())
                .offset(offset)
                .limit(limit)
            ).all()
        )

        # Trial balance across all ledger entries
        account_rows = db.execute(
            select(
                RefundLedgerEntry.account_code,
                RefundLedgerEntry.account_name,
                func.coalesce(func.sum(RefundLedgerEntry.debit_amount), Decimal("0.00")),
                func.coalesce(func.sum(RefundLedgerEntry.credit_amount), Decimal("0.00")),
            )
            .group_by(RefundLedgerEntry.account_code, RefundLedgerEntry.account_name)
            .order_by(RefundLedgerEntry.account_code.asc())
        ).all()

        accounts: list[RefundAccountBalance] = []
        total_debits = Decimal("0.00")
        total_credits = Decimal("0.00")
        for code, name, deb, cred in account_rows:
            d = Decimal(deb or 0).quantize(Decimal("0.01"))
            c = Decimal(cred or 0).quantize(Decimal("0.01"))
            total_debits += d
            total_credits += c
            accounts.append(
                RefundAccountBalance(
                    account_code=code,
                    account_name=name,
                    total_debits=d,
                    total_credits=c,
                    net_balance=(d - c).quantize(Decimal("0.01")),
                )
            )

        return RefundLedgerListResponse(
            entries=[
                RefundLedgerEntryResponse(
                    id=le.id,
                    journal_ref=le.journal_ref,
                    refund_id=le.refund_id,
                    order_id=le.order_id,
                    entry_type=le.entry_type,
                    account_code=le.account_code,
                    account_name=le.account_name,
                    debit_amount=le.debit_amount,
                    credit_amount=le.credit_amount,
                    currency=le.currency,
                    memo=le.memo,
                    created_by_user_id=le.created_by_user_id,
                    created_at=le.created_at,
                )
                for le in entries
            ],
            trial_balance=RefundLedgerTrialBalance(
                total_debits=total_debits.quantize(Decimal("0.01")),
                total_credits=total_credits.quantize(Decimal("0.01")),
                balanced=(total_debits == total_credits),
                accounts=accounts,
            ),
            total=int(total),
            page=page,
            limit=limit,
        )
