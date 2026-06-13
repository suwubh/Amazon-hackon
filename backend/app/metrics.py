"""Demo impact counters — computed live from passport ROUTED events plus a small
pre-session baseline (so the dashboard reads non-zero before the live demo and
grows with every item routed on stage). No hardcoded UI numbers: this is the API
source for the green-impact ticker and the batch-metrics screen.
"""
from __future__ import annotations

from . import passport, seed

# Items already processed before this demo session starts.
BASELINE = {
    "items_processed": 5,
    "routed": 5,
    "warehouse_bypassed": 4,
    "rupees_recovered": 3120,
    "rupees_vs_writeoff_baseline": 3980,
    "co2_saved_kg": 9.4,
    "landfill_diverted_kg": 4.2,
    "inspection_hours_saved": 1.7,
}

# Approx unit mass diverted from landfill when reused instead of written off (kg).
LANDFILL_KG = {"footwear": 0.8, "electronics": 1.5, "apparel": 0.4, "appliances": 3.0,
               "books": 0.3, "home": 0.5, "bags": 1.0}
INSPECTION_HOURS_PER_BYPASS = 0.33  # ~20 min of manual FC inspection saved per bypass


def metrics() -> dict:
    graded = sum(1 for it in seed.ITEMS if passport.latest_event(it, "GRADED"))
    routed = [(it, passport.latest_event(it, "ROUTED")) for it in seed.ITEMS]
    routed = [(it, ev) for it, ev in routed if ev]

    recovered = vs_writeoff = co2 = landfill = 0.0
    bypassed = 0
    for item_id, ev in routed:
        d = ev["data"]
        recovered += max(0, d["recovery"])
        vs_writeoff += d["recovery"] - d["warehouse_recovery"]
        co2 += d.get("co2_saved_kg", 0)
        if d["decision"] != "warehouse_relist":
            bypassed += 1
            if d["decision"] != "liquidate":
                landfill += LANDFILL_KG.get(seed.ITEMS[item_id]["category"], 1.0)

    total_routed = BASELINE["routed"] + len(routed)
    total_bypassed = BASELINE["warehouse_bypassed"] + bypassed
    return {
        "items_processed": BASELINE["items_processed"] + graded,
        "rupees_recovered": BASELINE["rupees_recovered"] + round(recovered),
        "rupees_vs_writeoff_baseline": BASELINE["rupees_vs_writeoff_baseline"] + round(vs_writeoff),
        "warehouse_bypass_pct": round(100 * total_bypassed / total_routed) if total_routed else 0,
        "co2_saved_kg": round(BASELINE["co2_saved_kg"] + co2, 1),
        "landfill_diverted_kg": round(BASELINE["landfill_diverted_kg"] + landfill, 1),
        "inspection_hours_saved": round(
            BASELINE["inspection_hours_saved"] + bypassed * INSPECTION_HOURS_PER_BYPASS, 1),
    }
