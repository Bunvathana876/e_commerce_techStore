from decimal import Decimal
from fastapi import HTTPException, status
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session, selectinload

from app.models.cart import CartItem
from app.models.notification import Notification
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.models.user import User
from app.schemas.order import OrderCreateRequest, OrderResponse
from app.services.authorization_service import AuthorizationService
from app.services.inventory_service import InventoryService

ALLOWED_ORDER_STATUSES = {
    "pending",
    "processing",
    "shipped",
    "delivered",
    "cancelled",
}

ALLOWED_ORDER_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"processing", "cancelled"},
    "processing": {"shipped", "cancelled"},
    "shipped": {"delivered"},
    "delivered": set(),
    "cancelled": set(),
}

SELLER_ALLOWED_TARGET_STATUSES = {"processing", "shipped"}

ALLOWED_PAYMENT_STATUSES = {"pending", "paid", "failed", "refunded"}

ALLOWED_PAYMENT_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"paid", "failed"},
    "failed": {"pending"},
    "paid": {"refunded"},
    "refunded": set(),
}

CASH_SETTLEMENT_METHODS = {
    "cash",
    "cash on delivery",
    "cash on delivery (cod)",
    "cod",
}

COD_PAYMENT_METHODS = {
    "cash on delivery",
    "cash on delivery (cod)",
    "cod",
}

ALLOWED_CHECKOUT_PAYMENT_METHODS: dict[str, str] = {
    "cash on delivery": "Cash on Delivery",
    "cash on delivery (cod)": "Cash on Delivery",
    "cod": "Cash on Delivery",
    "credit / debit card": "Credit / Debit Card",
    "credit or debit card": "Credit / Debit Card",
    "credit card": "Credit Card",
    "debit card": "Debit Card",
    "card": "Credit / Debit Card",
    "khqr scan & pay": "KHQR Scan & Pay",
    "aba / khqr pay": "ABA / KHQR Pay",
    "aba khqr": "ABA / KHQR Pay",
    "khqr": "KHQR Scan & Pay",
    "qr pay": "QR Pay",
    "apple pay": "Apple Pay",
}


