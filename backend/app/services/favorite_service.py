from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.favorite import Favorite
from app.models.product import Product
from app.schemas.favorite import FavoriteResponse
from app.schemas.product import ProductResponse


class FavoriteService:
    @staticmethod
    def get_favorites(db: Session, user_id: int) -> list[FavoriteResponse]:
        favorites = list(
            db.scalars(
                select(Favorite)
                .options(
                    joinedload(Favorite.product).joinedload(Product.category),
                    joinedload(Favorite.product).joinedload(Product.seller),
                )
                .where(Favorite.user_id == user_id)
                .order_by(Favorite.created_at.desc())
            ).all()
        )

        return [
            FavoriteResponse(
                id=fav.id,
                product_id=fav.product_id,
                product=ProductResponse.model_validate(fav.product),
                created_at=fav.created_at,
            )
            for fav in favorites
            if fav.product and fav.product.is_active
        ]

    @staticmethod
    def add_favorite(db: Session, user_id: int, product_id: int) -> FavoriteResponse:
        # Check product exists
        product = db.scalar(
            select(Product)
            .options(selectinload(Product.category))
            .where(Product.id == product_id)
        )
        if not product or not product.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found or unavailable.",
            )

        existing = db.scalar(
            select(Favorite).where(
                Favorite.user_id == user_id,
                Favorite.product_id == product_id,
            )
        )

        if not existing:
            existing = Favorite(user_id=user_id, product_id=product_id)
            db.add(existing)
            db.commit()
            db.refresh(existing)

        return FavoriteResponse(
            id=existing.id,
            product_id=existing.product_id,
            product=ProductResponse.model_validate(product),
            created_at=existing.created_at,
        )

    @staticmethod
    def remove_favorite(db: Session, user_id: int, product_id: int) -> None:
        favorite = db.scalar(
            select(Favorite).where(
                Favorite.user_id == user_id,
                Favorite.product_id == product_id,
            )
        )
        if favorite:
            db.delete(favorite)
            db.commit()

    @staticmethod
    def toggle_favorite(db: Session, user_id: int, product_id: int) -> dict:
        favorite = db.scalar(
            select(Favorite).where(
                Favorite.user_id == user_id,
                Favorite.product_id == product_id,
            )
        )
        if favorite:
            db.delete(favorite)
            db.commit()
            return {"is_favorite": False, "message": "Removed from favorites."}
        else:
            product = db.scalar(select(Product).where(Product.id == product_id))
            if not product or not product.is_active:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Product not found.",
                )
            new_fav = Favorite(user_id=user_id, product_id=product_id)
            db.add(new_fav)
            db.commit()
            return {"is_favorite": True, "message": "Added to favorites."}

