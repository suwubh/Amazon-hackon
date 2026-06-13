import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from mangum import Mangum
from .llm import ask_llm
from . import grading, passport, seed, vrs, healthcard, radar, inspection, pricing, metrics

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
        return grading.grade_item(body.item_id, force_cached=body.force_cached)
    except KeyError:
        raise HTTPException(status_code=404, detail="item not found")
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


# Lambda entrypoint. Locally you still run: uvicorn app.main:app --reload --port 8080
handler = Mangum(app)