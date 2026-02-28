"""
WebSocket router.
- /ws/orders/{order_id}        — subscribe to FSM events, bids, escrow updates
- /ws/middlemen/me/location    — middleman GPS push stream
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select, text

from app.database import AsyncSessionLocal
from app.dependencies import decode_ws_token
from app.models.logistics_assignment import LogisticsAssignment
from app.models.order import OrderStatus
from app.ws.manager import manager

router = APIRouter(tags=["websockets"])

_GPS_DB_THROTTLE = 10  # Write GPS to DB every N updates


@router.websocket("/ws/orders/{order_id}")
async def order_websocket(
    websocket: WebSocket,
    order_id: uuid.UUID,
    token: str = Query(...),
):
    """
    Any authenticated user (farmer/buyer/middleman) can subscribe to an order room.
    Receives: FSM_TRANSITION, NEW_BID, ESCROW_UPDATE, GPS_HEARTBEAT_LOST, LOCATION_UPDATE.
    Supports client PING → PONG keepalive.
    """
    try:
        user_id, role = decode_ws_token(token)
    except Exception:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    conn_id = str(uuid.uuid4())
    await manager.connect_to_order(websocket, str(order_id), conn_id)
    try:
        await websocket.send_json(
            {
                "type": "CONNECTED",
                "order_id": str(order_id),
                "role": role,
                "user_id": str(user_id),
            }
        )
        while True:
            raw = await websocket.receive_text()
            if raw == '{"type":"PING"}':
                await websocket.send_text('{"type":"PONG"}')
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect_from_order(str(order_id), conn_id)


@router.websocket("/ws/middlemen/me/location")
async def middleman_location_stream(
    websocket: WebSocket,
    token: str = Query(...),
    order_id: uuid.UUID = Query(...),
):
    """
    Middleman device pushes GPS coordinates continuously.
    Server re-broadcasts to all parties subscribed to the order room.
    Persists to DB every GPS_DB_THROTTLE messages.
    Also updates last_gps_ping_at on the LogisticsAssignment.
    """
    try:
        user_id, role = decode_ws_token(token)
    except Exception:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    if role != "middleman":
        await websocket.close(code=4003, reason="Forbidden: middleman role required")
        return

    await manager.register_middleman_stream(websocket, str(user_id))
    update_count = 0

    try:
        await websocket.send_json({"type": "LOCATION_STREAM_READY"})
        while True:
            data = await websocket.receive_json()
            lat = float(data["latitude"])
            lon = float(data["longitude"])

            await manager.broadcast_location_update(str(order_id), str(user_id), lat, lon)

            update_count += 1
            if update_count % _GPS_DB_THROTTLE == 0:
                async with AsyncSessionLocal() as db:
                    async with db.begin():
                        # Update middleman current location
                        await db.execute(
                            text(
                                "UPDATE middlemen "
                                "SET current_location = ST_SetSRID(ST_MakePoint(:lon, :lat), 4326) "
                                "WHERE id = :id"
                            ),
                            {"lon": lon, "lat": lat, "id": str(user_id)},
                        )
                        # Update heartbeat on active assignment
                        await db.execute(
                            text(
                                "UPDATE logistics_assignments "
                                "SET last_gps_ping_at = :now, gps_alert_sent = FALSE "
                                "WHERE order_id = :order_id AND middleman_id = :mid_id"
                            ),
                            {
                                "now": datetime.now(tz=timezone.utc),
                                "order_id": str(order_id),
                                "mid_id": str(user_id),
                            },
                        )
    except WebSocketDisconnect:
        pass
    finally:
        await manager.unregister_middleman_stream(str(user_id))
