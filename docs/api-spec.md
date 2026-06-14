# API Specification: Amazon Second Life

The Amazon Second Life service exposes a set of REST endpoints for product lifecycle management, automated grading, dynamic routing, and secondary listings.

### Base URLs
- **Production API:** `https://ahwfmhaqed45p5xxk2u663oi6m0mejgi.lambda-url.ca-central-1.on.aws`
- **Development API:** `http://localhost:8080`

*All request and response bodies use JSON formatting. CORS is configured at the application level via the `ALLOWED_ORIGINS` environment variable.*

### Error Handling
- **404 Not Found:** Returned when the requested `item_id` or `asin` does not exist in the database catalog. Example: `{"detail": "item not found"}`
- **422 Unprocessable Entity:** Returned for validation errors on request fields (e.g., malformed JSON, out-of-bounds metrics, or base64 photo sizes exceeding limits).
- **502 Bad Gateway:** Returned if backend upstream systems (such as AI models or fallbacks) fail to respond. Example: `{"detail": "ai_unavailable"}`

### Intelligent Failover Strategy
AI-powered endpoints (`/grade`, `/seal-check`, and `/diagnose-listing`) implement a highly resilient multi-tier orchestration pattern. They return metadata indicating the model and provider used in the response:
- **Primary Provider:** Gemini 2.5 Flash (configured for JSON output mode)
- **Secondary Failover:** Amazon Bedrock (Nova 2 Lite)
- **Durable Local Fallback:** High-performance pre-computed caches matching product catalogs.
- **Response Attribution:** Every AI-backed payload contains `"source"` (e.g., `"live-gemini"`, `"live-bedrock"`, or `"cached"`) and `"model"`.

---

## GET /health

Returns service health status.
→ `200 {"status": "ok"}`

---

## GET /items

Retrieves the inbox and seeded item list.
→ `200 {"items": [{"item_id": "SL-001", "asin": "B0SHOE500", "title": "Aurelle Women's Running Shoes", "category": "footwear", "mrp": 500, "age_months": 1, "status": "return_initiated", "persona": "priya", "thumb": "/items/SL-001/current_1.jpg", "return_reason": "size too small", "rto": false}, ...]}`

---

## GET /items/{item_id}

Retrieves full metadata for a specific item, including the complete Product Passport event history.

### Response `200 OK`
```json
{
  "item": {
    "item_id": "SL-001",
    "asin": "B0SHOE500",
    "title": "Aurelle Women's Running Shoes",
    "category": "footwear",
    "mrp": 500,
    "age_months": 1,
    "status": "return_initiated",
    "persona": "priya",
    "thumb": "/items/SL-001/current_1.jpg",
    "return_reason": "size too small",
    "rto": false,
    "order": {
      "order_id": "171-7781002-RH04",
      "purchase_date": "2026-06-09",
      "price_paid": 500,
      "invoice_id": "INV-2026-99182"
    }
  },
  "passport": [
    {
      "ts": "2026-06-13T10:00:00Z",
      "event": "SOLD",
      "data": {
        "buyer": "priya",
        "price_paid": 500
      }
    },
    {
      "ts": "2026-06-13T10:05:00Z",
      "event": "BIRTH_CERT_CAPTURED",
      "data": {
        "inspector_id": "AGT-09"
      }
    }
  ]
}
```
*Valid passport events include: `SOLD`, `BIRTH_CERT_CAPTURED`, `RETURN_INITIATED`, `GRADED`, `ROUTED`, `LISTED`, `SOLD_SECOND_LIFE`, `DONATED`.*

---

## POST /grade

Triggers the AI-powered delta-grading engine. The engine compares current photos of the returned item against its baseline catalog information and initial Day-0 birth certificate images.

### Request Body
```json
{
  "item_id": "SL-001",
  "force_cached": false,
  "current_images": [
    "data:image/jpeg;base64,/9j/4AAQSkZJRg..."
  ]
}
```
*Parameters:*
- `item_id` (string, required): The ID of the item being returned or listed.
- `force_cached` (boolean, optional): If `true`, directs the engine to bypass live API calls and retrieve cached responses (useful for verification testing). Defaults to `false`.
- `current_images` (array of strings, optional): An array of base64-encoded strings representing current product images (up to 3 images, maximum 1.5MB each). If omitted, the engine uses seeded baseline imagery on file.

