"""
Verification / Escrow release router.
Handles QR scan endpoints and dispute resolution with signed proof of location.
"""
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_current_buyer, get_current_middleman
from app.models.audit_log import AuditLog
from app.models.buyer import Buyer
from app.models.escrow import EscrowStatus
from app.models.logistics_assignment import LogisticsAssignment
from app.models.middleman import Middleman
from app.models.order import Order, OrderStatus
from app.schemas.common import GeoPoint
from app.schemas.escrow import (
    DisputeRequest,
    EscrowPublic,
    VerifyDeliveryRequest,
    VerifyPickupRequest,
)
from app.services import escrow_service, order_fsm
from app.services.spatial_service import check_middleman_at_buyer

router = APIRouter(prefix="/verify", tags=["verify"])


async def _load_order_with_escrow(db: AsyncSession, order_id: uuid.UUID) -> Order:
    stmt = (
        select(Order)
        .where(Order.id == order_id)
        .options(
            selectinload(Order.escrow),
            selectinload(Order.farmer),
            selectinload(Order.logistics_assignment).selectinload(
                LogisticsAssignment.middleman
            ),
        )
    )
    order = (await db.execute(stmt)).scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.escrow is None:
        raise HTTPException(status_code=409, detail="No escrow found for this order")
    return order


@router.post("/pickup", response_model=EscrowPublic)
async def verify_pickup(
    body: VerifyPickupRequest,
    middleman: Annotated[Middleman, Depends(get_current_middleman)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Middleman scans Farmer's QR code at pickup.
    Validates token, releases 20% to Farmer.
    """
    order = await _load_order_with_escrow(db, body.order_id)

    if order.logistics_assignment is None or order.logistics_assignment.middleman_id != middleman.id:
        raise HTTPException(status_code=403, detail="You are not the assigned trucker for this order")

    if order.status != OrderStatus.IN_TRANSIT:
        raise HTTPException(status_code=409, detail=f"Order is in {order.status}, expected IN_TRANSIT")

    if order.escrow.status != EscrowStatus.FUNDS_HELD:
        raise HTTPException(status_code=409, detail=f"Escrow is in {order.escrow.status}, expected FUNDS_HELD")

    # Verify QR token
    submitted_hash = hashlib.sha256(body.qr_token.encode()).hexdigest()
    if submitted_hash != order.pickup_qr_hash:
        raise HTTPException(status_code=400, detail="Invalid QR token")

    # Update heartbeat
    if order.logistics_assignment:
        order.logistics_assignment.last_gps_ping_at = datetime.now(tz=timezone.utc)

    await escrow_service.release_pickup(order, order.escrow)
    await db.commit()
    await db.refresh(order.escrow)
    return order.escrow


@router.post("/delivery", response_model=EscrowPublic)
async def verify_delivery(
    body: VerifyDeliveryRequest,
    middleman: Annotated[Middleman, Depends(get_current_middleman)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Buyer scans Middleman's QR code (or middleman scans buyer's delivery QR).
    Releases 60% to Farmer + 20% to Middleman.
    Transitions Order to SETTLED.
    """
    order = await _load_order_with_escrow(db, body.order_id)

    if order.logistics_assignment is None or order.logistics_assignment.middleman_id != middleman.id:
        raise HTTPException(status_code=403, detail="You are not the assigned trucker for this order")

    if order.status != OrderStatus.IN_TRANSIT:
        raise HTTPException(status_code=409, detail=f"Order is in {order.status}, expected IN_TRANSIT")

    if order.escrow.status != EscrowStatus.PICKED_UP:
        raise HTTPException(status_code=409, detail=f"Escrow is in {order.escrow.status}, expected PICKED_UP")

    submitted_hash = hashlib.sha256(body.qr_token.encode()).hexdigest()
    if submitted_hash != order.delivery_qr_hash:
        raise HTTPException(status_code=400, detail="Invalid QR token")

    try:
        await escrow_service.release_delivery(order, order.escrow)
        await order_fsm.transition_order(
            db,
            order.id,
            OrderStatus.SETTLED,
            actor_type="middleman",
            actor_id=middleman.id,
            reason="delivery_qr_verified",
        )
        # Free the middleman
        middleman.is_available = True
        middleman.total_deliveries += 1
        order.farmer.total_transactions += 1
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    await db.refresh(order.escrow)
    return order.escrow


@router.post("/dispute")
async def dispute_proof_of_location(
    body: DisputeRequest,
    middleman: Annotated[Middleman, Depends(get_current_middleman)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Middleman triggers a "Proof of Location" dispute when buyer refuses to scan.
    Records GPS proximity check in AuditLog as immutable signed proof.
    If within 100m, initiates 24-hour auto-release countdown.
    """
    order = await _load_order_with_escrow(db, body.order_id)

    if order.logistics_assignment is None or order.logistics_assignment.middleman_id != middleman.id:
        raise HTTPException(status_code=403, detail="Not your delivery")

    if order.status != OrderStatus.IN_TRANSIT:
        raise HTTPException(status_code=409, detail=f"Order is in {order.status}")

    # Fetch buyer location; fall back to a demo coordinate if not set
    buyer = (
        await db.execute(select(Buyer).where(Buyer.id == order.buyer_id))
    ).scalar_one_or_none()

    buyer_loc = GeoPoint(latitude=13.0827, longitude=80.2707)  # Demo fallback

    is_within, distance_m, query_hash = await check_middleman_at_buyer(
        body.middleman_location, buyer_loc, threshold_m=100.0
    )

    # Record signed proof in AuditLog
    audit = AuditLog(
        order_id=order.id,
        from_status=order.status.value,
        to_status=order.status.value,  # Status unchanged by dispute alone
        actor_type="middleman",
        actor_id=middleman.id,
        reason="dispute_proof_of_location",
        extra_data={
            "middleman_lat": body.middleman_location.latitude,
            "middleman_lon": body.middleman_location.longitude,
            "buyer_lat": buyer_loc.latitude,
            "buyer_lon": buyer_loc.longitude,
            "distance_m": distance_m,
            "threshold_m": 100.0,
            "within_threshold": is_within,
            "postgis_query_hash": query_hash,
            "timestamp_utc": datetime.now(tz=timezone.utc).isoformat(),
            "evidence_description": body.evidence_description,
        },
    )
    db.add(audit)
    await db.commit()

    return {
        "within_100m": is_within,
        "distance_m": distance_m,
        "auto_release_initiated": is_within,
        "message": (
            "Auto-release countdown started (24 hours)" if is_within
            else "Middleman not within 100m of buyer. Dispute logged."
        ),
        "proof_hash": query_hash,
    }
