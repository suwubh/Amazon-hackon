# Demo Video Beat Sheet — Amazon Second Life (3:00, owner: C)

Follows docs/PRD.md. Record one clean take + one backup. Live calls only on the 2–3 hero items tested beforehand; everything else `force_cached`. No live un-tested scans, ever.

| Time | Beat | On screen | Script anchor |
|---|---|---|---|
| 0:00–0:15 | **Hook** | Priya's ₹500 shoes + the PS's own equation "Cost > Value = Written off" | "Nearly $890 billion of merchandise was returned in the US alone last year. A return today is an act of amnesia — Amazon forgets everything it knew about a product the moment it comes back. We built the system that never forgets." |
| 0:15–0:40 | **Customer + quantified problem** | Three personas, one equation; unit-economics: ₹220 cost on a ₹150 margin | "Priya, Rahul, and a small seller are the same problem wearing different clothes: the cost of trust and relisting exceeds the value of the item. Right now the cheapest thing Amazon can do with this ₹500 shoe is destroy its value." |
| 0:40–1:10 | **LIVE: Delta-grade** (Pillar 1) | Guided scan → side-by-side day-0 vs now, four localized defects called out, same-unit verified badge, one-line justification | "Not 'AI, grade this shoe' — we grade the *delta* against this exact unit's day-0 photos and the catalog. Same-unit verified: no swap fraud, and worn-then-returned gets caught too." |
| 1:10–1:40 | **LIVE: VRS routing** (Pillar 2) | Six paths animate with rupee math; local hop wins; "600 km → 4 km"; warehouse −₹129 vs Second Life +₹83 (₹212 swing) | "The AI sees; deterministic economics decide. Their equation, defeated in real time: re-identification ₹0, local hop ₹40 — the item never sees the warehouse." |
| 1:40–2:00 | **Health Card + handoff** (Pillar 3) | Card generates: provenance, grading report, **warranty-transfer badge**; locker/escrow screen flash | "The next buyer knows exactly what they're getting — including its remaining transferable warranty, because Amazon holds the invoice. OLX never can." |
| 2:00–2:20 | **Rahul + Idle Asset Radar** (Pillar 4) | Order history → one-tap resell → liquidity slider → radar ping arrives *before he thinks of it* | "Amazon's largest warehouse is the one it can't see — millions of homes. We made it searchable. Demand finds Rahul; he never even decides to sell." |
| 2:20–2:35 | **Prevention + RTO** | Listing diagnostics auto-patch ("returns on this SKU −40%") · RTO sealed lane verdict (15 seconds, no more) | "Best return is no return — we fix the listings that cause them. And India's biggest bleed, COD refusals: sealed boxes re-offered locally the same day, zero grading needed." |
| 2:35–2:50 | **Architecture + metrics** | One diagram (multimodal vision → VRS → DynamoDB passport) + the live `/metrics` counter: **"5 items → ₹3,120 recovered · 80% warehouse-bypass · 9.4 kg CO₂"** (these are the real baseline fields; the counter then ticks up live as the items we just routed on stage are added) + CO₂ ticker | "Serverless on AWS — multimodal vision for perception with Bedrock Nova as the AWS-native failover, auditable code for money. Amazon earns a take-rate on every rupee recovered: we only earn when value is saved." |
| 2:50–3:00 | **Close + team** | Flywheel + team intro (one human touch) | "Every product finds its next best owner. We're [team] — thank you." |

**Backup plan:** if a live call stalls on camera, the cached path renders identically — keep talking, nothing visibly fails.

**Metrics beat — stable number:** `/metrics` is cumulative over the warm Lambda instance, so every rehearsal route nudges it up. The numbers narrated above are the fresh-instance baseline. For a clean, repeatable stage number, hit `POST /metrics/reset` once right before the take (resets the per-instance counter to baseline; it then grows live during the run — which is the proof the numbers are real, not hardcoded).

## Q&A pocket answers (Grand Finale prep — keep, don't volunteer)
1. **Doesn't Amazon already do this?** Renewed/Warehouse Deals prove demand but are warehouse-bound, human-graded, premium-skewed, separate storefront. FBA Grade & Resell still ships to the FC for human grading — we grade at source and delete the trip. Returnless refunds abandon value in a drawer — we recover it; the handoff is the novel part.
2. **No local buyer in 48h?** Time-decay guarantees a terminal state: relist → discount → donate w/ CSR certificate. Worst case the item reaches the warehouse already graded and listed — which alone kills the liquidation economics.
3. **Keep-it fraud?** Refund held as instant credit, released on handoff/locker-drop confirmation.
4. **Swapped item?** Birth-certificate baseline — same-unit verification before any refund. Also catches wardrobing.
5. **Trust the grade?** Grounded delta vs the unit's own baseline + catalog, localized evidence on screen, confidence-thresholded human queue, and every sale ends in a buyer confirmation that audits the model for free.
6. **Cannibalizing new sales?** Residual value at checkout *raises* conversion (effective cost ₹900 vs ₹2,400); recovered long-tail is pure loss today; ESG/EPR adds a revenue line. Resale closes the sale, it doesn't cannibalize it.
7. **Privacy of radar pings?** Opt-in, silent aggregate matching, identities exchanged only after handoff.
8. **Agent time per stop?** 15–20s, commission-aligned (₹20–30) — and that's a pitch line, not our demo dependency: customer self-scan is the primary flow.
9. **Why Gemini and not just Bedrock?** The grader is provider-agnostic by design (`LLM_PRIMARY`/`LLM_FALLBACK`) — the LLM is a swappable perception layer; the money math is ours. We run Gemini 2.5 Flash as the live primary purely for free-tier headroom under demo load; **Bedrock Nova 2 Lite is the AWS-native failover** (funded by credits) and a one-env-var swap back to primary. Nothing in the architecture depends on the vendor — that separation of perception from economics is the point.
