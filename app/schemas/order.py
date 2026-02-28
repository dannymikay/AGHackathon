import uuid
from datetime import datetime

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
