"""Guards the VRS invariant the whole pitch leans on (audit LOW 11).

Every eligible disposition path's ``recovery`` must equal the exact sum of its
``breakdown`` — that's what lets the frontend render the money math and have it
reconcile on screen. A nudged cost constant could silently break this; this test
fails loudly if it does. Also pins the SL-001 hero golden (+₹83 / −₹129).

Runs with pytest (``python -m pytest backend/tests``) OR standalone with no deps
(``python backend/tests/test_vrs.py``) — pytest isn't a project dependency.
"""
import sys
from pathlib import Path

# Make ``app`` importable whether run via pytest or directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import pricing, seed, vrs  # noqa: E402

GRADES = ("A", "B", "C", "D")


def _resale_pair(item: dict, grade: str):
    """Replicate route_item's resale inputs for a given grade."""
    buyers = seed.buyers_for_asin(item["asin"], vrs.LOCAL_RADIUS_KM)
    demand = pricing.demand_multiplier(len(buyers))
    resale = pricing.resale_value(item["mrp"], item["category"], item["age_months"], grade, demand)
    refurb = pricing.resale_value(
        item["mrp"], item["category"], item["age_months"], vrs._GRADE_UP[grade], demand)
    return buyers, resale, refurb


def test_recovery_reconciles_every_path():
    """recovery == sum(breakdown) for every ELIGIBLE path, all items × grades A–D,
    including the sealed-RTO path for RTO items."""
    for item in seed.ITEMS.values():
        for grade in GRADES:
            buyers, resale, refurb = _resale_pair(item, grade)
            for sealed in ({False, True} if item.get("rto") else {False}):
                paths = vrs.build_paths(item, grade, resale, refurb, buyers, is_sealed_rto=sealed)
                for p in paths:
                    if not p["eligible"]:
                        continue
                    total = sum(p["breakdown"].values())
                    assert p["recovery"] == total, (
                        f"{item['item_id']} grade {grade} sealed={sealed}: path "
                        f"{p['path']} recovery {p['recovery']} != sum(breakdown) {total}")


def test_sl001_hero_golden():
    """The numbers on the hero RouteScreen: local_p2p +₹83, warehouse −₹129."""
    item = seed.get_item("SL-001")
    buyers, resale, refurb = _resale_pair(item, "D")
    paths = vrs.build_paths(item, "D", resale, refurb, buyers, is_sealed_rto=False)
    by_path = {p["path"]: p for p in paths}
    assert by_path["local_p2p"]["recovery"] == 83, by_path["local_p2p"]
    assert by_path["warehouse_relist"]["recovery"] == -129, by_path["warehouse_relist"]
    # local must beat warehouse — the whole thesis in one assert.
    assert by_path["local_p2p"]["recovery"] > by_path["warehouse_relist"]["recovery"]


if __name__ == "__main__":
    test_recovery_reconciles_every_path()
    test_sl001_hero_golden()
    print("VRS invariant OK: recovery == sum(breakdown) for every eligible path; "
          "SL-001 hero golden +83 / -129 holds.")
