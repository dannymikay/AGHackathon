from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_farmer
from app.models.farmer import Farmer
from app.schemas.farmer import FarmerPrivate, FarmerPublic, FarmerUpdate

router = APIRouter(prefix="/farmers", tags=["farmers"])


@router.get("/me", response_model=FarmerPrivate)
async def get_my_profile(
    farmer: Annotated[Farmer, Depends(get_current_farmer)],
):
    return farmer


@router.put("/me", response_model=FarmerPrivate)
async def update_my_profile(
    body: FarmerUpdate,
    farmer: Annotated[Farmer, Depends(get_current_farmer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if body.name is not None:
        farmer.name = body.name
    if body.farm_name is not None:
        farmer.farm_name = body.farm_name
    if body.farm_size_hectares is not None:
        farmer.farm_size_hectares = body.farm_size_hectares
    await db.commit()
    await db.refresh(farmer)
    return farmer
