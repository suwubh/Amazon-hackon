"""Dynamic returns desk store (MT10 Fix 2).

The Ops returns desk = static return-class items (from /items) + this store. This
store holds the seeded placeholder extras plus any return a buyer initiates from
their order history (POST /returns). In-memory per-Lambda-instance, like the cart:
a cold start resets to the seed (fine for the demo; rock-solid locally). No LLM.
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone

from . import seed

# Lazily seeded from returns_seed.json; dynamic buyer returns are appended.
_RETURNS: list[dict] | None = None
_counter = 0


def _store() -> list[dict]:
    global _RETURNS
    if _RETURNS is None:
        _RETURNS = copy.deepcopy(seed.returns_seed())
    return _RETURNS


def list_returns() -> dict:
    # Newest first: dynamic buyer returns (appended) shown before seeded extras.
    return {"returns": list(reversed(_store()))}


def add_return(order: dict) -> dict:
    global _counter
    _counter += 1
    item = seed.item_by_asin(order.get("asin", "")) or {}
    entry = {
        "return_id": f"RTN-B{_counter:03d}",
        "title": order.get("title") or item.get("title") or "Returned item",
        "category": order.get("category") or item.get("category") or "other",
        "thumb": order.get("thumb") or item.get("thumb"),
        "return_reason": order.get("return_reason") or "buyer-initiated return",
        "price_paid": order.get("price_paid"),
        "order_id": order.get("order_id"),
        "persona": (order.get("persona") or "buyer").lower(),
        "source": "buyer",
        "status": "queued",
        "created_ts": datetime.now(timezone.utc).isoformat(),
    }
    _store().append(entry)
    return entry
