"""
APScheduler background jobs:

Job 1 (every 5 min): Roll back LOGISTICS_SEARCH orders that exceed 48 hours.
Job 2 (every 15 min): Alert on IN_TRANSIT orders with no GPS ping in 2 hours.
"""
import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal
from app.models.logistics_assignment import LogisticsAssignment
from app.models.order import Order, OrderStatus
from app.services import escrow_service, notification_service, order_fsm

logger = logging.getLogger(__name__)

_LOGISTICS_TIMEOUT_HOURS = 48
_GPS_SILENCE_HOURS = 2

scheduler = AsyncIOScheduler(timezone="UTC")


@scheduler.scheduled_job("interval", minutes=5, id="logistics_timeout_monitor")
async def check_logistics_timeouts() -> None:
    """
    Find orders stuck in LOGISTICS_SEARCH for > 48 hours and roll them back.
    Uses SKIP LOCKED to safely support concurrent instances during restarts.
    """
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=_LOGISTICS_TIMEOUT_HOURS)

    try:
        async with AsyncSessionLocal() as db:
            stmt = (
                select(Order)
                .where(
                    Order.status == OrderStatus.LOGISTICS_SEARCH,
                    Order.logistics_search_started_at <= cutoff,
                )
                .options(selectinload(Order.escrow), selectinload(Order.farmer))
                .with_for_update(skip_locked=True)
            )
            expired_orders = (await db.execute(stmt)).scalars().all()

            for order in expired_orders:
                try:
                    await order_fsm.rollback_to_listed(db, order, reason="48hr_timeout")

                    # Cancel escrow and refund buyer
                    if order.escrow is not None:
                        await escrow_service.cancel_escrow(order, order.escrow)

                    await db.commit()
                    logger.info("Rolled back order %s (48hr logistics timeout)", order.id)
                except Exception as exc:
                    await db.rollback()
                    logger.error(
                        "Failed to roll back order %s: %s", order.id, exc, exc_info=True
                    )
    except Exception as exc:
        logger.error("check_logistics_timeouts job failed (DB unavailable?): %s", exc, exc_info=True)


@scheduler.scheduled_job("interval", minutes=15, id="gps_heartbeat_monitor")
async def check_gps_heartbeats() -> None:
    """
    Find IN_TRANSIT orders where the middleman has not sent a GPS update in 2 hours.
    Sends a WebSocket alert to buyer and farmer — does NOT cancel the order.
    """
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=_GPS_SILENCE_HOURS)

    try:
        async with AsyncSessionLocal() as db:
            stmt = (
                select(LogisticsAssignment)
                .join(Order, Order.id == LogisticsAssignment.order_id)
                .where(
                    Order.status == OrderStatus.IN_TRANSIT,
                    LogisticsAssignment.last_gps_ping_at <= cutoff,
                    LogisticsAssignment.gps_alert_sent == False,  # noqa: E712
                )
            )
            stale_assignments = (await db.execute(stmt)).scalars().all()

            for assignment in stale_assignments:
                try:
                    await notification_service.notify_gps_heartbeat_lost(
                        str(assignment.order_id), str(assignment.middleman_id)
                    )
                    assignment.gps_alert_sent = True
                    await db.commit()
                    logger.warning(
                        "GPS silence alert sent for order %s (middleman %s)",
                        assignment.order_id,
                        assignment.middleman_id,
                    )
                except Exception as exc:
                    await db.rollback()
                    logger.error("GPS heartbeat alert failed: %s", exc, exc_info=True)
    except Exception as exc:
        logger.error("check_gps_heartbeats job failed (DB unavailable?): %s", exc, exc_info=True)


def start_scheduler() -> None:
    scheduler.start()
    logger.info("APScheduler started (logistics timeout + GPS heartbeat monitors)")


def stop_scheduler() -> None:
    scheduler.shutdown(wait=False)
    logger.info("APScheduler stopped")
