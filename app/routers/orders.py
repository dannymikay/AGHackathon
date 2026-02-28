"""Orders router — create listings, browse marketplace, upload crop images."""
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_current_farmer
from app.models.farmer import Farmer
from app.models.order import Order, OrderStatus
from app.schemas.order import (
    GradingResult,
    OrderCreate,
    OrderCreateResponse,
    OrderDetail,
    OrderPublic,
    PriceGuidanceResponse,
    ProduceIntelligenceResponse,
)
from app.services import external_api_service
from app.services.grading_service import grade_crop_image_bytes
from app.services.produce_intelligence import (
    auto_suggest_cold_chain,
    compute_days_remaining,
    get_produce_info,
    suggest_price_for_grade,
)

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderCreateResponse, status_code=201)
async def create_listing(
    body: OrderCreate,
    farmer: Annotated[Farmer, Depends(get_current_farmer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Create a new produce listing.

    Returns the saved order plus inline price guidance so the Farmer immediately
    sees whether their asking price is in line with Grade A/B norms for this crop.
    """
    # Auto-upgrade cold chain requirement if the crop inherently needs it
    cold_chain = body.requires_cold_chain or auto_suggest_cold_chain(body.crop_type)

    order = Order(
        farmer_id=farmer.id,
        crop_type=body.crop_type,
        variety=body.variety,
        total_volume_kg=body.total_volume_kg,
        available_volume_kg=body.total_volume_kg,
        unit_price_asking=body.unit_price_asking,
        status=OrderStatus.LISTED,
        requires_cold_chain=cold_chain,
        harvest_date=body.harvest_date,
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)

    # Build inline price guidance from produce intelligence
    guidance = _build_price_guidance(
        crop_type=body.crop_type,
        asking_price=body.unit_price_asking,
        harvest_date=body.harvest_date,
    )

    response = OrderCreateResponse.model_validate(order)
    response.price_guidance = guidance
    return response


@router.get("", response_model=list[OrderPublic])
async def list_orders(
    db: Annotated[AsyncSession, Depends(get_db)],
    status: OrderStatus | None = Query(default=None),
    crop_type: str | None = Query(default=None),
    farmer_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    stmt = select(Order)
    if status:
        stmt = stmt.where(Order.status == status)
    if crop_type:
        stmt = stmt.where(Order.crop_type.ilike(f"%{crop_type}%"))
    if farmer_id:
        stmt = stmt.where(Order.farmer_id == farmer_id)
    stmt = stmt.order_by(Order.created_at.desc()).offset(offset).limit(limit)
    orders = (await db.execute(stmt)).scalars().all()
    return orders


# NOTE: This route must stay ABOVE /{order_id} so FastAPI doesn't try to parse
# "price-guidance" as a UUID.
@router.get("/price-guidance/{crop_type}", response_model=PriceGuidanceResponse)
async def get_price_guidance(
    crop_type: str,
    asking_price: float | None = Query(default=None, gt=0, description="Farmer's intended asking price per kg"),
    harvest_date: datetime | None = Query(default=None, description="ISO-8601 harvest timestamp"),
):
    """
    Return pricing guidance for a given crop type **before** a listing is created.

    The Farmer can call this endpoint while filling in the listing form.
    The response shows:
    - Standard Grade A price (unchanged from asking_price)
    - Standard Grade B discount (based on UC Davis / USDA ERS norms)
    - Urgency-adjusted Grade B price (further reduced as expiry approaches)
    - A plain-English urgency note explaining the discount
    """
    guidance = _build_price_guidance(
        crop_type=crop_type,
        asking_price=asking_price,
        harvest_date=harvest_date,
    )
    return guidance


@router.get("/{order_id}", response_model=OrderDetail)
async def get_order(
    order_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    stmt = (
        select(Order)
        .where(Order.id == order_id)
        .options(
            selectinload(Order.bids),
            selectinload(Order.escrow),
        )
    )
    order = (await db.execute(stmt)).scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.post("/{order_id}/upload-image", response_model=GradingResult)
async def upload_crop_image(
    order_id: uuid.UUID,
    file: UploadFile,
    farmer: Annotated[Farmer, Depends(get_current_farmer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    order = (await db.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.farmer_id != farmer.id:
        raise HTTPException(status_code=403, detail="Not your listing")

    image_bytes = await file.read()
    grade, confidence = grade_crop_image_bytes(image_bytes)

    order.quality_grade = grade
    # In production, upload to S3/GCS and store the URL
    order.crop_image_url = f"/static/crops/{order_id}/{file.filename}"

    await db.commit()

    market_price = await external_api_service.fetch_market_price(order.crop_type, "IN")
    days_remaining = (
        compute_days_remaining(order.harvest_date, order.crop_type)
        if order.harvest_date
        else None
    )
    # Now passes days_remaining so urgency is factored into the suggested price
    suggested_grade_b_price = suggest_price_for_grade(
        order.crop_type, grade, order.unit_price_asking, days_remaining
    )

    return GradingResult(
        quality_grade=grade,
        confidence_score=confidence,
        image_url=order.crop_image_url,
        market_price_hint=market_price,
        days_remaining=days_remaining,
        suggested_grade_b_price=suggested_grade_b_price,
    )


@router.get("/{order_id}/intelligence", response_model=ProduceIntelligenceResponse)
async def get_order_intelligence(
    order_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Return shelf-life intelligence and Grade B pricing suggestion for a listing."""
    order = (await db.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    info = get_produce_info(order.crop_type)
    days_remaining = (
        compute_days_remaining(order.harvest_date, order.crop_type)
        if order.harvest_date
        else None
    )
    # Urgency-adjusted price: the closer to expiry, the lower the suggested price
    suggested_price = suggest_price_for_grade(
        order.crop_type, order.quality_grade or "A", order.unit_price_asking, days_remaining
    )

    return ProduceIntelligenceResponse(
        crop_type=order.crop_type,
        shelf_life_days=info["shelf_days"] if info else None,
        days_remaining=days_remaining,
        requires_cold_chain=order.requires_cold_chain,
        suggested_price=suggested_price,
        grade=order.quality_grade,
    )


@router.delete("/{order_id}", status_code=204)
async def delete_listing(
    order_id: uuid.UUID,
    farmer: Annotated[Farmer, Depends(get_current_farmer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    order = (await db.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.farmer_id != farmer.id:
        raise HTTPException(status_code=403, detail="Not your listing")
    if order.status != OrderStatus.LISTED:
        raise HTTPException(
            status_code=409, detail="Cannot delete a listing that is not in LISTED state"
        )
    await db.delete(order)
    await db.commit()


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _build_price_guidance(
    crop_type: str,
    asking_price: float | None,
    harvest_date: datetime | None,
) -> PriceGuidanceResponse:
    """
    Build a PriceGuidanceResponse from produce intelligence data.

    Called both from create_listing (inline guidance) and the standalone
    GET /orders/price-guidance/{crop_type} endpoint.
    """
    info = get_produce_info(crop_type)
    days_remaining = (
        compute_days_remaining(harvest_date, crop_type) if harvest_date else None
    )

    grade_a_price = asking_price
    grade_b_standard = (
        suggest_price_for_grade(crop_type, "B", asking_price) if asking_price else None
    )
    grade_b_urgency = (
        suggest_price_for_grade(crop_type, "B", asking_price, days_remaining)
        if asking_price
        else None
    )

    # Plain-English note for the Farmer
    urgency_note: str | None = None
    if info and days_remaining is not None:
        shelf = info["shelf_days"]
        pct = int(100 * days_remaining / shelf) if shelf else 100
        if days_remaining == 0:
            urgency_note = (
                "Produce has reached its shelf limit — buyers will expect maximum discount."
            )
        elif pct <= 20:
            urgency_note = (
                f"Only {days_remaining} day(s) left ({pct}% of shelf life remaining). "
                "Urgent liquidation pricing has been applied."
            )
        elif pct <= 50:
            urgency_note = (
                f"{days_remaining} of {shelf} days remaining. "
                "Moderate urgency discount applied on top of Grade B rate."
            )
        else:
            urgency_note = (
                f"{days_remaining} of {shelf} days remaining — produce is still relatively fresh. "
                "Standard Grade B pricing applies."
            )
    elif info and asking_price:
        urgency_note = (
            "No harvest date set — standard Grade B pricing shown. "
            "Add a harvest date to see urgency-adjusted price."
        )

    return PriceGuidanceResponse(
        crop_type=crop_type,
        shelf_life_days=info["shelf_days"] if info else None,
        requires_cold_chain=info["cold_chain"] if info else False,
        grade_a_suggested_price=grade_a_price,
        grade_b_standard_price=grade_b_standard,
        grade_b_urgency_price=grade_b_urgency,
        days_remaining=days_remaining,
        urgency_note=urgency_note,
    )
