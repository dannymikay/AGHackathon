"""
Seeds demo data on startup if the database is empty.
Inserts demo farmers, buyers, middlemen, and sample listings.
"""
import json
import logging
import uuid
from pathlib import Path

from passlib.context import CryptContext
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.buyer import Buyer
from app.models.farmer import Farmer
from app.models.middleman import Middleman
from app.models.order import Order, OrderStatus

logger = logging.getLogger(__name__)
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_GEOJSON_DIR = Path(__file__).parent / "geojson"
_DEMO_PASSWORD = _pwd_context.hash("demo1234")


async def seed_if_empty() -> None:
    """Called from app lifespan. Inserts demo data only if tables are empty."""
    async with AsyncSessionLocal() as db:
        try:
            count = (await db.execute(select(Farmer))).scalars().first()
            if count is not None:
                return  # Already seeded
            await _seed_all(db)
            await db.commit()
            logger.info("Demo data seeded successfully")
        except Exception as exc:
            await db.rollback()
            logger.warning("Demo seed skipped (DB may not be ready yet): %s", exc)


async def _seed_all(db: AsyncSession) -> None:
    farms_geojson = json.loads((_GEOJSON_DIR / "demo_farms.geojson").read_text())
    trucks_geojson = json.loads((_GEOJSON_DIR / "demo_trucks.geojson").read_text())
    buyers_geojson = json.loads((_GEOJSON_DIR / "demo_buyers.geojson").read_text())

    # ----- Farmers -----
    farmers: list[Farmer] = []
    for feature in farms_geojson["features"]:
        props = feature["properties"]
        coords = feature["geometry"]["coordinates"]  # [lon, lat]
        farmer = Farmer(
            id=uuid.UUID(props["id"]),
            name=props["name"],
            email=props["email"],
            phone=f"+91900000{len(farmers)+1:04d}",
            hashed_password=_DEMO_PASSWORD,
            farm_name=props.get("farm_name"),
            farm_size_hectares=props.get("farm_size_hectares"),
            quality_rating=props.get("quality_rating", 0.0),
            total_transactions=props.get("total_transactions", 0),
        )
        db.add(farmer)
        farmers.append(farmer)

        # Set PostGIS location if available
        if coords:
            await db.execute(
                text(
                    "UPDATE farmers SET location = ST_SetSRID(ST_MakePoint(:lon, :lat), 4326) "
                    "WHERE id = :id"
                ),
                {"lon": coords[0], "lat": coords[1], "id": str(farmer.id)},
            )

    # ----- Buyers -----
    for feature in buyers_geojson["features"]:
        props = feature["properties"]
        coords = feature["geometry"]["coordinates"]
        buyer = Buyer(
            id=uuid.UUID(props["id"]),
            name=props["name"],
            email=props["email"],
            phone=f"+91800000{buyers_geojson['features'].index(feature)+1:04d}",
            hashed_password=_DEMO_PASSWORD,
            delivery_address=props.get("delivery_address"),
            payment_speed_rating=props.get("payment_speed_rating", 0.0),
            purchase_history_count=props.get("purchase_history_count", 0),
        )
        db.add(buyer)

        if coords:
            await db.execute(
                text(
                    "UPDATE buyers SET delivery_location = ST_SetSRID(ST_MakePoint(:lon, :lat), 4326) "
                    "WHERE id = :id"
                ),
                {"lon": coords[0], "lat": coords[1], "id": str(buyer.id)},
            )

    # ----- Middlemen -----
    for feature in trucks_geojson["features"]:
        props = feature["properties"]
        coords = feature["geometry"]["coordinates"]
        middleman = Middleman(
            id=uuid.UUID(props["id"]),
            name=props["name"],
            email=f"{props['name'].lower().replace(' ', '.')}@demo.com",
            phone=f"+91700000{trucks_geojson['features'].index(feature)+1:04d}",
            hashed_password=_DEMO_PASSWORD,
            truck_capacity_kg=props.get("truck_capacity_kg", 5000),
            truck_plate=props.get("truck_plate", f"XX00{trucks_geojson['features'].index(feature):04d}"),
            route_radius_km=props.get("route_radius_km", 100),
            on_time_rating=props.get("on_time_rating", 0.0),
            total_deliveries=props.get("total_deliveries", 0),
            is_available=True,
        )
        db.add(middleman)

        if coords:
            await db.execute(
                text(
                    "UPDATE middlemen SET current_location = ST_SetSRID(ST_MakePoint(:lon, :lat), 4326) "
                    "WHERE id = :id"
                ),
                {"lon": coords[0], "lat": coords[1], "id": str(middleman.id)},
            )

    await db.flush()

    # ----- Sample listings -----
    sample_listings = [
        {"crop_type": "Tomato", "variety": "Cherry", "total_volume_kg": 2000, "unit_price_asking": 0.45, "quality_grade": "A"},
        {"crop_type": "Mango", "variety": "Alphonso", "total_volume_kg": 5000, "unit_price_asking": 1.20, "quality_grade": "A"},
        {"crop_type": "Onion", "variety": "Red", "total_volume_kg": 10000, "unit_price_asking": 0.22, "quality_grade": "B"},
        {"crop_type": "Banana", "variety": "Cavendish", "total_volume_kg": 3500, "unit_price_asking": 0.35, "quality_grade": "A"},
        {"crop_type": "Spinach", "variety": None, "total_volume_kg": 800, "unit_price_asking": 0.80, "quality_grade": "B"},
    ]
    for i, listing in enumerate(sample_listings):
        farmer = farmers[i % len(farmers)]
        order = Order(
            farmer_id=farmer.id,
            crop_type=listing["crop_type"],
            variety=listing["variety"],
            total_volume_kg=listing["total_volume_kg"],
            available_volume_kg=listing["total_volume_kg"],
            unit_price_asking=listing["unit_price_asking"],
            quality_grade=listing["quality_grade"],
            status=OrderStatus.LISTED,
        )
        db.add(order)

    logger.info(
        "Seeded %d farmers, %d buyers, %d middlemen, %d listings",
        len(farmers),
        len(buyers_geojson["features"]),
        len(trucks_geojson["features"]),
        len(sample_listings),
    )
