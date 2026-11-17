from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.services.favorite_service import FavoriteService

router = APIRouter(prefix="/favorites", tags=["Favorites"])


@router.get("", status_code=status.HTTP_200_OK)
def get_favorites(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    favorites = FavoriteService.get_favorites(db, current_user.id)
    return {
        "success": True,
        "message": "Favorites retrieved successfully.",
        "data": [f.model_dump() for f in favorites],
    }


@router.post("/{product_id}", status_code=status.HTTP_200_OK)
def add_favorite(
    product_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    fav = FavoriteService.add_favorite(db, current_user.id, product_id)
    return {
        "success": True,
        "message": "Product added to favorites.",
        "data": fav.model_dump(),
    }


@router.delete("/{product_id}", status_code=status.HTTP_200_OK)
def remove_favorite(
    product_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    FavoriteService.remove_favorite(db, current_user.id, product_id)
    return {
        "success": True,
        "message": "Product removed from favorites.",
    }


@router.post("/{product_id}/toggle", status_code=status.HTTP_200_OK)
def toggle_favorite(
    product_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = FavoriteService.toggle_favorite(db, current_user.id, product_id)
    return {
        "success": True,
        "message": result["message"],
        "data": result,
    }

