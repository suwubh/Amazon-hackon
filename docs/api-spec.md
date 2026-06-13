# API Spec — Amazon Second Life

Base URL (deployed): `https://ahwfmhaqed45p5xxk2u663oi6m0mejgi.lambda-url.ca-central-1.on.aws`
Local: `http://localhost:8080`. All endpoints JSON. CORS: app-level via `ALLOWED_ORIGINS`.

**Common errors:** `404 {"detail": "item not found"}` for unknown `item_id`/`asin` · `422` FastAPI validation · `502 {"detail": "ai_unavailable"}` only if both providers fail AND no cache exists (cannot happen for seeded items — every seeded item ships with cached responses).

**AI-backed responses** (`/grade`, `/seal-check`, `/diagnose-listing`) always include `"source": "live-bedrock" | "live-gemini" | "cached"` and `"model"`.

---

## GET /health
→ `200 {"status": "ok"}` (exists, unchanged)

## GET /items
Returns inbox + all seeded demo items.
→ `200 {"items": [{"item_id": "SL-001", "asin": "B0SHOE500", "title": "Aurelle Women's Running Shoes", "category": "footwear", "mrp": 500, "age_months": 1, "status": "return_initiated", "persona": "priya", "thumb": "/items/SL-001/current_1.jpg", "return_reason": "size too small", "rto": false}, ...]}`

## GET /items/{item_id}
Item detail + full passport event log.
→ `200 {"item": {...as above plus order: {order_id, purchase_date, price_paid, invoice_id}}, "passport": [{"ts": "2026-06-13T10:00:00Z", "event": "SOLD" | "BIRTH_CERT_CAPTURED" | "RETURN_INITIATED" | "GRADED" | "ROUTED" | "LISTED" | "SOLD_SECOND_LIFE" | "DONATED", "data": {...}}]}`

## POST /grade
Body: `{"item_id": "SL-001", "force_cached": false}` — photos come from the seed store (current photos for the item); `force_cached: true` skips the live call (stage safety toggle).
→ `200`:
```json
{
  "item_id": "SL-001",
  "same_unit": {"verified": true, "confidence": 0.94},
  "grade": "B",
  "defects": [{"area": "sole-heel-left", "description": "moderate tread wear", "severity": "moderate"}],
  "completeness": [{"item": "original box", "present": true}, {"item": "spare laces", "present": false}],
  "usage_detected": true,
  "confidence": 0.91,
  "justification": "Light, even wear consistent with brief indoor use; structurally like-new.",
  "needs_human_review": false,
  "source": "live-bedrock",
  "model": "us.amazon.nova-2-lite-v1:0",
  "latency_ms": 1840
}
```
Side effect: appends `GRADED` passport event. `needs_human_review = confidence < 0.70`.

## POST /route
Body: `{"item_id": "SL-001"}` (requires a prior grade; `409 {"detail": "grade required"}` otherwise).
→ `200` (real output for SL-001 at the current cached grade D; every `recovery` equals the sum of its `breakdown`):
```json
{
  "item_id": "SL-001",
  "resale_value": 132,
  "paths": [
    {"path": "local_p2p", "recovery": 83, "eligible": true, "winner": true,
     "breakdown": {"sale_price": 125, "local_hop": -40, "payment_fee": -2},
     "note": "3 matched buyers within 4 km", "distance_km": 2.7},
    {"path": "warehouse_relist", "recovery": -129, "eligible": true, "winner": false,
     "breakdown": {"sale_price": 121, "reverse_ship": -120, "inspection": -40, "relist": -60, "fc_handling": -30}},
    {"path": "refurbish", "recovery": 0, "eligible": false, "winner": false, "note": "not economical to refurbish this item"},
    {"path": "donate", "recovery": 45, "eligible": true, "winner": false, "breakdown": {"csr_tax_credit": 75, "pickup": -30}},
    {"path": "liquidate", "recovery": 40, "eligible": true, "winner": false, "breakdown": {"sale_price": 60, "bulk_handling": -20}},
    {"path": "rto_relist", "recovery": 0, "eligible": false, "winner": false, "note": "not an RTO item"}
  ],
  "decision": "local_p2p",
  "co2_saved_kg": 2.1,
  "km_saved": 597
}
```
Side effect: appends `ROUTED` event. Recovery figures scale with grade (B target ≈ local +₹279 vs warehouse +₹66); local_p2p wins at every grade for this item. Ineligible paths return `recovery: 0`, `eligible: false`, an empty `breakdown` omitted, and a `note`.

## GET /health-card/{item_id}
Requires grade + route (`409` otherwise).
→ `200 {"item_id", "title", "grade", "defects": [...], "justification", "provenance": {"purchase_date", "price_paid", "invoice_verified": true, "single_owner": true}, "warranty": {"total_months": 12, "remaining_months": 8, "transferable": true}, "suggested_price": 310, "price_decay": [{"week": 0, "price": 310}, {"week": 1, "price": 295}, ...], "photos": [...]}`
Side effect: appends `LISTED` event.

## POST /seal-check
Body: `{"item_id": "SL-004"}` (an RTO-flagged seed item; `409` if `rto: false`).
→ `200 {"item_id", "sealed": true, "tamper_evidence": null, "verdict": "SEALED_NEW", "confidence": 0.96, "source": "live-bedrock", "model": "..."}`
Side effect: marks item eligible for `rto_relist` path.

## GET /radar/{asin}
Idle Asset Radar: dormant units of this ASIN near the demand point (demo uses a fixed seeded location).
→ `200 {"asin", "demand": {"query": "baby monitor", "buyers_waiting": 3}, "dormant_units": [{"item_id": "SL-002", "owner": "Rahul S.", "purchased_months_ago": 19, "distance_km": 2.3, "est_value": 1800, "ping_message": "Someone nearby will pay ₹1,800 for your monitor — sell in one tap."}, ...], "total_dormant_value": 21400}`

## GET /price-curve/{item_id}
Liquidity slider data (requires grade).
→ `200 {"item_id", "points": [{"price": 1400, "est_days_to_sell": 1, "buyers_at_price": 3}, {"price": 1550, "est_days_to_sell": 4, "buyers_at_price": 1}, {"price": 1650, "est_days_to_sell": 8, "buyers_at_price": 1}], "recommended": 1500}`

## POST /diagnose-listing
Body: `{"asin": "B0KURTA01"}` (seed item with listing-vs-reality mismatch).
→ `200 {"asin", "returns_analyzed": 18, "discrepancies": [{"aspect": "color", "listing_shows": "navy blue", "returns_show": "royal blue"}], "patch": {"field": "title/photos", "current_text": "...", "suggested_text": "..."}, "projected_return_reduction_pct": 40, "source": "live-bedrock"}`

## GET /metrics
Running demo counters (from passport events this session + seeded baseline).
→ `200 {"items_processed": 8, "rupees_recovered": 4830, "rupees_vs_writeoff_baseline": 5390, "warehouse_bypass_pct": 62, "co2_saved_kg": 14.2, "landfill_diverted_kg": 6.1, "inspection_hours_saved": 2.7}`

## POST /chat — legacy boilerplate, kept but unused by the UI.
