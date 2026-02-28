import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SQLEnum, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class BidStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"


class Bid(Base):
    __tablename__ = "bids"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id"), nullable=False, index=True
    )
    buyer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("buyers.id"), nullable=False)

    offered_price_per_kg: Mapped[float] = mapped_column(Float, nullable=False)
    volume_kg: Mapped[float] = mapped_column(Float, nullable=False)

    status: Mapped[BidStatus] = mapped_column(
        SQLEnum(BidStatus, name="bid_status_enum"),
        default=BidStatus.PENDING,
        nullable=False,
    )

    message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    order: Mapped["Order"] = relationship("Order", back_populates="bids")
    buyer: Mapped["Buyer"] = relationship("Buyer", back_populates="bids")
