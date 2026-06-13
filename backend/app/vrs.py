"""Value Recovery Score engine — deterministic, auditable, no LLM.

For a graded item it computes the rupee recovery of every disposition path,
returns each path's full cost breakdown (the frontend renders the math, not just
the winner), and routes to the argmax. The whole point of the project: a returned
₹500 shoe is destroyed by reverse-logistics at the warehouse but recovers most of
its value via a local hop to a nearby buyer.

LLM gives the condition facts (grade). This file turns facts into money.
"""
from __future__ import annotations

from . import passport, pricing, seed

# --- locked cost constants (architecture §4) -----------------------------
WAREHOUSE_COSTS = {"reverse_ship": 120, "inspection": 40, "relist": 60, "fc_handling": 30}
LOCAL_HOP = 40
PAYMENT_FEE_PCT = 0.02
DONATE_PICKUP = 30
CSR_CREDIT_PCT = 0.15          # tax/CSR credit on fair value (MRP)
LIQUIDATE_PCT = 0.12           # bulk liquidator pays ~12% of MRP
LIQUIDATE_HANDLING = 20
RTO_PCT = 0.90                 # sealed RTO unit resells near-new
RTO_RELABEL = 15
RTO_LOCAL_DELIVERY = 40

# Refurbish is only economical above this resale floor and for repairable goods.
REFURB_MIN_RESALE = 600
REPAIR_COST = {"footwear": 90, "electronics": 200, "appliances": 250,
               "bags": 120, "apparel": 60, "home": 50}
REFURB_LOGISTICS = 60
_GRADE_UP = {"D": "C", "C": "B", "B": "A", "A": "A"}

# Environmental accounting for the warehouse trip a local hop avoids.
WAREHOUSE_KM = 600
CO2_PER_KM = 0.0035            # kg CO2 per item-km of avoided reverse freight
LOCAL_DEFAULT_KM = 5

LOCAL_RADIUS_KM = 15          # eligibility radius for a local match
LOCAL_NOTE_KM = 4             # "buyers within N km" headline


class NeedsGrade(Exception):
    """/route called before the item was graded."""


def _path(name: str, breakdown: dict[str, int], *, eligible: bool, note: str | None = None,
          distance_km: float | None = None) -> dict:
    """Build a path entry whose recovery is exactly the sum of its breakdown —
    so the math always adds up on screen."""
    p = {
        "path": name,
        "recovery": sum(breakdown.values()) if eligible else 0,
        "eligible": eligible,
        "winner": False,
        "breakdown": breakdown if eligible else {},
    }
    if note is not None:
        p["note"] = note
    if distance_km is not None:
        p["distance_km"] = distance_km
    return p


def grade_for(item_id: str) -> tuple[dict, str, bool]:
    """Resolve (item, grade, is_sealed_rto) for routing/cascade. A sealed RTO unit
    is never opened, so it skips grading and routes as factory-new (architecture
    §3.2); everything else needs a prior delta-grade. Raises NeedsGrade otherwise."""
    item = seed.get_item(item_id)
    if item is None:
        raise KeyError(item_id)
    seal = passport.latest_event(item_id, "SEAL_CHECKED")
    is_sealed_rto = bool(item.get("rto")) and seal is not None and seal["data"].get("sealed")
    graded = passport.latest_event(item_id, "GRADED")
    if graded is not None:
        grade = graded["data"]["grade"]
    elif is_sealed_rto:
        grade = "A"
    else:
        raise NeedsGrade(item_id)
    return item, grade, is_sealed_rto


