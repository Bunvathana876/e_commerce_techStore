from decimal import Decimal
from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.models.cart import CartItem
from app.models.product import Product
from app.schemas.cart import CartItemAddRequest, CartItemResponse, CartItemUpdateRequest, CartResponse
from app.schemas.product import ProductResponse


class CartService:
    @staticmethod
    def get_cart(db: Session, user_id: int) -> CartResponse:
        cart_items = list(
            db.scalars(
                select(CartItem)
                .options(
                    selectinload(CartItem.product).selectinload(Product.category)
                )
                .where(CartItem.user_id == user_id)
                .order_by(CartItem.created_at.desc())
            ).all()
        )

        subtotal = Decimal("0.00")
        total_items = 0
        response_items: list[CartItemResponse] = []

        for item in cart_items:
            product = item.product
            # Use discount price if available, otherwise regular price
            unit_price = product.discount_price if product.discount_price and product.discount_price > 0 else product.price
            item_total = unit_price * item.quantity

            subtotal += item_total
            total_items += item.quantity

            response_items.append(
                CartItemResponse(
                    id=item.id,
                    product_id=item.product_id,
                    quantity=item.quantity,
                    product=ProductResponse.model_validate(product),
                    item_total=item_total,
                    created_at=item.created_at,
                    updated_at=item.updated_at,
                )
            )

        return CartResponse(
            items=response_items,
            total_items=total_items,
            subtotal=subtotal,
        )

    @staticmethod
    def add_item(db: Session, user_id: int, data: CartItemAddRequest) -> CartResponse:
        # Check product exists and active
        product = db.scalar(select(Product).where(Product.id == data.product_id))
        if not product or not product.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found or unavailable.",
            )

        if product.stock < data.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Only {product.stock} items available in stock.",
            )

        # Check if already in cart
        existing_item = db.scalar(
            select(CartItem).where(
                CartItem.user_id == user_id,
                CartItem.product_id == data.product_id,
            )
        )

        if existing_item:
            new_qty = existing_item.quantity + data.quantity
            if product.stock < new_qty:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot add more. Total in cart ({new_qty}) exceeds stock ({product.stock}).",
                )
            existing_item.quantity = new_qty
        else:
            new_cart_item = CartItem(
                user_id=user_id,
                product_id=data.product_id,
                quantity=data.quantity,
            )
            db.add(new_cart_item)

        db.commit()
        return CartService.get_cart(db, user_id)

    @staticmethod
    def update_item(
        db: Session,
        user_id: int,
        item_id: int,
        data: CartItemUpdateRequest,
    ) -> CartResponse:
        """
        Update cart item quantity by deterministic cart item primary key (CartItem.id).
        Enforces customer ownership.
        """
        cart_item = db.scalar(
            select(CartItem)
            .options(selectinload(CartItem.product))
            .where(
                CartItem.id == item_id,
                CartItem.user_id == user_id,
            )
        )

        if not cart_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cart item not found.",
            )

        if cart_item.product.stock < data.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Only {cart_item.product.stock} items available in stock.",
            )

        cart_item.quantity = data.quantity
        db.commit()
        return CartService.get_cart(db, user_id)

    @staticmethod
    def remove_item(db: Session, user_id: int, item_id: int) -> CartResponse:
        """
        Remove cart item by deterministic cart item primary key (CartItem.id).
        Enforces customer ownership.
        """
        cart_item = db.scalar(
            select(CartItem).where(
                CartItem.id == item_id,
                CartItem.user_id == user_id,
            )
        )

        if not cart_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cart item not found.",
            )

        db.delete(cart_item)
        db.commit()
        return CartService.get_cart(db, user_id)

    @staticmethod
    def update_item_by_product_id(
        db: Session,
        user_id: int,
        product_id: int,
        data: CartItemUpdateRequest,
    ) -> CartResponse:
        """
        Update cart item quantity by product reference (CartItem.product_id).
        Enforces customer ownership.
        """
        cart_item = db.scalar(
            select(CartItem)
            .options(selectinload(CartItem.product))
            .where(
                CartItem.product_id == product_id,
                CartItem.user_id == user_id,
            )
        )

        if not cart_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cart item not found for specified product.",
            )

        if cart_item.product.stock < data.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Only {cart_item.product.stock} items available in stock.",
            )

        cart_item.quantity = data.quantity
        db.commit()
        return CartService.get_cart(db, user_id)

    @staticmethod
    def remove_item_by_product_id(
        db: Session,
        user_id: int,
        product_id: int,
    ) -> CartResponse:
        """
        Remove cart item by product reference (CartItem.product_id).
        Enforces customer ownership.
        """
        cart_item = db.scalar(
            select(CartItem).where(
                CartItem.product_id == product_id,
                CartItem.user_id == user_id,
            )
        )

        if not cart_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cart item not found for specified product.",
            )

        db.delete(cart_item)
        db.commit()
        return CartService.get_cart(db, user_id)

    @staticmethod
    def update_item_resolved(
        db: Session,
        user_id: int,
        identifier: int,
        data: CartItemUpdateRequest,
    ) -> CartResponse:
        """
        Resolve identifier for legacy generic endpoints:
        - If identifier unambiguously matches CartItem.id, update that item.
        - If identifier unambiguously matches CartItem.product_id, update that item.
        - If identifier matches both a CartItem.id and a different CartItem.product_id,
          reject with HTTP 409 Conflict to prevent silent mutation of the wrong item.
        """
        item_by_id = db.scalar(
            select(CartItem)
            .options(selectinload(CartItem.product))
            .where(
                CartItem.id == identifier,
                CartItem.user_id == user_id,
            )
        )

        item_by_product = db.scalar(
            select(CartItem)
            .options(selectinload(CartItem.product))
            .where(
                CartItem.product_id == identifier,
                CartItem.user_id == user_id,
            )
        )

        if item_by_id is None and item_by_product is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cart item not found.",
            )

        if (
            item_by_id is not None
            and item_by_product is not None
            and item_by_id.id != item_by_product.id
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Ambiguous cart identifier '{identifier}'. The ID matches both cart item #{item_by_id.id} "
                    f"and product #{item_by_product.product_id}. Use explicit endpoint "
                    f"'/cart/items/{identifier}' or '/cart/product/{identifier}'."
                ),
            )

        cart_item = item_by_id or item_by_product
        assert cart_item is not None

        if cart_item.product.stock < data.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Only {cart_item.product.stock} items available in stock.",
            )

        cart_item.quantity = data.quantity
        db.commit()
        return CartService.get_cart(db, user_id)

    @staticmethod
    def remove_item_resolved(
        db: Session,
        user_id: int,
        identifier: int,
    ) -> CartResponse:
        """
        Resolve identifier for legacy generic endpoints:
        - If identifier unambiguously matches CartItem.id, delete that item.
        - If identifier unambiguously matches CartItem.product_id, delete that item.
        - If identifier matches both a CartItem.id and a different CartItem.product_id,
          reject with HTTP 409 Conflict to prevent silent deletion of the wrong item.
        """
        item_by_id = db.scalar(
            select(CartItem).where(
                CartItem.id == identifier,
                CartItem.user_id == user_id,
            )
        )

        item_by_product = db.scalar(
            select(CartItem).where(
                CartItem.product_id == identifier,
                CartItem.user_id == user_id,
            )
        )

        if item_by_id is None and item_by_product is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cart item not found.",
            )

        if (
            item_by_id is not None
            and item_by_product is not None
            and item_by_id.id != item_by_product.id
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Ambiguous cart identifier '{identifier}'. The ID matches both cart item #{item_by_id.id} "
                    f"and product #{item_by_product.product_id}. Use explicit endpoint "
                    f"'/cart/items/{identifier}' or '/cart/product/{identifier}'."
                ),
            )

        cart_item = item_by_id or item_by_product
        assert cart_item is not None

        db.delete(cart_item)
        db.commit()
        return CartService.get_cart(db, user_id)

    @staticmethod
    def clear_cart(db: Session, user_id: int) -> None:
        db.execute(delete(CartItem).where(CartItem.user_id == user_id))
        db.commit()

    @staticmethod
    def reconcile_cart(
        db: Session,
        user_id: int,
        items: list[CartItemAddRequest],
    ) -> CartResponse:
        """Safely and non-destructively reconcile the customer's server cart in a single transaction.

        Validates all products before mutating state:
        - If ANY product is missing, inactive, or has insufficient stock, raises HTTPException(400/404)
          and rolls back. The user's existing cart items are completely preserved without partial mutation.
        - If all items pass validation, atomically syncs the database CartItems to match the requested items.
        """
        target_quantities: dict[int, int] = {}
        for item in items:
            if item.product_id <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid product ID in cart reconciliation.",
                )
            if item.quantity < 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Item quantity must be at least 1.",
                )
            target_quantities[item.product_id] = (
                target_quantities.get(item.product_id, 0) + item.quantity
            )

        # 1. Validation phase (read-only checks before mutation)
        for product_id, requested_qty in target_quantities.items():
            product = db.scalar(select(Product).where(Product.id == product_id))
            if not product or not product.is_active:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Product #{product_id} not found or unavailable.",
                )
            if product.stock < requested_qty:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot add {requested_qty} of '{product.name}'. Only {product.stock} items available in stock.",
                )

        # 2. Atomic reconciliation phase inside a single transaction
        try:
            # Remove any cart items that are not in target_quantities
            if target_quantities:
                db.execute(
                    delete(CartItem).where(
                        CartItem.user_id == user_id,
                        ~CartItem.product_id.in_(list(target_quantities.keys())),
                    )
                )
            else:
                db.execute(delete(CartItem).where(CartItem.user_id == user_id))

            # Fetch existing items for this user to update or insert
            existing_items = {
                ci.product_id: ci
                for ci in db.scalars(
                    select(CartItem).where(CartItem.user_id == user_id)
                ).all()
            }

            for product_id, requested_qty in target_quantities.items():
                if product_id in existing_items:
                    existing_items[product_id].quantity = requested_qty
                else:
                    db.add(
                        CartItem(
                            user_id=user_id,
                            product_id=product_id,
                            quantity=requested_qty,
                        )
                    )

            db.commit()
            return CartService.get_cart(db, user_id)
        except Exception:
            db.rollback()
            raise

