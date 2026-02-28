import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.order import OrderStatus
from app.schemas.bid import BidPublic
from app.schemas.common import GeoPoint
from app.schemas.escrow import EscrowPublic


class OrderCreate(BaseModel):
    crop_type: str = Field(min_length=2, max_length=100)
    variety: str | None = Field(default=None, max_length=100)
    total_volume_kg: float = Field(gt=0)
    unit_price_asking: float = Field(gt=0)
    location: GeoPoint | None = None
    requires_cold_chain: bool = False
    harvest_date: datetime | None = None


class OrderPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    farmer_id: uuid.UUID
    crop_type: str
    variety: str | None
    available_volume_kg: float
    unit_price_asking: float
    status: OrderStatus
    quality_grade: str | None
    crop_image_url: str | None
    requires_cold_chain: bool
    harvest_date: datetime | None
    created_at: datetime


class OrderDetail(OrderPublic):
    buyer_id: uuid.UUID | None
    accepted_price: float | None
    logistics_search_started_at: datetime | None
    settled_at: datetime | None
    bids: list[BidPublic] = []
    escrow: EscrowPublic | None = None


class GradingResult(BaseModel):
    quality_grade: str
    confidence_score: float
    image_url: str
    market_price_hint: float | None = None
    days_remaining: int | None = None
    suggested_grade_b_price: float | None = None


class ProduceIntelligenceResponse(BaseModel):
    crop_type: str
    shelf_life_days: int | None
    days_remaining: int | None
    requires_cold_chain: bool
    suggested_price: float | None
    grade: str | None


class PriceGuidanceResponse(BaseModel):
    """
    Returned before a Farmer creates a listing so they know what price to ask.
    Shows Grade A price (unchanged), standard Grade B discount, and the urgency-
    adjusted price if the Farmer has already declared a harvest date.
    """
    crop_type: str
    shelf_life_days: int | None
    requires_cold_chain: bool
    grade_a_suggested_price: float | None      # asking_price, no change
    grade_b_standard_price: float | None       # asking_price × grade_b_ratio
    grade_b_urgency_price: float | None        # further reduced by days remaining
    days_remaining: int | None
    urgency_note: str | None                   # human-readable explanation shown to Farmer


class OrderCreateResponse(OrderPublic):
    """
    Extended response returned when a Farmer creates a listing.
    Includes all standard OrderPublic fields plus inline price guidance
    so the Farmer can see immediately whether their asking price is in range.
    """
    price_guidance: Optional[PriceGuidanceResponse] = None
