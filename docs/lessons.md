# Lessons

One lesson per entry, newest on top, one-line summary first. Read this every fresh session. Don't duplicate what CLAUDE.md/architecture.md already record.

## MT2 (June 13)
- **The IAM deploy blocker is RESOLVED.** `deploy.ps1` now pushes to ECR and runs `aws lambda update-function-code` successfully; the new image is live on the Function URL. Quirk: the `aws ecr get-login-password | docker login` step still prints `400 Bad Request`, but `docker push` succeeds anyway because Docker reuses cached ECR creds from a prior good login — so a 400 on the login line is NOT a deploy failure; check for `latest: digest: sha256...` and `Done. Deployed` at the end instead.
- **deploy.ps1 must run from `backend/`** (its build context is `.`). The PowerShell tool's working dir was already `backend`, so a leading `Set-Location backend` errored with `backend\backend not found` — harmless, the script still ran from the right place. If you script it, guard the cd or just run `./deploy.ps1` from backend.
- **Background shells (`run_in_background`) start in a fresh CWD, not the persisted one** — use absolute paths (`cd "C:/.../backend"`) when launching uvicorn/scripts in the background, or you get `cd: backend: No such file or directory`.
- **Windows console is cp1252 — printing the ₹ char (U+20B9) crashes with UnicodeEncodeError.** Set `PYTHONIOENCODING=utf-8` for any python that prints rupee strings (e.g. radar ping_message), or extract numeric fields instead of printing the whole JSON.
- **VRS integrity rule that MT3 depends on:** each path's `recovery` is the exact sum of its `breakdown` values (sale/credit positive, costs negative). The frontend renders the breakdown and the total must reconcile on screen. If you tune a constant, keep this invariant.
- **The api-spec /route example numbers were illustrative and didn't sum** (and assumed grade B). MT2 made them real: the example now reflects the live grade-D output for SL-001 and every figure reconciles. Recovery scales with grade — don't expect the +₹290 "hero" number unless the shoe is graded B (current placeholder cache grades it D → local +₹83).
- **Sealed RTO items skip grading** (architecture §3.2): `/route` normally 409s without a prior grade, but a verified-sealed RTO item routes as factory-new (grade A) with no grade required. So the RTO demo beat is seal-check → route (no scan).
- **In-memory passport is per-Lambda-instance.** `/route` and `/health-card` need the prior `/grade`/`/route` events to be in the SAME warm instance. Sequential demo curls reuse one instance so it works; a cold start (or parallel calls hitting different instances) loses the chain → 409. For a bulletproof stage, set `DYNAMODB_TABLE_NAME` (MT5) or always run the spine in order on one session.

## MT1 (June 13)
- **Deploy is blocked by IAM, not code.** The configured AWS CLI user `hackon-app` (account 656751413989) can invoke Bedrock (local grading works) but is **denied `ecr:GetAuthorizationToken`/ECR push and `lambda:UpdateFunctionCode`** → `deploy.ps1` builds fine, then fails at ECR login (400) and Lambda update (AccessDeniedException). A failed deploy changes nothing on the live function, so the demo path stays up — but **MT2 cannot ship to Lambda until `hackon-app` gets ECR-push + Lambda-deploy permissions, or deploy.ps1 is run with admin creds.** HUMAN TASK before MT2.
- **Nova-2 multimodal converse: image blocks go in `content` as `{"image": {"format": "jpeg", "source": {"bytes": <raw bytes>}}}`** (raw bytes, not base64), text block last. Worked first try in ca-central-1.
- **Grading consistency is solid at temperature=0.2**: hero shoe graded D/D/D across 3 live runs. The same-unit check is genuinely discriminative — placeholder current-photo (different shoe) correctly returned `same_unit.verified=false`; swap in real day-0-vs-now photos of the *same* unit before judging same-unit accuracy.
- **Git on Windows rewrites LF→CRLF** on these files (harmless warning); seed `.jpg`/`.json` commit fine and bake into the container via `COPY app` in the Dockerfile.

## Pre-build gotchas (carried from boilerplate phase — verified the hard way)
- **Bedrock throttles new accounts in us-east-1** → everything runs in ca-central-1.
- **Nova 2 Lite needs the inference-profile ID** `us.amazon.nova-2-lite-v1:0` (fallback `global.amazon.nova-2-lite-v1:0`), not a bare model ID.
- **Nova 2 is a reasoning model** → responses may contain a `reasoningContent` block before the text; extract the block that has `text`, never `content[0]`. Same applies to multimodal/JSON outputs.
- **Lambda container builds need `--provenance=false`** (handled in deploy.ps1); base image already has the RIC; x86_64, 512 MB, 30s timeout.
- **`load_dotenv()` must run before boto3 use locally**, else `NoCredentialsError`.
- **CORS lives in the FastAPI app only**; Function URL CORS stays disabled or it answers preflights itself.
- **Bedrock calls must be time-bounded** (connect 5s / read 15s, 2 retries) so a hung primary fails over to Gemini before the Lambda 30s timeout. Budget: with images, leave headroom — one live multimodal call + one fallback must fit in 30s.
- **Failover needs both creds present** (Bedrock via role/keys + `GEMINI_API_KEY`).
- **Don't use the full /gsd:* ceremony as the build spine** — plain task-by-task per docs/tasks.md; /gsd:debug, /code-review, /verify as point tools.
