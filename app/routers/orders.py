"""Orders router — create listings, browse marketplace, upload crop images."""
import io
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_current_farmer
from app.models.farmer import Farmer
from app.models.order import Order, OrderStatus
from app.schemas.order import GradingResult, OrderCreate, OrderDetail, OrderPublic
from app.services import external_api_service
from app.services.grading_service import grade_crop_image_bytes

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderPublic, status_code=201)
async def create_listing(
    body: OrderCreate,
    farmer: Annotated[Farmer, Depends(get_current_farmer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    order = Order(
        farmer_id=farmer.id,
        crop_type=body.crop_type,
        variety=body.variety,
        total_volume_kg=body.total_volume_kg,
        available_volume_kg=body.total_volume_kg,
        unit_price_asking=body.unit_price_asking,
        status=OrderStatus.LISTED,
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    return order


@router.get("", response_model=list[OrderPublic])
async def list_orders(
    db: Annotated[AsyncSession, Depends(get_db)],
    status: OrderStatus | None = Query(default=None),
    crop_type: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    stmt = select(Order)
    if status:
        stmt = stmt.where(Order.status == status)
    if crop_type:
        stmt = stmt.where(Order.crop_type.ilike(f"%{crop_type}%"))
    stmt = stmt.order_by(Order.created_at.desc()).offset(offset).limit(limit)
    orders = (await db.execute(stmt)).scalars().all()
    return orders


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

    return GradingResult(
        quality_grade=grade,
        confidence_score=confidence,
        image_url=order.crop_image_url,
        market_price_hint=market_price,
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
