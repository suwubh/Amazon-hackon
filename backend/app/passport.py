"""Product Passport: append-only event log per item.

In-memory store seeded from items.json at import time; writes go through to
DynamoDB (best-effort, via store.py) when DYNAMODB_TABLE_NAME is set. A DynamoDB
error never blocks the demo (see docs/db-setup.md).

Cross-instance / cold-start integrity (audit finding 2): the spine reads the
latest GRADED / ROUTED / SEAL_CHECKED event via latest_event() to decide whether
to route or build a Health Card. On a cold start (or when a parallel Lambda
instance graded the item), this instance's in-memory log has only the seeded
baseline, so latest_event() reads back from DynamoDB on a miss — the grade→route
→health-card chain survives an instance swap instead of 409-ing mid-demo.
"""
import logging
from datetime import datetime, timezone

from . import seed, store

log = logging.getLogger("passport")

_events: dict[str, list[dict]] = {}


def _now() -> str:
    # Microsecond resolution so two events on the same item in the same second get
    # distinct DynamoDB sort keys (second-resolution keys would overwrite).
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


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
    # Write-through to DynamoDB (best-effort; no-ops when the table is unset).
    store.put(item_id, record["ts"], {"event": event, "data": data})
    return record


def get_events(item_id: str) -> list[dict]:
    # In-memory only by design: /metrics + green-ledger count off this log and
    # POST /metrics/reset clears it, so it stays per-instance and resettable.
    return _events.get(item_id, [])


def _dynamo_events(item_id: str) -> list[dict]:
    """The item's events read back from DynamoDB, oldest-first. [] when the table
    is unset or unreachable (the demo then relies on the in-memory log). Uses a
    strongly-consistent read so an event written moments earlier (on this or a
    parallel instance) is guaranteed visible — the passport is the source of truth."""
    rows = store.query(item_id, consistent=True)
    out = [{"ts": r["sk"], "event": r["data"].get("event"), "data": r["data"].get("data", {})}
           for r in rows if r.get("data", {}).get("event")]
    out.sort(key=lambda r: r["ts"])
    return out


def latest_event(item_id: str, event: str) -> dict | None:
    # DynamoDB-first: the passport table is the single source of truth across all
    # Lambda instances, so a grade written on ANY instance is visible to the next
    # route/health-card call — not just the warm instance that produced it. The read
    # is strongly consistent (see _dynamo_events) so a just-written event can't be
    # missed. Trades a little read latency for a globally-consistent view.
    if store.enabled():
        for record in reversed(_dynamo_events(item_id)):
            if record["event"] == event:
                return record
    # Fallback: the per-instance in-memory log. This is the ONLY path when DynamoDB
    # is unconfigured/unreachable, and the safety net if a best-effort write never
    # landed in the table but the in-memory append did.
    for record in reversed(_events.get(item_id, [])):
        if record["event"] == event:
            return record
    return None