### Response `200 OK`
```json
{
  "item_id": "SL-001",
  "same_unit": {
    "verified": true,
    "confidence": 0.94
  },
  "grade": "B",
  "defects": [
    {
      "area": "sole-heel-left",
      "description": "moderate tread wear",
      "severity": "moderate"
    }
  ],
  "completeness": [
    {
      "item": "original box",
      "present": true
    },
    {
      "item": "spare laces",
      "present": false
    }
  ],
  "usage_detected": true,
  "confidence": 0.91,
  "justification": "Light, even wear consistent with brief indoor use; structurally like-new.",
  "catalog_matches_day0": {
    "verified": true,
    "confidence": 0.95
  },
  "fault_attribution": "none",
  "returnable": true,
  "needs_human_review": false,
  "review_reason": null,
  "source": "live-gemini",
  "model": "gemini-2.5-flash",
  "graded_uploaded_photos": false,
  "latency_ms": 1840
}
```
*Notes:*
- **Passport Side Effect:** Appends a `GRADED` event to the item's Product Passport history.
- **Trust Gate:** `needs_human_review` is set to `true` if `same_unit.verified` is false, `same_unit.confidence` is less than `0.50`, or overall classification `confidence` is less than `0.70`.
- **Fault Attribution:** Computed by comparing the seller's catalog item with Day-0 photography (`catalog_matches_day0`) and the returned item with Day-0 (`same_unit`). Resolves to `none`, `seller` (mis-labeled catalog), or `customer` (damaged or swapped item, marking `returnable: false`).

---

## POST /route

Calculates net recovery values across all recovery channels via the deterministic Value Recovery Score (VRS) engine, routing the item to the channel yielding the highest net return.

### Request Body
```json
{
  "item_id": "SL-001"
}
```
*Note: Requires a prior grading event on the passport; returns `409 Conflict` otherwise.*

### Response `200 OK`
```json
{
  "item_id": "SL-001",
  "resale_value": 132,
  "paths": [
    {
      "path": "local_p2p",
      "recovery": 83,
      "eligible": true,
      "winner": true,
      "breakdown": {
        "sale_price": 125,
        "local_hop": -40,
        "payment_fee": -2
      },
      "note": "3 matched buyers within 4 km",
      "distance_km": 2.7,
      "dark_store": {
        "id": "DS-09",
        "name": "Amazon Now · Indiranagar",
        "distance_km": 1.9
      }
    },
    {
      "path": "warehouse_relist",
      "recovery": -129,
      "eligible": true,
      "winner": false,
      "breakdown": {
        "sale_price": 121,
        "reverse_ship": -120,
        "inspection": -40,
        "relist": -60,
        "fc_handling": -30
      }
    },
    {
      "path": "refurbish",
      "recovery": 0,
      "eligible": false,
      "winner": false,
      "note": "not economical to refurbish this item"
    },
    {
      "path": "donate",
      "recovery": 45,
      "eligible": true,
      "winner": false,
      "breakdown": {
        "csr_tax_credit": 75,
        "pickup": -30
      }
    },
    {
      "path": "liquidate",
      "recovery": 40,
      "eligible": true,
      "winner": false,
      "breakdown": {
        "sale_price": 60,
        "bulk_handling": -20
      }
    },
    {
      "path": "rto_relist",
      "recovery": 0,
      "eligible": false,
      "winner": false,
      "note": "not an RTO item"
    }
  ],
  "decision": "local_p2p",
  "quick_commerce_eligible": true,
  "co2_saved_kg": 2.1,
  "km_saved": 597
}
```
*Notes:*
- **Passport Side Effect:** Appends a `ROUTED` event to the Product Passport.
- **Routing Decision:** The chosen route is determined as the `winner` with the highest net recovery.
- **Hyperlocal Fulfillment:** When `local_p2p` is selected, `dark_store` coordinates point to the nearest physical fulfillment node (e.g., Amazon Now MFC).
- **Certified Refurbished Integration:** Electronics items route to secondary buyer networks under `"renewed_channel"` rather than `dark_store` options, mapping to Amazon Renewed channels, and return `quick_commerce_eligible: false`.
- **Automatic Marketplace Listing:** If the winning path is `local_p2p`, the engine automatically initializes a local Flash-deals listing, ensuring immediate secondary availability.

