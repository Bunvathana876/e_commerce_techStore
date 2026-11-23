from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class StoreSettingsUpdate(BaseModel):
    store_name: str = Field(..., min_length=1, max_length=150)
    store_email: EmailStr
    store_phone: str | None = Field(default=None, max_length=50)
    store_address: str | None = Field(default=None, max_length=500)
    store_logo_url: str | None = Field(default=None, max_length=500)
    currency: str = Field(default="USD", min_length=3, max_length=10)
    language: str = Field(default="en", min_length=2, max_length=20)
    timezone: str = Field(default="Asia/Phnom_Penh", min_length=2, max_length=80)

    theme: str = Field(default="light", max_length=30)
    primary_color: str = Field(default="#245BE7", max_length=20)
    sidebar_style: str = Field(default="default", max_length=30)

    free_shipping_min: Decimal = Field(default=Decimal("100.00"), ge=0)
    standard_shipping_fee: Decimal = Field(default=Decimal("2.00"), ge=0)
    express_shipping_fee: Decimal = Field(default=Decimal("12.00"), ge=0)
    estimated_delivery_days: str = Field(default="1-3", min_length=1, max_length=50)

    enable_card_payment: bool = True
    enable_cod_payment: bool = True

    notify_new_order: bool = True
    notify_low_stock: bool = True
    notify_customer_message: bool = True
    notify_weekly_report: bool = False

    @model_validator(mode="after")
    def validate_business_rules(self) -> "StoreSettingsUpdate":
        self.store_name = self.store_name.strip()
        if not self.store_name:
            raise ValueError("Store name is required.")
        self.currency = self.currency.strip().upper()
        self.estimated_delivery_days = self.estimated_delivery_days.strip() or "1-3"
        if not self.enable_card_payment and not self.enable_cod_payment:
            raise ValueError("At least one payment method (Credit / Debit Card or Cash on Delivery) must stay enabled.")
        return self


class StoreSettingsData(BaseModel):
    id: int
    key: str
    store_name: str
    store_email: str
    store_phone: str | None = None
    store_address: str | None = None
    store_logo_url: str | None = None
    currency: str
    language: str
    timezone: str
    theme: str
    primary_color: str
    sidebar_style: str
    free_shipping_min: Decimal
    standard_shipping_fee: Decimal
    express_shipping_fee: Decimal
    estimated_delivery_days: str
    enable_card_payment: bool
    enable_cod_payment: bool
    notify_new_order: bool
    notify_low_stock: bool
    notify_customer_message: bool
    notify_weekly_report: bool
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InfrastructureStatusResponse(BaseModel):
    database_dialect: str
    database_connected: bool
    table_count: int
    table_names: list[str]
    upload_storage_backend: str
    email_provider: str
    card_gateway_configured: bool


class AdminSettingsResponse(BaseModel):
    settings: StoreSettingsData
    infrastructure: InfrastructureStatusResponse


class PublicStoreSettingsResponse(BaseModel):
    store_name: str
    store_email: str
    store_phone: str | None = None
    store_logo_url: str | None = None
    currency: str
    free_shipping_min: Decimal
    standard_shipping_fee: Decimal
    express_shipping_fee: Decimal
    estimated_delivery_days: str
    enable_card_payment: bool
    enable_cod_payment: bool


class RoleUserSummary(BaseModel):
    id: int
    name: str
    email: str
    is_active: bool


class RolePermissionGroup(BaseModel):
    module: str
    permissions: list[str]


class RoleDefinitionResponse(BaseModel):
    id: str
    name: str
    description: str
    is_system: bool
    permissions_count: int
    permission_groups: list[RolePermissionGroup]
    users_count: int
    users: list[RoleUserSummary] = []
