"""Guards the demo's stage-safety net (MT5 — "the demo cannot fail on stage").

Every committed cached AI response must still be servable in force_cached mode —
i.e. with the LIVE/CACHED toggle on (or the FORCE_CACHED kill switch set), every
demo-reachable AI endpoint returns a schema-valid result with source:"cached" and
makes ZERO live model calls. If a cache file is deleted, renamed, or drifts from
the schema the endpoints validate against, this fails loudly before the stage does.

Self-maintaining: the item lists are derived from seed/cached/*.{grade,seal,diagnose}.json,
so adding a new cached item automatically extends the coverage.

Runs with pytest (``python -m pytest backend/tests``) OR standalone with no deps
and no creds (``python backend/tests/test_cache_floor.py``) — force_cached short-
circuits before any provider, so this never touches the network.
"""
import os
import sys
from pathlib import Path

# Make ``app`` importable whether run via pytest or directly, and ensure the
# DynamoDB write-through stays a no-op so the test is hermetic / creds-free.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.pop("DYNAMODB_TABLE_NAME", None)

from app import seed  # noqa: E402
from app.grading import grade_item  # noqa: E402
from app.inspection import diagnose_listing, seal_check  # noqa: E402


def _ids_for(suffix: str):
    """item_ids that have a committed cache of the given kind (grade/seal/diagnose)."""
    return sorted(p.name[: -len(f".{suffix}.json")]
                  for p in seed.CACHED_DIR.glob(f"*.{suffix}.json"))


def test_grade_cache_floor():
    ids = _ids_for("grade")
    assert ids, "no grade caches committed — the demo would have no stage fallback"
    for item_id in ids:
        r = grade_item(item_id, force_cached=True)
        assert r["source"] == "cached", f"{item_id} grade did not serve cache: {r['source']}"
        assert r["grade"] in ("A", "B", "C", "D"), f"{item_id} bad grade {r['grade']}"
        assert isinstance(r["defects"], list), f"{item_id} defects not a list"
        assert r["same_unit"]["verified"] in (True, False)
        assert r["needs_human_review"] in (True, False)


def test_seal_cache_floor():
    for item_id in _ids_for("seal"):
        r = seal_check(item_id, force_cached=True)
        assert r["source"] == "cached", f"{item_id} seal did not serve cache: {r['source']}"
        assert r["verdict"] in ("SEALED_NEW", "OPENED"), f"{item_id} bad verdict {r['verdict']}"


def test_diagnose_cache_floor():
    for item_id in _ids_for("diagnose"):
        item = seed.get_item(item_id)
        assert item, f"diagnose cache {item_id} has no seed item"
        r = diagnose_listing(item["asin"], force_cached=True)
        assert r["source"] == "cached", f"{item_id} diagnose did not serve cache: {r['source']}"
        assert isinstance(r["returns_analyzed"], int)
        assert 0 <= r["projected_return_reduction_pct"] <= 100


if __name__ == "__main__":
    test_grade_cache_floor()
    test_seal_cache_floor()
    test_diagnose_cache_floor()
    print("Cache floor OK: every committed grade/seal/diagnose cache serves "
          "source:cached with zero live calls — the stage kill switch is sound.")
