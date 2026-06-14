"""Seed store: repo-baked demo data (items, orders, neighbors, images, cached AI responses).

Everything the demo needs ships in this package so a cold Lambda always has it.
"""
import json
import math
from pathlib import Path

SEED_DIR = Path(__file__).parent
IMAGES_DIR = SEED_DIR / "images"
CACHED_DIR = SEED_DIR / "cached"

with open(SEED_DIR / "items.json", encoding="utf-8") as f:
    ITEMS = {it["item_id"]: it for it in json.load(f)["items"]}

with open(SEED_DIR / "orders.json", encoding="utf-8") as f:
    ORDERS = json.load(f)

with open(SEED_DIR / "neighbors.json", encoding="utf-8") as f:
    NEIGHBORS = json.load(f)

with open(SEED_DIR / "size_signals.json", encoding="utf-8") as f:
    SIZE_SIGNALS = json.load(f)

with open(SEED_DIR / "seller_catalog.json", encoding="utf-8") as f:
    SELLER_CATALOG = json.load(f)

with open(SEED_DIR / "buyer.json", encoding="utf-8") as f:
    BUYER = json.load(f)

with open(SEED_DIR / "dark_stores.json", encoding="utf-8") as f:
    DARK_STORES = json.load(f)["dark_stores"]

with open(SEED_DIR / "returns_seed.json", encoding="utf-8") as f:
    RETURNS_SEED = json.load(f)["returns"]


def returns_seed() -> list[dict]:
    return RETURNS_SEED


with open(SEED_DIR / "second_life_offers.json", encoding="utf-8") as f:
    SECOND_LIFE_OFFERS = json.load(f)["offers"]


def second_life_offers(asin: str) -> list[dict]:
    """Seeded buy-side recovered units for an ASIN (grade/distance/eta facts);
    empty list if this product has no nearby Second Life inventory."""
    val = SECOND_LIFE_OFFERS.get(asin, [])
    return val if isinstance(val, list) else []


with open(SEED_DIR / "purchase_profile.json", encoding="utf-8") as f:
    PURCHASE_PROFILE = json.load(f)


def purchase_profile(persona: str) -> list[dict]:
    val = PURCHASE_PROFILE.get(persona.lower(), [])
    return val if isinstance(val, list) else []


def get_item(item_id: str) -> dict | None:
    return ITEMS.get(item_id)


def list_items() -> list[dict]:
    """Items without the order block (that's detail-only)."""
    return [{k: v for k, v in it.items() if k != "order"} for it in ITEMS.values()]


def item_images(item_id: str) -> dict[str, list[Path]]:
    """Grouped image paths for an item: catalog / day0 / current, sorted."""
    d = IMAGES_DIR / item_id
    if not d.is_dir():
        return {"catalog": [], "day0": [], "current": []}
    files = sorted(d.glob("*.jpg")) + sorted(d.glob("*.jpeg")) + sorted(d.glob("*.png"))
    return {
        "catalog": [p for p in files if p.stem == "catalog"],
        "day0": [p for p in files if p.stem.startswith("day0")],
        "current": [p for p in files if p.stem.startswith("current")],
    }


def cached_response(item_id: str, call: str) -> dict | None:
    """Committed cached AI response, e.g. cached/SL-001.grade.json."""
    p = CACHED_DIR / f"{item_id}.{call}.json"
    if p.is_file():
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return None


def item_by_asin(asin: str) -> dict | None:
    for it in ITEMS.values():
        if it["asin"] == asin:
            return it
    return None


def buyers_for_asin(asin: str, max_km: float | None = None) -> list[dict]:
    """Synthetic local buyers (wishlist / notify-me / recent-search) for an ASIN,
    nearest first, optionally capped to a radius."""
    out = [
        b for b in NEIGHBORS["buyers"]
        if asin in b["wishlist_asins"] and (max_km is None or b["distance_km"] <= max_km)
    ]
    return sorted(out, key=lambda b: b["distance_km"])


def demand_point() -> dict:
    return ORDERS["demand_point"]


def dormant_units(asin: str) -> list[dict]:
    """Dormant units of an ASIN sitting in homes near the demand point, nearest first."""
    out = [u for u in ORDERS["dormant_units"] if u["asin"] == asin]
    return sorted(out, key=lambda u: u["distance_km"])


def size_signal(asin: str) -> dict | None:
    """Per-ASIN fit social proof (footwear/apparel only), or None."""
    sig = SIZE_SIGNALS.get(asin)
    return sig if isinstance(sig, dict) else None


def seller_catalog() -> dict:
    return SELLER_CATALOG


def order_history(persona: str) -> list[dict] | None:
    """A persona's seeded order history, e.g. orders.json -> rahul_order_history."""
    return ORDERS.get(f"{persona.lower()}_order_history")


def buyer_data(persona: str) -> dict | None:
    """A persona's seeded storefront block (cart + notifications + upi_vpa)."""
    return BUYER.get(persona.lower())


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km between two lat/lon points."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return r * 2 * math.asin(math.sqrt(a))


def nearest_dark_store(item: dict) -> dict | None:
    """Nearest Amazon Now MFC (open-box node) to an item's location, as
    {id, name, distance_km}. None if the item has no location."""
    loc = item.get("location")
    if not loc:
        return None
    best, best_km = None, None
    for ds in DARK_STORES:
        km = _haversine_km(loc["lat"], loc["lon"], ds["lat"], ds["lon"])
        if best_km is None or km < best_km:
            best, best_km = ds, km
    if best is None:
        return None
    return {"id": best["id"], "name": best["name"], "distance_km": round(best_km, 1)}
