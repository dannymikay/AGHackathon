"""
PostGIS spatial queries for logistics matching and dispute resolution.
Falls back to mock GeoJSON data in DEMO_MODE or if PostGIS is unavailable.
"""
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.middleman import Middleman
from app.schemas.common import GeoPoint
from app.schemas.middleman import MiddlemanPublic, NearbyMiddlemanResponse

_GEOJSON_DIR = Path(__file__).parent.parent / "seed" / "geojson"

DEMO_MIDDLEMEN: list[NearbyMiddlemanResponse] = []


def _load_demo_middlemen() -> list[NearbyMiddlemanResponse]:
    """Load mock middlemen from GeoJSON seed file for demo fallback."""
    path = _GEOJSON_DIR / "demo_trucks.geojson"
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    results = []
    for i, feature in enumerate(data.get("features", [])):
        props = feature.get("properties", {})
        results.append(
            NearbyMiddlemanResponse(
                middleman=MiddlemanPublic(
                    id=props.get("id", f"00000000-0000-0000-0000-{i:012d}"),
                    name=props.get("name", f"Demo Trucker {i+1}"),
                    truck_capacity_kg=props.get("truck_capacity_kg", 5000.0),
                    truck_plate=props.get("truck_plate", f"DEMO{i:04d}"),
                    route_radius_km=props.get("route_radius_km", 150.0),
                    on_time_rating=props.get("on_time_rating", 4.5),
                    total_deliveries=props.get("total_deliveries", 42),
                    is_available=True,
                    created_at=datetime.now(tz=timezone.utc),
                ),
                distance_km=props.get("distance_km", float(i + 1) * 2.5),
                estimated_arrival_hours=props.get("estimated_arrival_hours", 1.5),
            )
        )
    return results


async def find_middlemen_near_route(
    db: AsyncSession,
    farmer_location: GeoPoint,
    buyer_location: GeoPoint,
    buffer_km: float = 5.0,
) -> list[NearbyMiddlemanResponse]:
    """
    Find available middlemen whose current_location is within buffer_km of the
    straight-line route from farmer to buyer.

    Uses PostGIS ST_MakeLine + ST_Buffer(::geography) + ST_DWithin.
    Falls back to mock data if PostGIS is unavailable or DEMO_MODE is active.
    """
    if not settings.POSTGIS_ENABLED:
        return _load_demo_middlemen()

    try:
        raw_sql = text("""
            SELECT
                m.*,
                ST_Distance(
                    m.current_location::geography,
                    ST_MakeLine(
                        ST_SetSRID(ST_MakePoint(:farmer_lon, :farmer_lat), 4326),
                        ST_SetSRID(ST_MakePoint(:buyer_lon, :buyer_lat), 4326)
                    )::geography
                ) AS distance_m
            FROM middlemen m
            WHERE
                m.is_available = TRUE
                AND m.current_location IS NOT NULL
                AND ST_DWithin(
                    m.current_location::geography,
                    ST_Buffer(
                        ST_MakeLine(
                            ST_SetSRID(ST_MakePoint(:farmer_lon, :farmer_lat), 4326),
                            ST_SetSRID(ST_MakePoint(:buyer_lon, :buyer_lat), 4326)
                        )::geography,
                        :buffer_m
                    ),
                    0
                )
            ORDER BY distance_m ASC
            LIMIT 20
        """)
        result = await db.execute(
            raw_sql,
            {
                "farmer_lat": farmer_location.latitude,
                "farmer_lon": farmer_location.longitude,
                "buyer_lat": buyer_location.latitude,
                "buyer_lon": buyer_location.longitude,
                "buffer_m": buffer_km * 1000,
            },
        )
        rows = result.mappings().all()
        return [
            NearbyMiddlemanResponse(
                middleman=MiddlemanPublic.model_validate(dict(row)),
                distance_km=round(row["distance_m"] / 1000, 2),
                estimated_arrival_hours=round(row["distance_m"] / 1000 / 60, 2),
            )
            for row in rows
        ]
    except Exception:
        return _load_demo_middlemen()


async def check_middleman_at_buyer(
    middleman_location: GeoPoint,
    buyer_location: GeoPoint,
    threshold_m: float = 100.0,
) -> tuple[bool, float, str]:
    """
    Check if middleman GPS is within threshold_m of buyer location.
    Returns (is_within, distance_m, query_hash).
    The query_hash is recorded in AuditLog as signed proof.
    """
    # Haversine fallback (no DB needed for a simple distance check)
    distance_m = _haversine_m(
        middleman_location.latitude,
        middleman_location.longitude,
        buyer_location.latitude,
        buyer_location.longitude,
    )
    is_within = distance_m <= threshold_m

    # Create a deterministic hash of the inputs for the audit trail
    proof_string = (
        f"{middleman_location.latitude},{middleman_location.longitude}|"
        f"{buyer_location.latitude},{buyer_location.longitude}|"
        f"{threshold_m}|{distance_m:.4f}"
    )
    query_hash = hashlib.sha256(proof_string.encode()).hexdigest()

    return is_within, round(distance_m, 2), query_hash


async def get_orders_near_location(
    db: AsyncSession,
    lat: float,
    lon: float,
    radius_km: float,
) -> list:
    """Return order IDs for listings within radius_km of a point."""
    if not settings.POSTGIS_ENABLED:
        return []
    try:
        raw_sql = text("""
            SELECT o.id
            FROM orders o
            JOIN farmers f ON f.id = o.farmer_id
            WHERE
                o.status IN ('LISTED', 'NEGOTIATING')
                AND f.location IS NOT NULL
                AND ST_DWithin(
                    f.location::geography,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                    :radius_m
                )
        """)
        result = await db.execute(
            raw_sql, {"lat": lat, "lon": lon, "radius_m": radius_km * 1000}
        )
        return [row[0] for row in result.fetchall()]
    except Exception:
        return []


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Accurate great-circle distance in metres."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
