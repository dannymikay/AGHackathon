import asyncio
import json
import uuid
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import WebSocket


class ConnectionManager:
    """
    Manages WebSocket connections grouped by order_id.
    Also handles a separate stream for middleman GPS pushes.
    Thread-safe via asyncio.Lock.
    """

    def __init__(self) -> None:
        # { order_id_str: { connection_id_str: WebSocket } }
        self._order_rooms: dict[str, dict[str, WebSocket]] = defaultdict(dict)
        # { middleman_id_str: WebSocket }
        self._middleman_streams: dict[str, WebSocket] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------ #
    #  Order rooms                                                         #
    # ------------------------------------------------------------------ #

    async def connect_to_order(
        self, websocket: WebSocket, order_id: str, connection_id: str
    ) -> None:
        await websocket.accept()
        async with self._lock:
            self._order_rooms[order_id][connection_id] = websocket

    async def disconnect_from_order(self, order_id: str, connection_id: str) -> None:
        async with self._lock:
            self._order_rooms[order_id].pop(connection_id, None)
            if not self._order_rooms.get(order_id):
                self._order_rooms.pop(order_id, None)

    async def broadcast_to_order(self, order_id: str, event: dict) -> None:
        message = json.dumps(event, default=str)
        dead: list[str] = []

        async with self._lock:
            room = dict(self._order_rooms.get(order_id, {}))

        for conn_id, ws in room.items():
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(conn_id)

        if dead:
            async with self._lock:
                for conn_id in dead:
                    self._order_rooms[order_id].pop(conn_id, None)

    # ------------------------------------------------------------------ #
    #  Typed broadcast helpers                                             #
    # ------------------------------------------------------------------ #

    async def broadcast_fsm_event(
        self,
        order_id: str,
        from_status: str,
        to_status: str,
        metadata: dict | None = None,
    ) -> None:
        await self.broadcast_to_order(
            order_id,
            {
                "type": "FSM_TRANSITION",
                "order_id": order_id,
                "from": from_status,
                "to": to_status,
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                "metadata": metadata or {},
            },
        )

    async def broadcast_new_bid(self, order_id: str, bid: dict) -> None:
        await self.broadcast_to_order(
            order_id,
            {"type": "NEW_BID", "order_id": order_id, "bid": bid},
        )

    async def broadcast_escrow_update(self, order_id: str, escrow: dict) -> None:
        await self.broadcast_to_order(
            order_id,
            {"type": "ESCROW_UPDATE", "order_id": order_id, "escrow": escrow},
        )

    async def broadcast_gps_heartbeat_lost(self, order_id: str, middleman_id: str) -> None:
        await self.broadcast_to_order(
            order_id,
            {
                "type": "GPS_HEARTBEAT_LOST",
                "order_id": order_id,
                "middleman_id": middleman_id,
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            },
        )

    async def broadcast_location_update(
        self,
        order_id: str,
        middleman_id: str,
        lat: float,
        lon: float,
    ) -> None:
        await self.broadcast_to_order(
            order_id,
            {
                "type": "LOCATION_UPDATE",
                "order_id": order_id,
                "middleman_id": middleman_id,
                "latitude": lat,
                "longitude": lon,
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            },
        )

    # ------------------------------------------------------------------ #
    #  Middleman GPS streams                                               #
    # ------------------------------------------------------------------ #

    async def register_middleman_stream(
        self, websocket: WebSocket, middleman_id: str
    ) -> None:
        await websocket.accept()
        async with self._lock:
            self._middleman_streams[middleman_id] = websocket

    async def unregister_middleman_stream(self, middleman_id: str) -> None:
        async with self._lock:
            self._middleman_streams.pop(middleman_id, None)


# Singleton used by all routers and services
manager = ConnectionManager()
