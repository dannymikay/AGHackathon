"""
Auth router — register and login for Farmer, Buyer, Middleman.
Issues JWT tokens with role claims.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.buyer import Buyer
from app.models.farmer import Farmer
from app.models.middleman import Middleman
from app.schemas.buyer import BuyerCreate, BuyerLogin, BuyerPrivate
from app.schemas.common import TokenResponse
from app.schemas.farmer import FarmerCreate, FarmerLogin, FarmerPrivate
from app.schemas.middleman import MiddlemanCreate, MiddlemanLogin, MiddlemanPrivate

router = APIRouter(prefix="/auth", tags=["auth"])
_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _hash(password: str) -> str:
    return _pwd.hash(password)


def _verify(plain: str, hashed: str) -> bool:
    return _pwd.verify(plain, hashed)


def _make_token(user_id: uuid.UUID, role: str) -> str:
    expire = datetime.now(tz=timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": str(user_id), "role": role, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


# --------------------------------------------------------------------------- #
#  Farmer                                                                      #
# --------------------------------------------------------------------------- #


@router.post("/farmer/register", response_model=FarmerPrivate, status_code=201)
async def register_farmer(
    body: FarmerCreate, db: Annotated[AsyncSession, Depends(get_db)]
):
    existing = (
        await db.execute(select(Farmer).where(Farmer.email == body.email))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    farmer = Farmer(
        name=body.name,
        phone=body.phone,
        email=body.email,
        hashed_password=_hash(body.password),
        farm_name=body.farm_name,
        farm_size_hectares=body.farm_size_hectares,
    )
    db.add(farmer)
    await db.commit()
    await db.refresh(farmer)
    return farmer


@router.post("/farmer/login", response_model=TokenResponse)
async def login_farmer(
    body: FarmerLogin, db: Annotated[AsyncSession, Depends(get_db)]
):
    farmer = (
        await db.execute(select(Farmer).where(Farmer.email == body.email))
    ).scalar_one_or_none()
    if farmer is None or not _verify(body.password, farmer.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return TokenResponse(access_token=_make_token(farmer.id, "farmer"), role="farmer")


# --------------------------------------------------------------------------- #
#  Buyer                                                                       #
# --------------------------------------------------------------------------- #


@router.post("/buyer/register", response_model=BuyerPrivate, status_code=201)
async def register_buyer(
    body: BuyerCreate, db: Annotated[AsyncSession, Depends(get_db)]
):
    existing = (
        await db.execute(select(Buyer).where(Buyer.email == body.email))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    buyer = Buyer(
        name=body.name,
        phone=body.phone,
        email=body.email,
        hashed_password=_hash(body.password),
        delivery_address=body.delivery_address,
    )
    db.add(buyer)
    await db.commit()
    await db.refresh(buyer)
    return buyer


@router.post("/buyer/login", response_model=TokenResponse)
async def login_buyer(
    body: BuyerLogin, db: Annotated[AsyncSession, Depends(get_db)]
):
    buyer = (
        await db.execute(select(Buyer).where(Buyer.email == body.email))
    ).scalar_one_or_none()
    if buyer is None or not _verify(body.password, buyer.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return TokenResponse(access_token=_make_token(buyer.id, "buyer"), role="buyer")


# --------------------------------------------------------------------------- #
#  Middleman                                                                   #
# --------------------------------------------------------------------------- #


@router.post("/middleman/register", response_model=MiddlemanPrivate, status_code=201)
async def register_middleman(
    body: MiddlemanCreate, db: Annotated[AsyncSession, Depends(get_db)]
):
    existing = (
        await db.execute(select(Middleman).where(Middleman.email == body.email))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    middleman = Middleman(
        name=body.name,
        phone=body.phone,
        email=body.email,
        hashed_password=_hash(body.password),
        truck_capacity_kg=body.truck_capacity_kg,
        truck_plate=body.truck_plate,
        route_radius_km=body.route_radius_km,
    )
    db.add(middleman)
    await db.commit()
    await db.refresh(middleman)
    return middleman


@router.post("/middleman/login", response_model=TokenResponse)
async def login_middleman(
    body: MiddlemanLogin, db: Annotated[AsyncSession, Depends(get_db)]
):
    middleman = (
        await db.execute(select(Middleman).where(Middleman.email == body.email))
    ).scalar_one_or_none()
    if middleman is None or not _verify(body.password, middleman.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return TokenResponse(
        access_token=_make_token(middleman.id, "middleman"), role="middleman"
    )
