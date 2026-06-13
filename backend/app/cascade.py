"""Derived value cascade — the terminal-state waterfall (MT8).

Judges arrive with Optoro's tiered-waterfall mental model ("dark store → wholesale
→ liquidation over time"). We already hold both halves: the VRS argmax (which
channel) and −5%/wk time-decay pricing (how value erodes). This composes them into
ONE derived artifact — NO fixed timer, NO hardcoded tiers: re-run the argmax
week-by-week as the resale price decays, and emit a tier each time the winning
channel flips. Pure-Python deterministic (reuses vrs.py + pricing.py) — no LLM, so
nothing to cache and nothing that can fail live.

Items that DON'T sell at the hyperlocal open-box node are exactly the ones the
cascade falls past to the lower tiers — the visible answer to "what happens to
everything that isn't dark-store-eligible."
"""
from __future__ import annotations

from . import pricing, seed, vrs

MAX_WEEKS = 26  # half a year of −5%/wk decay is plenty to reach the terminal tier

# Human-readable channel labels for the cascade strip.
LABELS = {
    "local_p2p": "Amazon Now dark store · open-box",
    "warehouse_relist": "central marketplace",
    "refurbish": "refurbish · relist one grade up",
    "liquidate": "wholesale / bulk",
    "donate": "donate · CSR certificate",
    "rto_relist": "sealed relist · local",
}
# The breakdown key that carries each channel's headline sale price (donate has none).
PRICE_KEY = {
    "local_p2p": "sale_price",
    "warehouse_relist": "sale_price",
    "refurbish": "refurbished_sale",
    "liquidate": "sale_price",
    "rto_relist": "sale_price",
}


def cascade(item_id: str) -> dict:
    """Derive the tier waterfall by re-running the VRS argmax over a decaying price.
    Requires a prior grade (raises vrs.NeedsGrade otherwise)."""
    item, grade, is_sealed_rto = vrs.grade_for(item_id)  # raises KeyError / NeedsGrade

    mrp, category, age, asin = item["mrp"], item["category"], item["age_months"], item["asin"]
    buyers = seed.buyers_for_asin(asin, vrs.LOCAL_RADIUS_KM)
    demand = pricing.demand_multiplier(len(buyers))
    resale0 = pricing.resale_value(mrp, category, age, grade, demand)
    refurb0 = pricing.resale_value(mrp, category, age, vrs._GRADE_UP[grade], demand)

    tiers: list[dict] = []
    last_channel = None
    for week in range(MAX_WEEKS + 1):
        factor = (1.0 - pricing.WEEKLY_DECAY) ** week
        resale = round(resale0 * factor)
        refurb = round(refurb0 * factor)
        paths = vrs.build_paths(item, grade, resale, refurb, buyers,
                                is_sealed_rto=is_sealed_rto)
        winner = max((p for p in paths if p["eligible"]), key=lambda p: p["recovery"])
        channel = winner["path"]
        if channel != last_channel:
            tiers.append({
                "week": week,
                "channel": channel,
                "label": LABELS.get(channel, channel),
                "price": winner["breakdown"].get(PRICE_KEY.get(channel, ""), 0),
                "net": winner["recovery"],
            })
            last_channel = channel
        # donate is the floor (a CSR credit, no cash sale) — once it wins, the
        # waterfall has bottomed out.
        if channel == "donate":
            tiers[-1]["terminal"] = True
            break
    else:
        # never reached donate (e.g. a sealed RTO holds value) — the last tier stands.
        tiers[-1]["terminal"] = True

    return {
        "item_id": item_id,
        "tiers": tiers,
        "decay_pct_per_week": round(pricing.WEEKLY_DECAY * 100),
    }
