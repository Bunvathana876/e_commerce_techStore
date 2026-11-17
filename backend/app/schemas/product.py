from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict

from app.schemas.category import CategoryResponse


class ProductSellerSummary(BaseModel):
    id: int
    name: str
    logo: str | None = None
    rating: float = 5.0
    status: str = "Active"

    model_config = ConfigDict(from_attributes=True)


class ProductBase(BaseModel):
    category_id: int
    seller_id: int | None = None
    name: str
    description: str | None = None
    price: Decimal
    discount_price: Decimal | None = None
    stock: int = 0
    image_url: str | None = None
    rating: Decimal = Decimal("0.00")
    is_active: bool = True


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    category_id: int | None = None
    seller_id: int | None = None
    name: str | None = None
    description: str | None = None
    price: Decimal | None = None
    discount_price: Decimal | None = None
    stock: int | None = None
    image_url: str | None = None
    rating: Decimal | None = None
    is_active: bool | None = None


class ProductResponse(ProductBase):
    id: int
    created_at: datetime
    updated_at: datetime
    category: CategoryResponse | None = None
    seller: ProductSellerSummary | None = None

    model_config = ConfigDict(from_attributes=True)


class ProductPaginationResponse(BaseModel):
    items: list[ProductResponse]
    total: int
    page: int
    limit: int
    total_pages: int
