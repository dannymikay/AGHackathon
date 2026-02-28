"""Thin wrappers around ConnectionManager for service-layer broadcasts."""
from app.ws.manager import manager


async def notify_fsm_transition(order_id: str, from_status: str, to_status: str) -> None:
    await manager.broadcast_fsm_event(order_id, from_status, to_status)


async def notify_new_bid(order_id: str, bid_data: dict) -> None:
    await manager.broadcast_new_bid(order_id, bid_data)


async def notify_escrow_update(order_id: str, escrow_data: dict) -> None:
    await manager.broadcast_escrow_update(order_id, escrow_data)


async def notify_gps_heartbeat_lost(order_id: str, middleman_id: str) -> None:
    await manager.broadcast_gps_heartbeat_lost(order_id, middleman_id)
