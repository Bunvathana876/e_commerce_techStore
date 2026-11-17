from app.services.authorization_service import AuthorizationService
from app.core.config import settings
from app.core.dependencies import require_roles, get_optional_current_user
from app.core.rate_limit import RateLimiter
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.schemas.category import CategoryCreate, CategoryResponse, CategoryUpdate
from app.services.product_service import ProductService

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RateLimiter(times=settings.RATE_LIMIT_CATALOG_BROWSING, seconds=60, scope="catalog:browse"))],
)
def list_categories(
    active_only: bool = Query(False, description="Filter active categories only"),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    categories = ProductService.get_categories(db, active_only=active_only or not AuthorizationService.is_admin(current_user))
    return {
        "success": True,
        "message": "Categories retrieved successfully.",
        "data": [CategoryResponse.model_validate(c).model_dump() for c in categories],
    }


@router.get(
    "/{category_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RateLimiter(times=settings.RATE_LIMIT_CATALOG_BROWSING, seconds=60, scope="catalog:browse"))],
)
def get_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    category = ProductService.get_category_by_id(db, category_id)
    if not category.is_active and not AuthorizationService.is_admin(current_user):
        raise HTTPException(status_code=404, detail="Category not found.")
    return {
        "success": True,
        "message": "Category retrieved successfully.",
        "data": CategoryResponse.model_validate(category).model_dump(),
    }


@router.get(
    "/{category_id}/products",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RateLimiter(times=settings.RATE_LIMIT_CATALOG_BROWSING, seconds=60, scope="catalog:browse"))],
)
def get_category_products(
    category_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Page size"),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    get_category(category_id, db, current_user)
    result = ProductService.get_products(
        db, category_id=category_id, page=page, limit=limit, viewer=current_user
    )
    return {
        "success": True,
        "message": "Category products retrieved successfully.",
        "data": result.model_dump(),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_category(
    request: CategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    category = ProductService.create_category(db, request)
    return {
        "success": True,
        "message": "Category created successfully.",
        "data": CategoryResponse.model_validate(category).model_dump(),
    }


@router.put("/{category_id}", status_code=status.HTTP_200_OK)
def update_category(
    category_id: int,
    request: CategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    category = ProductService.update_category(db, category_id, request)
    return {
        "success": True,
        "message": "Category updated successfully.",
        "data": CategoryResponse.model_validate(category).model_dump(),
    }


@router.delete("/{category_id}", status_code=status.HTTP_200_OK)
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    ProductService.delete_category(db, category_id)
    return {
        "success": True,
        "message": "Category deleted successfully.",
    }

