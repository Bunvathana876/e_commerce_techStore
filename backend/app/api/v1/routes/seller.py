from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_roles
from app.db.database import get_db
from app.models.user import User
from app.schemas.seller import SellerProfileUpdate, SellerResponse
from app.services.product_service import ProductService
from app.services.seller_service import SellerService

router = APIRouter(prefix="/seller", tags=["Seller Self-Service"])


@router.get("/me", status_code=status.HTTP_200_OK)
def get_my_store(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("seller", "admin")),
):
    seller = SellerService.get_seller_by_user_id(db, current_user.id)
    if not seller:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Seller store profile not found.",
        )
    return {
        "success": True,
        "message": "Seller store profile retrieved successfully.",
        "data": SellerResponse.model_validate(seller).model_dump(),
    }


@router.put("/me", status_code=status.HTTP_200_OK)
def update_my_store(
    request: SellerProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("seller", "admin")),
):
    seller = SellerService.get_seller_by_user_id(db, current_user.id)
    if not seller:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Seller store profile not found.",
        )
    updated_seller = SellerService.update_seller_profile(db, seller, request)
    return {
        "success": True,
        "message": "Seller store profile updated successfully.",
        "data": SellerResponse.model_validate(updated_seller).model_dump(),
    }


@router.get("/products", status_code=status.HTTP_200_OK)
def list_my_products(
    search: str | None = Query(None, description="Search product name or description"),
    category_id: int | None = Query(None, ge=1, description="Filter by category ID"),
    status_filter: str | None = Query(None, alias="status", description="Filter by status: active, inactive, low_stock, out_of_stock, all"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, description="Page size"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("seller", "admin")),
):
    seller = SellerService.get_seller_by_user_id(db, current_user.id)
    if not seller:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Seller store profile not found.",
        )
    result = ProductService.get_seller_products(
        db=db,
        seller_id=seller.id,
        search=search,
        category_id=category_id,
        status_filter=status_filter,
        page=page,
        limit=limit,
    )
    return {
        "success": True,
        "message": "Seller products retrieved successfully.",
        "data": result.model_dump(),
    }
