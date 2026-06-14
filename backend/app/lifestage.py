"""Life-stage prediction (MT12 NEW 1) — the time-based twin of the demand radar.

Products end a useful *stage* on a predictable curve (a baby outgrows gear ~18mo, a
phone hits its refresh cycle ~30mo). This nudges the owner to resell BECAUSE the
time elapsed — before any buyer searches — with a forward value projection. The
stage curve is seeded (lifestage_curves.json); the current value + ₹/month decay
are DERIVED from pricing.py over the owner's real purchase date, so every rupee is
auditable (no hardcoded "₹X dropping per month" copy). Pure Python, no LLM.
"""
from __future__ import annotations

from datetime import date, datetime

from . import orders, pricing, seed

# An item is "due to resell" once it's this far through its typical stage.
DUE_FRACTION = 0.6


def _months_owned(purchase_date: str | None, today: date) -> int:
    if not purchase_date:
        return 0
    try:
        d = datetime.strptime(purchase_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return 0
    months = (today.year - d.year) * 12 + (today.month - d.month)
    if today.day < d.day:
        months -= 1
    return max(0, months)


def _purchase_date(asin: str, persona: str, item: dict) -> str | None:
    """Owner's purchase date from their order history, falling back to the item's
    own seeded order so a life-stage is always computable."""
    for o in seed.order_history(persona) or []:
        if o.get("asin") == asin:
            return o.get("purchase_date")
    return (item.get("order") or {}).get("purchase_date")


def life_stage(asin: str, persona: str = "rahul") -> dict | None:
    """Time-triggered resell signal for a product the persona owns.

    Returns None only if the ASIN isn't in the catalog. Every numeric field is
    derived (months from the real purchase date; value/decay from pricing.py)."""
    item = seed.item_by_asin(asin)
    if item is None:
        return None

    today = orders.TODAY
    purchase_date = _purchase_date(asin, persona, item)
    months_owned = _months_owned(purchase_date, today)

    curve = seed.lifestage_curve(asin, item.get("category")) or {
        "typical_life_months": 24, "stage_label": "useful life"
    }
    typical = curve["typical_life_months"]

    # Current resale value + next-month value from the deterministic pricing engine
    # (a well-kept idle unit grades ~B); the gap is the monthly value decay.
    mrp, category = item["mrp"], item["category"]
    current_value = pricing.resale_value(mrp, category, months_owned, "B", 1.0)
    next_value = pricing.resale_value(mrp, category, months_owned + 1, "B", 1.0)
    decay_per_month = max(0, current_value - next_value)

    stage_pct = round(min(months_owned / typical, 1.0) * 100) if typical else 0
    due_to_resell = months_owned >= round(typical * DUE_FRACTION)

    return {
        "asin": asin,
        "persona": persona.lower(),
        "title": item.get("title"),
        "category": category,
        "purchase_date": purchase_date,
        "months_owned": months_owned,
        "typical_life_months": typical,
        "stage_label": curve.get("stage_label", "useful life"),
        "stage_pct": stage_pct,
        "past_typical_life": months_owned >= typical,
        "current_value": current_value,
        "decay_per_month": decay_per_month,
        "due_to_resell": due_to_resell,
    }
