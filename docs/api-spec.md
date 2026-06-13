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

**MT9 — uploaded current photos (hybrid):** optional `"current_images": ["<base64>", ...]` (≤3 images, ≤~1.5 MB each *decoded*; an optional `data:image/...;base64,` prefix is stripped server-side). When present, the AI grades the **uploaded** photos as the CURRENT set against the seeded catalog + day-0 baseline; absent → seeded current photos (today's path). Oversize/too-many/invalid uploads → `422`. The response gains `"graded_uploaded_photos": true|false`. The frontend downscales to ~1024px/~300 KB before sending.
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
  "graded_uploaded_photos": false,
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
     "note": "3 matched buyers within 4 km", "distance_km": 2.7,
     "dark_store": {"id": "DS-09", "name": "Amazon Now · Indiranagar", "distance_km": 1.9}},
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
Side effect: appends `ROUTED` event. Recovery figures scale with grade (B target ≈ local +₹279 vs warehouse +₹66); local_p2p wins at every grade for this item. Ineligible paths return `recovery: 0`, `eligible: false`, an empty `breakdown` omitted, and a `note`. *(MT8)* When `local_p2p` is eligible, its path object carries `dark_store: {id, name, distance_km}` — the nearest Amazon Now MFC from `seed/dark_stores.json` (nearest-distance), so the UI can name the open-box node instead of a generic "local hop."

## GET /cascade/{item_id}  *(MT8 — derived value cascade)*
The time-decay tier waterfall, **derived** from the VRS engine — NOT a fixed timer. Re-runs the argmax week-by-week as the −5%/wk decay erodes the resale price; emits a new tier whenever the winning channel changes; terminates at `donate` (CSR) once no monetary path clears the donate credit. Requires a prior grade (`409 {"detail": "grade required"}` otherwise). Pure-Python deterministic — **no AI call, so no cache and nothing that can fail live**. Backed by `cascade.py` (reuses `vrs.py` + `pricing.py`, no new economics).
→ `200` (real output for the spine SL-001 at the current cached grade D — channels and nets are computed live by the argmax at each decayed price; depth is an honest function of the LOCKED constants, so a low-MRP ₹500 shoe falls straight from the local open-box node to the donate floor):
```json
{
  "item_id": "SL-001",
  "tiers": [
    {"week": 0, "channel": "local_p2p", "label": "Amazon Now dark store · open-box", "price": 125, "net": 83},
    {"week": 8, "channel": "donate",    "label": "donate · CSR certificate",         "price": 0,   "net": 45, "terminal": true}
  ],
  "decay_pct_per_week": 5
}
```
Each `channel` is the live VRS winner at that week's decayed price; `net` equals that path's recovery; `price` is the channel's headline sale line (0 for donate, a credit). The frontend renders these as the cascade strip (dark-store open-box → … → donate). Higher-value/repairable items cascade through more tiers (e.g. SL-006 headphones at grade C: refurbish → donate); the shoe's two-tier fall is the honest result, not a bug. This is the visible answer to "how are items that DON'T sell at the dark store handled?" — they are the tiers the cascade falls through.

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

## GET /size-advice/{asin}?persona=  *(MT7 — buyer PREVENT; MT10 adds `persona`)*
Fit social proof + Second Life resale hint for a catalog ASIN. `fit` is a seeded per-ASIN signal (footwear/apparel only; `null` for unsized items); `resale_hint` is deterministic pricing math over the seeded local buyers (grade-B resale at current local demand). `404 {"detail": "asin not in catalog"}` if the ASIN isn't a seed item.
**MT10:** the optional `?persona=rahul` query adds a `personal` block tied to that buyer's past purchases (`seed/purchase_profile.json`), matched by the item's **brand** (first word of the title) or **category** — e.g. `{"matched_on": "brand", "past_size": "M", "past_outcome": "fit_true", "recommended_size": "L", "copy": "You bought a Vastram Linen Shirt in M — it fit true to size. This Vastram runs slim, so we suggest you size up to L."}`. No persona, no match, or an unsized item → `"personal": null`.
→ `200`:
```json
{
  "asin": "B0SHOE500",
  "title": "Aurelle Women's Running Shoes",
  "category": "footwear",
  "mrp": 500,
  "thumb": "/items/SL-001/current_1.jpg",
  "fit": {
    "size_system": "UK", "your_size": "UK 8", "recommended_size": "UK 9",
    "headline_pct": 68, "direction": "up", "sample_size": 1240,
    "fit_distribution": [{"bucket": "ran small — sized up", "pct": 68}, {"bucket": "fit true to size", "pct": 25}, {"bucket": "ran large — sized down", "pct": 7}],
    "advice": "This pair runs small. 68% of UK-8 buyers ordered one size up — we suggest UK 9."
  },
  "resale_hint": {"amount": 343, "buyers_nearby": 4, "top_offer": 310}
}
```
Stateless read (no passport prereq). Backed by `seed/size_signals.json` + `size.py`.

