import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from mangum import Mangum
from .llm import ask_llm
from . import grading, passport, seed, vrs, healthcard, radar, inspection, pricing, metrics
from . import size, seller, orders as orders_mod, buyer, cascade as cascade_mod
from . import returns as returns_mod, resell as resell_mod, second_life as second_life_mod

app = FastAPI(title="Amazon Second Life API")

# --- CORS ---
# Handled HERE, in the app (works for both local uvicorn AND Lambda).
# IMPORTANT: keep CORS DISABLED on the Lambda Function URL, or Lambda will
# answer the OPTIONS preflight itself and bypass this config.
# Origins are read from an env var (comma-separated) so you can add one
# without a code change. Default covers local dev + your deployed frontend.
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,        # no cookies/auth, so keep this False
    allow_methods=["GET", "POST"],  # only what the API actually uses
    allow_headers=["Content-Type"],
)


class ChatIn(BaseModel):
    # Cap input length: the endpoint is public/unauthenticated, so an unbounded
    # prompt is a direct token-cost lever for abuse. 4000 chars is generous for
    # a chat turn; oversized requests get a 422 before they ever reach the LLM.
    message: str = Field(..., min_length=1, max_length=4000)


class ChatOut(BaseModel):
    reply: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatOut)
def chat(body: ChatIn):
    return ChatOut(reply=ask_llm(body.message))


class GradeIn(BaseModel):
    item_id: str = Field(..., min_length=1, max_length=20)
    force_cached: bool = False
    # Optional uploaded current photos (base64). The agent captures the unit's
    # current state at handoff; we grade THESE against the seeded day-0 baseline.
    # Capped at 3 here (count); per-image byte size is enforced in grading.py.
    current_images: list[str] | None = Field(default=None, max_length=3)


@app.get("/items")
def items():
    return {"items": seed.list_items()}


@app.get("/items/{item_id}")
def item_detail(item_id: str):
    item = seed.get_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="item not found")
    return {"item": item, "passport": passport.get_events(item_id)}


@app.post("/grade")
def grade(body: GradeIn):
    try:
        return grading.grade_item(
            body.item_id,
            force_cached=body.force_cached,
            current_images=body.current_images,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="item not found")
    except grading.ImageTooLarge:
        raise HTTPException(status_code=422, detail="uploaded image too large")
    except ValueError:
        raise HTTPException(status_code=422, detail="invalid uploaded image")
    except grading.CacheMiss:
        raise HTTPException(status_code=502, detail="ai_unavailable")


class ItemIn(BaseModel):
    item_id: str = Field(..., min_length=1, max_length=20)


class SealIn(ItemIn):
    force_cached: bool = False


class DiagnoseIn(BaseModel):
    asin: str = Field(..., min_length=1, max_length=20)
    force_cached: bool = False


@app.post("/route")
def route(body: ItemIn):
    try:
        return vrs.route_item(body.item_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="item not found")
    except vrs.NeedsGrade:
        raise HTTPException(status_code=409, detail="grade required")


@app.get("/cascade/{item_id}")
def get_cascade(item_id: str):
    """Derived terminal-state waterfall (MT8): VRS argmax re-run week-by-week over
    −5%/wk decay. Pure-Python, no AI. Requires a prior grade (409 otherwise)."""
    try:
        return cascade_mod.cascade(item_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="item not found")
    except vrs.NeedsGrade:
        raise HTTPException(status_code=409, detail="grade required")


@app.get("/health-card/{item_id}")
def health_card(item_id: str):
    try:
        return healthcard.health_card(item_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="item not found")
    except healthcard.NeedsGradeAndRoute:
        raise HTTPException(status_code=409, detail="grade and route required")


@app.post("/seal-check")
def seal_check(body: SealIn):
    item = seed.get_item(body.item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="item not found")
    if not item.get("rto"):
        raise HTTPException(status_code=409, detail="not an RTO item")
    try:
        return inspection.seal_check(body.item_id, force_cached=body.force_cached)
    except inspection.CacheMiss:
        raise HTTPException(status_code=502, detail="ai_unavailable")


