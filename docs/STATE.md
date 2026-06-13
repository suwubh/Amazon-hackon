# Project State — Amazon Second Life

## Status: MT2 done & verified on the DEPLOYED Function URL (June 13, 2026)

## Done
- ✅ PS + angle locked: Stores "Products Without a Second Chance" → Second Life (delta-grading + VRS interception + Health Card + Idle Asset Radar spine), per STEP 1 + strategic review of the master playbook
- ✅ All plan files written: CLAUDE.md (project + environment), docs/PRD.md, architecture.md, api-spec.md, tasks.md, demo-and-prfaq.md, db-setup.md, lessons.md
- ✅ Boilerplate deployed & verified (pre-hackathon): FastAPI on Lambda (ca-central-1, Function URL) + Bedrock Nova 2 Lite w/ Gemini failover + React/Tailwind on Vercel
- ✅ **MT1 — Seed store + Product Passport + Delta-Grader** (commit `be97d15`). Local-verified, fresh verifier signed off. Built: `seed/` (8 items + orders + neighbors JSON, placeholder images for SL-001 shoe & SL-002 monitor, cached grades), `passport.py` (in-memory event log + DynamoDB write-through behind flag), `grading.py` (Nova-2 multimodal delta-grader, Pydantic schema, retry-on-bad-JSON, Bedrock→Gemini→cache), `llm.py` `ask_llm_images()`, endpoints `GET /items`, `GET /items/{id}`, `POST /grade`, `scripts/capture_cache.py`. Hero shoe grades **D/D/D** across 3 live runs (consistency ✅); creds-broken server returns identical shape with `source:cached` ✅.
- ✅ **MT2 — VRS engine + Health Card + RTO + Radar + Pricing + deploy** (this session). **DEPLOY BLOCKER RESOLVED** — `deploy.ps1` now pushes to ECR and updates Lambda successfully (IAM fixed). All endpoints in docs/api-spec.md are LIVE on the Function URL and a fresh verifier signed off (9/9). Built: `pricing.py` (per-category depreciation, grade factors, resale, −5%/wk price decay, liquidity curve), `vrs.py` (6-path engine, breakdowns that sum exactly to recovery, eligibility gates, winner=argmax, co2/km saved; sealed RTO skips grading→grade A), `radar.py` (Idle Asset Radar over orders/neighbors), `healthcard.py` (provenance + warranty calc + price decay), `inspection.py` (`/seal-check` + `/diagnose-listing`, live-AI→cache), `metrics.py` (passport + baseline counters). New endpoints: `POST /route`, `GET /health-card/{id}`, `POST /seal-check`, `GET /radar/{asin}`, `GET /price-curve/{id}`, `POST /diagnose-listing`, `GET /metrics`. Cached AI responses added: `SL-004.seal.json` (SEALED_NEW), `SL-003.diagnose.json` (navy→royal blue). VRS constants LOCKED in architecture.md §4. Hero shoe → `local_p2p` winner at every grade (grade D: local **+₹83** vs warehouse **−₹129**); sealed mixer → `rto_relist` **+₹2,464**.

## In Progress
- (nothing — MT2 closed; next session starts MT3, the frontend spine)

## Next: **MT3 — Frontend spine: the demo console** (B builds with Fable, A supports API) — see docs/tasks.md
The 5-screen hero flow clickable end-to-end on Vercel (phone-frame, Amazon-look): Returns inbox → item + guided-capture → delta-grade screen → VRS screen (6 paths animate in with rupee math, winner highlighted) → Health Card → radar ping toast. Backend is fully ready: every number comes from a live endpoint (no hardcoded JSX). Use `force_cached:true` on `/grade` for the stage-safe path.
Verify check: live Vercel URL full click-through with real backend; with `force_cached` → visually identical; no dead buttons on the spine; playwright/chrome-devtools pass.

## Open items (not blocking MT3)
- **Real demo photos** still pending (you'll add later). Today: SL-001/SL-002 use Wikimedia placeholders (grade live or cached); SL-003..008 are metadata-only → `/grade` 502 (cached covers SL-001/002). `/seal-check` (SL-004) and `/diagnose-listing` (SL-003) serve hand-authored cached responses — the stage-safe path — until photos land, then re-capture with `python scripts/capture_cache.py --seal SL-004` / `--diagnose SL-003`. None of this blocks the MT3 spine.
- Frontend must serve item thumbnails from `frontend/public/items/...` (the `thumb`/`photos` paths are frontend-static, not a backend route).

## Current major task queue
MT1 ✅ → MT2 ✅ → MT3 (⭐ spine, hour-24 target) → MT4 → MT5 → MT6 (submission). One MT per session; end-of-session protocol: commit → update STATE/tasks/lessons → handoff → new session.
