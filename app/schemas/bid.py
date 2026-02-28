import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.bid import BidStatus


class BidCreate(BaseModel):
    order_id: uuid.UUID
    offered_price_per_kg: float = Field(gt=0)
    volume_kg: float = Field(gt=0)
    message: str | None = Field(default=None, max_length=1000)


class BidPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_id: uuid.UUID
    buyer_id: uuid.UUID
    offered_price_per_kg: float
    volume_kg: float
    status: BidStatus
    message: str | None
    created_at: datetime
