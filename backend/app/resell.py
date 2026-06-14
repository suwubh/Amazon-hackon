"""Resell marketplace (MT10 Fix 4) — deterministic economics + an in-memory
listing/interest store.

Rahul lists a used order item; the quote trades reach (range_km) for price: a wider
radius reaches more local buyers (higher achievable price) but Amazon's delivery cut
grows with distance, so NET can peak mid-range. Buyers tap "I'm interested" on a
public board; the reseller polls the listing for the live feed (real cross-tab).

Stores are in-memory per-Lambda-instance (cart/passport pattern): cross-tab works
locally (one uvicorn process) and on a single warm Lambda. Reuses pricing.py +
seed.buyers_for_asin — pure Python, no LLM, can't fail live.
"""
from __future__ import annotations

import random
from datetime import datetime, timezone

from . import passport, pricing, seed

RANGE_TIERS_KM = [3, 7, 15]
DELIVERY_BASE = 25      # ₹ flat
DELIVERY_PER_KM = 6     # ₹ per km of reach (Amazon's cut grows with distance)

# Seeded starter listings so the board isn't empty before Rahul lists. Each carries
# a grade + confidence so the Flash-deal detail view (MT12 NEW 12) always has a
# condition report to show before a buyer expresses interest.
_STARTER = [
    {"item_id": "SL-006", "asin": "B0HDPHN880", "title": "SonicWave ANC Headphones",
     "thumb": "/items/SL-006/current_1.jpg", "ask_price": 2600, "range_km": 7, "owner": "Sneha K.",
     "grade": "B", "confidence": 0.9, "source": "resell", "category": "electronics"},
    {"item_id": "SL-008", "asin": "B0BCKPCK19", "title": "TrailMate 28L Backpack",
     "thumb": "/items/SL-008/current_1.jpg", "ask_price": 850, "range_km": 7, "owner": "Arjun M.",
     "grade": "A", "confidence": 0.95, "source": "resell", "category": "bags"},
]
_INTEREST_POOL = [
    ("Asha D.", 2.4), ("Nikhil R.", 3.6), ("Farah S.", 1.8), ("Imran K.", 4.1),
    ("Rhea M.", 5.2), ("Tanvi P.", 2.9), ("Kabir S.", 6.0),
]

_LISTINGS: dict[str, dict] | None = None
_seq = 0


def _delivery_cut(range_km: int) -> int:
    return round(DELIVERY_BASE + DELIVERY_PER_KM * range_km)


def quote(item_id: str, range_km: int, grade: str = "B") -> dict | None:
    item = seed.get_item(item_id)
    if item is None:
        return None
    grade = grade if grade in pricing.GRADE_FACTOR else "B"
    ai_suggested = pricing.resale_value(item["mrp"], item["category"],
                                        item["age_months"], grade, 1.0)
    buyers = seed.buyers_for_asin(item["asin"], range_km)
    reachable = len(buyers)
    demand = pricing.demand_multiplier(reachable)
    best_price = pricing.resale_value(item["mrp"], item["category"],
                                      item["age_months"], grade, demand)
    cut = _delivery_cut(range_km)
    curve = pricing.liquidity_curve([b["max_price"] for b in buyers] or [ai_suggested],
                                    best_price)
    return {
        "item_id": item_id,
        "range_km": range_km,
        "grade": grade,
        "ai_suggested": ai_suggested,
        "reachable_buyers": reachable,
        "best_price": best_price,
        "delivery_cut": cut,
        "net": best_price - cut,
        "points": curve["points"],
        "recommended": curve["recommended"],
        "range_tiers": [
            {"range_km": r, "reachable_buyers": len(seed.buyers_for_asin(item["asin"], r)),
             "delivery_cut": _delivery_cut(r)}
            for r in RANGE_TIERS_KM
        ],
    }


def _store() -> dict[str, dict]:
    global _LISTINGS, _seq
    if _LISTINGS is None:
        _LISTINGS = {}
        for s in _STARTER:
            _seq += 1
            lid = f"RL-{_seq:03d}"
            _LISTINGS[lid] = {
                "listing_id": lid, **s, "delivery_cut": _delivery_cut(s["range_km"]),
                "net": s["ask_price"] - _delivery_cut(s["range_km"]),
                "status": "active", "sold_to": None,
                "interests": [], "created_ts": datetime.now(timezone.utc).isoformat(),
            }
    return _LISTINGS


