import enum
import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Enum as SQLEnum, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class OrderStatus(str, enum.Enum):
    LISTED = "LISTED"
    NEGOTIATING = "NEGOTIATING"
    LOGISTICS_SEARCH = "LOGISTICS_SEARCH"
    IN_TRANSIT = "IN_TRANSIT"
    SETTLED = "SETTLED"
    CANCELLED = "CANCELLED"


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farmer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farmers.id"), nullable=False)
    buyer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("buyers.id"), nullable=True
    )

    crop_type: Mapped[str] = mapped_column(String(100), nullable=False)
    variety: Mapped[str | None] = mapped_column(String(100), nullable=True)
    total_volume_kg: Mapped[float] = mapped_column(Float, nullable=False)
    available_volume_kg: Mapped[float] = mapped_column(Float, nullable=False)
    unit_price_asking: Mapped[float] = mapped_column(Float, nullable=False)
    accepted_price: Mapped[float | None] = mapped_column(Float, nullable=True)

    status: Mapped[OrderStatus] = mapped_column(
        SQLEnum(OrderStatus, name="order_status_enum"),
        default=OrderStatus.LISTED,
        nullable=False,
        index=True,
    )

    # PostGIS LINESTRING from farmer location to buyer location
    route_vector = mapped_column(Geometry("LINESTRING", srid=4326), nullable=True)

    crop_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    quality_grade: Mapped[str | None] = mapped_column(String(10), nullable=True)

    logistics_search_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # SHA-256 hashed QR tokens
    pickup_qr_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    delivery_qr_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    farmer: Mapped["Farmer"] = relationship("Farmer", back_populates="orders")
    buyer: Mapped["Buyer | None"] = relationship("Buyer", back_populates="orders")
    bids: Mapped[list["Bid"]] = relationship("Bid", back_populates="order")
    escrow: Mapped["Escrow | None"] = relationship(
        "Escrow", back_populates="order", uselist=False
    )
    logistics_assignment: Mapped["LogisticsAssignment | None"] = relationship(
        "LogisticsAssignment", back_populates="order", uselist=False
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship("AuditLog", back_populates="order")
