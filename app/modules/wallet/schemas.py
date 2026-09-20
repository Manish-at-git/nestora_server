from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field


class WalletResponse(BaseModel):
    id: str
    balance: Decimal
    reward_points: int = 0
    has_pin: bool = False


class WalletTransactionResponse(BaseModel):
    id: str
    type: str
    amount: Decimal
    status: str
    description: str | None = None
    created_at: datetime | None = None


class PinRequest(BaseModel):
    pin: str = Field(min_length=4, max_length=4, pattern=r"^\d{4}$")


class AddMoneyRequest(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    method: str = Field(default="UPI", min_length=1, max_length=50)


class SendMoneyRequest(BaseModel):
    recipient_email: EmailStr
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    pin: str = Field(min_length=4, max_length=4, pattern=r"^\d{4}$")
    purpose: str | None = Field(default=None, max_length=255)


class PayDuesRequest(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    pin: str = Field(min_length=4, max_length=4, pattern=r"^\d{4}$")


class PayDuesUpiRequest(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)


class WalletMutationResponse(BaseModel):
    ok: bool = True
    message: str
    balance: Decimal | None = None


class CreateOrderRequest(BaseModel):
    amount: int = Field(gt=0)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    receipt: str | None = Field(default=None, max_length=40)


class CreateOrderResponse(BaseModel):
    order_id: str
    amount: int
    currency: str
    receipt: str | None = None


class VerifyPaymentRequest(BaseModel):
    razorpay_payment_id: str
    razorpay_order_id: str
    razorpay_signature: str
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)


class VerifyPaymentResponse(BaseModel):
    success: bool = True
    wallet_added: bool = False
    message: str
