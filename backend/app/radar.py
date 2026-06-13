"""Idle Asset Radar — activates dormant inventory sitting in people's homes.

Given an ASIN with live local demand, surface the dormant units of that ASIN
near the demand point and the one-tap resell pitch for each owner. Pure data over
the seeded order graph (orders.json / neighbors.json) — no LLM.
"""
from __future__ import annotations

from . import seed


def radar(asin: str) -> dict | None:
    units = seed.dormant_units(asin)
    if not units:
        return None
    dp = seed.demand_point()
    listing = seed.item_by_asin(asin)
    product = listing["title"] if listing else "unit"
    enriched = [
        {
            "item_id": u["item_id"],
            "owner": u["owner"],
            "purchased_months_ago": u["purchased_months_ago"],
            "distance_km": u["distance_km"],
            "est_value": u["est_value"],
            "ping_message": (f"Someone nearby will pay ₹{u['est_value']:,} for your "
                             f"{product} — sell in one tap."),
        }
        for u in units
    ]
    return {
        "asin": asin,
        "demand": {"query": dp["query"], "buyers_waiting": dp["buyers_waiting"]},
        "dormant_units": enriched,
        "total_dormant_value": sum(u["est_value"] for u in units),
    }
