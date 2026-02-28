"""
FastAPI dependency injection helpers: database session + JWT auth per role.
"""
import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.buyer import Buyer
from app.models.farmer import Farmer
from app.models.middleman import Middleman

_bearer = HTTPBearer(auto_error=True)

_CREDS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired token",
    headers={"WWW-Authenticate": "Bearer"},
)

_ROLE_EXCEPTION = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Insufficient role",
)


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise _CREDS_EXCEPTION


def _extract_sub_and_role(token: str) -> tuple[uuid.UUID, str]:
    payload = _decode_token(token)
    sub = payload.get("sub")
    role = payload.get("role")
    if sub is None or role is None:
        raise _CREDS_EXCEPTION
    try:
        return uuid.UUID(sub), role
    except ValueError:
        raise _CREDS_EXCEPTION


async def get_current_farmer(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Farmer:
    user_id, role = _extract_sub_and_role(credentials.credentials)
    if role != "farmer":
        raise _ROLE_EXCEPTION
    farmer = (await db.execute(select(Farmer).where(Farmer.id == user_id))).scalar_one_or_none()
    if farmer is None:
        raise _CREDS_EXCEPTION
    return farmer


async def get_current_buyer(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Buyer:
    user_id, role = _extract_sub_and_role(credentials.credentials)
    if role != "buyer":
        raise _ROLE_EXCEPTION
    buyer = (await db.execute(select(Buyer).where(Buyer.id == user_id))).scalar_one_or_none()
    if buyer is None:
        raise _CREDS_EXCEPTION
    return buyer


async def get_current_middleman(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Middleman:
    user_id, role = _extract_sub_and_role(credentials.credentials)
    if role != "middleman":
        raise _ROLE_EXCEPTION
    middleman = (
        await db.execute(select(Middleman).where(Middleman.id == user_id))
    ).scalar_one_or_none()
    if middleman is None:
        raise _CREDS_EXCEPTION
    return middleman


def decode_ws_token(token: str) -> tuple[uuid.UUID, str]:
    """Used by WebSocket endpoints where headers cannot carry Bearer tokens."""
    return _extract_sub_and_role(token)
