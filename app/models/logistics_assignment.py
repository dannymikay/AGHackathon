import enum
import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, Float, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AssignmentStatus(str, enum.Enum):
    OFFERED = "OFFERED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class LogisticsAssignment(Base):
    __tablename__ = "logistics_assignments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id"), unique=True, nullable=False
    )
    middleman_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("middlemen.id"), nullable=False
    )

    pickup_location = mapped_column(Geometry("POINT", srid=4326), nullable=True)
    dropoff_location = mapped_column(Geometry("POINT", srid=4326), nullable=True)
    agreed_fee_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[AssignmentStatus] = mapped_column(
        SQLEnum(AssignmentStatus, name="assignment_status_enum"),
        default=AssignmentStatus.OFFERED,
        nullable=False,
    )

    # GPS heartbeat tracking for IN_TRANSIT resilience
    last_gps_ping_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    gps_alert_sent: Mapped[bool] = mapped_column(Boolean, default=False)

    estimated_distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)

    offered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    order: Mapped["Order"] = relationship("Order", back_populates="logistics_assignment")
    middleman: Mapped["Middleman"] = relationship(
        "Middleman", back_populates="logistics_assignments"
    )
