from app.services.authorization_service import AuthorizationService
from app.core.dependencies import require_roles, get_optional_current_user
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.models.seller import Seller
from app.schemas.seller import SellerCreate, SellerProfileUpdate, SellerResponse, SellerUpdate
from app.services.product_service import ProductService
from app.services.seller_service import SellerService

router = APIRouter(prefix="/sellers", tags=["Sellers"])


@router.get("", status_code=status.HTTP_200_OK)
def list_sellers(
    status_filter: str | None = Query(None, alias="status", description="Filter by status (Active, Pending, Suspended)"),
    search: str | None = Query(None, description="Search by store, owner, or email"),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    if not AuthorizationService.is_admin(current_user):
        status_filter = "Active"
    sellers = SellerService.get_sellers(db, status_filter=status_filter, search=search)
    return {
        "success": True,
        "message": "Sellers retrieved successfully.",
        "data": [_seller_response(s, current_user) for s in sellers],
    }


@router.get("/me", status_code=status.HTTP_200_OK)
def get_my_seller_store_alias(
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
def update_my_seller_store_alias(
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
def list_my_products_alias(
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


@router.get("/{seller_id}", status_code=status.HTTP_200_OK)
def get_seller(
    seller_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    seller = SellerService.get_seller_by_id(db, seller_id)
    if not AuthorizationService.is_admin(current_user) and seller.status != "Active":
        raise HTTPException(status_code=404, detail="Seller not found.")
    return {
        "success": True,
        "message": "Seller retrieved successfully.",
        "data": _seller_response(seller, current_user),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_seller(
    request: SellerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    seller = SellerService.create_seller(db, request)
    return {
        "success": True,
        "message": "Seller created successfully in database.",
        "data": _seller_response(seller, current_user),
    }


@router.put("/{seller_id}", status_code=status.HTTP_200_OK)
def update_seller(
    seller_id: int,
    request: SellerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    seller = SellerService.update_seller(db, seller_id, request)
    return {
        "success": True,
        "message": "Seller updated successfully.",
        "data": _seller_response(seller, current_user),
    }


@router.delete("/{seller_id}", status_code=status.HTTP_200_OK)
def delete_seller(
    seller_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    SellerService.delete_seller(db, seller_id)
    return {
        "success": True,
        "message": f"Seller #{seller_id} deleted successfully from database.",
        "data": None,
    }


def _seller_response(seller: Seller, user: User | None) -> dict:
    data = SellerResponse.model_validate(seller).model_dump()
    if AuthorizationService.is_admin(user) or (
        user is not None and user.role == "seller" and seller.user_id == user.id
    ):
        return data
    return {key: data[key] for key in (
        "id", "name", "description", "logo", "status", "rating", "products_count",
        "created_at", "updated_at",
    )}
