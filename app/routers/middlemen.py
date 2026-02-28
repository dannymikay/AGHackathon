from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_middleman
from app.models.middleman import Middleman
from app.schemas.middleman import MiddlemanLocationUpdate, MiddlemanPrivate, MiddlemanUpdate
from app.ws.manager import manager

router = APIRouter(prefix="/middlemen", tags=["middlemen"])


@router.get("/me", response_model=MiddlemanPrivate)
async def get_my_profile(
    middleman: Annotated[Middleman, Depends(get_current_middleman)],
):
    return middleman


@router.put("/me", response_model=MiddlemanPrivate)
async def update_my_profile(
    body: MiddlemanUpdate,
    middleman: Annotated[Middleman, Depends(get_current_middleman)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if body.name is not None:
        middleman.name = body.name
    if body.truck_capacity_kg is not None:
        middleman.truck_capacity_kg = body.truck_capacity_kg
    if body.route_radius_km is not None:
        middleman.route_radius_km = body.route_radius_km
    if body.is_available is not None:
        middleman.is_available = body.is_available
    await db.commit()
    await db.refresh(middleman)
    return middleman


@router.put("/me/location", response_model=MiddlemanPrivate)
async def update_location(
    body: MiddlemanLocationUpdate,
    middleman: Annotated[Middleman, Depends(get_current_middleman)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update middleman GPS location (REST endpoint — WS stream is preferred for live updates)."""
    await db.execute(
        text(
            "UPDATE middlemen SET current_location = ST_SetSRID(ST_MakePoint(:lon, :lat), 4326) "
            "WHERE id = :id"
        ),
        {
            "lon": body.current_location.longitude,
            "lat": body.current_location.latitude,
            "id": str(middleman.id),
        },
    )
    await db.commit()
    await db.refresh(middleman)
    return middleman
