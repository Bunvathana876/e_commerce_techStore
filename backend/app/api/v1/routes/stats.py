from app.core.dependencies import require_roles
from decimal import Decimal
from fastapi import APIRouter, Depends, status
from sqlalchemy import and_, case, func, select
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
    # Optimized combined queries for Product and Order statistics
    prod_stats = db.execute(
        select(
            func.count(Product.id),
            func.coalesce(
                func.sum(case((and_(Product.stock < 10, Product.stock > 0), 1), else_=0)), 0
            ),
            func.coalesce(func.sum(case((Product.stock == 0, 1), else_=0)), 0),
        )
    ).one()
    total_products = int(prod_stats[0] or 0)
    low_stock_count = int(prod_stats[1] or 0)
    out_of_stock_count = int(prod_stats[2] or 0)

    order_stats = db.execute(
        select(
            func.count(Order.id),
            func.coalesce(
                func.sum(
                    case(
                        (
                            and_(
                                Order.payment_status == "paid",
                                Order.status != "cancelled",
                            ),
                            Order.total,
                        ),
                        else_=Decimal("0.00"),
                    )
                ),
                Decimal("0.00"),
            ),
            func.coalesce(func.sum(case((Order.status == "pending", 1), else_=0)), 0),
            func.coalesce(func.sum(case((Order.status == "processing", 1), else_=0)), 0),
            func.coalesce(func.sum(case((Order.status == "delivered", 1), else_=0)), 0),
        )
    ).one()
    total_orders = int(order_stats[0] or 0)
    total_revenue = order_stats[1] or Decimal("0.00")
    pending_orders_count = int(order_stats[2] or 0)
    processing_orders_count = int(order_stats[3] or 0)
    delivered_orders_count = int(order_stats[4] or 0)

    total_categories = db.scalar(select(func.count(Category.id))) or 0
    total_users = db.scalar(select(func.count(User.id))) or 0

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
