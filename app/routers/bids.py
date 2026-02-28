"""Bids router — submit, list, accept, reject, withdraw bids."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_buyer, get_current_farmer
from app.models.bid import Bid, BidStatus
from app.models.buyer import Buyer
from app.models.farmer import Farmer
from app.models.order import Order
from app.schemas.bid import BidCreate, BidPublic
from app.schemas.escrow import PaymentInitiate
from app.schemas.order import OrderDetail
from app.services import escrow_service, order_fsm
from app.services.order_fsm import (
    BidNotFoundError,
    InsufficientVolumeError,
    InvalidTransitionError,
    OrderNotFoundError,
    UnauthorizedError,
)

router = APIRouter(prefix="/bids", tags=["bids"])


@router.post("", response_model=BidPublic, status_code=201)
async def submit_bid(
    body: BidCreate,
    buyer: Annotated[Buyer, Depends(get_current_buyer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    try:
        bid, _ = await order_fsm.submit_bid(
            db,
            body.order_id,
            buyer.id,
            body.offered_price_per_kg,
            body.volume_kg,
            body.message,
        )
        await db.commit()
        await db.refresh(bid)
        return bid
    except OrderNotFoundError as exc:
        await db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))
    except (InvalidTransitionError, InsufficientVolumeError) as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))


@router.get("/order/{order_id}", response_model=list[BidPublic])
async def list_bids_for_order(
    order_id: uuid.UUID,
    farmer: Annotated[Farmer, Depends(get_current_farmer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    order = (await db.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.farmer_id != farmer.id:
        raise HTTPException(status_code=403, detail="Not your listing")

    bids = (
        await db.execute(select(Bid).where(Bid.order_id == order_id))
    ).scalars().all()
    return bids


@router.post("/{bid_id}/accept", response_model=PaymentInitiate)
async def accept_bid(
    bid_id: uuid.UUID,
    farmer: Annotated[Farmer, Depends(get_current_farmer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Farmer accepts a bid:
    - Atomically decrements available volume.
    - Creates Escrow (WAITING_FUNDS).
    - Creates Stripe PaymentIntent (capture_method='manual').
    - Returns client_secret to forward to the buyer.
    """
    try:
        order, escrow, raw_pickup_token, raw_delivery_token = await order_fsm.accept_bid(
            db, farmer.id, bid_id
        )
        client_secret = await escrow_service.create_payment_intent(order, escrow)
        await db.commit()
        return PaymentInitiate(
            stripe_client_secret=client_secret,
            amount_cents=escrow.total_amount_cents,
        )
    except BidNotFoundError as exc:
        await db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))
    except (InvalidTransitionError, InsufficientVolumeError) as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))
    except UnauthorizedError as exc:
        await db.rollback()
        raise HTTPException(status_code=403, detail=str(exc))


@router.post("/{bid_id}/reject", response_model=BidPublic)
async def reject_bid(
    bid_id: uuid.UUID,
    farmer: Annotated[Farmer, Depends(get_current_farmer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    bid = (await db.execute(select(Bid).where(Bid.id == bid_id))).scalar_one_or_none()
    if bid is None:
        raise HTTPException(status_code=404, detail="Bid not found")

    order = (await db.execute(select(Order).where(Order.id == bid.order_id))).scalar_one_or_none()
    if order is None or order.farmer_id != farmer.id:
        raise HTTPException(status_code=403, detail="Not your listing")

    if bid.status != BidStatus.PENDING:
        raise HTTPException(status_code=409, detail="Can only reject PENDING bids")

    bid.status = BidStatus.REJECTED
    await db.commit()
    await db.refresh(bid)
    return bid


@router.delete("/{bid_id}", status_code=204)
async def withdraw_bid(
    bid_id: uuid.UUID,
    buyer: Annotated[Buyer, Depends(get_current_buyer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    bid = (await db.execute(select(Bid).where(Bid.id == bid_id))).scalar_one_or_none()
    if bid is None:
        raise HTTPException(status_code=404, detail="Bid not found")
    if bid.buyer_id != buyer.id:
        raise HTTPException(status_code=403, detail="Not your bid")
    if bid.status != BidStatus.PENDING:
        raise HTTPException(status_code=409, detail="Can only withdraw PENDING bids")

    bid.status = BidStatus.WITHDRAWN
    await db.commit()
