"""Capture live AI responses into the committed cache.

Run from backend/ with creds in .env:
    python scripts/capture_cache.py [SL-001 ...]      # grade every item w/ photos
    python scripts/capture_cache.py --seal SL-004     # capture seal-check
    python scripts/capture_cache.py --diagnose SL-003 # capture listing diagnostics

Writes seed/cached/{id}.{grade|seal|diagnose}.json. At request time these serve as
the source:"cached" fallback when both providers fail (or before photos exist).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import seed  # noqa: E402
from app.grading import PROVIDER_MODEL, _grade_live  # noqa: E402
from app import inspection  # noqa: E402


def _write(item_id: str, call: str, data: dict) -> None:
    path = seed.CACHED_DIR / f"{item_id}.{call}.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"{item_id}: {call} -> {path.name}")


def capture_grade(item_id: str) -> None:
    item = seed.get_item(item_id)
    if item is None:
        print(f"{item_id}: unknown item, skipped"); return
    if not seed.item_images(item_id)["current"]:
        print(f"{item_id}: no current photos yet, skipped"); return
    core, provider = _grade_live(item)
    _write(item_id, "grade", {**core.model_dump(), "model": PROVIDER_MODEL[provider]})


def capture_seal(item_id: str) -> None:
    res = inspection.seal_check(item_id)
    if res["source"] == "cached":
        print(f"{item_id}: no photo — seal still served from existing cache"); return
    keep = ("sealed", "tamper_evidence", "verdict", "confidence", "model")
    _write(item_id, "seal", {k: res[k] for k in keep})


def capture_diagnose(item_id: str) -> None:
    item = seed.get_item(item_id)
    if item is None:
        print(f"{item_id}: unknown item, skipped"); return
    res = inspection.diagnose_listing(item["asin"])
    if res["source"] == "cached":
        print(f"{item_id}: no photos — diagnose still served from existing cache"); return
    keep = ("returns_analyzed", "discrepancies", "patch", "projected_return_reduction_pct", "model")
    _write(item_id, "diagnose", {k: res[k] for k in keep})


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] == "--seal":
        for i in args[1:]:
            capture_seal(i)
    elif args and args[0] == "--diagnose":
        for i in args[1:]:
            capture_diagnose(i)
    else:
        for item_id in (args or list(seed.ITEMS)):
            capture_grade(item_id)


if __name__ == "__main__":
    main()
