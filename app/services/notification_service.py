"""
Notification service: WebSocket broadcasts + Firebase Cloud Messaging push.

WebSocket (via ConnectionManager) is the primary real-time channel for all
connected clients. Firebase FCM adds push notifications for mobile/web
clients that may not have an active WebSocket connection.

FCM setup:
  1. Download your Firebase service account JSON from:
     Firebase Console → Project Settings → Service Accounts → Generate new key
  2. Save it as firebase-credentials.json in the project root directory
  3. Set FCM_PROJECT_NUMBER in .env to match your Firebase project number
"""
import logging
from pathlib import Path

from app.config import settings
from app.ws.manager import manager

logger = logging.getLogger(__name__)

_FCM_CREDENTIALS_PATH = Path(__file__).parent.parent.parent / "firebase-credentials.json"
_firebase_app = None
_firebase_init_attempted = False


def _get_firebase_app():
    """
    Lazily initialise Firebase Admin SDK on first use.
    Returns the app instance or None if credentials are missing or invalid.
    Initialization is attempted only once to avoid repeated failure logs.
    """
    global _firebase_app, _firebase_init_attempted
    if _firebase_init_attempted:
        return _firebase_app

    _firebase_init_attempted = True

    if not settings.FCM_PROJECT_NUMBER:
        return None

    if not _FCM_CREDENTIALS_PATH.exists():
        logger.info(
            "firebase-credentials.json not found at %s. "
            "FCM push notifications disabled — WebSocket only.",
            _FCM_CREDENTIALS_PATH,
        )
        return None

    try:
        import firebase_admin  # type: ignore[import-untyped]
        from firebase_admin import credentials  # type: ignore[import-untyped]

        cred = credentials.Certificate(str(_FCM_CREDENTIALS_PATH))
        _firebase_app = firebase_admin.initialize_app(cred)
        logger.info(
            "Firebase Admin SDK initialised (project: %s)", settings.FCM_PROJECT_NUMBER
        )
    except Exception as exc:
        logger.warning("Firebase Admin SDK init failed (%s)", type(exc).__name__)
        _firebase_app = None

    return _firebase_app


async def _send_fcm_push(
    title: str,
    body: str,
    data: dict[str, str],
    topic: str,
) -> None:
    """
    Send a Firebase push notification to a topic channel.
    Silently skips if Firebase is not configured or the send fails.

    All parties subscribe to 'order_{order_id}' on their client to receive
    push updates for a given order when they are not connected via WebSocket.
    """
    if _get_firebase_app() is None:
        return

    try:
        from firebase_admin import messaging  # type: ignore[import-untyped]

        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data=data,  # caller is responsible for ensuring all values are str
            topic=topic,
        )
        response = messaging.send(message)
        logger.debug("FCM sent to topic '%s': %s", topic, response)
    except Exception as exc:
        logger.warning("FCM push failed for topic '%s' (%s)", topic, type(exc).__name__)


# ── Public notification functions ──────────────────────────────────────────


async def notify_fsm_transition(order_id: str, from_status: str, to_status: str) -> None:
    """Broadcast FSM state change via WebSocket and FCM push."""
    await manager.broadcast_fsm_event(order_id, from_status, to_status)
    await _send_fcm_push(
        title="Order Status Updated",
        body=f"Order moved from {from_status} \u2192 {to_status}.",
        data={"order_id": order_id, "from_status": from_status, "to_status": to_status},
        topic=f"order_{order_id}",
    )


async def notify_new_bid(order_id: str, bid_data: dict) -> None:
    """Broadcast new bid via WebSocket and FCM push to the Farmer."""
    await manager.broadcast_new_bid(order_id, bid_data)
    # Build the FCM data payload explicitly — do not spread bid_data to avoid
    # accidentally shadowing the order_id key or including non-string values.
    fcm_data: dict[str, str] = {
        "order_id": order_id,
        "bid_id": str(bid_data.get("id", "")),
        "offered_price_per_kg": str(bid_data.get("offered_price_per_kg", "")),
        "volume_kg": str(bid_data.get("volume_kg", "")),
        "buyer_id": str(bid_data.get("buyer_id", "")),
    }
    await _send_fcm_push(
        title="New Bid Received",
        body="A buyer has placed a bid on your listing.",
        data=fcm_data,
        topic=f"order_{order_id}",
    )


async def notify_escrow_update(order_id: str, escrow_data: dict) -> None:
    """Broadcast escrow status change via WebSocket and FCM push."""
    await manager.broadcast_escrow_update(order_id, escrow_data)

    # status is required in escrow_data; fall back to generic message if missing
    status = escrow_data.get("status", "")
    _STATUS_MESSAGES: dict[str, tuple[str, str]] = {
        "FUNDS_HELD":  ("Payment Secured",    "Buyer's funds are now held in escrow."),
        "PICKED_UP":   ("Pickup Confirmed",    "Produce picked up \u2014 20% released to Farmer."),
        "DELIVERED":   ("Delivery Complete",   "Delivery confirmed. Final payment released."),
        "CANCELLED":   ("Order Cancelled",     "Order cancelled. Buyer funds refunded."),
    }
    title, body = _STATUS_MESSAGES.get(
        status, ("Payment Update", f"Escrow status: {status}.")
    )
    # Build FCM data payload explicitly with only known string fields
    fcm_data: dict[str, str] = {"order_id": order_id, "status": status}
    if "farmer_released_cents" in escrow_data:
        fcm_data["farmer_released_cents"] = str(escrow_data["farmer_released_cents"])
    if "farmer_final_cents" in escrow_data:
        fcm_data["farmer_final_cents"] = str(escrow_data["farmer_final_cents"])
    if "middleman_cents" in escrow_data:
        fcm_data["middleman_cents"] = str(escrow_data["middleman_cents"])
    if "refunded_cents" in escrow_data:
        fcm_data["refunded_cents"] = str(escrow_data["refunded_cents"])

    await _send_fcm_push(
        title=title,
        body=body,
        data=fcm_data,
        topic=f"order_{order_id}",
    )


async def notify_gps_heartbeat_lost(order_id: str, middleman_id: str) -> None:
    """Broadcast GPS heartbeat loss via WebSocket and FCM push."""
    await manager.broadcast_gps_heartbeat_lost(order_id, middleman_id)
    await _send_fcm_push(
        title="GPS Signal Lost",
        body="Trucker GPS signal has been lost. Please check order status.",
        data={"order_id": order_id, "middleman_id": middleman_id},
        topic=f"order_{order_id}",
    )