---

## GET /cascade/{item_id}

Calculates the time-decay value waterfall for a graded item. The engine runs week-by-week simulations using a 5% weekly depreciation factor on resale value, identifying when the optimal recovery path transitions and terminating at donation when monetary channels are no longer viable.

### Request Parameters
- `item_id` (string, required): The ID of the graded item.
*Note: Requires a prior grading event; returns `409 Conflict` otherwise.*

### Response `200 OK`
```json
{
  "item_id": "SL-001",
  "tiers": [
    {
      "week": 0,
      "channel": "local_p2p",
      "label": "Amazon Now dark store · open-box",
      "price": 125,
      "net": 83
    },
    {
      "week": 8,
      "channel": "donate",
      "label": "donate · CSR certificate",
      "price": 0,
      "net": 45,
      "terminal": true
    }
  ],
  "decay_pct_per_week": 5
}
```
*Note: This calculation is deterministic and derived dynamically, ensuring the cascade perfectly mirrors the underlying economic formulas of the VRS engine.*

---

## GET /health-card/{item_id}

Generates the Product Health Card and transferable warranty certificate for secondary market listings.

### Response `200 OK`
```json
{
  "item_id": "SL-001",
  "title": "Aurelle Women's Running Shoes",
  "grade": "B",
  "defects": [
    {
      "area": "sole-heel-left",
      "description": "moderate tread wear",
      "severity": "moderate"
    }
  ],
  "justification": "Light, even wear consistent with brief indoor use; structurally like-new.",
  "provenance": {
    "purchase_date": "2026-06-09",
    "price_paid": 500,
    "invoice_verified": true,
    "single_owner": true
  },
  "warranty": {
    "total_months": 12,
    "remaining_months": 11,
    "transferable": true
  },
  "suggested_price": 310,
  "price_decay": [
    {"week": 0, "price": 310},
    {"week": 1, "price": 295},
    {"week": 2, "price": 280}
  ],
  "usage_cert": null,
  "photos": [
    "/items/SL-001/current_1.jpg"
  ]
}
```
*Notes:*
- **Passport Side Effect:** Appends a `LISTED` event to the Product Passport.
- **Electronics Telemetry:** For electronics, the response populates the `usage_cert` attribute with battery cycles, battery health, and telemetry verification details. For non-electronic items, `usage_cert` is `null`.

---

## POST /seal-check

Verifies the packaging seal integrity of returned orders that were refused or failed delivery (RTO lane).

### Request Body
```json
{
  "item_id": "SL-004"
}
```
*Note: Returns `409 Conflict` if the item is not registered as an RTO package.*

### Response `200 OK`
```json
{
  "item_id": "SL-004",
  "sealed": true,
  "tamper_evidence": null,
  "verdict": "SEALED_NEW",
  "confidence": 0.96,
  "source": "live-bedrock",
  "model": "bedrock-nova-2-lite"
}
```
*Note: A `SEALED_NEW` verdict allows the item to bypass manual/AI quality grading and route directly to standard inventory under the `rto_relist` path.*

---

## GET /radar/{asin}

Queries the Idle Asset Radar for dormant units of a specific ASIN in the vicinity of active customer search demand.

### Response `200 OK`
```json
{
  "asin": "B0MONITOR1",
  "demand": {
    "query": "baby monitor",
    "buyers_waiting": 3
  },
  "dormant_units": [
    {
      "item_id": "SL-002",
      "owner": "Rahul S.",
      "purchased_months_ago": 19,
      "distance_km": 2.3,
      "est_value": 1800,
      "ping_message": "Someone nearby will pay ₹1,800 for your monitor — sell in one tap."
    }
  ],
  "total_dormant_value": 21400
}
```

---

## GET /price-curve/{item_id}

Returns pricing elasticity and liquidity curve options for a graded item, matching customer demand counts to listing price levels.

### Response `200 OK`
```json
{
  "item_id": "SL-002",
  "points": [
    {"price": 1400, "est_days_to_sell": 1, "buyers_at_price": 3},
    {"price": 1550, "est_days_to_sell": 4, "buyers_at_price": 1},
    {"price": 1650, "est_days_to_sell": 8, "buyers_at_price": 1}
  ],
  "recommended": 1500
}
```

