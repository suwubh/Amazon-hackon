# System Architecture: Amazon Second Life

Amazon Second Life is built using a modern, serverless architecture on AWS, designed to scale to millions of transactions while maintaining high availability and economic precision.

## 1. System Overview

```
[Client Web Console: React on Vercel]
        │
        │ HTTPS REST Requests
        ▼
[AWS Lambda: FastAPI Application Container via ECR]
        │
        ├── Product Catalog & Seed Store (DynamoDB / Local JSON Cache)
        │
        ├── Multimodal Grading Engine
        │       ├── Primary: Gemini 2.5 Flash (via API)
        │       └── Failover: Amazon Bedrock (Nova 2 Lite)
        │
        ├── Value Recovery Score (VRS) Economics Engine (Deterministic Python)
        ├── Pricing & Dynamic Time-Decay Module (Deterministic Python)
        ├── Health Card Assembler (Passport verification & warranty transfer)
        ├── Idle Asset Radar (Hyperlocal demand-to-asset mapping)
        │
        └── Product Passport Database (Amazon DynamoDB single-table schema)
```

### Core Design Philosophy: AI as Perception, Code as Valuation
**The Large Language Model functions strictly as a perception layer; the economic logic resides entirely in deterministic code.** 
The multimodal vision model (Gemini 2.5 Flash or Amazon Bedrock Nova 2 Lite) acts as the quality inspector, analyzing images to output structured condition facts (such as wear locations, packaging presence, and defects). The Value Recovery Score (VRS) engine then processes these facts using auditable, deterministic economic formulas to calculate pricing, shipping overheads, and path selection. This prevents hallucinated pricing and guarantees complete compliance and auditing capabilities.

## 2. System Execution Flow

```mermaid
flowchart LR
    subgraph CT["Customer touchpoints"]
        A["Guided photo capture\nat return initiation"] --> G
        R["One-tap resell\nfrom order history"] --> P
        D["Demand: search/wishlist\nnear the item"] --> IAR
    end

    subgraph GAI["GenAI core - Gemini 2.5 Flash multimodal, Nova failover"]
        G["Delta-Grader\ncatalog + birth-certificate vs now"] --> V["grade, defects,\nconfidence, same-unit"]
        S["Seal-Check\nrTO lane"] --> V
        L["Listing Diagnostics\nlisting vs returned photos"] --> PATCH["Auto-patch listing"]
    end

    subgraph DE["Deterministic engines"]
        V --> VC["winner + visible math"]
        IAR["Idle Asset Radar\ngeo-match order history"] --> P
    end
    P[Product Passport\nDynamoDB event log] <--> G & V & HC
    HC[Product Health Card\n+ warranty transfer] --> BUY[Next owner\nPDP row / locker / agent hop]
    V -. -->|confidence < 0.70| HQ[Human review queue]
```

## 3. Computer Vision & Grading Core

The backend orchestration layer interacts with the vision models using structured image input blocks and enforces schema-conforming JSON outputs. 

### Resiliency & Orchestrated Failover
We utilize **Gemini 2.5 Flash** as our primary inference engine for its speed and native JSON mode configuration, and **Amazon Bedrock (Nova 2 Lite)** as our high-reliability failover. 
- **Deterministic Schema Enforcement:** Models are prompted with a strict JSON structure. Responses are validated against Pydantic schema definitions in the backend. 
- **Validation Retry Logic:** If a model returns schema-deviant or malformed JSON, a corrective retry is automatically dispatched containing the validation error logs. If both models fail, a pre-computed cache maps the request to keep the user experience seamless.
- **Inference Stability:** We run the models with a temperature of `0.2` to prioritize consistency over creative variance, and disable thinking tokens for Gemini 2.5 Flash (`thinking_budget=0`) to ensure response formatting is not truncated mid-object.

### Condition Delta Prompting
The delta-grading prompt is explicitly optimized to measure physical wear compared to Day-0, ignoring environmental lighting, camera angles, shadows, or image quality differences.

### Trust Gate Verification
To safeguard against return fraud, the engine returns a `needs_human_review` flag with an accompanying `review_reason` if:
- Same-unit verification fails (`same_unit.verified == false`).
- Same-unit confidence falls below `0.50`.
- Grading model confidence falls below `0.70`.

This ensures anomalous uploads (such as wrong products or blurred photos) are flagged for human inspection rather than automatically cleared as secondary inventory.

