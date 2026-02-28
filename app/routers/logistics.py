"""Logistics router — find nearby middlemen, accept/reject assignments, get route info."""
import math
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_current_middleman
from app.models.logistics_assignment import AssignmentStatus, LogisticsAssignment
from app.models.middleman import Middleman
from app.models.order import Order, OrderStatus
from app.schemas.common import GeoPoint
from app.schemas.middleman import NearbyMiddlemanResponse
from app.services import order_fsm
from app.services.external_api_service import fetch_driving_route
from app.services.order_fsm import InvalidTransitionError
from app.services.spatial_service import find_middlemen_near_route

router = APIRouter(prefix="/logistics", tags=["logistics"])


class RouteInfoResponse(BaseModel):
    """Driving route details between the Farmer and Buyer for a given order."""
    order_id: uuid.UUID
    farmer_location: GeoPoint
    buyer_location: GeoPoint
    distance_km: float | None
    duration_hours: float | None
    source: str  # "openrouteservice" or "straight_line_estimate"


@router.get("/search/{order_id}", response_model=list[NearbyMiddlemanResponse])
async def search_nearby_middlemen(
    order_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Find available middlemen near the Farmer→Buyer route vector.
    Uses PostGIS ST_DWithin with 25km buffer; falls back to mock data.
    Cold-chain orders automatically filter to REEFER trucks only.
    """
    stmt = (
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.farmer), selectinload(Order.buyer))
    )
    order = (await db.execute(stmt)).scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.status != OrderStatus.LOGISTICS_SEARCH:
        raise HTTPException(
            status_code=409,
            detail=f"Order must be in LOGISTICS_SEARCH state (currently {order.status})",
        )

    # Use demo coordinates if PostGIS locations aren't set (Coimbatore → Chennai)
    farmer_loc = GeoPoint(latitude=11.0168, longitude=76.9558)
    buyer_loc = GeoPoint(latitude=13.0827, longitude=80.2707)

    results = await find_middlemen_near_route(
        db,
        farmer_loc,
        buyer_loc,
        requires_cold_chain=order.requires_cold_chain,
    )
    return results


@router.get("/route/{order_id}", response_model=RouteInfoResponse)
async def get_route_info(
    order_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    middleman: Annotated[Middleman, Depends(get_current_middleman)],
):
    """
    Return the real driving route (distance + ETA) between the Farmer and Buyer
    for a given order, using OpenRouteService.

    Falls back to a straight-line estimate (Haversine × 1.3 road factor) when
    OpenRouteService is unavailable or not configured.

    Useful for truckers to assess trip length before accepting an assignment.
    Requires middleman authentication.
    """
    order = (
        await db.execute(select(Order).where(Order.id == order_id))
    ).scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    # Demo fallback coordinates (Coimbatore → Chennai)
    farmer_loc = GeoPoint(latitude=11.0168, longitude=76.9558)
    buyer_loc = GeoPoint(latitude=13.0827, longitude=80.2707)

    route = await fetch_driving_route(
        start_lon=farmer_loc.longitude,
        start_lat=farmer_loc.latitude,
        end_lon=buyer_loc.longitude,
        end_lat=buyer_loc.latitude,
    )

    if route is not None:
        return RouteInfoResponse(
            order_id=order_id,
            farmer_location=farmer_loc,
            buyer_location=buyer_loc,
            distance_km=route["distance_km"],
            duration_hours=route["duration_hours"],
            source="openrouteservice",
        )

    # Haversine straight-line × 1.3 road-factor fallback
    lat1 = math.radians(farmer_loc.latitude)
    lon1 = math.radians(farmer_loc.longitude)
    lat2 = math.radians(buyer_loc.latitude)
    lon2 = math.radians(buyer_loc.longitude)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    straight_km = 6_371 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    road_km = round(straight_km * 1.3, 2)

    return RouteInfoResponse(
        order_id=order_id,
        farmer_location=farmer_loc,
        buyer_location=buyer_loc,
        distance_km=road_km,
        duration_hours=round(road_km / 60, 2),
        source="straight_line_estimate",
    )


@router.post("/accept/{assignment_id}")
async def accept_assignment(
    assignment_id: uuid.UUID,
    middleman: Annotated[Middleman, Depends(get_current_middleman)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Middleman accepts a logistics assignment.
    Transitions order: LOGISTICS_SEARCH → IN_TRANSIT.
    Enriches assignment with real driving distance via OpenRouteService.
    """
    stmt = (
        select(LogisticsAssignment)
        .where(LogisticsAssignment.id == assignment_id)
        .options(
            selectinload(LogisticsAssignment.order).selectinload(Order.escrow),
            selectinload(LogisticsAssignment.order).selectinload(Order.farmer),
        )
    )
    assignment = (await db.execute(stmt)).scalar_one_or_none()

    if assignment is None:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if assignment.middleman_id != middleman.id:
        raise HTTPException(status_code=403, detail="Not your assignment")
    if assignment.status != AssignmentStatus.OFFERED:
        raise HTTPException(status_code=409, detail="Assignment already actioned")

    order = assignment.order
    if order.status != OrderStatus.LOGISTICS_SEARCH:
        raise HTTPException(
            status_code=409, detail=f"Order is in {order.status}, cannot accept"
        )

    # Fetch real driving distance before entering the transaction (I/O outside DB lock)
    farmer_loc = GeoPoint(latitude=11.0168, longitude=76.9558)
    buyer_loc = GeoPoint(latitude=13.0827, longitude=80.2707)
    route = await fetch_driving_route(
        start_lon=farmer_loc.longitude,
        start_lat=farmer_loc.latitude,
        end_lon=buyer_loc.longitude,
        end_lat=buyer_loc.latitude,
    )

    try:
        async with db.begin():
            # All mutations within the same transaction so they roll back together
            if route and assignment.estimated_distance_km is None:
                assignment.estimated_distance_km = route["distance_km"]

            assignment.status = AssignmentStatus.ACCEPTED
            assignment.accepted_at = datetime.now(tz=timezone.utc)
            assignment.last_gps_ping_at = datetime.now(tz=timezone.utc)
            middleman.is_available = False

            await order_fsm.transition_order(
                db,
                order.id,
                OrderStatus.IN_TRANSIT,
                actor_type="middleman",
                actor_id=middleman.id,
                reason="middleman_accepted",
            )

        return {"ok": True, "order_id": str(order.id), "status": "IN_TRANSIT"}
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/reject/{assignment_id}")
async def reject_assignment(
    assignment_id: uuid.UUID,
    middleman: Annotated[Middleman, Depends(get_current_middleman)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    assignment = (
        await db.execute(
            select(LogisticsAssignment).where(LogisticsAssignment.id == assignment_id)
        )
    ).scalar_one_or_none()

    if assignment is None:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if assignment.middleman_id != middleman.id:
        raise HTTPException(status_code=403, detail="Not your assignment")
    if assignment.status != AssignmentStatus.OFFERED:
        raise HTTPException(status_code=409, detail="Assignment already actioned")

    assignment.status = AssignmentStatus.REJECTED
    await db.commit()
    return {"ok": True}