@app.get("/radar/{asin}")
def radar_for(asin: str):
    result = radar.radar(asin)
    if result is None:
        raise HTTPException(status_code=404, detail="no dormant units for this asin")
    return result


@app.get("/price-curve/{item_id}")
def price_curve(item_id: str):
    item = seed.get_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="item not found")
    graded = passport.latest_event(item_id, "GRADED")
    if graded is None:
        raise HTTPException(status_code=409, detail="grade required")
    buyers = seed.buyers_for_asin(item["asin"], vrs.LOCAL_RADIUS_KM)
    demand = pricing.demand_multiplier(len(buyers))
    resale = pricing.resale_value(item["mrp"], item["category"], item["age_months"],
                                  graded["data"]["grade"], demand)
    curve = pricing.liquidity_curve([b["max_price"] for b in buyers], resale)
    return {"item_id": item_id, **curve}


@app.post("/diagnose-listing")
def diagnose_listing(body: DiagnoseIn):
    try:
        return inspection.diagnose_listing(body.asin, force_cached=body.force_cached)
    except KeyError:
        raise HTTPException(status_code=404, detail="item not found")
    except inspection.CacheMiss:
        raise HTTPException(status_code=502, detail="ai_unavailable")


@app.get("/metrics")
def get_metrics():
    return metrics.metrics()


@app.post("/metrics/reset")
def reset_metrics():
    """Clear live passport events back to the seeded baseline so the impact
    counter is stable across rehearsal runs (the cumulative metric otherwise
    drifts up each time an item is routed). Presenter tool — not wired to any UI."""
    passport.reset()
    return metrics.metrics()


# --- MT7: two-sided console (Prevent + Recirculate) ---


@app.get("/size-advice/{asin}")
def size_advice(asin: str, persona: str | None = None):
    """Buyer PDP: fit social proof (sized items) + personal history note + resale hint."""
    result = size.size_advice(asin, persona=persona)
    if result is None:
        raise HTTPException(status_code=404, detail="asin not in catalog")
    return result


@app.get("/seller/returns")
def seller_returns():
    """Seller dashboard: catalog sorted worst-first by return rate."""
    return seller.seller_returns()


@app.get("/orders/{persona}")
def orders(persona: str):
    """Buyer order history with a resellable flag per order."""
    result = orders_mod.order_history(persona)
    if result is None:
        raise HTTPException(status_code=404, detail="no order history for this persona")
    return {"persona": persona, "orders": result}


@app.get("/second-life/{asin}")
def second_life(asin: str):
    """Buyer PDP: recovered units of this product on offer near the shopper
    (price from the pricing engine; grade/distance/eta seeded). Empty offers
    list if the product has no nearby Second Life inventory."""
    result = second_life_mod.second_life(asin)
    if result is None:
        raise HTTPException(status_code=404, detail="asin not in catalog")
    return result


# --- MT9: buyer storefront (cart · notifications · UPI checkout) ---


class CartLineIn(BaseModel):
    asin: str = Field(..., min_length=1, max_length=20)
    size: str | None = Field(default=None, max_length=20)
    qty: int = Field(default=1, ge=1, le=10)


class CheckoutIn(BaseModel):
    confirm: bool = False


@app.get("/cart/{persona}")
def get_cart(persona: str):
    result = buyer.get_cart(persona)
    if result is None:
        raise HTTPException(status_code=404, detail="no cart for this persona")
    return result


@app.post("/cart/{persona}")
def add_to_cart(persona: str, body: CartLineIn):
    result = buyer.add_to_cart(persona, body.asin, size=body.size, qty=body.qty)
    if result is None:
        raise HTTPException(status_code=404, detail="asin not in catalog")
    return result


@app.get("/notifications/{persona}")
def get_notifications(persona: str):
    result = buyer.get_notifications(persona)
    if result is None:
        raise HTTPException(status_code=404, detail="no notifications for this persona")
    return result