## GET /seller/returns  *(MT7 — seller PREVENT)*
Seller catalog sorted worst-first by return rate. `return_rate_pct` is computed (`returns/units_sold`); `diagnosable` SKUs (kurta, shoe) have a `/diagnose-listing` drill-down whose `returns_analyzed` equals this row's `returns`.
→ `200 {"seller": {"name": "Vastram Apparel & Goods", "store_id": "A1SELLER42", "quarter": "Q2 FY26"}, "skus": [{"asin": "B0KURTA01", "item_id": "SL-003", "title": "...", "category": "apparel", "thumb": "...", "units_sold": 64, "returns": 18, "top_return_reason": "colour not as shown", "diagnosable": true, "return_rate_pct": 28}, ...], "total_units_sold": 3334, "total_returns": 117}`
Stateless read. Backed by `seed/seller_catalog.json` + `seller.py`.

## GET /orders/{persona}  *(MT7 — buyer RECIRCULATE entry; MT10 adds return-window fields)*
A persona's order history with a `resellable` flag (true when the ASIN has dormant units on the radar) and **MT10 return-window fields** (`return_window_open`, `return_by`, `days_left` — a 10-day window from `purchase_date`, computed against the demo date 2026-06-13). The resellable order (monitor) feeds the new resell flow (`/resell/*`); orders inside the window show an active Return button (→ `POST /returns`). `404` if the persona has no seeded history.
→ `200 {"persona": "rahul", "orders": [{"order_id": "171-7781002-RH04", "asin": "B0KURTA01", "title": "Vastram Men's Cotton Kurta (Navy Blue)", "purchase_date": "2026-06-09", "price_paid": 899, "status": "delivered", "return_window_open": true, "return_by": "2026-06-19", "days_left": 6, "item_id": "SL-003", "resellable": false}, {"order_id": "171-8835520-SL002", "asin": "B0MONITOR1", "purchase_date": "2024-11-02", "return_window_open": false, "return_by": "2024-11-12", "days_left": 0, "item_id": "SL-002", "resellable": true}]}`
Stateless read. Backed by `seed/orders.json → {persona}_order_history` + `orders.py`.

## GET /returns · POST /returns  *(MT10 — Ops returns desk)*
The Ops returns desk = static return-class items (`/items` where `status` is `return_initiated`/`rto_in_transit`) **+** this store. The store holds seeded placeholder extras (`seed/returns_seed.json`) plus any return a buyer initiates from order history. In-memory **per-Lambda-instance** (cart pattern) — a cold start resets to the seed.
- `GET /returns` → `200 {"returns": [{"return_id": "RTN-B001", "title": "...", "category": "apparel", "thumb": "...", "return_reason": "...", "price_paid": 899, "order_id": "...", "persona": "rahul", "source": "buyer"|"seed", "status": "queued", "created_ts": "..."}, ...]}` (newest first; buyer returns ahead of seeded extras).
- `POST /returns` body `{"persona": "rahul", "order_id": "...", "asin": "B0KURTA01", "title": "...", "category": "apparel"?, "thumb": "..."?, "return_reason": "..."?, "price_paid": 899?}` → appends a `source:"buyer"` entry (`return_id` `RTN-B00N`) and returns it. The buyer's Return button posts here; the row then shows on the Ops desk.

