"""Product Health Card — the trust artifact that travels with the item.

Assembles provenance (from the order/invoice), the delta-grade report (from the
passport), the recovered/suggested price + time-decay curve (from the routing
decision), and a transferable-warranty calculation. Requires the item to have
been graded and routed.
"""
from __future__ import annotations

from . import passport, pricing, seed


class NeedsGradeAndRoute(Exception):
    """/health-card called before the item was graded and routed."""


def _photo_urls(item_id: str) -> list[str]:
    imgs = seed.item_images(item_id)
    return [f"/items/{item_id}/{p.name}" for p in imgs["day0"] + imgs["current"]]


def health_card(item_id: str) -> dict:
    item = seed.get_item(item_id)
    if item is None:
        raise KeyError(item_id)

    graded = passport.latest_event(item_id, "GRADED")
    routed = passport.latest_event(item_id, "ROUTED")
    if graded is None or routed is None:
        raise NeedsGradeAndRoute(item_id)

    g, r = graded["data"], routed["data"]
    order = item["order"]
    suggested = r["resale_value"]

    total_months = item["warranty_months"]
    remaining = max(0, total_months - item["age_months"])

    return {
        "item_id": item_id,
        "title": item["title"],
        "grade": g["grade"],
        "defects": g.get("defects", []),
        "justification": g.get("justification", ""),
        "provenance": {
            "purchase_date": order["purchase_date"],
            "price_paid": order["price_paid"],
            "invoice_verified": bool(order.get("invoice_id")),
            "single_owner": True,
        },
        "warranty": {
            "total_months": total_months,
            "remaining_months": remaining,
            "transferable": remaining > 0,
        },
        "suggested_price": suggested,
        "price_decay": pricing.price_decay(suggested),
        "photos": _photo_urls(item_id),
    }
