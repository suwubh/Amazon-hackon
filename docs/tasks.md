# Tasks — Amazon Second Life (48h: June 13–15)

MVP-only. One MAJOR TASK = one Fable session. Owners: **A** = backend (me + Fable) · **B** = frontend/demo · **C** = research/PRD/video. The ⭐ spine (MT1–MT3) is the must-have-by-hour-24 demoable core: **scan → delta-grade → VRS math → Health Card → radar ping**. If anything slips, cut from MT4 edges, never from the spine.

## HUMAN TASKS (not Fable — do these first, tonight June 13)

- [ ] **Photograph the demo item set** (owner: A+B, ~90 min, BLOCKS MT1 cache quality):
  8 real items, each with: 1 catalog-style shot (clean background), 2 "day-0" shots (good light, multiple angles), 2–3 "current" shots (show real wear where it exists).
  1. Hero: pair of worn-ish shoes (Priya, ₹500-class)
  2. Hero: baby monitor or any outgrown kid-gear/electronics you own (Rahul)
  3. Apparel item, ideally one whose color photographs differently than catalog-style lighting (kurta — listing diagnostics)
  4. A sealed Amazon box, tape intact (RTO lane)
  5.–8. Filler: book, headphones, bottle, backpack — anything (batch view; cached grades only)
  Drop into `backend/app/seed/images/SL-00X/` as `catalog.jpg`, `day0_1.jpg`, `day0_2.jpg`, `current_1.jpg`… Fable handles the rest. **Until photos land, MT1 builds against 2 stock-photo placeholder items — pipeline first, photos swap in.**
- [ ] Check email for AWS/Kiro credit codes; set AWS billing alert (A)
- [ ] OBS/Loom recording test (C)
- [ ] C starts citation verification for the `[VERIFY-C]` stats in docs/PRD.md

## MT1 ⭐ — Seed store + Product Passport + Delta-Grader (A) ✅ DONE (commit be97d15)
**Goal:** `POST /grade` returns real Nova-2 delta-grading JSON for seeded items, with cached fallback.
Scope: `seed/` module (items/orders/neighbors JSON + images), passport event store (in-memory + DynamoDB behind env flag), multimodal extension of `llm.py`, grading prompt + Pydantic schema + retry-on-invalid-JSON, cache capture script, `GET /items`, `GET /items/{id}`.
**Verify (done when):** local uvicorn: `POST /grade` for the shoe returns schema-valid JSON with ≥1 localized defect, confidence, same-unit block, `source: live-bedrock`; rerun with AWS creds removed → identical shape, `source: cached`; `GET /items` lists all seeded items. Grading consistency: same item graded 3× → same letter grade ≥2/3 (else tighten prompt before proceeding — this is the highest-risk item in the build, test in the first 6 hours).
**Result:** all checks PASS, fresh verifier signed off. Hero shoe D/D/D (3/3 consistency). 2 placeholder items (SL-001 shoe, SL-002 monitor) with Commons images + cached grades; SL-003..008 metadata only (no images → `/grade` 502 until photos land). ⚠️ Discovered: deploy is IAM-blocked (see top of file + STATE.md).

