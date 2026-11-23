from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from fastapi import HTTPException, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.models.coupon import Coupon, CouponRedemption
from app.models.order import Order
from app.schemas.coupon import (
    CouponCreateRequest,
    CouponUpdateRequest,
    CouponValidateResponse,
)

TWOPLACES = Decimal("0.01")
ZERO = Decimal("0.00")

# Default promo vouchers for explicit database seeding (never seeded implicitly during requests)
DEFAULT_COUPONS = [
    {
        "code": "WELCOME10",
        "description": "10% off on your entire order",
        "discount_type": "percent",
        "discount_value": Decimal("10.00"),
        "min_order_amount": Decimal("0.00"),
        "max_discount_amount": Decimal("100.00"),
        "usage_limit": None,
    },
    {
        "code": "SAVE20",
        "description": "$20 off on orders over $50",
        "discount_type": "fixed",
        "discount_value": Decimal("20.00"),
        "min_order_amount": Decimal("50.00"),
        "max_discount_amount": None,
        "usage_limit": None,
    },
    {
        "code": "SUPER50",
        "description": "$50 off on orders over $150",
        "discount_type": "fixed",
        "discount_value": Decimal("50.00"),
        "min_order_amount": Decimal("150.00"),
        "max_discount_amount": None,
        "usage_limit": None,
    },
    {
        "code": "SUMMER15",
        "description": "15% off summer sale special",
        "discount_type": "percent",
        "discount_value": Decimal("15.00"),
        "min_order_amount": Decimal("30.00"),
        "max_discount_amount": Decimal("75.00"),
        "usage_limit": None,
    },
]