def create_listing(item_id: str, persona: str, ask_price: int, range_km: int, *,
                   grade: str | None = None, confidence: float | None = None,
                   source: str = "resell") -> dict | None:
    global _seq
    item = seed.get_item(item_id)
    if item is None:
        return None
    store = _store()
    _seq += 1
    lid = f"RL-{_seq:03d}"
    store[lid] = {
        "listing_id": lid,
        "item_id": item_id,
        "asin": item["asin"],
        "title": item["title"],
        "category": item.get("category"),
        "thumb": item.get("thumb"),
        "ask_price": ask_price,
        "range_km": range_km,
        "delivery_cut": _delivery_cut(range_km),
        "net": ask_price - _delivery_cut(range_km),
        "owner": persona,
        # Condition report carried on the listing so a buyer sees the AI grade +
        # confidence BEFORE expressing interest (MT12 NEW 12). source distinguishes
        # a neighbour resell from a graded warehouse return (MT12 NEW 9).
        "grade": grade,
        "confidence": confidence,
        "source": source,
        "status": "active",
        "sold_to": None,
        "interests": [],
        "created_ts": datetime.now(timezone.utc).isoformat(),
    }
    return store[lid]


def list_from_route(item_id: str, owner: str = "Amazon · Returned") -> dict | None:
    """MT12 NEW 9 — when a returned item is graded on the Ops desk and the VRS winner
    is local_p2p, surface it on the public Flash-deals board alongside neighbour
    resells. Price = the engine's resale_value (the buyer-facing fair price), grade +
    confidence from the GRADED event. Idempotent per item (won't double-list)."""
    item = seed.get_item(item_id)
    if item is None:
        return None
    routed = passport.latest_event(item_id, "ROUTED")
    if routed is None or routed["data"].get("decision") != "local_p2p":
        return None
    store = _store()
    for l in store.values():
        if l.get("source") == "return" and l.get("item_id") == item_id and l["status"] == "active":
            return l  # already on the board
    graded = passport.latest_event(item_id, "GRADED")
    gdata = graded["data"] if graded else {}
    ask = routed["data"].get("resale_value") or item["mrp"]
    return create_listing(item_id, owner, int(ask), 7,
                          grade=gdata.get("grade"), confidence=gdata.get("confidence"),
                          source="return")


def list_listings() -> dict:
    return {"listings": list(reversed(list(_store().values())))}


def get_listing(listing_id: str) -> dict | None:
    return _store().get(listing_id)


def add_interest(listing_id: str, buyer_name: str | None = None,
                 distance_km: float | None = None, offer: int | None = None) -> dict | None:
    listing = _store().get(listing_id)
    if listing is None:
        return None
    if buyer_name is None or distance_km is None:
        name, dist = random.choice(_INTEREST_POOL)
        buyer_name = buyer_name or name
        distance_km = distance_km if distance_km is not None else dist
    interest = {
        "interest_id": f"IN-{len(listing['interests']) + 1:03d}",
        "buyer_name": buyer_name,
        "distance_km": distance_km,
        "offer": offer if offer is not None else listing["ask_price"],
        "status": "pending",
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    listing["interests"].append(interest)
    return listing


def _find_interest(listing: dict, interest_id: str) -> dict | None:
    return next((i for i in listing["interests"] if i["interest_id"] == interest_id), None)


def sell_to_interest(listing_id: str, interest_id: str) -> dict | None:
    """The reseller accepts one interested buyer → the listing is sold to them.
    The take-home (net) is the buyer's offer minus the delivery cut for this reach."""
    listing = _store().get(listing_id)
    if listing is None:
        return None
    interest = _find_interest(listing, interest_id)
    if interest is None:
        return None
    interest["status"] = "accepted"
    for other in listing["interests"]:
        if other["interest_id"] != interest_id and other["status"] == "pending":
            other["status"] = "passed"
    listing["status"] = "sold"
    listing["sold_to"] = interest
    listing["net_earned"] = interest["offer"] - listing["delivery_cut"]
    listing["sold_ts"] = datetime.now(timezone.utc).isoformat()
    return listing


def decline_interest(listing_id: str, interest_id: str) -> dict | None:
    """The reseller declines one interested buyer; the listing stays active for others."""
    listing = _store().get(listing_id)
    if listing is None:
        return None
    interest = _find_interest(listing, interest_id)
    if interest is None:
        return None
    interest["status"] = "declined"
    return listing