## POST /resell/quote  *(MT10 — resell economics)*
Deterministic resale economics for an order item; trades reach for price. Body `{"item_id": "SL-002", "range_km": 7, "grade": "B"?}` (grade defaults to B). `reachable_buyers` = seeded local buyers within `range_km` (`seed.buyers_for_asin`); `best_price` lifts `ai_suggested` by the demand multiplier of those buyers; `delivery_cut = 25 + 6·range_km` (Amazon's cut, grows with reach); `net = best_price − delivery_cut` (peaks mid-range). `points` is a liquidity curve for the price slider. `404` if the item isn't a seed item.
→ `200 {"item_id": "SL-002", "range_km": 7, "grade": "B", "ai_suggested": 978, "reachable_buyers": 3, "best_price": 1076, "delivery_cut": 67, "net": 1009, "points": [{"price": 1076, "est_days_to_sell": 3, "buyers_at_price": 3}, ...], "recommended": 1550, "range_tiers": [{"range_km": 3, "reachable_buyers": 1, "delivery_cut": 43}, {"range_km": 7, "reachable_buyers": 3, "delivery_cut": 67}, {"range_km": 15, "reachable_buyers": 4, "delivery_cut": 115}]}`

## POST /resell/listings · GET /resell/listings · GET /resell/listings/{id} · POST /resell/listings/{id}/interest  *(MT10 — flash-deals board + live cross-tab interest)*
In-memory **per-Lambda-instance** marketplace (seeded with 2 starter listings so the board isn't empty). Cross-tab works locally (one uvicorn process) and on a single warm Lambda.
- `POST /resell/listings` body `{"item_id": "SL-002", "persona": "rahul", "ask_price": 1000, "range_km": 7}` → `200 {"listing_id": "RL-003", "item_id": "...", "asin": "...", "title": "...", "thumb": "...", "ask_price": 1000, "range_km": 7, "delivery_cut": 67, "net": 933, "owner": "rahul", "interests": [], "created_ts": "..."}`.
- `GET /resell/listings` → `200 {"listings": [ ...newest first... ]}` (the public board).
- `GET /resell/listings/{id}` → the listing incl. its `interests` (the reseller polls this for the live feed). `404` if unknown.
- `POST /resell/listings/{id}/interest` body `{"buyer_name": "..."?, "distance_km": 2.4?, "offer": 1000?}` (all optional — auto-filled from a buyer pool, offer defaults to the ask) → the updated listing with the new interest appended (`{"interest_id": "IN-001", "buyer_name": "...", "distance_km": 2.4, "offer": 1000, "status": "pending", "ts": "..."}`).
- `POST /resell/listings/{id}/sell` body `{"interest_id": "IN-001"}` *(MT10.1)* → the reseller accepts that buyer. Listing flips to `status: "sold"`, `sold_to` = that interest (now `status: "accepted"`), other pending interests → `passed`, and `net_earned` = `offer − delivery_cut` is added. `404` if the listing or interest is unknown.
- `POST /resell/listings/{id}/decline` body `{"interest_id": "IN-001"}` *(MT10.1)* → marks that interest `status: "declined"`; the listing stays `active` for other buyers. `404` if unknown. Listings now also carry `status` (`active`/`sold`) and `sold_to` (null until sold).

## GET /cart/{persona}  *(MT9 — buyer storefront)*
The persona's cart (per-Lambda-instance overlay, seeded from `seed/buyer.json`; a cold start resets to the seed). Total + count are computed server-side. `404` if the persona has no seeded storefront.
→ `200 {"persona": "rahul", "lines": [{"asin": "B0SHOE500", "item_id": "SL-001", "title": "...", "category": "footwear", "size": "UK 9", "qty": 1, "price": 500, "thumb": "/items/SL-001/current_1.jpg"}, ...], "count": 2, "total": 1399}`

## POST /cart/{persona}  *(MT9)*
Body: `{"asin": "B0HDPHN880", "size": "UK 9"|null, "qty": 1}`. Appends a line (merges qty into an existing asin+size line); resolves title/price/thumb from the catalog. Returns the same shape as `GET /cart`. `404` if the asin isn't in the catalog or the persona has no storefront.

## GET /notifications/{persona}  *(MT9)*
Seeded notifications; the hero (`kind: "resell"`, `hero: true`) references the idle monitor (`SL-002` / `B0MONITOR1`) → a tap feeds the resell → `/radar` flow. `404` if none.
→ `200 {"persona": "rahul", "notifications": [{"id": "n-resell", "kind": "resell", "hero": true, "asin": "B0MONITOR1", "item_id": "SL-002", "title": "...", "body": "...", "cta": "Resell now", "ts": "just now"}, {"kind": "price_drop"|"delivery", ...}]}`

## POST /checkout/{persona}  *(MT9 — demo UPI)*
Body: `{"confirm": false}`. No real payment — an API-returned UPI collect request. `confirm: false` → `status: "pending"`; `confirm: true` → `status: "success"` and the cart is emptied. `amount` = current cart total; `upi_vpa` from the seed. `404` if the persona has no storefront. The frontend keeps the order id + amount the user approved across the pending→success flip (the cart is per-instance, so a confirm on another warm instance could otherwise recompute a different total).
→ `200 {"persona": "rahul", "order_id": "171-7697281-SL", "amount": 1399, "upi_vpa": "rahul@okhdfc", "status": "pending"|"success"}`

## GET /metrics
Running demo counters (from passport events this session + seeded baseline).
→ `200 {"items_processed": 8, "rupees_recovered": 4830, "rupees_vs_writeoff_baseline": 5390, "warehouse_bypass_pct": 62, "co2_saved_kg": 14.2, "landfill_diverted_kg": 6.1, "inspection_hours_saved": 2.7}`

## POST /chat — legacy boilerplate, kept but unused by the UI.