---

## POST /diagnose-listing

Analyzes returned items for a specific catalog ASIN to diagnose catalog discrepancies causing high return rates, and auto-suggests corrections.

### Request Body
```json
{
  "asin": "B0KURTA01"
}
```

### Response `200 OK`
```json
{
  "asin": "B0KURTA01",
  "returns_analyzed": 18,
  "discrepancies": [
    {
      "aspect": "color",
      "listing_shows": "navy blue",
      "returns_show": "royal blue"
    }
  ],
  "patch": {
    "field": "title/photos",
    "current_text": "Vastram Men's Cotton Kurta (Navy Blue)",
    "suggested_text": "Vastram Men's Cotton Kurta (Royal Blue)"
  },
  "projected_return_reduction_pct": 40,
  "source": "live-bedrock",
  "model": "bedrock-nova-2-lite"
}
```

---

## GET /size-advice/{asin}

Retrieves structural size fit data and personalized recommendations for a buyer to prevent size-related returns.

### Request Parameters
- `asin` (string, path parameter): The catalog ASIN.
- `persona` (string, query parameter, optional): The customer ID to load historical fitting data and personalize the recommendation.

### Response `200 OK`
```json
{
  "asin": "B0SHOE500",
  "title": "Aurelle Women's Running Shoes",
  "category": "footwear",
  "mrp": 500,
  "thumb": "/items/SL-001/current_1.jpg",
  "fit": {
    "size_system": "UK",
    "your_size": "UK 8",
    "recommended_size": "UK 9",
    "headline_pct": 68,
    "direction": "up",
    "sample_size": 1240,
    "fit_distribution": [
      {"bucket": "ran small — sized up", "pct": 68},
      {"bucket": "fit true to size", "pct": 25},
      {"bucket": "ran large — sized down", "pct": 7}
    ],
    "advice": "This pair runs small. 68% of UK-8 buyers ordered one size up — we suggest UK 9."
  },
  "personal": {
    "matched_on": "brand",
    "past_size": "M",
    "past_outcome": "fit_true",
    "recommended_size": "L",
    "copy": "You bought a Vastram Linen Shirt in M — it fit true to size. This Vastram runs slim, so we suggest you size up to L."
  },
  "resale_hint": {
    "amount": 343,
    "buyers_nearby": 4,
    "top_offer": 310
  }
}
```

---

## GET /seller/returns

Retrieves the merchant returns dashboard, ranking their catalog items by return rate to prioritize products requiring diagnostic analysis.

### Response `200 OK`
```json
{
  "seller": {
    "name": "Vastram Apparel & Goods",
    "store_id": "A1SELLER42",
    "quarter": "Q2 FY26"
  },
  "skus": [
    {
      "asin": "B0KURTA01",
      "item_id": "SL-003",
      "title": "Vastram Men's Cotton Kurta",
      "category": "apparel",
      "thumb": "/items/SL-003/current_1.jpg",
      "units_sold": 64,
      "returns": 18,
      "top_return_reason": "colour not as shown",
      "diagnosable": true,
      "return_rate_pct": 28
    }
  ],
  "total_units_sold": 3334,
  "total_returns": 117
}
```

---

## GET /orders/{persona}

Retrieves purchase order history for a shopper, indicating active return windows and identifying items eligible for resale.

### Request Parameters
- `persona` (string, path parameter): The customer ID.

### Response `200 OK`
```json
{
  "persona": "rahul",
  "orders": [
    {
      "order_id": "171-7781002-RH04",
      "asin": "B0KURTA01",
      "title": "Vastram Men's Cotton Kurta (Navy Blue)",
      "purchase_date": "2026-06-09",
      "price_paid": 899,
      "status": "delivered",
      "return_window_open": true,
      "return_by": "2026-06-19",
      "days_left": 6,
      "item_id": "SL-003",
      "resellable": false
    },
    {
      "order_id": "171-8835520-SL002",
      "asin": "B0MONITOR1",
      "purchase_date": "2024-11-02",
      "return_window_open": false,
      "return_by": "2024-11-12",
      "days_left": 0,
      "item_id": "SL-002",
      "resellable": true
    }
  ]
}
```

