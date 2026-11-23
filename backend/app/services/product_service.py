from app.services.authorization_service import AuthorizationService
from app.models.user import User
import math
from decimal import Decimal
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.category import Category
from app.models.product import Product
from app.models.seller import Seller
from app.schemas.category import CategoryCreate, CategoryUpdate
from app.schemas.product import ProductCreate, ProductPaginationResponse, ProductResponse, ProductUpdate
from app.services.inventory_service import InventoryService


class ProductService:
    # ==============================
    # CATEGORIES
    # ==============================
    @staticmethod
    def get_categories(db: Session, active_only: bool = True) -> list[Category]:
        query = select(Category)
        if active_only:
            query = query.where(Category.is_active == True)
        query = query.order_by(Category.name.asc())
        return list(db.scalars(query).all())

    @staticmethod
    def get_category_by_id(db: Session, category_id: int) -> Category:
        category = db.scalar(select(Category).where(Category.id == category_id))
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found.",
            )
        return category

    @staticmethod
    def create_category(db: Session, data: CategoryCreate) -> Category:
        existing = db.scalar(select(Category).where(Category.name == data.name))
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Category with this name already exists.",
            )
        category = Category(**data.model_dump())
        db.add(category)
        db.commit()
        db.refresh(category)
        return category

    @staticmethod
    def update_category(db: Session, category_id: int, data: CategoryUpdate) -> Category:
        category = ProductService.get_category_by_id(db, category_id)
        update_dict = data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(category, key, value)
        db.commit()
        db.refresh(category)
        return category

    @staticmethod
    def delete_category(db: Session, category_id: int) -> None:
        category = ProductService.get_category_by_id(db, category_id)
        db.delete(category)
        db.commit()

    # ==============================
    # PRODUCTS
    # ==============================
    @staticmethod
    def get_products(
        db: Session,
        category_id: int | None = None,
        seller_id: int | None = None,
        search: str | None = None,
        min_price: Decimal | None = None,
        max_price: Decimal | None = None,
        min_rating: Decimal | None = None,
        sort: str | None = None,
        page: int = 1,
        limit: int = 20,
        active_only: bool = False,
        viewer: User | None = None,
    ) -> ProductPaginationResponse:
        page = max(1, page)
        limit = max(1, min(100, limit))

        query = select(Product).options(
            joinedload(Product.category),
            joinedload(Product.seller),
        )

        if active_only:
            query = query.where(Product.is_active == True)
        elif not AuthorizationService.is_admin(viewer):
            query = query.where(
                Product.is_active.is_(True)
                | Product.seller_id.in_(AuthorizationService.seller_ids(db, viewer))
            )

        if category_id is not None:
            query = query.where(Product.category_id == category_id)

        if seller_id is not None:
            query = query.where(Product.seller_id == seller_id)

        if search:
            search_term = f"%{search.strip()}%"
            query = query.where(
                (Product.name.ilike(search_term)) | (Product.description.ilike(search_term))
            )

        if min_price is not None:
            query = query.where(Product.price >= min_price)

        if max_price is not None:
            query = query.where(Product.price <= max_price)

        if min_rating is not None:
            query = query.where(Product.rating >= min_rating)

        # Sorting
        if sort == "price_asc":
            query = query.order_by(Product.price.asc())
        elif sort == "price_desc":
            query = query.order_by(Product.price.desc())
        elif sort in ("rating_desc", "rating", "highest_rated"):
            query = query.order_by(Product.rating.desc(), Product.id.desc())
        elif sort in ("popular", "most_popular"):
            query = query.order_by(Product.rating.desc(), Product.created_at.desc())
        elif sort == "oldest":
            query = query.order_by(Product.created_at.asc())
        else:
            # Default newest
            query = query.order_by(Product.created_at.desc())

        # Total count query
        count_query = select(func.count()).select_from(query.order_by(None).subquery())
        total = db.scalar(count_query) or 0

        # Pagination offset and limit
        offset = (page - 1) * limit
        items = list(db.scalars(query.offset(offset).limit(limit)).all())
        total_pages = math.ceil(total / limit) if total > 0 else 1

        return ProductPaginationResponse(
            items=[ProductResponse.model_validate(p) for p in items],
            total=total,
            page=page,
            limit=limit,
            total_pages=total_pages,
        )

    @staticmethod
    def get_seller_products(
        db: Session,
        seller_id: int,
        search: str | None = None,
        category_id: int | None = None,
        status_filter: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> ProductPaginationResponse:
        page = max(1, page)
        limit = max(1, min(100, limit))

        query = select(Product).where(Product.seller_id == seller_id).options(
            joinedload(Product.category),
            joinedload(Product.seller),
        )

        if category_id is not None:
            query = query.where(Product.category_id == category_id)

        if status_filter:
            norm = status_filter.strip().lower()
            if norm == "active":
                query = query.where(Product.is_active == True)
            elif norm in ("inactive", "draft"):
                query = query.where(Product.is_active == False)
            elif norm == "out_of_stock":
                query = query.where(Product.stock == 0)
            elif norm == "low_stock":
                query = query.where(Product.stock > 0, Product.stock < 10)

        if search:
            search_term = f"%{search.strip()}%"
            query = query.where(
                (Product.name.ilike(search_term)) | (Product.description.ilike(search_term))
            )

        # Order by newest
        query = query.order_by(Product.created_at.desc(), Product.id.desc())

        # Total count query
        count_query = select(func.count()).select_from(query.order_by(None).subquery())
        total = db.scalar(count_query) or 0

        # Offset and limit
        offset = (page - 1) * limit
        items = list(db.scalars(query.offset(offset).limit(limit)).all())
        total_pages = math.ceil(total / limit) if total > 0 else 1

        return ProductPaginationResponse(
            items=[ProductResponse.model_validate(p) for p in items],
            total=total,
            page=page,
            limit=limit,
            total_pages=total_pages,
        )

    @staticmethod
    def get_product_by_id(db: Session, product_id: int) -> Product:
        product = db.scalar(
            select(Product)
            .options(
                joinedload(Product.category),
                joinedload(Product.seller),
            )
            .where(Product.id == product_id)
        )
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found.",
            )
        return product

    @staticmethod
    def create_product(db: Session, data: ProductCreate) -> Product:
        # Check category exists
        ProductService.get_category_by_id(db, data.category_id)
        if data.seller_id is not None:
            seller = db.scalar(select(Seller).where(Seller.id == data.seller_id))
            if not seller:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Seller with id {data.seller_id} does not exist.",
                )

        product_data = data.model_dump()
        product_data["rating"] = Decimal("0.00")
        product = Product(**product_data)
        db.add(product)
        db.flush()
        if product.stock > 0:
            InventoryService.record_product_opening_stock(db, product)
        db.commit()
        db.refresh(product)

        # Update seller products_count if seller_id assigned
        if product.seller_id:
            db.query(Seller).filter(Seller.id == product.seller_id).update(
                {Seller.products_count: Seller.products_count + 1}
            )
            db.commit()

        return ProductService.get_product_by_id(db, product.id)

    @staticmethod
    def update_product(db: Session, product_id: int, data: ProductUpdate) -> Product:
        product = ProductService.get_product_by_id(db, product_id)
        old_seller_id = product.seller_id
        old_stock = int(product.stock)
        update_dict = data.model_dump(exclude_unset=True)

        if "category_id" in update_dict and update_dict["category_id"] is not None:
            ProductService.get_category_by_id(db, update_dict["category_id"])

        if "seller_id" in update_dict and update_dict["seller_id"] is not None:
            seller = db.scalar(select(Seller).where(Seller.id == update_dict["seller_id"]))
            if not seller:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Seller with id {update_dict['seller_id']} does not exist.",
                )

        for key, value in update_dict.items():
            setattr(product, key, value)

        if product.discount_price is not None and product.discount_price >= product.price:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Discount price must be strictly less than regular price.",
            )

        if "stock" in update_dict and int(product.stock) != old_stock:
            InventoryService.record_product_stock_delta(
                db, product, old_stock, int(product.stock)
            )

        db.commit()
        db.refresh(product)

        # Update seller products_count if seller changed
        if "seller_id" in update_dict and update_dict["seller_id"] != old_seller_id:
            if old_seller_id:
                count_old = db.scalar(select(func.count(Product.id)).where(Product.seller_id == old_seller_id)) or 0
                db.query(Seller).filter(Seller.id == old_seller_id).update({Seller.products_count: count_old})
            if product.seller_id:
                count_new = db.scalar(select(func.count(Product.id)).where(Product.seller_id == product.seller_id)) or 0
                db.query(Seller).filter(Seller.id == product.seller_id).update({Seller.products_count: count_new})
            db.commit()

        return ProductService.get_product_by_id(db, product.id)

    @staticmethod
    def delete_product(db: Session, product_id: int) -> None:
        product = ProductService.get_product_by_id(db, product_id)
        seller_id = product.seller_id
        db.delete(product)
        db.commit()

        if seller_id:
            count = db.scalar(select(func.count(Product.id)).where(Product.seller_id == seller_id)) or 0
            db.query(Seller).filter(Seller.id == seller_id).update({Seller.products_count: count})
            db.commit()
