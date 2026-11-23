from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.category import CategoryResponse


class ProductSellerSummary(BaseModel):
    id: int
    name: str
    logo: str | None = None
    rating: float = 5.0
    status: str = "Active"

    model_config = ConfigDict(from_attributes=True)


class ProductBase(BaseModel):
    category_id: int = Field(..., ge=1)
    seller_id: int | None = Field(default=None, ge=1)
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    price: Decimal = Field(..., gt=0)
    discount_price: Decimal | None = Field(default=None, gt=0)
    stock: int = Field(default=0, ge=0)
    image_url: str | None = None
    is_active: bool = True


class ProductCreate(ProductBase):
    rating: Decimal = Decimal("0.00")

    @model_validator(mode="after")
    def validate_product_fields(self) -> "ProductCreate":
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("Product name cannot be empty.")
        if self.discount_price is not None and self.discount_price >= self.price:
            raise ValueError("Discount price must be strictly less than regular price.")
        # Never allow clients to forge initial product ratings
        self.rating = Decimal("0.00")
        return self


class ProductUpdate(BaseModel):
    category_id: int | None = Field(default=None, ge=1)
    seller_id: int | None = Field(default=None, ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    price: Decimal | None = Field(default=None, gt=0)
    discount_price: Decimal | None = Field(default=None, gt=0)
    stock: int | None = Field(default=None, ge=0)
    image_url: str | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def validate_partial_fields(self) -> "ProductUpdate":
        if self.name is not None:
            self.name = self.name.strip()
            if not self.name:
                raise ValueError("Product name cannot be empty.")
        if (
            self.price is not None
            and self.discount_price is not None
            and self.discount_price >= self.price
        ):
            raise ValueError("Discount price must be strictly less than regular price.")
        return self


class ProductResponse(ProductBase):
    id: int
    rating: Decimal = Decimal("0.00")
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