### 3.1 Delta-Grader (`POST /grade`)
- **Input Images:** Original catalog image, Day-0 birth certificate image, and current return photos.
- **Output Schema:** `{same_unit: {verified, confidence}, grade, defects: [{area, description, severity}], completeness: [{item, present}], usage_detected, confidence, justification}`

### 3.2 Seal-Check (`POST /seal-check`) — RTO Lane
- **Input Images:** Step photo of packaging seals.
- **Output Schema:** `{sealed: bool, tamper_evidence: str|null, verdict: "SEALED_NEW"|"OPENED", confidence}`

### 3.3 Listing Diagnostics (`POST /diagnose-listing`)
- **Input Images:** Merchant listing image, return photos, and return reason strings.
- **Output Schema:** `{discrepancies: [{aspect, listing_shows, returns_show}], patch: {field, current_text, suggested_text}, projected_return_reduction_pct}`

## 4. Value Recovery Score (VRS) Economics Engine

The VRS engine implements a deterministic optimization search: `recovery(path) = sum(breakdown_components)`. The optimal path is chosen via `argmax(recovery)`.

### Cost and Recovery Functions
Our system uses the following economic formulas to evaluate paths for a graded item:

| Path | Revenue / Recovery Basis | Cost Deductions |
|---|---|---|
| **Warehouse Relisting** (`warehouse_relist`) | Resale Value × 0.92 (In-transit depreciation) | Reverse shipping (₹120) + Inspection (₹40) + Re-listing (₹60) + FC handling (₹30) |
| **Local P2P** (`local_p2p`) | Resale Value × 0.95 | Hyperlocal delivery (₹40) + Payment processing fee (2%) |
| **Refurbishment** (`refurbish`) | Resale Value + Value Uplift | Category-specific repair cost + Local transport logistics (₹60) |
| **Donation** (`donate`) | CSR Tax Credit (15% of fair market value) | Donation collection transport (₹30) |
| **Liquidation** (`liquidate`) | Original MRP × 0.12 | Bulk handling fee (₹20) |
| **RTO Sealed Lane** (`rto_relist`) | Original MRP × 0.90 | Relabeling (₹15) + Local delivery (₹40) |

### Resale Value Formula
The base resale value is calculated as:
`resale = round(MRP × depreciation(category, age) × grade_factor × demand_multiplier)`

- **Grade Factors:** Grade A (0.80) / Grade B (0.65) / Grade C (0.45) / Grade D (0.25)
- **Depreciation Curves:** Linear decay `max(floor, 1 - rate × age_months)` per category:
  - *Footwear:* Rate 4.0% per month, floor value 30% of MRP
  - *Electronics:* Rate 3.0% per month, floor value 25% of MRP
  - *Apparel:* Rate 6.0% per month, floor value 20% of MRP
  - *Appliances:* Rate 2.5% per month, floor value 35% of MRP
  - *Books:* Rate 5.0% per month, floor value 15% of MRP
  - *Home Goods:* Rate 3.0% per month, floor value 30% of MRP
  - *Luggage/Bags:* Rate 3.5% per month, floor value 25% of MRP
- **Demand Multiplier:** Derived from local active demand (buyers within 15 km):
  - 0 buyers: 0.90x
  - 1-2 buyers: 1.00x
  - 3-4 buyers: 1.10x
  - 5+ buyers: 1.15x
- **Time Decay:** Active listing prices depreciate at a rate of 5% weekly to accelerate inventory clearance.
- **Routing Eligibility Gates:**
  - `local_p2p` requires at least one matched local buyer within a 15 km radius.
  - `refurbish` requires the item to be in Grade C or D, have a projected post-repair value of at least ₹600, and belong to a repairable category.
  - `rto_relist` requires a sealed verdict from the doorstep package check, enabling the item to skip standard grading and list as factory new.

## 5. High Availability & Staging Resiliency

To guarantee seamless uptime and performance, the system architecture implements a robust caching and database virtualization layer:
- **Seed Datastore:** Local files store base configurations, customer purchase files, and regional demand matrices. These files serve as the default initialization state for new instances.
- **Intelligent Response Cache:** To shield the service from upstream LLM quota limits, API timeouts, or network drops, the backend stores pre-computed responses matching the catalog seeds. If a live multimodal request exceeds its timeout or fails validation, the system falls back to this cache, attributing the response source as `"cached"`.
- **Flexible Persistence Layer:** The Product Passport database connects to **Amazon DynamoDB** when environment configurations are present. If the database is unreachable or unset, the application automatically virtualizes updates inside a fast in-memory object store. This dual-mode design enables zero-overhead local debugging while maintaining production scalability.

