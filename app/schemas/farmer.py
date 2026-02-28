import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.common import GeoPoint


class FarmerCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    phone: str = Field(min_length=7, max_length=30)
    email: EmailStr
    password: str = Field(min_length=8)
    farm_name: str | None = Field(default=None, max_length=300)
    farm_size_hectares: float | None = Field(default=None, gt=0)
    location: GeoPoint | None = None


class FarmerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    farm_name: str | None = Field(default=None, max_length=300)
    farm_size_hectares: float | None = Field(default=None, gt=0)
    location: GeoPoint | None = None


class FarmerLogin(BaseModel):
    email: EmailStr
    password: str


class FarmerPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    farm_name: str | None
    farm_size_hectares: float | None
    quality_rating: float
    total_transactions: int
    created_at: datetime


class FarmerPrivate(FarmerPublic):
    email: str
    phone: str
    stripe_account_id: str | None
