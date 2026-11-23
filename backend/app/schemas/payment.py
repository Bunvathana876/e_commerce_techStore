from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field


class PaymentConfigResponse(BaseModel):
    supported_methods: list[str]
    card_gateway_configured: bool
    card_provider: str
    stripe_publishable_key: str | None = None
    currency: str
    enable_card_payment: bool = True
    enable_cod_payment: bool = True


class CardPaymentIntentRequest(BaseModel):
    order_id: int = Field(gt=0)


class CardPaymentIntentResponse(BaseModel):
    payment_id: int
    transaction_ref: str
    order_id: int
    payment_intent_id: str
    client_secret: str = Field(repr=False)
    amount: Decimal
    currency: str
    publishable_key: str | None = None


class CardPaymentConfirmRequest(BaseModel):
    order_id: int = Field(gt=0)
    payment_intent_id: str = Field(min_length=5, max_length=120)


class PaymentTransactionResponse(BaseModel):
    id: int
    transaction_ref: str
    order_id: int
    customer_id: int | None = None
    customer_name: str | None = None
    customer_email: str | None = None
    order_status: str | None = None
    provider: str
    payment_method: str
    amount: Decimal
    currency: str
    status: str
    provider_reference: str | None = None
    card_brand: str | None = None
    card_last4: str | None = None
    failure_reason: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