## 6. Production Architecture & Scale Strategy

For global production deployment, the backend scales horizontally using serverless AWS components:

```
[Customer Photo Upload]
        │
        ▼
[Amazon S3 Bucket]
        │ Event Trigger
        ▼
[Amazon EventBridge]
        │
        ▼
[AWS Step Functions Workflow]
        ├── 1. AI quality grading & verification (AWS Lambda + Amazon Bedrock)
        ├── 2. Optimal route calculation (VRS Engine)
        └── 3. Secondary marketplace publication
                │
                ├── Normal Case: DynamoDB Passport Update
                │
                └── Sub-threshold Confidence: Route to Amazon SQS Queue (Human Review)
```

- **Event-Driven Pipeline:** Quality inspections are triggered directly by product photo uploads to an Amazon S3 bucket. EventBridge routes the upload event to launch an AWS Step Functions workflow.
- **Asynchronous Step Functions:** The workflow orchestrates the grading checks, routing calculations, and marketplace publication. If grading confidence is low, it halts and flags the passport event, sending it to an Amazon SQS queue for manual reviewer action.
- **Scalable Database Schema:** The Product Passport utilizes a DynamoDB table with a partition key of `item_id` and a sort key of `ts` (timestamp). A Global Secondary Index (GSI) on `asin` and `geohash` allows the Idle Asset Radar to run millisecond geo-proximity queries to match regional demand.
- **Inventory-of-One Optimization:** Traditional search engines are designed for catalog inventory. Second-life items are unique assets ("inventory of one"). Rather than search indexes, we match supply dynamically to nearby demand points using purchase signals and alerts, pushing inventory directly onto local shopper detail pages.

## 7. Hyperlocal Routing & Value Cascades

The Value Recovery Score (VRS) engine computes a dynamic, decay-based waterfall for returned inventory:
- **Hyperlocal Fulfillment:** The `local_p2p` route identifies local buyers within 15 km. If matched, the system assigns the item to the nearest Amazon Now MFC (Micro-Fulfillment Center).
- **Dynamic Cascading Tiers:** If no local buyer claims the item, the value-decay module automatically steps the item down through subsequent tiers. For example, a premium item might cascade from a local open-box listing to a certified refurbished listing, then to liquidation, and finally to charity donation.
- **Time-Decay Valuations:** The waterfall is calculated dynamically, adjusting price levels by -5% per week. This prevents inventory from stagnating at fulfillment locations.

## 8. Marketplace Loops & Trust Verification

Amazon Second Life incorporates trust safeguards across transaction lifecycles:
- **Certified Refurbished (Amazon Renewed) Integration:** While everyday apparel and footwear route via hyperlocal MFCs, high-value electronics bypass quick-commerce networks. Instead, they are routed to Amazon Renewed channels, and their Health Cards are enriched with battery cycle and hardware health telemetry.
- **Automated Listing Corrections:** When an item faces elevated return rates due to inaccurate listings, the Listing Diagnostics engine compares returned item photography against the active seller listing, suggesting copy updates to prevent future returns.

## 9. Dormant Inventory Harvesting

Rather than relying purely on active returns, the system captures unused value within consumer households:
- **Idle Asset Radar:** Tracks local search volume for specific products and alerts regional owners who purchased those models in the past of active cash offers.
- **The "Your Things" Ledger:** Generates a personalized dashboard for shoppers showing their past purchases, their depreciated resale value, and a "Due to Resell" trigger indicating optimal listing times before value erodes.

## 10. Single-Table Database Design

To optimize resource usage and query efficiency, we implement a Single-Table DynamoDB schema:
- **Partition Key (`PK`):**
  - Passport Events: `item_id` (e.g., `SL-001`)
  - Active Listings: `LISTING`
  - Active Returns Desk: `RETURNS`
  - Customer Shopping Carts: `CART#<persona>` (e.g., `CART#rahul`)
- **Sort Key (`SK`):**
  - Passport Events: Timestamp (`ts`)
  - Shared Entities: Entity IDs or user identifiers.
This design allows our database query layer to perform rapid lookups and atomic updates across transaction states within a single DynamoDB query context.