def _normalize_to_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class CouponService:
    @staticmethod
    def seed_default_coupons(db: Session) -> int:
        """Explicit seed method for CLI or startup setup. Never invoked implicitly on requests."""
        inserted = 0
        for item in DEFAULT_COUPONS:
            exists = db.scalar(select(Coupon).where(Coupon.code == item["code"]))
            if not exists:
                db.add(Coupon(**item, is_active=True, used_count=0))
                inserted += 1
        if inserted:
            db.commit()
        return inserted

    @staticmethod
    def get_available_coupons(db: Session) -> list[Coupon]:
        """Read-only view of active, non-expired coupons. Performs zero database mutations."""
        all_active = list(
            db.scalars(
                select(Coupon)
                .where(Coupon.is_active == True)
                .order_by(Coupon.id.asc())
            ).all()
        )
        now_utc = datetime.now(timezone.utc)
        available: list[Coupon] = []
        for c in all_active:
            exp_utc = _normalize_to_utc(c.expires_at)
            if exp_utc and exp_utc <= now_utc:
                continue
            if c.usage_limit is not None and c.used_count >= c.usage_limit:
                continue
            available.append(c)
        return available

    @staticmethod
    def _validate_coupon_rules(
        db: Session,
        coupon: Coupon,
        subtotal: Decimal,
        user_id: int | None = None,
    ) -> CouponValidateResponse:
        clean_code = coupon.code

        if not coupon.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Promo code '{clean_code}' is no longer active.",
            )

        now_utc = datetime.now(timezone.utc)
        exp_utc = _normalize_to_utc(coupon.expires_at)
        if exp_utc and exp_utc <= now_utc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Promo code '{clean_code}' has expired.",
            )

        if subtotal < coupon.min_order_amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Promo code '{clean_code}' requires a minimum subtotal of "
                    f"${coupon.min_order_amount:.2f}."
                ),
            )

        if coupon.usage_limit is not None and coupon.used_count >= coupon.usage_limit:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Promo code '{clean_code}' usage limit has been reached.",
            )

        if coupon.per_user_limit is not None and user_id is not None:
            recorded_redemptions = db.scalar(
                select(func.count(CouponRedemption.id)).where(
                    CouponRedemption.coupon_id == coupon.id,
                    CouponRedemption.user_id == user_id,
                )
            ) or 0
            legacy_orders_without_row = db.scalar(
                select(func.count(Order.id)).where(
                    Order.user_id == user_id,
                    Order.coupon_code == clean_code,
                    Order.status != "cancelled",
                    ~Order.id.in_(
                        select(CouponRedemption.order_id).where(
                            CouponRedemption.coupon_id == coupon.id
                        )
                    ),
                )
            ) or 0
            if (recorded_redemptions + legacy_orders_without_row) >= coupon.per_user_limit:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"You have already reached the usage limit for promo code '{clean_code}'.",
                )

        # Validate discount configuration
        if coupon.discount_value <= ZERO:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Coupon discount configuration is invalid.",
            )

        if coupon.discount_type == "percent":
            if coupon.discount_value > Decimal("100.00"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Percentage coupon discount cannot exceed 100%.",
                )
            discount_amount = (subtotal * coupon.discount_value) / Decimal("100.00")
            if (
                coupon.max_discount_amount is not None
                and coupon.max_discount_amount > ZERO
                and discount_amount > coupon.max_discount_amount
            ):
                discount_amount = coupon.max_discount_amount
        elif coupon.discount_type == "fixed":
            discount_amount = coupon.discount_value
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported coupon discount type '{coupon.discount_type}'.",
            )

        # Cap discount at current subtotal and quantize
        discount_amount = min(discount_amount, subtotal)
        discount_amount = max(ZERO, discount_amount).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        new_subtotal = (subtotal - discount_amount).quantize(TWOPLACES, rounding=ROUND_HALF_UP)

        return CouponValidateResponse(
            valid=True,
            code=coupon.code,
            discount_type=coupon.discount_type,
            discount_value=coupon.discount_value,
            discount_amount=discount_amount,
            new_subtotal=new_subtotal,
            message=f"Promo code '{coupon.code}' applied! You saved ${discount_amount:.2f}.",
        )

    @staticmethod
    def validate_and_calculate_discount(
        db: Session,
        code: str,
        subtotal: Decimal,
        user_id: int | None = None,
    ) -> CouponValidateResponse:
        """Pure validation without mutation; safe for preview and checkout checks."""
        clean_code = (code or "").strip().upper()
        if not clean_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A valid promo code is required.",
            )

        coupon = db.scalar(select(Coupon).where(Coupon.code == clean_code))
        if not coupon:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Promo code '{clean_code}' does not exist.",
            )

        return CouponService._validate_coupon_rules(
            db=db,
            coupon=coupon,
            subtotal=subtotal,
            user_id=user_id,
        )

    @staticmethod
    def redeem_coupon_atomic(
        db: Session,
        code: str,
        subtotal: Decimal,
        user_id: int | None = None,
    ) -> CouponValidateResponse:
        """Atomically validates and increments used_count within the caller's transaction."""
        clean_code = (code or "").strip().upper()
        if not clean_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A valid promo code is required.",
            )

        coupon = db.scalar(select(Coupon).where(Coupon.code == clean_code))
        if not coupon:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Promo code '{clean_code}' does not exist.",
            )

        validation_res = CouponService._validate_coupon_rules(
            db=db,
            coupon=coupon,
            subtotal=subtotal,
            user_id=user_id,
        )

        # Atomic conditional increment
        if coupon.usage_limit is not None:
            result = db.execute(
                update(Coupon)
                .where(
                    Coupon.id == coupon.id,
                    Coupon.is_active.is_(True),
                    Coupon.used_count < coupon.usage_limit,
                )
                .values(used_count=Coupon.used_count + 1)
                .execution_options(synchronize_session=False)
            )
            if result.rowcount != 1:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Promo code '{clean_code}' usage limit has been reached.",
                )
        else:
            result = db.execute(
                update(Coupon)
                .where(
                    Coupon.id == coupon.id,
                    Coupon.is_active.is_(True),
                )
                .values(used_count=Coupon.used_count + 1)
                .execution_options(synchronize_session=False)
            )
            if result.rowcount != 1:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Promo code '{clean_code}' could not be redeemed.",
                )

        return validation_res

    @staticmethod
    def record_redemption(
        db: Session,
        *,
        code: str,
        user_id: int,
        order_id: int,
    ) -> None:
        """Records an auditable per-order coupon redemption in the active checkout transaction."""
        clean_code = (code or "").strip().upper()
        if not clean_code:
            return
        coupon = db.scalar(select(Coupon).where(Coupon.code == clean_code))
        if not coupon:
            return
        exists = db.scalar(
            select(CouponRedemption.id).where(CouponRedemption.order_id == order_id)
        )
        if exists is None:
            db.add(
                CouponRedemption(
                    coupon_id=coupon.id,
                    user_id=user_id,
                    order_id=order_id,
                )
            )
            db.flush()

    @staticmethod
    def restore_coupon_usage(
        db: Session,
        code: str,
        *,
        order_id: int | None = None,
    ) -> None:
        """Restores one usage count (and clears order redemption) when an eligible order is cancelled."""
        clean_code = (code or "").strip().upper()
        if not clean_code:
            return
        if order_id is not None:
            db.execute(
                delete(CouponRedemption).where(CouponRedemption.order_id == order_id)
            )
        db.execute(
            update(Coupon)
            .where(
                Coupon.code == clean_code,
                Coupon.used_count > 0,
            )
            .values(used_count=Coupon.used_count - 1)
            .execution_options(synchronize_session=False)
        )

    # -----------------------------------------------------------------------
    # Admin Coupon Management (CRUD)
    # -----------------------------------------------------------------------

    @staticmethod
    def list_all_coupons(db: Session) -> list[Coupon]:
        return list(
            db.scalars(
                select(Coupon).order_by(Coupon.id.desc())
            ).all()
        )

    @staticmethod
    def create_coupon(db: Session, request: CouponCreateRequest) -> Coupon:
        clean_code = request.code.strip().upper()
        existing = db.scalar(select(Coupon).where(Coupon.code == clean_code))
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Promo code '{clean_code}' already exists.",
            )

        if request.discount_type == "percent" and request.discount_value > Decimal("100.00"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Percentage discount cannot exceed 100%.",
            )

        coupon = Coupon(
            code=clean_code,
            description=request.description,
            discount_type=request.discount_type,
            discount_value=request.discount_value,
            min_order_amount=request.min_order_amount,
            max_discount_amount=request.max_discount_amount,
            is_active=request.is_active,
            expires_at=_normalize_to_utc(request.expires_at),
            usage_limit=request.usage_limit,
            per_user_limit=request.per_user_limit,
            used_count=0,
        )
        db.add(coupon)
        db.commit()
        db.refresh(coupon)
        return coupon

    @staticmethod
    def update_coupon(
        db: Session, coupon_id: int, request: CouponUpdateRequest
    ) -> Coupon:
        coupon = db.get(Coupon, coupon_id)
        if not coupon:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Coupon #{coupon_id} not found.",
            )

        if request.description is not None:
            coupon.description = request.description
        if request.discount_type is not None:
            coupon.discount_type = request.discount_type
        if request.discount_value is not None:
            if coupon.discount_type == "percent" and request.discount_value > Decimal("100.00"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Percentage discount cannot exceed 100%.",
                )
            coupon.discount_value = request.discount_value
        if request.min_order_amount is not None:
            coupon.min_order_amount = request.min_order_amount
        if request.max_discount_amount is not None:
            coupon.max_discount_amount = request.max_discount_amount
        if request.is_active is not None:
            coupon.is_active = request.is_active
        if request.expires_at is not None:
            coupon.expires_at = _normalize_to_utc(request.expires_at)
        if request.usage_limit is not None:
            coupon.usage_limit = request.usage_limit
        if "per_user_limit" in request.model_fields_set:
            coupon.per_user_limit = request.per_user_limit

        db.commit()
        db.refresh(coupon)
        return coupon

    @staticmethod
    def delete_coupon(db: Session, coupon_id: int) -> None:
        coupon = db.get(Coupon, coupon_id)
        if not coupon:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Coupon #{coupon_id} not found.",
            )
        db.delete(coupon)
        db.commit()
