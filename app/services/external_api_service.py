"""
External API integration stub.

When external data API keys are provided, update this single file.
All callers handle None gracefully (display "market data unavailable").
"""


async def fetch_market_price(crop_type: str, region: str) -> float | None:
    """
    Fetch indicative market price per kg for a crop in a given region.
    Returns None until a real data source is configured.
    """
    # TODO: integrate with a commodity price API when keys are available
    return None


async def fetch_weather_advisory(lat: float, lon: float) -> dict | None:
    """
    Fetch weather data for farm/transit route advisory.
    Returns None until a real data source is configured.
    """
    # TODO: integrate with a weather API when keys are available
    return None
