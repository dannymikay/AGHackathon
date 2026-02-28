import enum
import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, Float, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TruckType(str, enum.Enum):
    REEFER = "REEFER"          # Refrigerated — required for perishables / cold chain
    VENTILATED = "VENTILATED"  # Airflow only — good for root crops (onions, potatoes)
    INSULATED = "INSULATED"    # Passive insulation — medium-life produce
    DRY_VAN = "DRY_VAN"        # Standard — non-perishables or very short hauls


class Middleman(Base):
    __tablename__ = "middlemen"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    current_location = mapped_column(Geometry("POINT", srid=4326), nullable=True)

    truck_capacity_kg: Mapped[float] = mapped_column(Float, nullable=False)
    truck_plate: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    truck_type: Mapped[TruckType] = mapped_column(
        SQLEnum(TruckType, name="truck_type_enum"),
        nullable=False,
        default=TruckType.DRY_VAN,
    )
    route_radius_km: Mapped[float] = mapped_column(Float, default=100.0)

    on_time_rating: Mapped[float] = mapped_column(Float, default=0.0)
    total_deliveries: Mapped[int] = mapped_column(Integer, default=0)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)

    stripe_account_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    logistics_assignments: Mapped[list["LogisticsAssignment"]] = relationship(
        "LogisticsAssignment", back_populates="middleman"
    )
