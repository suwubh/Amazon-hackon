"""Buyer storefront — cart, notifications, and a demo UPI checkout.

Backs the MT9 buyer hub (Rahul). The cart is a per-Lambda-instance overlay seeded
from buyer.json — it mirrors the passport's per-instance pattern, so a cold start
resets to the seed (fine for the demo). Notifications are read-only seed. Checkout
returns an API-shaped UPI collect request (pending → success on confirm); there's no
real payment. Pure data, no LLM.
"""
from __future__ import annotations

import copy
import random

from . import lifestage, seed

# persona -> mutable cart lines, lazily seeded from buyer.json on first read.
_CARTS: dict[str, list[dict]] = {}


def _cart_lines(persona: str) -> list[dict] | None:
    persona = persona.lower()
    if persona not in _CARTS:
        data = seed.buyer_data(persona)
        if data is None:
            return None
        _CARTS[persona] = copy.deepcopy(data.get("cart", []))
    return _CARTS[persona]


def _shape(persona: str, lines: list[dict]) -> dict:
    return {
        "persona": persona,
        "lines": lines,
        "count": sum(l.get("qty", 1) for l in lines),
        "total": sum(l["price"] * l.get("qty", 1) for l in lines),
    }


def get_cart(persona: str) -> dict | None:
    lines = _cart_lines(persona)
    if lines is None:
        return None
    return _shape(persona.lower(), lines)


def add_to_cart(persona: str, asin: str, size: str | None = None, qty: int = 1) -> dict | None:
    lines = _cart_lines(persona)
    if lines is None:
        return None
    item = seed.item_by_asin(asin)
    if item is None:
        return None
    # Merge into an existing line of the same asin+size; else append a new line.
    for l in lines:
        if l["asin"] == asin and l.get("size") == size:
            l["qty"] = l.get("qty", 1) + qty
            return _shape(persona.lower(), lines)
    lines.append({
        "asin": asin,
        "item_id": item["item_id"],
        "title": item["title"],
        "category": item["category"],
        "size": size,
        "qty": qty,
        "price": item["mrp"],
        "thumb": item.get("thumb"),
    })
    return _shape(persona.lower(), lines)


def _enrich_resell(persona: str, n: dict) -> dict:
    """A 'resell' notification is the life-stage nudge: its 'idle N months / value
    dropping ₹X/month' copy is DERIVED from lifestage.py over the owner's real
    purchase date — not a hardcoded string. Falls back to the seeded body if the
    asin has no curve. Carries the life_stage block so the figures are inspectable."""
    asin = n.get("asin")
    if not asin:
        return n
    ls = lifestage.life_stage(asin, persona)
    if ls is None:
        return n
    buyers = seed.demand_point().get("buyers_waiting", 0)
    query = seed.demand_point().get("query", "this")
    body = (
        f"Idle {ls['months_owned']} months — past its typical "
        f"{ls['typical_life_months']}-month {ls['stage_label']}. "
        f"Worth about ₹{ls['current_value']:,} now, dropping ~₹{ls['decay_per_month']:,}/month. "
        f"{buyers} buyers searching “{query}” nearby — resell on Second Life?"
    )
    return {**n, "body": body, "life_stage": ls}


def get_notifications(persona: str) -> dict | None:
    data = seed.buyer_data(persona)
    if data is None:
        return None
    notes = [
        _enrich_resell(persona, n) if n.get("kind") == "resell" else n
        for n in data.get("notifications", [])
    ]
    return {"persona": persona.lower(), "notifications": notes}


def checkout(persona: str, confirm: bool = False) -> dict | None:
    """Demo UPI checkout. Without confirm → a pending collect request; with confirm →
    success (and the cart clears, like a real order would empty it)."""
    persona = persona.lower()
    data = seed.buyer_data(persona)
    lines = _cart_lines(persona)
    if data is None or lines is None:
        return None
    amount = sum(l["price"] * l.get("qty", 1) for l in lines)
    order_id = "171-" + "".join(random.choices("0123456789", k=7)) + "-SL"
    if confirm:
        _CARTS[persona] = []  # order placed → empty the cart
        return {"persona": persona, "order_id": order_id, "amount": amount,
                "upi_vpa": data.get("upi_vpa", f"{persona}@upi"), "status": "success"}
    return {"persona": persona, "order_id": order_id, "amount": amount,
            "upi_vpa": data.get("upi_vpa", f"{persona}@upi"), "status": "pending"}
