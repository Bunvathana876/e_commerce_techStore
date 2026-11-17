from datetime import datetime
from pydantic import BaseModel, ConfigDict


class AddressBase(BaseModel):
    full_name: str
    phone: str
    address_line: str
    city: str
    province: str | None = None
    postal_code: str | None = None
    is_default: bool = False


class AddressCreate(AddressBase):
    pass


class AddressUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    address_line: str | None = None
    city: str | None = None
    province: str | None = None
    postal_code: str | None = None
    is_default: bool | None = None


class AddressResponse(AddressBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

