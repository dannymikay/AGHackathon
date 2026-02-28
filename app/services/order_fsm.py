"""
Finite State Machine for Order lifecycle.
All transitions are atomic via SELECT FOR UPDATE.
"""
import hashlib
import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.bid import Bid, BidStatus
from app.models.escrow import Escrow, EscrowStatus
from app.models.order import Order, OrderStatus
from app.services import notification_service

# --------------------------------------------------------------------------- #
#  Valid state transitions                                                     #
# --------------------------------------------------------------------------- #

VALID_TRANSITIONS: dict[OrderStatus, list[OrderStatus]] = {
    OrderStatus.LISTED: [OrderStatus.NEGOTIATING],
    OrderStatus.NEGOTIATING: [OrderStatus.LOGISTICS_SEARCH, OrderStatus.LISTED],
    OrderStatus.LOGISTICS_SEARCH: [OrderStatus.IN_TRANSIT, OrderStatus.LISTED],
    OrderStatus.IN_TRANSIT: [OrderStatus.SETTLED],
    OrderStatus.SETTLED: [],
    OrderStatus.CANCELLED: [],
}


class OrderNotFoundError(Exception):
    pass


class InvalidTransitionError(Exception):
    def __init__(self, from_state: OrderStatus, to_state: OrderStatus):
        super().__init__(f"Cannot transition from {from_state} to {to_state}")


class InsufficientVolumeError(Exception):
    pass


class BidNotFoundError(Exception):
    pass


class UnauthorizedError(Exception):
    pass


# --------------------------------------------------------------------------- #
#  Core transition function                                                    #
# --------------------------------------------------------------------------- #


async def transition_order(
    db: AsyncSession,
    order_id: uuid.UUID,
    to_status: OrderStatus,
    actor_type: str,
    actor_id: uuid.UUID | None = None,
    reason: str | None = None,
    metadata: dict | None = None,
) -> Order:
    """
    Atomically transition an order to a new FSM state.
    Acquires a row-level lock (SELECT FOR UPDATE).
    Validates the transition is legal.
    Writes an AuditLog entry.
    Broadcasts a WebSocket FSM event after committing.
    """
    stmt = select(Order).where(Order.id == order_id).with_for_update()
    result = await db.execute(stmt)
    order = result.scalar_one_or_none()

    if order is None:
        raise OrderNotFoundError(f"Order {order_id} not found")

    if to_status not in VALID_TRANSITIONS[order.status]:
        raise InvalidTransitionError(order.status, to_status)

    from_status = order.status
    order.status = to_status

    if to_status == OrderStatus.LOGISTICS_SEARCH:
        order.logistics_search_started_at = datetime.now(tz=timezone.utc)

    if to_status == OrderStatus.SETTLED:
        order.settled_at = datetime.now(tz=timezone.utc)

    audit = AuditLog(
        order_id=order.id,
        from_status=from_status.value,
        to_status=to_status.value,
        actor_type=actor_type,
        actor_id=actor_id,
        reason=reason,
        extra_data=metadata,
    )
    db.add(audit)
    await db.flush()

    await notification_service.notify_fsm_transition(
        str(order_id), from_status.value, to_status.value
    )
    return order


# --------------------------------------------------------------------------- #
#  Submit bid                                                                  #
# --------------------------------------------------------------------------- #


async def submit_bid(
    db: AsyncSession,
    order_id: uuid.UUID,
    buyer_id: uuid.UUID,
    offered_price_per_kg: float,
    volume_kg: float,
    message: str | None = None,
) -> tuple[Bid, Order]:
    """
    Creates a Bid. If order is LISTED, transitions to NEGOTIATING.
    Validates volume does not exceed available_volume_kg.
    """
    stmt = select(Order).where(Order.id == order_id).with_for_update()
    result = await db.execute(stmt)
    order = result.scalar_one_or_none()

    if order is None:
        raise OrderNotFoundError(f"Order {order_id} not found")

    if order.status not in (OrderStatus.LISTED, OrderStatus.NEGOTIATING):
        raise InvalidTransitionError(order.status, OrderStatus.NEGOTIATING)

    if volume_kg > order.available_volume_kg:
        raise InsufficientVolumeError(
            f"Requested {volume_kg} kg exceeds available {order.available_volume_kg} kg"
        )

    bid = Bid(
        order_id=order_id,
        buyer_id=buyer_id,
        offered_price_per_kg=offered_price_per_kg,
        volume_kg=volume_kg,
        status=BidStatus.PENDING,
        message=message,
    )
    db.add(bid)

    if order.status == OrderStatus.LISTED:
        from_status = order.status
        order.status = OrderStatus.NEGOTIATING
        audit = AuditLog(
            order_id=order.id,
            from_status=from_status.value,
            to_status=OrderStatus.NEGOTIATING.value,
            actor_type="buyer",
            actor_id=buyer_id,
            reason="first_bid_submitted",
        )
        db.add(audit)

    await db.flush()

    if order.status == OrderStatus.NEGOTIATING:
        await notification_service.notify_new_bid(
            str(order_id),
            {
                "id": str(bid.id),
                "offered_price_per_kg": offered_price_per_kg,
                "volume_kg": volume_kg,
            },
        )

    return bid, order


# --------------------------------------------------------------------------- #
#  Accept bid                                                                  #
# --------------------------------------------------------------------------- #


