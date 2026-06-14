"""Buy-side 'Second Life options near you' — the layer-not-app twin on the PDP.

The whole solution is otherwise supply-side (grade → route → resell → list); the
buyer never *meets* a recovered unit on a normal product page. This surfaces 1–2
recovered units of the SAME product available near the shopper, right under the
buy box — closing the loop without a separate storefront (the part Renewed gets
wrong). PRICE is computed by the same deterministic pricing engine the sell side
uses; grade/distance/eta are seeded facts about each nearby recovered unit. No LLM.
"""
from __future__ import annotations

from . import pricing, seed, vrs


def second_life(asin: str) -> dict | None:
    """Recovered units of ``asin`` on offer near the shopper, nearest first.
    Returns None for an unknown ASIN; an empty ``offers`` list if the product
    has no nearby Second Life inventory."""
    item = seed.item_by_asin(asin)
    if item is None:
        return None

    # Local demand lifts the fair resale price (same multiplier the sell side uses).
    buyers = seed.buyers_for_asin(asin, vrs.LOCAL_RADIUS_KM)
    demand = pricing.demand_multiplier(len(buyers))

    offers = [
        {
            "item_id": o["item_id"],
            "grade": o["grade"],
            "price": pricing.resale_value(
                item["mrp"], item["category"], item["age_months"], o["grade"], demand),
            "distance_km": o["distance_km"],
            "eta": o["eta"],
        }
        for o in seed.second_life_offers(asin)
    ]
    offers.sort(key=lambda x: x["distance_km"])
    return {"asin": asin, "title": item["title"], "offers": offers}
