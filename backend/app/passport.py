"""Product Passport: append-only event log per item.

In-memory store seeded from items.json at import time; writes go through to
DynamoDB only when DYNAMODB_TABLE_NAME is set (best-effort — a DynamoDB error
never blocks the demo, see docs/db-setup.md). Cold-start loss of in-memory
events is acceptable for a demo run.
"""
import json
import logging
import os
from datetime import datetime, timezone

from . import seed

log = logging.getLogger("passport")

DYNAMODB_TABLE_NAME = os.getenv("DYNAMODB_TABLE_NAME", "")

_events: dict[str, list[dict]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _seed_baseline() -> None:
    """Every item starts life with SOLD + BIRTH_CERT_CAPTURED (+ RETURN_INITIATED if returning)."""
    for it in seed.ITEMS.values():
        ev = [
            {"ts": f"{it['order']['purchase_date']}T10:00:00Z", "event": "SOLD",
             "data": {"order_id": it["order"]["order_id"], "price_paid": it["order"]["price_paid"]}},
            {"ts": f"{it['order']['purchase_date']}T18:30:00Z", "event": "BIRTH_CERT_CAPTURED",
             "data": {"photos": ["day0_1.jpg", "day0_2.jpg"]}},
        ]
        if it["status"] == "return_initiated":
            ev.append({"ts": _now(), "event": "RETURN_INITIATED",
                       "data": {"reason": it["return_reason"]}})
        _events[it["item_id"]] = ev


_seed_baseline()


def reset() -> None:
    """Clear all live (in-memory) events back to the seeded baseline. Backs
    POST /metrics/reset so a presenter gets a clean, stable metrics number before
    a rehearsal run — the in-memory store is per-instance and the cumulative
    counter otherwise drifts up every time an item is routed. Does NOT touch
    DynamoDB history (append-only); only the per-instance working set."""
    _events.clear()
    _seed_baseline()


def append_event(item_id: str, event: str, data: dict) -> dict:
    record = {"ts": _now(), "event": event, "data": data}
    _events.setdefault(item_id, []).append(record)
    if DYNAMODB_TABLE_NAME:
        try:
            import boto3
            boto3.resource("dynamodb").Table(DYNAMODB_TABLE_NAME).put_item(
                Item={"item_id": item_id, "ts": record["ts"], "event": event,
                      "data": json.dumps(data)}
            )
        except Exception as e:
            log.warning("DynamoDB write failed (%s) — in-memory store still has the event.", e)
    return record


def get_events(item_id: str) -> list[dict]:
    return _events.get(item_id, [])


def latest_event(item_id: str, event: str) -> dict | None:
    for record in reversed(get_events(item_id)):
        if record["event"] == event:
            return record
    return None