@app.post("/checkout/{persona}")
def checkout(persona: str, body: CheckoutIn):
    result = buyer.checkout(persona, confirm=body.confirm)
    if result is None:
        raise HTTPException(status_code=404, detail="no cart for this persona")
    return result


# --- MT10: Ops returns desk (seeded extras + buyer-initiated returns) ---


class ReturnIn(BaseModel):
    persona: str = Field(default="buyer", max_length=20)
    order_id: str | None = Field(default=None, max_length=40)
    asin: str | None = Field(default=None, max_length=20)
    title: str | None = Field(default=None, max_length=120)
    category: str | None = Field(default=None, max_length=30)
    thumb: str | None = Field(default=None, max_length=120)
    return_reason: str | None = Field(default=None, max_length=120)
    price_paid: int | None = Field(default=None, ge=0, le=10_000_000)


@app.get("/returns")
def get_returns():
    """Ops returns desk: seeded extras + dynamic buyer-initiated returns."""
    return returns_mod.list_returns()


@app.post("/returns")
def post_return(body: ReturnIn):
    """A buyer initiates a return from order history → lands on the Ops desk."""
    return returns_mod.add_return(body.model_dump())


# --- MT10: resell marketplace (quote · listings · live interest) ---


class ResellQuoteIn(BaseModel):
    item_id: str = Field(..., min_length=1, max_length=20)
    range_km: int = Field(default=7, ge=1, le=50)
    grade: str | None = Field(default=None, max_length=2)


class ResellListIn(BaseModel):
    item_id: str = Field(..., min_length=1, max_length=20)
    persona: str = Field(default="rahul", max_length=20)
    ask_price: int = Field(..., ge=1, le=10_000_000)
    range_km: int = Field(default=7, ge=1, le=50)


class InterestIn(BaseModel):
    buyer_name: str | None = Field(default=None, max_length=40)
    distance_km: float | None = Field(default=None, ge=0, le=100)
    offer: int | None = Field(default=None, ge=0, le=10_000_000)


class SellIn(BaseModel):
    interest_id: str = Field(..., min_length=1, max_length=20)


@app.post("/resell/quote")
def resell_quote(body: ResellQuoteIn):
    result = resell_mod.quote(body.item_id, body.range_km, grade=body.grade or "B")
    if result is None:
        raise HTTPException(status_code=404, detail="item not found")
    return result


@app.post("/resell/listings")
def resell_create(body: ResellListIn):
    result = resell_mod.create_listing(body.item_id, body.persona, body.ask_price, body.range_km)
    if result is None:
        raise HTTPException(status_code=404, detail="item not found")
    return result


@app.get("/resell/listings")
def resell_listings():
    return resell_mod.list_listings()


@app.get("/resell/listings/{listing_id}")
def resell_listing(listing_id: str):
    result = resell_mod.get_listing(listing_id)
    if result is None:
        raise HTTPException(status_code=404, detail="listing not found")
    return result


@app.post("/resell/listings/{listing_id}/interest")
def resell_interest(listing_id: str, body: InterestIn):
    result = resell_mod.add_interest(listing_id, body.buyer_name, body.distance_km, body.offer)
    if result is None:
        raise HTTPException(status_code=404, detail="listing not found")
    return result


@app.post("/resell/listings/{listing_id}/sell")
def resell_sell(listing_id: str, body: SellIn):
    """The reseller one-tap sells to a chosen interested buyer → listing marked sold."""
    result = resell_mod.sell_to_interest(listing_id, body.interest_id)
    if result is None:
        raise HTTPException(status_code=404, detail="listing or interest not found")
    return result


@app.post("/resell/listings/{listing_id}/decline")
def resell_decline(listing_id: str, body: SellIn):
    """The reseller declines one interested buyer; the listing stays active for others."""
    result = resell_mod.decline_interest(listing_id, body.interest_id)
    if result is None:
        raise HTTPException(status_code=404, detail="listing or interest not found")
    return result


# Lambda entrypoint. Locally you still run: uvicorn app.main:app --reload --port 8080
handler = Mangum(app)