"""
Produce intelligence — shelf life, storage requirements, and grade-based pricing.

Data sourced from:
  - UC Davis Postharvest Technology Center fact sheets (shelf life at ambient ~20°C)
  - USDA ERS "Fruit and Vegetable Prices" (Grade B / Fancy discount norms)

This is an intentionally offline lookup — no API keys required for the hackathon demo.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TypedDict


class ProduceInfo(TypedDict):
    shelf_days: int    # Approximate shelf life in days at ambient temperature
    cold_chain: bool   # True = Reefer truck required for Grade B/damaged produce
    grade_b_ratio: float  # Grade B price as a fraction of Grade A / market price


# Keys are normalised crop names (title-case, stripped).
# Callers should do: PRODUCE_DATA.get(crop_type.strip().title())
PRODUCE_DATA: dict[str, ProduceInfo] = {
    "Tomato":      {"shelf_days": 7,   "cold_chain": False, "grade_b_ratio": 0.60},
    "Mango":       {"shelf_days": 5,   "cold_chain": False, "grade_b_ratio": 0.65},
    "Banana":      {"shelf_days": 3,   "cold_chain": False, "grade_b_ratio": 0.50},
    "Spinach":     {"shelf_days": 3,   "cold_chain": True,  "grade_b_ratio": 0.55},
    "Onion":       {"shelf_days": 180, "cold_chain": False, "grade_b_ratio": 0.75},
    "Potato":      {"shelf_days": 90,  "cold_chain": False, "grade_b_ratio": 0.80},
    "Strawberry":  {"shelf_days": 2,   "cold_chain": True,  "grade_b_ratio": 0.45},
    "Grapes":      {"shelf_days": 7,   "cold_chain": True,  "grade_b_ratio": 0.50},
    "Cabbage":     {"shelf_days": 14,  "cold_chain": False, "grade_b_ratio": 0.70},
    "Carrot":      {"shelf_days": 21,  "cold_chain": False, "grade_b_ratio": 0.75},
    "Papaya":      {"shelf_days": 5,   "cold_chain": False, "grade_b_ratio": 0.60},
    "Cucumber":    {"shelf_days": 7,   "cold_chain": False, "grade_b_ratio": 0.65},
    "Cauliflower": {"shelf_days": 14,  "cold_chain": False, "grade_b_ratio": 0.68},
    "Brinjal":     {"shelf_days": 7,   "cold_chain": False, "grade_b_ratio": 0.62},
    "Okra":        {"shelf_days": 4,   "cold_chain": False, "grade_b_ratio": 0.58},
    "Chilli":      {"shelf_days": 10,  "cold_chain": False, "grade_b_ratio": 0.65},
    "Pumpkin":     {"shelf_days": 60,  "cold_chain": False, "grade_b_ratio": 0.72},
    "Watermelon":  {"shelf_days": 14,  "cold_chain": False, "grade_b_ratio": 0.60},
    "Guava":       {"shelf_days": 4,   "cold_chain": False, "grade_b_ratio": 0.55},
    "Pomegranate": {"shelf_days": 30,  "cold_chain": False, "grade_b_ratio": 0.70},
}


def get_produce_info(crop_type: str) -> ProduceInfo | None:
    """Return produce intelligence for the given crop type, or None if unknown."""
    return PRODUCE_DATA.get(crop_type.strip().title())


def compute_days_remaining(harvest_date: datetime, crop_type: str) -> int | None:
    """
    Compute how many days are left before the produce expires.

    Returns None if the crop is unknown.
    Returns 0 if the produce is already past its shelf life.
    """
    info = get_produce_info(crop_type)
    if info is None:
        return None
    now = datetime.now(tz=timezone.utc)
    if harvest_date.tzinfo is None:
        harvest_date = harvest_date.replace(tzinfo=timezone.utc)
    elapsed_days = (now - harvest_date).total_seconds() / 86400
    remaining = info["shelf_days"] - elapsed_days
    return max(0, int(remaining))


def suggest_price_for_grade(
    crop_type: str,
    grade: str,
    asking_price: float,
    days_remaining: int | None = None,
) -> float | None:
    """
    Return a suggested price per kg for Grade B / damaged produce.

    For grade 'A' the asking_price is returned unchanged.
    Returns None if the crop is unknown.

    When days_remaining is provided, an urgency multiplier is applied on top of
    the standard Grade B discount:
      - At full shelf life (days_remaining == shelf_days): multiplier = 1.0 (no extra discount)
      - At expiry      (days_remaining == 0):             multiplier = 0.5 (50% additional cut)
    This reflects the reality that a buyer willing to pay 60% for Grade B tomatoes
    at day-0 harvest will only offer 30% if the tomatoes expire tomorrow.
    """
    info = get_produce_info(crop_type)
    if info is None:
        return None
    if grade.upper() == "B":
        base_price = asking_price * info["grade_b_ratio"]
        if days_remaining is not None and info["shelf_days"] > 0:
            urgency_factor = max(0.0, days_remaining / info["shelf_days"])
            # Multiplier: 0.5 (at expiry) → 1.0 (freshly harvested)
            urgency_multiplier = 0.5 + 0.5 * min(1.0, urgency_factor)
            return round(base_price * urgency_multiplier, 4)
        return round(base_price, 4)
    return asking_price


def auto_suggest_cold_chain(crop_type: str) -> bool:
    """Return True if this crop type requires a Reefer truck when damaged/Grade B."""
    info = get_produce_info(crop_type)
    return info["cold_chain"] if info else False