---

## GET /life-stage/{asin}

Analyzes a product owned by a customer, projecting its lifecycle duration and calculating its residual secondary market value based on age.

### Request Parameters
- `asin` (string, path parameter): The product ASIN.
- `persona` (string, query parameter, required): The customer ID.

### Response `200 OK`
```json
{
  "asin": "B0MONITOR1",
  "persona": "rahul",
  "title": "Video Baby Monitor",
  "category": "electronics",
  "purchase_date": "2024-11-02",
  "months_owned": 19,
  "typical_life_months": 18,
  "stage_label": "baby-gear stage",
  "stage_pct": 100,
  "past_typical_life": true,
  "current_value": 978,
  "decay_per_month": 68,
  "due_to_resell": true
}
```

---

## GET /second-life/{asin}

Lists available pre-owned and returned units of a specific product near the shopper, integration-ready for standard product detail pages.

### Response `200 OK`
```json
{
  "asin": "B0SHOE500",
  "title": "Aurelle Women's Running Shoes",
  "offers": [
    {
      "item_id": "SL-001",
      "grade": "C",
      "price": 238,
      "distance_km": 2.7,
      "eta": "Pickup today"
    },
    {
      "item_id": "SL-001",
      "grade": "D",
      "price": 132,
      "distance_km": 5.6,
      "eta": "Delivery tomorrow"
    }
  ]
}
```

---

## GET /your-things/{persona}

Retrieves all products owned by a specific shopper, evaluating their current estimated secondary values as dormant inventory assets.

### Response `200 OK`
```json
{
  "persona": "rahul",
  "total_dormant_value": 12040,
  "item_count": 8,
  "due_count": 3,
  "things": [
    {
      "order_id": "171-8835520-SL002",
      "asin": "B0MONITOR1",
      "item_id": "SL-002",
      "title": "Video Baby Monitor",
      "category": "electronics",
      "thumb": "/items/SL-002/current_1.jpg",
      "purchase_date": "2024-11-02",
      "price_paid": 3200,
      "months_owned": 19,
      "typical_life_months": 18,
      "stage_label": "baby-gear stage",
      "stage_pct": 100,
      "due_to_resell": true,
      "resale_value": 978,
      "decay_per_month": 68,
      "resellable": true
    }
  ]
}
```

---

## GET /green-ledger/{persona}

Retrieves local environmental sustainability impact metrics achieved by a specific shopper or merchant.

### Response `200 OK`
```json
{
  "persona": "rahul",
  "items_diverted": 2,
  "co2_saved_kg": 4.7,
  "landfill_diverted_kg": 2.3
}
```

---

## GET /returns

Retrieves active returned packages queued for grading at operations terminals.

### Response `200 OK`
```json
{
  "returns": [
    {
      "return_id": "RTN-B001",
      "title": "Aurelle Women's Running Shoes",
      "category": "footwear",
      "thumb": "/items/SL-001/current_1.jpg",
      "return_reason": "size too small",
      "price_paid": 500,
      "order_id": "171-7781002-RH04",
      "persona": "priya",
      "source": "buyer",
      "status": "queued",
      "created_ts": "2026-06-13T10:00:00Z"
    }
  ]
}
```

---

## POST /returns

Submits a new customer return request, queueing it for logistics pick-up and operations processing.

### Request Body
```json
{
  "persona": "rahul",
  "order_id": "171-7781002-RH04",
  "asin": "B0KURTA01",
  "title": "Vastram Men's Cotton Kurta",
  "category": "apparel",
  "thumb": "/items/SL-003/current_1.jpg",
  "return_reason": "colour not as shown",
  "price_paid": 899
}
```

---

## POST /resell/quote

Computes potential secondary sale payouts, platform shipping fees, and regional demand tier breakdown for listing an owned item.

### Request Body
```json
{
  "item_id": "SL-002",
  "range_km": 7,
  "grade": "B"
}
```

