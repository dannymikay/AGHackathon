from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_buyer
from app.models.buyer import Buyer
from app.schemas.buyer import BuyerPrivate, BuyerUpdate

router = APIRouter(prefix="/buyers", tags=["buyers"])


@router.get("/me", response_model=BuyerPrivate)
async def get_my_profile(
    buyer: Annotated[Buyer, Depends(get_current_buyer)],
):
    return buyer


@router.put("/me", response_model=BuyerPrivate)
async def update_my_profile(
    body: BuyerUpdate,
    buyer: Annotated[Buyer, Depends(get_current_buyer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if body.name is not None:
        buyer.name = body.name
    if body.delivery_address is not None:
        buyer.delivery_address = body.delivery_address
    await db.commit()
    await db.refresh(buyer)
    return buyer
