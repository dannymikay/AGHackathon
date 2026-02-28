import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.escrow import EscrowStatus
from app.schemas.common import GeoPoint


class EscrowPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_id: uuid.UUID
    total_amount_cents: int
    farmer_released_cents: int
    middleman_released_cents: int
    refunded_cents: int
    status: EscrowStatus
    funds_held_at: datetime | None
    picked_up_at: datetime | None
    delivered_at: datetime | None
    cancelled_at: datetime | None


class PaymentInitiate(BaseModel):
    stripe_client_secret: str
    amount_cents: int
    currency: str = "usd"


class VerifyPickupRequest(BaseModel):
    order_id: uuid.UUID
    qr_token: str
    middleman_location: GeoPoint


class VerifyDeliveryRequest(BaseModel):
    order_id: uuid.UUID
    qr_token: str
    middleman_location: GeoPoint


class DisputeRequest(BaseModel):
    order_id: uuid.UUID
    middleman_location: GeoPoint
    evidence_description: str | None = None
