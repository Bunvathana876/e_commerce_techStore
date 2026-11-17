from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.models.user import User
from app.schemas.pos import (
    PosCheckoutRequest,
    PosReceiptItem,
    PosReceiptResponse,
    PosSummaryResponse,
)
from app.services.inventory_service import InventoryService

TWOPLACES = Decimal("0.01")
ZERO = Decimal("0.00")
MAX_MONEY = Decimal("99999999.99")

CASH_POS_METHODS = {"cash"}
COD_METHODS = {"cash on delivery", "cod", "cash on delivery (cod)"}
UNVERIFIED_NON_CASH_POS_METHODS = {
    "credit card",
    "debit card",
    "card",
    "credit / debit card",
    "qr pay",
    "khqr",
    "aba khqr",
    "khqr scan & pay",
}


class PosService:
    @staticmethod
    def _quantize_money(value: Decimal | int | str, field_name: str) -> Decimal:
        try:
            dec = Decimal(value)
        except (InvalidOperation, TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid monetary value for {field_name}.",
            ) from None

        if not dec.is_finite() or dec < ZERO or dec > MAX_MONEY:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} must be between 0.00 and {MAX_MONEY}.",
            )

        return dec.quantize(TWOPLACES, rounding=ROUND_HALF_UP)

    @staticmethod
    def _effective_product_price(product: Product) -> Decimal:
        raw_price = (
            product.discount_price
            if product.discount_price is not None and Decimal(product.discount_price) > ZERO
            else product.price
        )
        unit_price = PosService._quantize_money(raw_price, f"catalog price for '{product.name}'")
        if unit_price <= ZERO:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Product '{product.name}' has an invalid catalog price.",
            )
        return unit_price

    @staticmethod
    def _resolve_payment_terms(
        raw_method: str | None,
        raw_amount_paid: Decimal,
        final_total: Decimal,
    ) -> tuple[str, str, str, Decimal, Decimal]:
        method_clean = (raw_method or "Cash").strip()
        if not method_clean:
            method_clean = "Cash"
        method_key = method_clean.lower()

        amount_paid_in = PosService._quantize_money(raw_amount_paid, "amount_paid")

        if method_key in CASH_POS_METHODS:
            if amount_paid_in < final_total:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Insufficient cash tendered: received ${amount_paid_in:.2f}, "
                        f"amount due is ${final_total:.2f}."
                    ),
                )
            change_due = (amount_paid_in - final_total).quantize(
                TWOPLACES, rounding=ROUND_HALF_UP
            )
            return "Cash", "paid", "delivered", amount_paid_in, change_due

        if method_key in COD_METHODS:
            if amount_paid_in > ZERO:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cash on Delivery orders cannot record upfront cash tender at POS.",
                )
            return "Cash on Delivery", "pending", "pending", ZERO, ZERO

        if method_key in UNVERIFIED_NON_CASH_POS_METHODS:
            if amount_paid_in != ZERO and amount_paid_in != final_total:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Non-cash tender amount (${amount_paid_in:.2f}) does not match "
                        f"server total (${final_total:.2f})."
                    ),
                )
            # Non-cash methods are not gateway-verified; never mark them paid automatically.
            return method_clean, "pending", "pending", ZERO, ZERO

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported POS payment method '{method_clean}'.",
        )

    @staticmethod
    def process_checkout(
        db: Session,
        cashier: User,
        request: PosCheckoutRequest,
    ) -> PosReceiptResponse:
        if not request.items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="POS Cart is empty. Please select at least one product.",
            )

        try:
            # 1. Resolve customer without mutating request model in place
            target_user_id = cashier.id
            resolved_customer_name = (request.customer_name or "").strip() or "Walk-in Customer"
            resolved_customer_phone = request.customer_phone

            if request.customer_id is not None:
                customer = db.scalar(
                    select(User).where(
                        User.id == request.customer_id,
                        User.is_active.is_(True),
                    )
                )
                if customer is None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Customer #{request.customer_id} is inactive or not found.",
                    )
                target_user_id = customer.id
                resolved_customer_name = customer.name
                if not resolved_customer_phone and customer.phone:
                    resolved_customer_phone = customer.phone

            # 2. Aggregate duplicate lines in deterministic product_id order and validate prices
            ordered_requirements = InventoryService.aggregate_quantities(
                [(item_in.product_id, item_in.quantity) for item_in in request.items]
            )

            products_by_id: dict[int, Product] = {}
            for product_id, _total_qty in ordered_requirements:
                product = db.scalar(select(Product).where(Product.id == product_id))
                if not product or not product.is_active:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Product #{product_id} is inactive or not found.",
                    )
                products_by_id[product_id] = product

            computed_subtotal = ZERO
            validated_lines: list[tuple[Product, int, Decimal, Decimal]] = []

            for item_in in request.items:
                product = products_by_id[item_in.product_id]
                unit_price = PosService._effective_product_price(product)

                if item_in.price is not None:
                    submitted_price = PosService._quantize_money(item_in.price, "item price")
                    if submitted_price != unit_price:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=(
                                f"Submitted price (${submitted_price:.2f}) for '{product.name}' "
                                f"does not match catalog price (${unit_price:.2f})."
                            ),
                        )

                item_subtotal = (unit_price * item_in.quantity).quantize(
                    TWOPLACES, rounding=ROUND_HALF_UP
                )
                computed_subtotal = (computed_subtotal + item_subtotal).quantize(
                    TWOPLACES, rounding=ROUND_HALF_UP
                )
                validated_lines.append((product, item_in.quantity, unit_price, item_subtotal))

            # 3. Validate server-side discount, tax, total, and tender before mutating DB state
            discount = PosService._quantize_money(request.discount_amount, "discount_amount")
            if discount > computed_subtotal:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Discount (${discount:.2f}) cannot exceed subtotal "
                        f"(${computed_subtotal:.2f})."
                    ),
                )

            tax = PosService._quantize_money(request.tax_amount, "tax_amount")
            if tax > computed_subtotal:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Tax (${tax:.2f}) cannot exceed subtotal "
                        f"(${computed_subtotal:.2f})."
                    ),
                )

            final_total = (computed_subtotal - discount + tax).quantize(
                TWOPLACES, rounding=ROUND_HALF_UP
            )
            if final_total > MAX_MONEY:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Calculated order total exceeds maximum allowed limit.",
                )

            (
                canonical_method,
                payment_status,
                order_status,
                amount_paid,
                change_due,
            ) = PosService._resolve_payment_terms(
                raw_method=request.payment_method,
                raw_amount_paid=request.amount_paid,
                final_total=final_total,
            )

            # 4. Atomically deduct stock in deterministic product_id order (raises 409 on conflict)
            updated_products = InventoryService.deduct_stock(db, ordered_requirements)

            order_items_to_create: list[OrderItem] = []
            receipt_items: list[PosReceiptItem] = []

            for product, quantity, unit_price, item_subtotal in validated_lines:
                order_items_to_create.append(
                    OrderItem(
                        product_id=product.id,
                        product_name=product.name,
                        price=unit_price,
                        quantity=quantity,
                        subtotal=item_subtotal,
                    )
                )
                receipt_items.append(
                    PosReceiptItem(
                        product_id=product.id,
                        product_name=product.name,
                        price=unit_price,
                        quantity=quantity,
                        subtotal=item_subtotal,
                    )
                )

            for product_id, _total_qty in ordered_requirements:
                updated_product = updated_products[product_id]
                if updated_product.stock <= 5:
                    db.add(
                        Notification(
                            user_id=cashier.id,
                            title="⚠️ Low Stock Alert (POS)",
                            message=(
                                f"'{updated_product.name}' now has only {updated_product.stock} units "
                                "remaining in inventory after POS sale."
                            ),
                            type="inventory",
                            link="/admin/inventory",
                            read=False,
                        )
                    )

            shipping_text = (
                f"POS Store Checkout | Cashier: {cashier.name} | "
                f"Customer: {resolved_customer_name}"
            )
            if request.notes:
                shipping_text += f" | Note: {request.notes}"

            order = Order(
                user_id=target_user_id,
                status=order_status,
                subtotal=computed_subtotal,
                discount_amount=discount,
                coupon_code="POS_DIRECT",
                shipping_fee=ZERO,
                total=final_total,
                payment_method=canonical_method,
                payment_status=payment_status,
                shipping_address=shipping_text,
            )

            db.add(order)
            db.flush()

            for item in order_items_to_create:
                item.order_id = order.id
                db.add(item)

            notif_title = (
                "🧾 POS Sale Completed"
                if payment_status == "paid"
                else "🧾 POS Order Recorded (Payment Pending)"
            )
            db.add(
                Notification(
                    user_id=cashier.id,
                    title=notif_title,
                    message=(
                        f"Order #{order.id} for ${final_total:.2f} ({payment_status}) "
                        f"processed at register by {cashier.name}."
                    ),
                    type="order",
                    link=f"/admin/orders/{order.id}",
                    read=False,
                )
            )

            db.commit()
            db.refresh(order)
        except Exception:
            db.rollback()
            raise

        order_number = f"POS-{order.id:06d}"

        return PosReceiptResponse(
            order_id=order.id,
            order_number=order_number,
            subtotal=computed_subtotal,
            discount_amount=discount,
            tax_amount=tax,
            shipping_fee=ZERO,
            total=final_total,
            payment_method=order.payment_method,
            payment_status=order.payment_status,
            amount_paid=amount_paid,
            change_due=change_due,
            customer_name=resolved_customer_name,
            customer_phone=resolved_customer_phone,
            cashier_name=cashier.name,
            notes=request.notes,
            created_at=order.created_at,
            items=receipt_items,
        )

    @staticmethod
    def get_daily_summary(db: Session) -> PosSummaryResponse:
        today_date = datetime.now(timezone.utc).date()
        today_start = datetime.combine(today_date, datetime.min.time())

        # Count only verified paid, non-cancelled POS orders in daily sales totals.
        orders = db.scalars(
            select(Order).where(
                Order.created_at >= today_start,
                Order.shipping_address.like("POS Store Checkout%"),
                Order.payment_status == "paid",
                Order.status != "cancelled",
            )
        ).all()

        total_orders = len(orders)
        total_sales = ZERO
        cash_sales = ZERO
        card_sales = ZERO
        qr_sales = ZERO

        for o in orders:
            total_sales += o.total
            method = (o.payment_method or "").lower()
            if "cash" in method:
                cash_sales += o.total
            elif "card" in method or "credit" in method or "debit" in method:
                card_sales += o.total
            elif "qr" in method or "pay" in method or "bank" in method:
                qr_sales += o.total
            else:
                cash_sales += o.total

        return PosSummaryResponse(
            date=today_date.isoformat(),
            today_orders_count=total_orders,
            today_total_sales=total_sales,
            today_cash_sales=cash_sales,
            today_card_sales=card_sales,
            today_qr_sales=qr_sales,
        )
