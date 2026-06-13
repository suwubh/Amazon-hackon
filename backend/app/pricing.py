"""Pricing engine — deterministic, auditable, no LLM.

Turns an item + its delta-grade into a resale value, a time-decay curve, and a
liquidity slider. The grade comes from the LLM perception layer; every rupee here
is plain Python so the demo can show its math.
"""
from __future__ import annotations

# Linear monthly depreciation per category: (rate_per_month, floor_fraction).
# Fraction of MRP a like-new (grade-A baseline applied separately) unit retains.
DEPRECIATION: dict[str, tuple[float, float]] = {
    "footwear": (0.040, 0.30),
    "electronics": (0.030, 0.25),
    "apparel": (0.060, 0.20),
    "appliances": (0.025, 0.35),
    "books": (0.050, 0.15),
    "home": (0.030, 0.30),
    "bags": (0.035, 0.25),
}
_DEFAULT_DEP = (0.040, 0.25)

# Condition multiplier on top of depreciation (architecture §4).
GRADE_FACTOR: dict[str, float] = {"A": 0.80, "B": 0.65, "C": 0.45, "D": 0.25}

WEEKLY_DECAY = 0.05  # -5%/week unsold (architecture §4)


def depreciation(category: str, age_months: int) -> float:
    rate, floor = DEPRECIATION.get(category, _DEFAULT_DEP)
    return max(floor, 1.0 - rate * age_months)


def demand_multiplier(buyer_count: int) -> float:
    """Local-demand lift on price (architecture §4: 0.9–1.15)."""
    if buyer_count >= 5:
        return 1.15
    if buyer_count >= 3:
        return 1.10
    if buyer_count >= 1:
        return 1.00
    return 0.90


def resale_value(mrp: int, category: str, age_months: int, grade: str,
                 demand_mult: float) -> int:
    """Expected fair resale price for a unit at this grade and local demand."""
    base = mrp * depreciation(category, age_months) * GRADE_FACTOR[grade] * demand_mult
    return round(base)


def price_decay(start_price: int, weeks: int = 8) -> list[dict]:
    """Time-decay schedule: what the item is worth each week it sits unsold."""
    out = []
    price = float(start_price)
    for week in range(weeks + 1):
        out.append({"week": week, "price": round(price)})
        price *= (1.0 - WEEKLY_DECAY)
    return out


def liquidity_curve(buyer_prices: list[int], resale: int) -> dict:
    """Liquidity slider: at each ask price, how many local buyers clear it and
    roughly how long it takes to sell. Derived from real seeded buyer willingness.

    buyers_at_price = buyers whose max_price >= ask. Fewer buyers => slower sale.
    """
    # Distinct ask levels the buyers actually support, low→high, plus the
    # engine's own resale estimate as a candidate point.
    levels = sorted({p for p in buyer_prices} | {resale})
    total = len(buyer_prices)
    points = []
    for ask in levels:
        buyers = sum(1 for p in buyer_prices if p >= ask)
        # 1 buyer ~ 8 days; more buyers clear faster (floor 1 day).
        est_days = max(1, round(8 / buyers)) if buyers else 30
        points.append({
            "price": ask,
            "est_days_to_sell": est_days,
            "buyers_at_price": buyers,
        })
    # Recommend the highest price that still has >=2 ready buyers (fast, fair),
    # falling back to the engine resale if demand is thin.
    ready = [p for p in points if p["buyers_at_price"] >= 2]
    recommended = max((p["price"] for p in ready), default=resale)
    return {"points": points, "recommended": recommended}
