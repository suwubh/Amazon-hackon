"""Buyer order history — the entry point for RECIRCULATE.

Exposes a persona's seeded order history with: a return-window flag (the 10-day
Amazon-style return window, Fix 1) and a resellable flag (the product has live local
demand on the Idle Asset Radar). The monitor is resellable → a one-tap resell flows
into the new resell flow (/resell/*). Pure data, no LLM.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from . import seed

RETURN_WINDOW_DAYS = 10


def _demo_today() -> date:
    """Anchor demo 'today' to just after the most recent seeded order so the
    return window is always open for the recent orders, no matter what calendar
    date the demo runs on (LOW 8 — avoids a stale hardcoded date that silently
    closes the window if the demo slips a few days)."""
    latest = None
    for o in seed.order_history("rahul") or []:
        try:
            d = datetime.strptime(o["purchase_date"], "%Y-%m-%d").date()
        except (ValueError, TypeError, KeyError):
            continue
        if latest is None or d > latest:
            latest = d
    return (latest + timedelta(days=2)) if latest else date(2026, 6, 13)


# Demo "today", derived once at import. With the current seed (latest order
# 2026-06-11) this is 2026-06-13 — unchanged numbers, now self-updating.
TODAY = _demo_today()


def _window(purchase_date: str) -> dict:
    try:
        d = datetime.strptime(purchase_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return {"return_window_open": False, "return_by": None, "days_left": 0}
    by = d + timedelta(days=RETURN_WINDOW_DAYS)
    days_left = (by - TODAY).days
    return {
        "return_window_open": days_left >= 0,
        "return_by": by.isoformat(),
        "days_left": max(0, days_left),
    }


def order_history(persona: str) -> list[dict] | None:
    history = seed.order_history(persona)
    if history is None:
        return None
    out = []
    for o in history:
        item = seed.item_by_asin(o["asin"])
        out.append({
            **o,
            **_window(o["purchase_date"]),
            "item_id": item["item_id"] if item else None,
            "resellable": bool(seed.dormant_units(o["asin"])),
        })
    return out