async def accept_bid(
    db: AsyncSession,
    farmer_id: uuid.UUID,
    bid_id: uuid.UUID,
) -> tuple[Order, Escrow, str, str]:
    """
    Farmer accepts a specific bid:
    1. Validates farmer owns the order.
    2. Atomically decrements available_volume_kg.
    3. Rejects all other PENDING bids on this order.
    4. Creates Escrow record (WAITING_FUNDS).
    5. Generates QR tokens (raw tokens returned once; hashes stored in DB).
    6. Transitions NEGOTIATING → LOGISTICS_SEARCH.
    Returns (order, escrow, raw_pickup_token, raw_delivery_token).
    """
    stmt = select(Bid).where(Bid.id == bid_id).with_for_update()
    bid = (await db.execute(stmt)).scalar_one_or_none()

    if bid is None:
        raise BidNotFoundError(f"Bid {bid_id} not found")

    order_stmt = select(Order).where(Order.id == bid.order_id).with_for_update()
    order = (await db.execute(order_stmt)).scalar_one_or_none()

    if order is None:
        raise OrderNotFoundError(f"Order {bid.order_id} not found")

    if order.farmer_id != farmer_id:
        raise UnauthorizedError("Only the listing farmer can accept bids")

    if order.status != OrderStatus.NEGOTIATING:
        raise InvalidTransitionError(order.status, OrderStatus.LOGISTICS_SEARCH)

    if bid.status != BidStatus.PENDING:
        raise InvalidTransitionError(bid.status, BidStatus.ACCEPTED)  # type: ignore[arg-type]

    # Atomic volume decrement (guard against over-acceptance)
    if bid.volume_kg > order.available_volume_kg:
        raise InsufficientVolumeError(
            f"Bid volume {bid.volume_kg} kg exceeds available {order.available_volume_kg} kg"
        )

    order.available_volume_kg -= bid.volume_kg
    order.buyer_id = bid.buyer_id
    order.accepted_price = bid.offered_price_per_kg
    bid.status = BidStatus.ACCEPTED

    # Reject all other pending bids
    reject_stmt = (
        select(Bid)
        .where(
            Bid.order_id == order.id,
            Bid.id != bid_id,
            Bid.status == BidStatus.PENDING,
        )
    )
    other_bids = (await db.execute(reject_stmt)).scalars().all()
    for other_bid in other_bids:
        other_bid.status = BidStatus.REJECTED

    # Generate QR tokens
    raw_pickup_token = secrets.token_hex(32)
    raw_delivery_token = secrets.token_hex(32)
    order.pickup_qr_hash = hashlib.sha256(raw_pickup_token.encode()).hexdigest()
    order.delivery_qr_hash = hashlib.sha256(raw_delivery_token.encode()).hexdigest()

    # Create escrow record
    total_cents = int(bid.volume_kg * bid.offered_price_per_kg * 100)
    escrow = Escrow(
        order_id=order.id,
        total_amount_cents=total_cents,
        status=EscrowStatus.WAITING_FUNDS,
    )
    db.add(escrow)

    # Transition FSM
    from_status = order.status
    order.status = OrderStatus.LOGISTICS_SEARCH
    order.logistics_search_started_at = datetime.now(tz=timezone.utc)

    audit = AuditLog(
        order_id=order.id,
        from_status=from_status.value,
        to_status=OrderStatus.LOGISTICS_SEARCH.value,
        actor_type="farmer",
        actor_id=farmer_id,
        reason="bid_accepted",
        extra_data={"bid_id": str(bid_id), "volume_kg": bid.volume_kg},
    )
    db.add(audit)
    await db.flush()

    await notification_service.notify_fsm_transition(
        str(order.id), from_status.value, OrderStatus.LOGISTICS_SEARCH.value
    )
    return order, escrow, raw_pickup_token, raw_delivery_token


# --------------------------------------------------------------------------- #
#  Rollback to LISTED (timeout / no middleman)                                #
# --------------------------------------------------------------------------- #


async def rollback_to_listed(
    db: AsyncSession,
    order: Order,
    reason: str = "48hr_timeout",
) -> Order:
    """
    Returns order to LISTED, restoring available_volume_kg.
    Called by the timeout monitor or when middleman rejects.
    """
    if order.status != OrderStatus.LOGISTICS_SEARCH:
        return order

    # Restore the accepted bid's volume
    if order.buyer_id is not None:
        bid_stmt = select(Bid).where(
            Bid.order_id == order.id,
            Bid.status == BidStatus.ACCEPTED,
        )
        accepted_bid = (await db.execute(bid_stmt)).scalar_one_or_none()
        if accepted_bid:
            order.available_volume_kg += accepted_bid.volume_kg
            accepted_bid.status = BidStatus.REJECTED

    order.status = OrderStatus.LISTED
    order.buyer_id = None
    order.accepted_price = None
    order.pickup_qr_hash = None
    order.delivery_qr_hash = None
    order.logistics_search_started_at = None

    audit = AuditLog(
        order_id=order.id,
        from_status=OrderStatus.LOGISTICS_SEARCH.value,
        to_status=OrderStatus.LISTED.value,
        actor_type="system",
        reason=reason,
    )
    db.add(audit)
    await db.flush()

    await notification_service.notify_fsm_transition(
        str(order.id), OrderStatus.LOGISTICS_SEARCH.value, OrderStatus.LISTED.value
    )
    return order
