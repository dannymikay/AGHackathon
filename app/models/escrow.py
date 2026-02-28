import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EscrowStatus(str, enum.Enum):
    WAITING_FUNDS = "WAITING_FUNDS"
    FUNDS_HELD = "FUNDS_HELD"
    PICKED_UP = "PICKED_UP"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


class Escrow(Base):
    __tablename__ = "escrows"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id"), unique=True, nullable=False
    )

    total_amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    farmer_released_cents: Mapped[int] = mapped_column(Integer, default=0)
    middleman_released_cents: Mapped[int] = mapped_column(Integer, default=0)
    refunded_cents: Mapped[int] = mapped_column(Integer, default=0)

    status: Mapped[EscrowStatus] = mapped_column(
        SQLEnum(EscrowStatus, name="escrow_status_enum"),
        default=EscrowStatus.WAITING_FUNDS,
        nullable=False,
    )

    stripe_payment_intent_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, unique=True
    )
    stripe_transfer_farmer_pickup_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    stripe_transfer_farmer_final_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    stripe_transfer_middleman_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )

    funds_held_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    picked_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    order: Mapped["Order"] = relationship("Order", back_populates="escrow")
