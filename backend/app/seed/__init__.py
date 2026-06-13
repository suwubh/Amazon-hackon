"""Seed store: repo-baked demo data (items, orders, neighbors, images, cached AI responses).

Everything the demo needs ships in this package so a cold Lambda always has it.
"""
import json
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
