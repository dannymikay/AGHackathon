"""
Stripe webhook receiver.
Verifies Stripe signature and dispatches to escrow service.
"""
import logging

import stripe
from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.escrow import Escrow
from app.models.order import Order
from app.services import escrow_service

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature"),
):
    payload = await request.body()

    # In development with placeholder key, skip signature verification
    if settings.STRIPE_WEBHOOK_SECRET == "whsec_placeholder":
        try:
            event = stripe.Event.construct_from(
                stripe.util.convert_to_stripe_object(
                    stripe.util.json.loads(payload)
                ),
                stripe.api_key,
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    else:
        try:
            event = stripe.Webhook.construct_event(
                payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET
            )
        except stripe.error.SignatureVerificationError:
            raise HTTPException(status_code=400, detail="Invalid Stripe signature")

    event_type = event["type"]
    logger.info("Stripe webhook received: %s", event_type)

    if event_type == "payment_intent.succeeded":
        await _handle_payment_intent_succeeded(event["data"]["object"])

    return {"received": True}


async def _handle_payment_intent_succeeded(payment_intent: dict) -> None:
    pi_id = payment_intent.get("id")
    if not pi_id:
        return

    async with AsyncSessionLocal() as db:
        async with db.begin():
            escrow = (
                await db.execute(
                    select(Escrow).where(Escrow.stripe_payment_intent_id == pi_id)
                )
            ).scalar_one_or_none()

            if escrow is None:
                logger.warning("No escrow found for payment_intent %s", pi_id)
                return

            order = (
                await db.execute(select(Order).where(Order.id == escrow.order_id))
            ).scalar_one_or_none()

            if order is None:
                return

            await escrow_service.handle_payment_succeeded(escrow, pi_id)
            logger.info("Escrow %s moved to FUNDS_HELD (order %s)", escrow.id, order.id)
