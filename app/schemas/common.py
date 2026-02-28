from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class GeoPoint(BaseModel):
    latitude: float
    longitude: float


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    has_next: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class HealthResponse(BaseModel):
    status: str
    db_ok: bool
    postgis_ok: bool
