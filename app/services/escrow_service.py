"""
Stripe Connect escrow logic.
Implements the Tripartite Conditional Escrow with Dual-Key release schedule:
  - Pickup  → 20% to Farmer
  - Delivery → 60% to Farmer + 20% to Middleman
  - Cancel   → 100% refund to Buyer
"""
import uuid
from datetime import datetime, timezone

import stripe

from app.config import settings
from app.models.escrow import Escrow, EscrowStatus
from app.models.order import Order, OrderStatus
from app.services import notification_service

stripe.api_key = settings.STRIPE_SECRET_KEY


async def create_payment_intent(order: Order, escrow: Escrow) -> str:
    """
    Creates a Stripe PaymentIntent with capture_method='manual' so the buyer
    authorizes but we don't charge until logistics are confirmed.
    Returns the client_secret to send to the buyer's frontend.
    """
    if settings.APP_ENV == "development" and settings.STRIPE_SECRET_KEY.startswith("sk_test_placeholder"):
        # Demo mode: return a fake client secret
        escrow.stripe_payment_intent_id = f"pi_demo_{uuid.uuid4().hex[:20]}"
        return f"pi_demo_secret_{uuid.uuid4().hex}"

    intent = stripe.PaymentIntent.create(
        amount=escrow.total_amount_cents,
        currency="usd",
        capture_method="manual",
        confirm=False,
        metadata={
            "order_id": str(order.id),
            "escrow_id": str(escrow.id),
        },
    )
    escrow.stripe_payment_intent_id = intent.id
    return intent.client_secret


async def handle_payment_succeeded(
    escrow: Escrow, payment_intent_id: str
) -> None:
    """
    Called by Stripe webhook (payment_intent.succeeded).
    Captures the PaymentIntent and moves escrow to FUNDS_HELD.
    """
    if escrow.status != EscrowStatus.WAITING_FUNDS:
        return

    if not escrow.stripe_payment_intent_id.startswith("pi_demo_"):
        stripe.PaymentIntent.capture(payment_intent_id)

    escrow.status = EscrowStatus.FUNDS_HELD
    escrow.funds_held_at = datetime.now(tz=timezone.utc)


async def release_pickup(order: Order, escrow: Escrow) -> None:
    """
    POST /verify/pickup:
    Releases 20% of total to Farmer immediately (covers labor/loading costs).
    Transitions Escrow: FUNDS_HELD → PICKED_UP.
    """
    if escrow.status != EscrowStatus.FUNDS_HELD:
        raise ValueError(f"Escrow is in {escrow.status}, expected FUNDS_HELD")

    farmer_pickup_cents = int(escrow.total_amount_cents * 0.20)

    if not (escrow.stripe_payment_intent_id or "").startswith("pi_demo_"):
        transfer = stripe.Transfer.create(
            amount=farmer_pickup_cents,
            currency="usd",
            destination=order.farmer.stripe_account_id,
            transfer_group=str(order.id),
            metadata={"type": "pickup_20pct", "order_id": str(order.id)},
        )
        escrow.stripe_transfer_farmer_pickup_id = transfer.id

    escrow.farmer_released_cents += farmer_pickup_cents
    escrow.status = EscrowStatus.PICKED_UP
    escrow.picked_up_at = datetime.now(tz=timezone.utc)

    await notification_service.notify_escrow_update(
        str(order.id),
        {"status": EscrowStatus.PICKED_UP.value, "farmer_released_cents": farmer_pickup_cents},
    )


async def release_delivery(order: Order, escrow: Escrow) -> None:
    """
    POST /verify/delivery:
    Releases remaining balance:
      - 60% to Farmer (final payment)
      - 20% to Middleman
    Transitions Escrow: PICKED_UP → DELIVERED.
    Triggers Order: IN_TRANSIT → SETTLED.
    """
    if escrow.status != EscrowStatus.PICKED_UP:
        raise ValueError(f"Escrow is in {escrow.status}, expected PICKED_UP")

    farmer_final_cents = int(escrow.total_amount_cents * 0.60)
    middleman_cents = int(escrow.total_amount_cents * 0.20)

    is_demo = (escrow.stripe_payment_intent_id or "").startswith("pi_demo_")

    if not is_demo:
        farmer_transfer = stripe.Transfer.create(
            amount=farmer_final_cents,
            currency="usd",
            destination=order.farmer.stripe_account_id,
            transfer_group=str(order.id),
            metadata={"type": "delivery_60pct", "order_id": str(order.id)},
        )
        escrow.stripe_transfer_farmer_final_id = farmer_transfer.id

        if order.logistics_assignment and order.logistics_assignment.middleman.stripe_account_id:
            middleman_transfer = stripe.Transfer.create(
                amount=middleman_cents,
                currency="usd",
                destination=order.logistics_assignment.middleman.stripe_account_id,
                transfer_group=str(order.id),
                metadata={"type": "delivery_middleman_20pct", "order_id": str(order.id)},
            )
            escrow.stripe_transfer_middleman_id = middleman_transfer.id

    escrow.farmer_released_cents += farmer_final_cents
    escrow.middleman_released_cents += middleman_cents
    escrow.status = EscrowStatus.DELIVERED
    escrow.delivered_at = datetime.now(tz=timezone.utc)

    await notification_service.notify_escrow_update(
        str(order.id),
        {
            "status": EscrowStatus.DELIVERED.value,
            "farmer_final_cents": farmer_final_cents,
            "middleman_cents": middleman_cents,
        },
    )


async def cancel_escrow(order: Order, escrow: Escrow) -> None:
    """
    Full refund to Buyer on timeout or cancellation.
    Transitions Escrow: any → CANCELLED.
    """
    if escrow.status == EscrowStatus.CANCELLED:
        return

    is_demo = (escrow.stripe_payment_intent_id or "").startswith("pi_demo_")

    if not is_demo and escrow.stripe_payment_intent_id:
        try:
            intent = stripe.PaymentIntent.retrieve(escrow.stripe_payment_intent_id)
            if intent.status == "requires_capture":
                stripe.PaymentIntent.cancel(escrow.stripe_payment_intent_id)
            elif intent.status in ("succeeded", "amount_capturable_updated"):
                stripe.Refund.create(
                    payment_intent=escrow.stripe_payment_intent_id,
                    reason="requested_by_customer",
                )
        except stripe.error.StripeError:
            pass  # Log in production; don't block the state transition

    escrow.refunded_cents = escrow.total_amount_cents - escrow.farmer_released_cents
    escrow.status = EscrowStatus.CANCELLED
    escrow.cancelled_at = datetime.now(tz=timezone.utc)

    await notification_service.notify_escrow_update(
        str(order.id),
        {
            "status": EscrowStatus.CANCELLED.value,
            "refunded_cents": escrow.refunded_cents,
        },
    )