## MT2 ⭐ — VRS engine + Health Card + RTO + Radar + Pricing + deploy (A) ✅ DONE (this session)
**Goal:** every endpoint in docs/api-spec.md live on the Function URL.
Scope: `vrs.py` (6 paths, breakdowns, eligibility), `pricing.py` (depreciation, decay, liquidity curve), `healthcard.py` (warranty months from seeded invoice), `radar.py`, `inspection.py` (`/seal-check` + `/diagnose-listing`), `metrics.py`, endpoints `/route` `/health-card` `/seal-check` `/radar/{asin}` `/price-curve` `/diagnose-listing` `/metrics`. Redeploy via `./deploy.ps1`.
**Verify (done when):** all api-spec curls pass against the **deployed** Function URL; `/route` on the shoe shows `local_p2p` winner with the hero math; `/seal-check` on SL-004 returns `SEALED_NEW`; cached fallback verified post-deploy.
**Result:** all 9 verify checks PASS on the deployed Function URL, fresh verifier signed off. **Deploy blocker (IAM) RESOLVED** — `deploy.ps1` now pushes ECR + updates Lambda. VRS constants LOCKED (architecture.md §4): every path's `recovery` = exact sum of its breakdown. Hero shoe → `local_p2p` winner at every grade (grade D: local +₹83 vs warehouse −₹129; grade B target ≈ +₹279 vs +₹66). Sealed RTO mixer → `rto_relist` +₹2,464 (skips grading). Two AI endpoints serve hand-authored cached responses (`SL-004.seal.json`, `SL-003.diagnose.json`) until real photos land — the stage-safe path. ⚠️ Note: `/route` & `/health-card` read grade/route from the in-memory passport, which is per-Lambda-instance — sequential demo calls hit the same warm instance, so the spine flow works; a cold start resets to no-grade (call `/grade` first).

## MT3 ⭐ — Frontend spine: the demo console (B builds with Fable, A supports API)
**Goal:** the 5-screen hero flow clickable end-to-end on Vercel, phone-frame, Amazon-look.
Screens: Returns inbox → item + guided-capture intro → **delta-grade screen (side-by-side day-0 vs now, defect callouts, confidence, same-unit badge)** → **VRS screen (6 paths animate in with rupee math, winner highlighted, "₹410 warehouse route defeated by ₹40 local hop")** → **Health Card (provenance, grading report, warranty-transfer badge)** → radar ping toast ("3 buyers within 4 km"). Brand: Amazon-adjacent palette, "Second Life" badge styling; design skills (frontend-design / ui-ux-pro-max) apply.
**Verify:** live Vercel URL: full click-through with real backend; then with `force_cached` → visually identical; no dead buttons on the spine; playwright/chrome-devtools pass over the flow.

## MT4 — Frontend moments + supporting screens (B + Fable)
**Goal:** every remaining demo beat reachable.
Scope (cut from the bottom if time pressure): Rahul one-tap resell from order history + Idle Asset Radar ping screen + liquidity slider · keep-it decision screen ("keep them — buyer 4 km away, earn ₹250") · RTO Sealed Lane screen · listing-diagnostics comparison screen (auto-patch before/after) · mock PDP: "Second Life options near you" row + buyback badge + static size widget (30 min, no more) · "Your Things" dashboard ("your home holds ₹47,300 in dormant value") · green counter (minimal ticker) · locker/escrow state screen · batch metrics view ("8 items → ₹4,830 recovered vs ₹0 baseline").
**Verify:** docs/demo-and-prfaq.md script walkable end-to-end on Vercel with zero dead ends; every number on screen comes from the API, not hardcoded JSX.

## MT5 — Bulletproof + polish + repo (A+B)
**Goal:** the demo cannot fail on stage.
Scope: cached responses verified for all items × all AI endpoints; kill-switch env (`FORCE_CACHED=1`); failover drill (break Bedrock creds on a test invoke → Gemini → cache); loading/error states; mobile-frame polish pass; README with architecture diagram + live URLs; repo public; final deploy both ends.
**Verify:** full demo run on live URLs with Bedrock disabled → no visible difference; fresh-context verifier subagent walks the script and signs off; Lighthouse sanity on the Vercel app.

## MT6 — PRD final + demo video + submission (C owns, A+B support)
**Goal:** submitted.
Scope: `[VERIFY-C]` citations resolved in PRD; PRD mapped onto the official submission template section-by-section; 3-min video recorded per docs/demo-and-prfaq.md (+ backup recording); architecture diagram exported; team intro with personality; submit; dry-run pitch.
**Verify:** video ≤3:00, opens with Priya hook, shows live grade + VRS math + Health Card + radar ping; every template section answered; submission confirmed before deadline with ≥2h buffer.

---
**Reserve the final 6–8 hours exclusively for MT6.** | Done log: see docs/STATE.md
