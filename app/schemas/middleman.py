import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.common import GeoPoint


class MiddlemanCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    phone: str = Field(min_length=7, max_length=30)
    email: EmailStr
    password: str = Field(min_length=8)
    truck_capacity_kg: float = Field(gt=0)
    truck_plate: str = Field(min_length=2, max_length=20)
    route_radius_km: float = Field(default=100.0, gt=0)
    current_location: GeoPoint | None = None


class MiddlemanUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    truck_capacity_kg: float | None = Field(default=None, gt=0)
    route_radius_km: float | None = Field(default=None, gt=0)
    is_available: bool | None = None


class MiddlemanLogin(BaseModel):
    email: EmailStr
    password: str


class MiddlemanLocationUpdate(BaseModel):
    current_location: GeoPoint


class MiddlemanPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    truck_capacity_kg: float
    truck_plate: str
    route_radius_km: float
    on_time_rating: float
    total_deliveries: int
    is_available: bool
    created_at: datetime


class MiddlemanPrivate(MiddlemanPublic):
    email: str
    phone: str
    stripe_account_id: str | None


class NearbyMiddlemanResponse(BaseModel):
    middleman: MiddlemanPublic
    distance_km: float
    estimated_arrival_hours: float | None = None
