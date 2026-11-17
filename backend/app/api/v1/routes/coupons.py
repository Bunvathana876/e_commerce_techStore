from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_roles
from app.db.database import get_db
from app.models.user import User
from app.schemas.coupon import (
    CouponCreateRequest,
    CouponResponse,
    CouponUpdateRequest,
    CouponValidateRequest,
    CouponValidateResponse,
)
from app.services.coupon_service import CouponService

router = APIRouter(prefix="/coupons", tags=["Coupons & Discounts"])


# ---------------------------------------------------------------------------
# Public / Storefront Routes
# ---------------------------------------------------------------------------


@router.post("/validate", status_code=status.HTTP_200_OK)
def validate_coupon(
    request: CouponValidateRequest,
    db: Session = Depends(get_db),
):
    result = CouponService.validate_and_calculate_discount(
        db=db,
        code=request.code,
        subtotal=request.subtotal,
    )
    return {
        "success": True,
        "message": result.message,
        "data": result.model_dump(),
    }


@router.get("/available", status_code=status.HTTP_200_OK)
def get_available_coupons(
    db: Session = Depends(get_db),
):
    coupons = CouponService.get_available_coupons(db)
    return {
        "success": True,
        "message": "Available promo coupons retrieved successfully.",
        "data": [CouponResponse.model_validate(c).model_dump() for c in coupons],
    }


# ---------------------------------------------------------------------------
# Admin Protected Routes
# ---------------------------------------------------------------------------


@router.get("", status_code=status.HTTP_200_OK)
def list_coupons_admin(
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    coupons = CouponService.list_all_coupons(db)
    return {
        "success": True,
        "message": "Coupons retrieved successfully.",
        "data": [CouponResponse.model_validate(c).model_dump() for c in coupons],
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_coupon_admin(
    request: CouponCreateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    coupon = CouponService.create_coupon(db, request)
    return {
        "success": True,
        "message": f"Promo coupon '{coupon.code}' created successfully.",
        "data": CouponResponse.model_validate(coupon).model_dump(),
    }


@router.put("/{coupon_id}", status_code=status.HTTP_200_OK)
def update_coupon_admin(
    coupon_id: int,
    request: CouponUpdateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    coupon = CouponService.update_coupon(db, coupon_id, request)
    return {
        "success": True,
        "message": f"Promo coupon '{coupon.code}' updated successfully.",
        "data": CouponResponse.model_validate(coupon).model_dump(),
    }


@router.delete("/{coupon_id}", status_code=status.HTTP_200_OK)
def delete_coupon_admin(
    coupon_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    CouponService.delete_coupon(db, coupon_id)
    return {
        "success": True,
        "message": f"Coupon #{coupon_id} deleted successfully.",
        "data": None,
    }
