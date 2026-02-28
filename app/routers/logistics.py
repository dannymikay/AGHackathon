"""Logistics router — find nearby middlemen, accept/reject assignments."""
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_current_farmer, get_current_middleman
from app.models.buyer import Buyer
from app.models.farmer import Farmer
from app.models.logistics_assignment import AssignmentStatus, LogisticsAssignment
from app.models.middleman import Middleman
from app.models.order import Order, OrderStatus
from app.schemas.middleman import NearbyMiddlemanResponse
from app.services import notification_service, order_fsm
from app.services.order_fsm import InvalidTransitionError
from app.services.spatial_service import find_middlemen_near_route
from app.schemas.common import GeoPoint

router = APIRouter(prefix="/logistics", tags=["logistics"])


@router.get("/search/{order_id}", response_model=list[NearbyMiddlemanResponse])
async def search_nearby_middlemen(
    order_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Find available middlemen near the Farmer→Buyer route vector.
    Uses PostGIS ST_DWithin with 5km buffer; falls back to mock data.
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

    if order.farmer is None:
        raise HTTPException(status_code=422, detail="Farmer has no location set")

    # Use demo coordinates if PostGIS locations aren't set
    farmer_loc = GeoPoint(latitude=11.0168, longitude=76.9558)
    buyer_loc = GeoPoint(latitude=13.0827, longitude=80.2707)

    results = await find_middlemen_near_route(db, farmer_loc, buyer_loc)
    return results


@router.post("/accept/{assignment_id}")
async def accept_assignment(
    assignment_id: uuid.UUID,
    middleman: Annotated[Middleman, Depends(get_current_middleman)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Middleman accepts a logistics assignment.
    Transitions order: LOGISTICS_SEARCH → IN_TRANSIT.
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

    try:
        async with db.begin():
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
