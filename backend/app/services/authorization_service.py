from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.seller import Seller
from app.models.user import User


class AuthorizationService:
    @staticmethod
    def is_admin(user: User | None) -> bool:
        return user is not None and user.role == "admin"

    @staticmethod
    def seller_ids(db: Session, user: User | None) -> list[int]:
        if user is None or user.role != "seller":
            return []
        return list(db.scalars(select(Seller.id).where(
            Seller.user_id == user.id, Seller.status == "Active"
        )).all())

    @staticmethod
    def require_seller(db: Session, user: User, seller_id: int | None) -> None:
        if AuthorizationService.is_admin(user):
            return
        if seller_id not in AuthorizationService.seller_ids(db, user):
            raise HTTPException(status_code=403, detail="Permission denied for this seller.")

    @staticmethod
    def require_product(db: Session, user: User, product_id: int) -> None:
        if AuthorizationService.is_admin(user):
            return
        product = db.scalar(select(Product).where(
            Product.id == product_id,
            Product.seller_id.in_(AuthorizationService.seller_ids(db, user)),
        ))
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found.")
