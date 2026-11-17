from app.core.dependencies import require_roles
from decimal import Decimal
from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.category import Category
from app.models.order import Order
from app.models.product import Product
from app.models.user import User

router = APIRouter(prefix="/stats", tags=["Dashboard Stats"])


@router.get("/overview", status_code=status.HTTP_200_OK)
def get_stats_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    total_products = db.scalar(select(func.count(Product.id))) or 0
    total_categories = db.scalar(select(func.count(Category.id))) or 0
    total_orders = db.scalar(select(func.count(Order.id))) or 0
    total_users = db.scalar(select(func.count(User.id))) or 0

    # Recognized revenue strictly includes orders with verified paid status that are not cancelled
    revenue_query = select(func.sum(Order.total)).where(
        Order.payment_status == "paid",
        Order.status != "cancelled",
    )
    total_revenue = db.scalar(revenue_query) or Decimal("0.00")

    low_stock_count = (
        db.scalar(select(func.count(Product.id)).where(Product.stock < 10, Product.stock > 0)) or 0
    )
    out_of_stock_count = db.scalar(select(func.count(Product.id)).where(Product.stock == 0)) or 0

    pending_orders_count = (
        db.scalar(select(func.count(Order.id)).where(Order.status == "pending")) or 0
    )
    processing_orders_count = (
        db.scalar(select(func.count(Order.id)).where(Order.status == "processing")) or 0
    )
    delivered_orders_count = (
        db.scalar(select(func.count(Order.id)).where(Order.status == "delivered")) or 0
    )

    return {
        "success": True,
        "message": "Dashboard statistics retrieved successfully.",
        "data": {
            "total_products": total_products,
            "total_categories": total_categories,
            "total_orders": total_orders,
            "pending_orders_count": pending_orders_count,
            "processing_orders_count": processing_orders_count,
            "delivered_orders_count": delivered_orders_count,
            "total_users": total_users,
            "total_revenue": float(total_revenue),
            "low_stock_count": low_stock_count,
            "out_of_stock_count": out_of_stock_count,
        },
    }