class OrderService:
    @staticmethod
    def _normalize_checkout_payment_method(raw_method: str | None) -> str:
        cleaned = (raw_method or "Cash on Delivery").strip()
        if not cleaned or any(ord(ch) < 32 for ch in cleaned):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A valid payment method is required.",
            )
        canonical = ALLOWED_CHECKOUT_PAYMENT_METHODS.get(cleaned.lower())
        if canonical is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported payment method '{cleaned}'.",
            )
        return canonical

    @staticmethod
    def _is_cash_settlement_method(method: str | None) -> bool:
        return (method or "").strip().lower() in CASH_SETTLEMENT_METHODS

    @staticmethod
    def _is_cod_method(method: str | None) -> bool:
        return (method or "").strip().lower() in COD_PAYMENT_METHODS

    @staticmethod
    def create_order(
        db: Session,
        user_id: int,
        request: OrderCreateRequest,
        idempotency_key: str | None = None,
        return_replay_status: bool = False,
    ) -> OrderResponse | tuple[OrderResponse, bool]:
        canonical_payment_method = OrderService._normalize_checkout_payment_method(
            request.payment_method
        )

        effective_key = idempotency_key or request.idempotency_key
        validated_key: str | None = None
        if effective_key:
            from app.services.idempotency_service import IdempotencyService

            validated_key = IdempotencyService.validate_key(effective_key)
            if validated_key:
                is_replay, cached_data = IdempotencyService.check_or_acquire(
                    db, user_id, validated_key
                )
                if is_replay and cached_data:
                    order_id = cached_data.get("id")
                    if order_id:
                        existing_order = OrderService.get_order_by_id(
                            db, order_id=order_id, user_id=user_id
                        )
                        return (
                            (existing_order, True)
                            if return_replay_status
                            else existing_order
                        )
                    resp = OrderResponse.model_validate(cached_data)
                    return (resp, True) if return_replay_status else resp

        # 1. Determine checkout items (atomic explicit items or user's server cart)
        checkout_items: list[tuple[int, int]] = []
        if request.items is not None:
            if not request.items:
                if validated_key:
                    from app.services.idempotency_service import IdempotencyService

                    IdempotencyService.release(db, user_id, validated_key)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Checkout items list cannot be empty.",
                )
            qty_by_prod: dict[int, int] = {}
            for item in request.items:
                if item.quantity < 1:
                    if validated_key:
                        from app.services.idempotency_service import IdempotencyService

                        IdempotencyService.release(db, user_id, validated_key)
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Item quantity must be at least 1.",
                    )
                qty_by_prod[item.product_id] = (
                    qty_by_prod.get(item.product_id, 0) + item.quantity
                )
            checkout_items = list(qty_by_prod.items())
        else:
            cart_items = list(
                db.scalars(
                    select(CartItem)
                    .options(selectinload(CartItem.product))
                    .where(CartItem.user_id == user_id)
                ).all()
            )
            if not cart_items:
                if validated_key:
                    from app.services.idempotency_service import IdempotencyService

                    IdempotencyService.release(db, user_id, validated_key)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Your cart is empty. Please add products before placing an order.",
                )
            for item in cart_items:
                if item.quantity < 1:
                    if validated_key:
                        from app.services.idempotency_service import IdempotencyService

                        IdempotencyService.release(db, user_id, validated_key)
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Item quantity must be at least 1.",
                    )
            checkout_items = [(item.product_id, item.quantity) for item in cart_items]

        try:
            # 2. Resolve shipping address before mutating inventory
            final_address = ""
            if request.shipping_address_id:
                from app.models.address import Address

                user_addr = db.scalar(
                    select(Address).where(
                        Address.id == request.shipping_address_id,
                        Address.user_id == user_id,
                    )
                )
                if user_addr:
                    parts = [
                        user_addr.full_name,
                        user_addr.phone,
                        user_addr.address_line,
                        user_addr.city,
                        user_addr.province,
                        user_addr.postal_code,
                    ]
                    final_address = ", ".join([p for p in parts if p])

            if not final_address:
                final_address = request.shipping_address or ""

            if not final_address.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="A valid shipping address is required.",
                )

            # 3. Atomically deduct stock in deterministic ID order
            updated_products = InventoryService.deduct_stock(
                db,
                checkout_items,
                inactive_detail_fn=lambda _pid, prod: (
                    f"Product '{prod.name if prod else 'Unknown'}' is no longer available."
                ),
            )

            subtotal = Decimal("0.00")
            order_items_to_create = []

            for product_id, quantity in checkout_items:
                product = updated_products[product_id]
                unit_price = (
                    product.discount_price
                    if product.discount_price and product.discount_price > 0
                    else product.price
                )
                item_subtotal = unit_price * quantity
                subtotal += item_subtotal

                order_items_to_create.append(
                    {
                        "product_id": product.id,
                        "product_name": product.name,
                        "price": unit_price,
                        "quantity": quantity,
                        "subtotal": item_subtotal,
                    }
                )

            # Calculate coupon discount if promo code was provided
            discount_amount = Decimal("0.00")
            applied_coupon_code = None
            if request.coupon_code and request.coupon_code.strip():
                from app.services.coupon_service import CouponService

                coupon_res = CouponService.redeem_coupon_atomic(
                    db=db,
                    code=request.coupon_code,
                    subtotal=subtotal,
                    user_id=user_id,
                )
                discount_amount = coupon_res.discount_amount
                applied_coupon_code = coupon_res.code

            # Standard shipping fee (free if subtotal >= 100)
            shipping_fee = (
                Decimal("0.00")
                if subtotal >= Decimal("100.00")
                else Decimal("2.00")
            )
            total = max(Decimal("0.00"), subtotal - discount_amount + shipping_fee)

            # 3. Create Order — payment_status always starts pending until verified/settled
            new_order = Order(
                user_id=user_id,
                status="pending",
                subtotal=subtotal,
                discount_amount=discount_amount,
                coupon_code=applied_coupon_code,
                shipping_fee=shipping_fee,
                total=total,
                payment_method=canonical_payment_method,
                payment_status="pending",
                shipping_address=final_address.strip(),
            )
            db.add(new_order)
            db.flush()

            # 4. Create Order Items with historical price snapshots
            for oi_data in order_items_to_create:
                order_item = OrderItem(
                    order_id=new_order.id,
                    product_id=oi_data["product_id"],
                    product_name=oi_data["product_name"],
                    price=oi_data["price"],
                    quantity=oi_data["quantity"],
                    subtotal=oi_data["subtotal"],
                )
                db.add(order_item)

            # 5. Clear user's cart (or checked-out items)
            if request.items is not None:
                checked_out_product_ids = [pid for pid, _ in checkout_items]
                db.execute(
                    delete(CartItem).where(
                        CartItem.user_id == user_id,
                        CartItem.product_id.in_(checked_out_product_ids),
                    )
                )
            else:
                db.execute(delete(CartItem).where(CartItem.user_id == user_id))

            # 6. Add notification
            order_notif = Notification(
                user_id=user_id,
                type="order",
                title=f"Order #{new_order.id} Placed Successfully 🎉",
                message=f"Thank you for your order of ${total:.2f}. We're preparing your items for delivery.",
                link=f"/orders/{new_order.id}",
                read=False,
            )
            db.add(order_notif)

            # 7. Atomically complete idempotency record in the same commit
            if validated_key:
                from datetime import datetime, timezone
                from app.models.idempotency import IdempotencyRecord

                db.flush()  # Populates new_order.id
                idem_rec = db.scalar(
                    select(IdempotencyRecord).where(
                        IdempotencyRecord.user_id == user_id,
                        IdempotencyRecord.key == validated_key,
                    )
                )
                if idem_rec:
                    idem_rec.status = "completed"
                    idem_rec.order_id = new_order.id
                    idem_rec.updated_at = datetime.now(timezone.utc)

            # Commit transaction: Order, items, stock, cart cleanup, and idempotency record
            db.commit()
        except Exception:
            db.rollback()
            # Acquisition is part of this transaction. Never delete the key
            # after rollback: another worker may already have acquired it.
            raise

        # 8. Reload and return complete order with items and user
        loaded_order = db.scalar(
            select(Order)
            .options(
                selectinload(Order.items),
                selectinload(Order.user),
            )
            .where(Order.id == new_order.id)
        )
        response_model = OrderResponse.model_validate(loaded_order)

        if return_replay_status:
            return response_model, False
        return response_model

    @staticmethod
    def get_user_orders(db: Session, user_id: int) -> list[OrderResponse]:
        orders = list(
            db.scalars(
                select(Order)
                .options(
                    selectinload(Order.items),
                    selectinload(Order.user),
                )
                .where(Order.user_id == user_id)
                .order_by(Order.created_at.desc())
            ).all()
        )
        return [OrderResponse.model_validate(o) for o in orders]

    @staticmethod
    def get_order_by_id(
        db: Session, order_id: int, user_id: int | None = None
    ) -> OrderResponse:
        query = select(Order).options(
            selectinload(Order.items),
            selectinload(Order.user),
        ).where(Order.id == order_id)

        if user_id is not None:
            query = query.where(Order.user_id == user_id)

        order = db.scalar(query)
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found.",
            )
        return OrderResponse.model_validate(order)

    @staticmethod
    def get_all_orders(db: Session, limit: int | None = None) -> list[OrderResponse]:
        query = (
            select(Order)
            .options(
                selectinload(Order.items),
                selectinload(Order.user),
            )
            .order_by(Order.created_at.desc())
        )
        if limit is not None and limit > 0:
            query = query.limit(limit)
        orders = list(db.scalars(query).all())
        return [OrderResponse.model_validate(o) for o in orders]

    @staticmethod
    def update_order_status(
        db: Session,
        order_id: int,
        status_val: str | None = None,
        payment_status_val: str | None = None,
        actor: User | None = None,
        reason: str | None = None,
    ) -> OrderResponse:
        if status_val is None and payment_status_val is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one of 'status' or 'payment_status' must be provided.",
            )

        target_status: str | None = None
        if status_val is not None:
            target_status = status_val.strip().lower()
            if target_status not in ALLOWED_ORDER_STATUSES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Invalid order status '{status_val}'. "
                        f"Allowed values: {', '.join(sorted(ALLOWED_ORDER_STATUSES))}."
                    ),
                )

        target_payment: str | None = None
        if payment_status_val is not None:
            target_payment = payment_status_val.strip().lower()
            if target_payment not in ALLOWED_PAYMENT_STATUSES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Invalid payment status '{payment_status_val}'. "
                        f"Allowed values: {', '.join(sorted(ALLOWED_PAYMENT_STATUSES))}."
                    ),
                )

        # Enforce actor role & seller action constraints before loading order
        seller_store_ids: set[int] = set()
        if actor is not None:
            if actor.role == "seller":
                seller_store_ids = set(AuthorizationService.seller_ids(db, actor))
                if not seller_store_ids:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="An active seller account is required.",
                    )
                if target_payment is not None or target_status not in SELLER_ALLOWED_TARGET_STATUSES:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Sellers may only advance fulfillment status to processing or shipped.",
                    )
            elif not AuthorizationService.is_admin(actor):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Permission denied.",
                )

        order = db.scalar(
            select(Order)
            .options(
                selectinload(Order.items).selectinload(OrderItem.product),
                selectinload(Order.user),
            )
            .where(Order.id == order_id)
        )
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found.",
            )

        # Enforce strict seller item ownership when actor is a seller
        if actor is not None and actor.role == "seller":
            if not order.items or any(
                item.product is None or item.product.seller_id not in seller_store_ids
                for item in order.items
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Permission denied: order contains items outside your store.",
                )

        current_status = (order.status or "pending").strip().lower()
        current_payment = (order.payment_status or "pending").strip().lower()

        # 1. Validate order status transition (if changing)
        if target_status == "cancelled" and current_status == "cancelled" and target_payment is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Order #{order.id} is already cancelled.",
            )

        status_changed = target_status is not None and target_status != current_status
        if status_changed:
            allowed_next = ALLOWED_ORDER_TRANSITIONS.get(current_status, set())
            if target_status not in allowed_next:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Invalid order status transition from '{current_status}' "
                        f"to '{target_status}'."
                    ),
                )

        effective_status = target_status if target_status is not None else current_status

        # Prevent cancelling a paid order unless simultaneously refunded or already refunded
        if (
            status_changed
            and target_status == "cancelled"
            and current_payment == "paid"
            and target_payment != "refunded"
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Paid orders cannot be cancelled without recording a 'refunded' payment status and reason.",
            )

        # 2. Validate payment status transition & verification rules (if changing)
        payment_changed = target_payment is not None and target_payment != current_payment
        clean_reason = (reason or "").strip()

        if payment_changed:
            if actor is None or not AuthorizationService.is_admin(actor):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only an authorized administrator can update payment status.",
                )

            allowed_pay_next = ALLOWED_PAYMENT_TRANSITIONS.get(current_payment, set())
            if target_payment not in allowed_pay_next:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Invalid payment status transition from '{current_payment}' "
                        f"to '{target_payment}'."
                    ),
                )

            if effective_status == "cancelled" and target_payment != "refunded":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Cannot set payment status to '{target_payment}' on a cancelled order.",
                )

            if target_payment == "paid":
                if not OrderService._is_cash_settlement_method(order.payment_method):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            f"Cannot mark electronic payment method '{order.payment_method}' as paid "
                            "without trusted payment gateway verification."
                        ),
                    )
                if OrderService._is_cod_method(order.payment_method) and effective_status not in {
                    "shipped",
                    "delivered",
                }:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Cash on Delivery payment can only be settled after shipment or delivery.",
                    )
                if len(clean_reason) < 3:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Manual cash settlement requires a recorded reason or receipt reference.",
                    )

            if target_payment == "refunded" and len(clean_reason) < 3:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Marking a payment as refunded requires a recorded reason or refund reference.",
                )

        # 3. Apply validated mutations atomically inside a rollback-safe transaction
        try:
            if status_changed and target_status is not None:
                transition_res = db.execute(
                    update(Order)
                    .where(
                        Order.id == order.id,
                        Order.status == current_status,
                        Order.payment_status == current_payment,
                    )
                    .values(status=target_status)
                    .execution_options(synchronize_session=False)
                )
                if transition_res.rowcount != 1:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            f"Order #{order.id} status changed concurrently; "
                            f"cannot transition from '{current_status}' to '{target_status}'."
                        ),
                    )
                order.status = target_status

                if target_status == "cancelled":
                    InventoryService.restore_stock(
                        db,
                        [
                            (item.product_id, item.quantity)
                            for item in order.items
                            if item.product_id is not None
                        ],
                    )
                    if order.coupon_code:
                        from app.services.coupon_service import CouponService
                        CouponService.restore_coupon_usage(db, order.coupon_code)

                status_titles = {
                    "processing": f"Order #{order.id} is Processing ⚙️",
                    "shipped": f"Order #{order.id} has Shipped! 🚚",
                    "delivered": f"Order #{order.id} Delivered! 🎁",
                    "cancelled": f"Order #{order.id} Cancelled ❌",
                }
                title = status_titles.get(target_status, f"Order #{order.id} Update")
                db.add(
                    Notification(
                        user_id=order.user_id,
                        type="delivery" if target_status in ("shipped", "delivered") else "order",
                        title=title,
                        message=f"Status for your order #{order.id} has been updated to '{target_status.title()}'.",
                        link=f"/orders/{order.id}",
                        read=False,
                    )
                )

            if payment_changed and target_payment is not None:
                pay_res = db.execute(
                    update(Order)
                    .where(
                        Order.id == order.id,
                        Order.payment_status == current_payment,
                        Order.status == effective_status,
                    )
                    .values(payment_status=target_payment)
                    .execution_options(synchronize_session=False)
                )
                if pay_res.rowcount != 1:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            f"Order #{order.id} payment status changed concurrently; "
                            f"cannot transition from '{current_payment}' to '{target_payment}'."
                        ),
                    )
                order.payment_status = target_payment
                actor_label = f"Admin #{actor.id} ({actor.email})" if actor else "System"
                audit_suffix = f" Reason: {clean_reason}" if clean_reason else ""
                db.add(
                    Notification(
                        user_id=None,
                        type="order",
                        title=f"Payment Audit: Order #{order.id}",
                        message=(
                            f"{actor_label} updated payment_status from '{current_payment}' "
                            f"to '{target_payment}' on Order #{order.id} "
                            f"({order.payment_method}).{audit_suffix}"
                        ),
                        link=f"/admin/orders/{order.id}",
                        read=False,
                    )
                )

            db.commit()
            db.refresh(order)
        except Exception:
            db.rollback()
            raise

        loaded_order = db.scalar(
            select(Order)
            .options(
                selectinload(Order.items),
                selectinload(Order.user),
            )
            .where(Order.id == order.id)
        )
        return OrderResponse.model_validate(loaded_order)
    @staticmethod
    def cancel_or_archive_order(
        db: Session,
        order_id: int,
        actor: User | None = None,
        reason: str | None = None,
    ) -> OrderResponse:
        """Controlled cancellation and archival service replacing direct order deletion.

        Preserves financial, audit, and inventory records:
        - Never removes an order or its items from the database (hard deletion is prohibited).
        - Enforces admin authorization.
        - Validates order state:
            * 'cancelled': 409 Conflict — already cancelled, rejects redundant cancellation
              to prevent duplicate stock restoration.
            * 'shipped': 409 Conflict — items in transit; stock cannot be restored to inventory
              and order cannot be cancelled.
            * 'delivered': 409 Conflict — items delivered; order history and financial record
              must remain intact.
            * 'paid' (unrefunded): 409 Conflict — active paid order requires a recorded refund
              before cancellation to preserve financial integrity.
            * 'pending' / 'processing': eligible for cancellation and stock restoration.
        - Conditionally restores stock: restored if and only if the order was in 'pending'
          or 'processing' status.
        - Conditionally restores coupon usage: decrements coupon used_count if a coupon
          code was applied.
        - Preserves audit trail: records admin audit notification and sends customer
          cancellation notification.
        """
        if actor is not None and not AuthorizationService.is_admin(actor):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only an administrator can cancel or archive orders.",
            )

        order = db.scalar(
            select(Order)
            .options(
                selectinload(Order.items).selectinload(OrderItem.product),
                selectinload(Order.user),
            )
            .where(Order.id == order_id)
        )
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found.",
            )

        current_status = (order.status or "pending").strip().lower()
        current_payment = (order.payment_status or "pending").strip().lower()

        # 1. State-specific validation
        if current_status == "cancelled":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Order #{order.id} is already cancelled.",
            )

        # Financial integrity: Paid orders must not be cancelled without recording a refund first
        if current_payment == "paid":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Cannot cancel or archive Order #{order.id}: paid orders require a processed refund "
                    "before cancellation to preserve financial audit integrity."
                ),
            )

        if current_status == "shipped":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot cancel or archive Order #{order.id}: order has already been shipped.",
            )

        if current_status == "delivered":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot cancel or archive Order #{order.id}: order has already been delivered.",
            )

        if current_status not in ("pending", "processing"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot cancel or archive Order #{order.id} in '{current_status}' state.",
            )

        # 2. Apply mutations atomically inside a rollback-safe transaction
        try:
            transition_res = db.execute(
                update(Order)
                .where(
                    Order.id == order.id,
                    Order.status == current_status,
                    Order.payment_status == current_payment,
                )
                .values(status="cancelled")
                .execution_options(synchronize_session=False)
            )
            if transition_res.rowcount != 1:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Order #{order.id} status changed concurrently; "
                        f"cannot transition from '{current_status}' to 'cancelled'."
                    ),
                )
            order.status = "cancelled"

            # Conditional stock restoration: only restore for unfulfilled orders (pending/processing)
            items_to_restore = [
                (item.product_id, item.quantity)
                for item in order.items
                if item.product_id is not None
            ]
            if items_to_restore:
                InventoryService.restore_stock(db, items_to_restore)

            # Conditional coupon usage restoration
            if order.coupon_code:
                from app.services.coupon_service import CouponService
                CouponService.restore_coupon_usage(db, order.coupon_code)

            # Audit notification preserving administrative history
            actor_label = f"Admin #{actor.id} ({actor.email})" if actor else "System"
            clean_reason = (reason or "").strip()
            audit_suffix = f" Reason: {clean_reason}" if clean_reason else ""
            db.add(
                Notification(
                    user_id=None,
                    type="order",
                    title=f"Order #{order.id} Cancelled & Archived",
                    message=(
                        f"{actor_label} cancelled and archived Order #{order.id} (was '{current_status}'). "
                        f"Stock restored: {bool(items_to_restore)}. Coupon restored: {bool(order.coupon_code)}.{audit_suffix}"
                    ),
                    link=f"/admin/orders/{order.id}",
                    read=False,
                )
            )

            # Customer notification
            db.add(
                Notification(
                    user_id=order.user_id,
                    type="order",
                    title=f"Order #{order.id} Cancelled ❌",
                    message=(
                        f"Your order #{order.id} has been cancelled and archived by support.{audit_suffix}"
                    ),
                    link=f"/orders/{order.id}",
                    read=False,
                )
            )

            db.commit()
            db.refresh(order)
        except Exception:
            db.rollback()
            raise

        loaded_order = db.scalar(
            select(Order)
            .options(
                selectinload(Order.items),
                selectinload(Order.user),
            )
            .where(Order.id == order.id)
        )
        return OrderResponse.model_validate(loaded_order)
