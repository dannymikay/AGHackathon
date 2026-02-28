"""
External API integrations.

  - OpenRouteService: real driving route, distance (km), and ETA (hours)
  - Market price:     stub — update when commodity API key is available
  - Weather:          stub — update when weather API key is available

All functions return None on failure so callers degrade gracefully.
"""
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_ORS_BASE = "https://api.openrouteservice.org/v2/directions/driving-car"


async def fetch_driving_route(
    start_lon: float,
    start_lat: float,
    end_lon: float,
    end_lat: float,
) -> dict | None:
    """
    Fetch actual road driving distance and estimated travel time between two
    coordinates using OpenRouteService.

    Returns {"distance_km": float, "duration_hours": float} or None on failure.
    Coordinates must be WGS-84 (longitude first, then latitude — ORS convention).

    The API key is passed as an Authorization Bearer header (not in the URL)
    so it never appears in access logs or exception messages.
    """
    if not settings.OPENROUTESERVICE_API_KEY:
        return None

    url = f"{_ORS_BASE}?start={start_lon},{start_lat}&end={end_lon},{end_lat}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                url,
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {settings.OPENROUTESERVICE_API_KEY}",
                },
            )
            response.raise_for_status()
            data = response.json()

        summary = data["features"][0]["properties"]["summary"]
        return {
            "distance_km": round(summary["distance"] / 1000, 2),
            "duration_hours": round(summary["duration"] / 3600, 2),
        }
    except httpx.HTTPStatusError as exc:
        # Log status code only — never log the URL which could contain credentials
        logger.warning(
            "OpenRouteService returned HTTP %s", exc.response.status_code
        )
        return None
    except Exception as exc:
        logger.warning("OpenRouteService call failed (%s)", type(exc).__name__)
        return None


async def fetch_market_price(crop_type: str, region: str) -> float | None:
    """
    Fetch indicative market price per kg for a crop in a given region.
    Returns None until a commodity price API key is configured.
    """
    return None


async def fetch_weather_advisory(lat: float, lon: float) -> dict | None:
    """
    Fetch weather advisory for a farm or transit route location.
    Returns None until a weather API key is configured.
    """
    return None
