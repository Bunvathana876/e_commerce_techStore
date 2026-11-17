from app.services.authorization_service import AuthorizationService
from app.core.config import settings
from app.core.dependencies import require_roles, get_optional_current_user
from app.core.rate_limit import RateLimiter
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.schemas.product import ProductCreate, ProductResponse, ProductUpdate
from app.services.product_service import ProductService

router = APIRouter(prefix="/products", tags=["Products"])


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RateLimiter(times=settings.RATE_LIMIT_CATALOG_BROWSING, seconds=60, scope="catalog:browse"))],
)
def list_products(
    category_id: int | None = Query(None, description="Filter by category ID"),
    seller_id: int | None = Query(None, description="Filter by seller ID"),
    search: str | None = Query(None, description="Search in product name or description"),
    min_price: Decimal | None = Query(None, ge=0, description="Minimum product price"),
    max_price: Decimal | None = Query(None, ge=0, description="Maximum product price"),
    min_rating: Decimal | None = Query(None, ge=0, le=5, description="Minimum product rating"),
    sort: str | None = Query(
        None,
        description="Sort by: price_asc, price_desc, rating_desc, popular, oldest, or newest",
    ),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Page size"),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    result = ProductService.get_products(
        db=db,
        viewer=current_user,
        category_id=category_id,
        seller_id=seller_id,
        search=search,
        min_price=min_price,
        max_price=max_price,
        min_rating=min_rating,
        sort=sort,
        page=page,
        limit=limit,
    )
    return {
        "success": True,
        "message": "Products retrieved successfully.",
        "data": result.model_dump(),
    }


@router.get(
    "/featured",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RateLimiter(times=settings.RATE_LIMIT_CATALOG_BROWSING, seconds=60, scope="catalog:browse"))],
)
def get_featured_products(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    result = ProductService.get_products(db=db, viewer=current_user, sort="popular", limit=limit)
    return {
        "success": True,
        "message": "Featured products retrieved successfully.",
        "data": result.model_dump(),
    }


@router.get(
    "/search",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RateLimiter(times=settings.RATE_LIMIT_CATALOG_BROWSING, seconds=60, scope="catalog:browse"))],
)
def search_products(
    q: str | None = Query(None, description="Search query string"),
    search: str | None = Query(None, description="Search query alias"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    query_str = q or search
    result = ProductService.get_products(db=db, viewer=current_user, search=query_str, page=page, limit=limit)
    return {
        "success": True,
        "message": "Products retrieved successfully.",
        "data": result.model_dump(),
    }


@router.get(
    "/{product_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RateLimiter(times=settings.RATE_LIMIT_CATALOG_BROWSING, seconds=60, scope="catalog:browse"))],
)
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    product = ProductService.get_product_by_id(db, product_id)
    if not product.is_active and not AuthorizationService.is_admin(current_user):
        if product.seller_id not in AuthorizationService.seller_ids(db, current_user):
            raise HTTPException(status_code=404, detail="Product not found.")
    return {
        "success": True,
        "message": "Product retrieved successfully.",
        "data": ProductResponse.model_validate(product).model_dump(),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_product(
    request: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "seller")),
):
    AuthorizationService.require_seller(db, current_user, request.seller_id)
    product = ProductService.create_product(db, request)
    return {
        "success": True,
        "message": "Product created successfully.",
        "data": ProductResponse.model_validate(product).model_dump(),
    }


@router.put("/{product_id}", status_code=status.HTTP_200_OK)
def update_product(
    product_id: int,
    request: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "seller")),
):
    AuthorizationService.require_product(db, current_user, product_id)
    if "seller_id" in request.model_fields_set:
        AuthorizationService.require_seller(db, current_user, request.seller_id)
    product = ProductService.update_product(db, product_id, request)
    return {
        "success": True,
        "message": "Product updated successfully.",
        "data": ProductResponse.model_validate(product).model_dump(),
    }


@router.delete("/{product_id}", status_code=status.HTTP_200_OK)
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "seller")),
):
    AuthorizationService.require_product(db, current_user, product_id)
    ProductService.delete_product(db, product_id)
    return {
        "success": True,
        "message": "Product deleted successfully.",
    }

