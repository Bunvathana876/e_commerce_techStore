from collections.abc import Callable, Iterable

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.product import Product


class InventoryService:
    """Shared atomic inventory operations for customer checkout, POS, and cancellations."""

    @staticmethod
    def aggregate_quantities(items: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
        totals: dict[int, int] = {}
        for product_id, quantity in items:
            if quantity < 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Item quantity must be at least 1.",
                )
            totals[product_id] = totals.get(product_id, 0) + quantity
        return sorted(totals.items(), key=lambda pair: pair[0])

    @staticmethod
    def deduct_stock(
        db: Session,
        items: Iterable[tuple[int, int]],
        *,
        inactive_detail_fn: Callable[[int, Product | None], str] | None = None,
    ) -> dict[int, Product]:
        ordered_requirements = InventoryService.aggregate_quantities(items)
        updated_products: dict[int, Product] = {}

        for product_id, required_qty in ordered_requirements:
            result = db.execute(
                update(Product)
                .where(
                    Product.id == product_id,
                    Product.is_active.is_(True),
                    Product.stock >= required_qty,
                )
                .values(stock=Product.stock - required_qty)
                .execution_options(synchronize_session=False)
            )

            current = db.scalar(
                select(Product)
                .where(Product.id == product_id)
                .execution_options(populate_existing=True)
            )

            if result.rowcount != 1:
                if current is None or not current.is_active:
                    detail = (
                        inactive_detail_fn(product_id, current)
                        if inactive_detail_fn is not None
                        else f"Product #{product_id} is inactive or not found."
                    )
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=detail,
                    )

                if current.stock < required_qty:
                    conflict_detail = (
                        f"Insufficient stock for '{current.name}'. "
                        f"Available: {current.stock}, requested: {required_qty}."
                    )
                else:
                    conflict_detail = (
                        f"Inventory changed concurrently for '{current.name}'. "
                        "Please retry your checkout."
                    )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=conflict_detail,
                )

            assert current is not None
            updated_products[product_id] = current

        return updated_products

    @staticmethod
    def restore_stock(
        db: Session,
        items: Iterable[tuple[int, int]],
    ) -> None:
        ordered_restorations = InventoryService.aggregate_quantities(items)
        for product_id, restore_qty in ordered_restorations:
            db.execute(
                update(Product)
                .where(Product.id == product_id)
                .values(stock=Product.stock + restore_qty)
                .execution_options(synchronize_session=False)
            )
            db.scalar(
                select(Product)
                .where(Product.id == product_id)
                .execution_options(populate_existing=True)
            )

