import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.common import GeoPoint


class BuyerCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    phone: str = Field(min_length=7, max_length=30)
    email: EmailStr
    password: str = Field(min_length=8)
    delivery_location: GeoPoint | None = None
    delivery_address: str | None = Field(default=None, max_length=500)


class BuyerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    delivery_location: GeoPoint | None = None
    delivery_address: str | None = Field(default=None, max_length=500)


class BuyerLogin(BaseModel):
    email: EmailStr
    password: str


class BuyerPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    payment_speed_rating: float
    purchase_history_count: int
    created_at: datetime


class BuyerPrivate(BuyerPublic):
    email: str
    phone: str
    delivery_address: str | None
    stripe_customer_id: str | None
