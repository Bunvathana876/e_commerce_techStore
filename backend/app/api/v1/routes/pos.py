from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_roles
from app.db.database import get_db
from app.models.user import User
from app.schemas.pos import PosCheckoutRequest, PosReceiptResponse, PosSummaryResponse
from app.services.pos_service import PosService

router = APIRouter(prefix="/pos", tags=["Point of Sale (POS)"])


@router.post("/checkout", status_code=status.HTTP_201_CREATED)
def pos_checkout(
    request: PosCheckoutRequest,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Processes a Point of Sale transaction, decrements stock, records order and returns a receipt."""
    receipt = PosService.process_checkout(db, current_user, request)
    return {
        "success": True,
        "message": "POS Transaction completed successfully.",
        "data": receipt.model_dump(),
    }


@router.get("/summary", status_code=status.HTTP_200_OK)
def pos_daily_summary(
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Retrieves register summary and sales metrics for today."""
    summary = PosService.get_daily_summary(db)
    return {
        "success": True,
        "message": "POS Daily summary retrieved successfully.",
        "data": summary.model_dump(),
    }


@router.get("/customers", status_code=status.HTTP_200_OK)
def search_pos_customers(
    q: str = Query(default="", description="Search customer name, email or phone"),
    limit: int = Query(default=10, le=50),
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Quick lookup of registered customer accounts for loyalty or invoice attachment."""
    query = select(User).where(User.is_active.is_(True))
    if q.strip():
        search_pattern = f"%{q.strip()}%"
        query = query.where(
            or_(
                User.name.ilike(search_pattern),
                User.email.ilike(search_pattern),
                User.phone.ilike(search_pattern),
            )
        )
    query = query.order_by(User.name.asc()).limit(limit)
    customers = db.scalars(query).all()

    return {
        "success": True,
        "data": [
            {
                "id": c.id,
                "name": c.name,
                "email": c.email,
                "phone": c.phone,
                "role": c.role,
            }
            for c in customers
        ],
    }