def build_paths(item: dict, grade: str, resale: int, refurb_resale: int,
                buyers: list[dict], *, is_sealed_rto: bool) -> list[dict]:
    """Pure VRS path list for a given resale price — no passport writes. Shared by
    route_item and the cascade, which re-runs this at week-by-week decayed prices."""
    mrp, category, asin = item["mrp"], item["category"], item["asin"]
    paths: list[dict] = []

    # local_p2p — interception before the item ever ships to a warehouse.
    near = [b for b in buyers if b["distance_km"] <= LOCAL_NOTE_KM]
    local_eligible = len(buyers) >= 1
    local_sale = round(resale * 0.95)
    local_dist = buyers[0]["distance_km"] if buyers else None
    local = _path(
        "local_p2p",
        {"sale_price": local_sale, "local_hop": -LOCAL_HOP,
         "payment_fee": -round(local_sale * PAYMENT_FEE_PCT)},
        eligible=local_eligible,
        note=(f"{len(near)} matched buyers within {LOCAL_NOTE_KM} km" if local_eligible
              else "no local buyers matched"),
        distance_km=local_dist,
    )
    # MT8: name the hyperlocal open-box node (nearest Amazon Now MFC).
    if local_eligible:
        ds = seed.nearest_dark_store(item)
        if ds is not None:
            local["dark_store"] = ds
    paths.append(local)

    # warehouse_relist — the default reverse-logistics route.
    wh_sale = round(resale * 0.92)
    paths.append(_path(
        "warehouse_relist",
        {"sale_price": wh_sale, **{k: -v for k, v in WAREHOUSE_COSTS.items()}},
        eligible=True,
    ))

    # refurbish — repair one grade up, then resell. Only worthwhile on repairable,
    # higher-value, actually-defective items.
    refurb_eligible = (grade in ("C", "D") and resale >= REFURB_MIN_RESALE
                       and category in REPAIR_COST)
    if refurb_eligible:
        paths.append(_path(
            "refurbish",
            {"refurbished_sale": refurb_resale, "repair": -REPAIR_COST[category],
             "logistics": -REFURB_LOGISTICS},
            eligible=True,
        ))
    else:
        paths.append(_path("refurbish", {}, eligible=False,
                           note="not economical to refurbish this item"))

    # donate — recovers a CSR/tax credit on fair value.
    paths.append(_path(
        "donate",
        {"csr_tax_credit": round(mrp * CSR_CREDIT_PCT), "pickup": -DONATE_PICKUP},
        eligible=True,
    ))

    # liquidate — bulk sale, the floor option.
    paths.append(_path(
        "liquidate",
        {"sale_price": round(mrp * LIQUIDATE_PCT), "bulk_handling": -LIQUIDATE_HANDLING},
        eligible=True,
    ))

    # rto_relist — only for a sealed RTO unit (seal verdict required).
    if is_sealed_rto:
        paths.append(_path(
            "rto_relist",
            {"sale_price": round(mrp * RTO_PCT), "relabel": -RTO_RELABEL,
             "local_delivery": -RTO_LOCAL_DELIVERY},
            eligible=True,
        ))
    else:
        paths.append(_path("rto_relist", {}, eligible=False,
                           note="not an RTO item" if not item.get("rto") else "seal not verified"))

    return paths


def route_item(item_id: str) -> dict:
    item, grade, is_sealed_rto = grade_for(item_id)

    mrp, category, age, asin = item["mrp"], item["category"], item["age_months"], item["asin"]
    buyers = seed.buyers_for_asin(asin, LOCAL_RADIUS_KM)
    demand_mult = pricing.demand_multiplier(len(buyers))
    resale = pricing.resale_value(mrp, category, age, grade, demand_mult)
    refurb_resale = pricing.resale_value(mrp, category, age, _GRADE_UP[grade], demand_mult)

    paths = build_paths(item, grade, resale, refurb_resale, buyers,
                        is_sealed_rto=is_sealed_rto)
    local_dist = buyers[0]["distance_km"] if buyers else None

    # winner = argmax recovery over eligible paths.
    winner = max((p for p in paths if p["eligible"]), key=lambda p: p["recovery"])
    winner["winner"] = True

    # environmental upside of avoiding the warehouse round-trip.
    wh_recovery = next(p["recovery"] for p in paths if p["path"] == "warehouse_relist")
    if winner["path"] == "warehouse_relist":
        km_saved = 0
    else:
        local_leg = local_dist if (winner["path"] == "local_p2p" and local_dist) else LOCAL_DEFAULT_KM
        km_saved = round(WAREHOUSE_KM - local_leg)
    co2_saved = round(km_saved * CO2_PER_KM, 1)

    result = {
        "item_id": item_id,
        "resale_value": resale,
        "paths": paths,
        "decision": winner["path"],
        "co2_saved_kg": co2_saved,
        "km_saved": km_saved,
    }
    passport.append_event(item_id, "ROUTED", {
        "decision": winner["path"], "recovery": winner["recovery"],
        "warehouse_recovery": wh_recovery, "resale_value": resale,
        "co2_saved_kg": co2_saved,
    })
    return result