### Response `200 OK`
```json
{
  "item_id": "SL-002",
  "range_km": 7,
  "grade": "B",
  "ai_suggested": 978,
  "reachable_buyers": 3,
  "best_price": 1076,
  "delivery_cut": 67,
  "net": 1009,
  "points": [
    {"price": 1076, "est_days_to_sell": 3, "buyers_at_price": 3}
  ],
  "recommended": 1550,
  "range_tiers": [
    {"range_km": 3, "reachable_buyers": 1, "delivery_cut": 43},
    {"range_km": 7, "reachable_buyers": 3, "delivery_cut": 67},
    {"range_km": 15, "reachable_buyers": 4, "delivery_cut": 115}
  ]
}
```

---

## GET /resell/listings

Retrieves active peer-to-peer listings on the secondary marketplace board.

### Response `200 OK`
```json
{
  "listings": [
    {
      "listing_id": "RL-001",
      "item_id": "SL-002",
      "asin": "B0MONITOR1",
      "title": "Video Baby Monitor",
      "thumb": "/items/SL-002/current_1.jpg",
      "ask_price": 1000,
      "range_km": 7,
      "delivery_cut": 67,
      "net": 933,
      "owner": "rahul",
      "status": "active",
      "grade": "B",
      "confidence": 0.94,
      "source": "resell",
      "interests": []
    }
  ]
}
```

---

## POST /resell/listings

Creates a new P2P listing on the secondary market board.

### Request Body
```json
{
  "item_id": "SL-002",
  "persona": "rahul",
  "ask_price": 1000,
  "range_km": 7
}
```

---

## GET /resell/listings/{id}

Retrieves a detailed view of a specific listing, including current buyer interest expressions.

---

## POST /resell/listings/{id}/interest

Submits interest from a potential buyer in a secondary listing.

### Request Body
```json
{
  "buyer_name": "Pooja K.",
  "distance_km": 2.4,
  "offer": 1000
}
```

---

## POST /resell/listings/{id}/sell

Accepts a buyer's offer, transitioning the listing status to sold.

### Request Body
```json
{
  "interest_id": "IN-001"
}
```

---

## POST /resell/listings/{id}/decline

Declines a buyer's offer, keeping the listing active for other buyers.

### Request Body
```json
{
  "interest_id": "IN-001"
}
```

---

## GET /cart/{persona}

Retrieves a shopper's circular shopping cart contents and totals.

### Response `200 OK`
```json
{
  "persona": "rahul",
  "lines": [
    {
      "asin": "B0SHOE500",
      "item_id": "SL-001",
      "title": "Aurelle Women's Running Shoes",
      "category": "footwear",
      "size": "UK 9",
      "qty": 1,
      "price": 500,
      "thumb": "/items/SL-001/current_1.jpg"
    }
  ],
  "count": 1,
  "total": 500
}
```

---

## POST /cart/{persona}

Adds a product to a shopper's cart.

### Request Body
```json
{
  "asin": "B0SHOE500",
  "size": "UK 9",
  "qty": 1
}
```

---

## GET /notifications/{persona}

Retrieves transactional and automated circular listing notifications for a shopper.

### Response `200 OK`
```json
{
  "persona": "rahul",
  "notifications": [
    {
      "id": "n-resell",
      "kind": "resell",
      "hero": true,
      "asin": "B0MONITOR1",
      "item_id": "SL-002",
      "title": "Resell your Baby Monitor",
      "body": "A buyer nearby is offering ₹1,800. Tap to list in one click.",
      "cta": "Resell now",
      "ts": "just now"
    }
  ]
}
```

---

## POST /checkout/{persona}

Initiates secondary checkout processing and payment request creation.

### Request Body
```json
{
  "confirm": true
}
```

### Response `200 OK`
```json
{
  "persona": "rahul",
  "order_id": "171-7697281-SL",
  "amount": 500,
  "upi_vpa": "rahul@okhdfc",
  "status": "success"
}
```

---

## GET /metrics

Retrieves system-wide circular economy impact metrics.

### Response `200 OK`
```json
{
  "items_processed": 5,
  "rupees_recovered": 3120,
  "rupees_vs_writeoff_baseline": 3980,
  "warehouse_bypass_pct": 80,
  "co2_saved_kg": 9.4,
  "landfill_diverted_kg": 4.2,
  "inspection_hours_saved": 1.7
}
```

---

## POST /metrics/reset

Resets the running system metrics counters to their baseline state (useful for system diagnostics and testing initialization).

### Response `200 OK`
```json
{
  "status": "metrics reset completed"
}
```
