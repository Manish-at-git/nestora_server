"""Marketplace API request and response contracts."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class MarketplaceCategoryResponse(BaseModel):
    id: str
    name: str
    created_at: datetime | None = None


class MarketplaceItemRequest(BaseModel):
    association_id: str | None = None
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    category_id: str
    price: Decimal | None = None
    condition_state: str | None = None
    brand: str | None = None
    item_age: str | None = None
    location: str | None = None
    contact_number: str | None = None
    listing_type: str = "Sell"
    is_negotiable: bool = False
    status: str = "Active"
    images: list[str] = Field(default_factory=list)


class MarketplaceItemUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    category_id: str | None = None
    price: Decimal | None = None
    condition_state: str | None = None
    brand: str | None = None
    item_age: str | None = None
    location: str | None = None
    contact_number: str | None = None
    listing_type: str | None = None
    is_negotiable: bool | None = None
    status: str | None = None
    images: list[str] | None = None


class MarketplaceFilters(BaseModel):
    category_id: str | None = None
    condition: str | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    is_negotiable: bool | None = None
    status: str | None = "Active"
    sort: str | None = "Newest"


class MarketplaceItemResponse(BaseModel):
    id: str
    association_id: str
    user_id: str
    owner_account_id: str | None = None
    category_id: str
    category_name: str | None = None
    title: str
    description: str | None = None
    price: Decimal | None = None
    condition_state: str | None = None
    brand: str | None = None
    item_age: str | None = None
    location: str | None = None
    contact_number: str | None = None
    is_negotiable: bool = False
    listing_type: str | None = None
    status: str | None = None
    views_count: int = 0
    saves_count: int = 0
    is_saved: bool = False
    seller_name: str | None = None
    images: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MarketplaceChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5000)
    receiver_id: str | None = None


class MarketplaceChatResponse(BaseModel):
    id: str
    item_id: str
    sender_id: str
    receiver_id: str
    message: str
    sender_name: str | None = None
    email: str | None = None
    is_mine: bool = False
    created_at: datetime | None = None


class MarketplaceChatThreadResponse(BaseModel):
    buyer_id: str
    buyer_name: str
    buyer_email: str
    last_message: str | None = None
    last_message_at: datetime | None = None


class MarketplaceReportRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class MarketplaceMutationResponse(BaseModel):
    ok: bool = True
    id: str | None = None
    saved: bool | None = None
