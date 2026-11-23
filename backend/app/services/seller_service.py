from decimal import Decimal
import secrets
from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.password_policy import validate_password_strength
from app.core.security import hash_password
from app.models.seller import Seller
from app.models.user import User
from app.schemas.seller import SellerCreate, SellerProfileUpdate, SellerUpdate


class SellerService:
    @staticmethod
    def get_sellers(
        db: Session,
        status_filter: str | None = None,
        search: str | None = None,
    ) -> list[Seller]:
        query = select(Seller)
        if status_filter and status_filter.lower() != "all":
            query = query.where(Seller.status.ilike(status_filter))
        if search:
            search_term = f"%{search}%"
            query = query.where(
                or_(
                    Seller.name.ilike(search_term),
                    Seller.owner_name.ilike(search_term),
                    Seller.email.ilike(search_term),
                )
            )
        query = query.order_by(Seller.id.desc())
        return list(db.scalars(query).all())

    @staticmethod
    def get_seller_by_id(db: Session, seller_id: int) -> Seller:
        seller = db.scalar(select(Seller).where(Seller.id == seller_id))
        if not seller:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Seller with id {seller_id} not found.",
            )
        return seller

    @staticmethod
    def create_seller(db: Session, data: SellerCreate) -> Seller:
        clean_email = data.email.lower().strip()
        existing = db.scalar(select(Seller).where(func.lower(Seller.email) == clean_email))
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A seller with this email already exists.",
            )

        # Check or create associated User account without hardcoded credentials
        user = db.scalar(select(User).where(func.lower(User.email) == clean_email))
        if not user:
            raw_pwd = (data.password or "").strip()
            if raw_pwd:
                is_valid, error_msg = validate_password_strength(raw_pwd)
                if not is_valid:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=error_msg or "Password does not meet security policy requirements.",
                    )
                pwd = raw_pwd
            else:
                pwd = f"{secrets.token_urlsafe(18)}!A9a"
            user = User(
                name=data.owner_name.strip(),
                email=clean_email,
                phone=data.phone,
                password_hash=hash_password(pwd),
                role="seller",
                is_active=True,
            )
            db.add(user)
            db.flush()
            user_id = user.id
        else:
            if user.role == "customer":
                user.role = "seller"
                db.flush()
            user_id = user.id

        seller = Seller(
            user_id=user_id,
            name=data.name.strip(),
            owner_name=data.owner_name.strip(),
            email=clean_email,
            phone=data.phone,
            address=data.address,
            description=data.description,
            logo=data.logo,
            status=data.status if data.status else "Active",
            rating=Decimal("5.00"),
            products_count=0,
            orders_count=0,
            total_revenue=Decimal("0.00"),
        )
        db.add(seller)
        db.commit()
        db.refresh(seller)
        return seller

    @staticmethod
    def update_seller(db: Session, seller_id: int, data: SellerUpdate) -> Seller:
        seller = SellerService.get_seller_by_id(db, seller_id)

        update_dict = data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            if value is not None:
                setattr(seller, key, value)

        db.commit()
        db.refresh(seller)
        return seller

    @staticmethod
    def delete_seller(db: Session, seller_id: int) -> None:
        seller = SellerService.get_seller_by_id(db, seller_id)
        db.delete(seller)
        db.commit()

    @staticmethod
    def get_seller_by_user_id(db: Session, user_id: int) -> Seller | None:
        return db.scalar(select(Seller).where(Seller.user_id == user_id))

    @staticmethod
    def update_seller_profile(db: Session, seller: Seller, data: SellerProfileUpdate) -> Seller:
        # Check for attempted modification of privileged fields
        if data.status is not None and data.status.strip().lower() != seller.status.strip().lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Sellers are not permitted to modify their approval status.",
            )
        if data.user_id is not None and data.user_id != seller.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Sellers are not permitted to change store ownership.",
            )
        if data.email is not None and data.email.strip().lower() != seller.email.strip().lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Sellers are not permitted to change store registered email.",
            )
        if (
            data.rating is not None
            or data.products_count is not None
            or data.orders_count is not None
            or data.total_revenue is not None
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Sellers are not permitted to modify store metrics.",
            )

        # Enforce seller account approval status
        if seller.status != "Active":
            if seller.status == "Suspended":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Store is suspended. Profile updates are disabled.",
                )
            elif seller.status == "Pending":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Store is pending approval. Profile updates are disabled until approved.",
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Store status is '{seller.status}'. Profile updates are not permitted.",
                )

        # Only apply allowed fields
        allowed_fields = {"name", "description", "phone", "address", "logo"}
        update_data = data.model_dump(exclude_unset=True)
        for field in allowed_fields:
            if field in update_data:
                setattr(seller, field, update_data[field])

        db.commit()
        db.refresh(seller)
        return seller
