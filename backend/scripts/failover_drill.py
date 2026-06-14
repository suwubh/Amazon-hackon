"""MT5 failover drill — prove the provider chain degrades safely on stage.

The pitch's reliability story is: Gemini 2.5 Flash (primary) → Bedrock Nova 2 Lite
(failover) → committed cached response. This script proves it end-to-end against the
real SL-001 grade, by running three subprocesses (config is read at import, so each
stage needs a fresh process):

    Stage 1  primary healthy            -> source: live-<primary>
    Stage 2  primary broken (bad key)   -> source: live-<fallback>   (failover fires)
    Stage 3  both broken                -> source: cached            (kill-switch floor)

The grade LETTER must be identical across all three (D for SL-001) — that's what keeps
the hero VRS math (+₹83 / −₹129) invariant no matter who answers.

Run from backend/ with .env present (real GEMINI_API_KEY + AWS creds for Bedrock):
    python scripts/failover_drill.py

Exit code 0 = all three stages behaved as designed.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ITEM = "SL-001"


def _worker() -> None:
    """Run one live grade in this process's env and print the result as JSON."""
    sys.path.insert(0, str(BACKEND))
    os.environ.pop("DYNAMODB_TABLE_NAME", None)  # keep the drill hermetic
    from app.grading import grade_item
    try:
        r = grade_item(ITEM)  # no force_cached -> exercises the live chain, then cache
        print(json.dumps({"grade": r["grade"], "source": r["source"], "model": r["model"]}))
    except Exception as e:  # pragma: no cover - surfaced to the orchestrator
        print(json.dumps({"error": f"{type(e).__name__}: {e}"}))


def _run_stage(name: str, env_overrides: dict, expect_source_prefix: str) -> tuple[bool, dict]:
    env = {**os.environ, **env_overrides, "PYTHONIOENCODING": "utf-8"}
    out = subprocess.run(
        [sys.executable, __file__, "--worker"],
        cwd=str(BACKEND), env=env, capture_output=True, text=True,
    )
    # The worker prints exactly one JSON line; provider-failure warnings go to stderr.
    line = next((l for l in out.stdout.splitlines() if l.strip().startswith("{")), "{}")
    res = json.loads(line)
    ok = res.get("source", "").startswith(expect_source_prefix)
    print(f"  {name}: source={res.get('source') or res.get('error')!r} "
          f"grade={res.get('grade')!r}  -> {'OK' if ok else 'FAIL (expected ' + expect_source_prefix + ')'}")
    return ok, res


def main() -> int:
    base = {"LLM_PRIMARY": "gemini", "LLM_FALLBACK": "bedrock", "GEMINI_MODEL": "gemini-2.5-flash"}
    print(f"Failover drill on {ITEM} (primary=gemini, fallback=bedrock):")

    # Stage 1 sets no GEMINI_API_KEY so the worker loads the real one from .env
    # (load_dotenv won't override a key we explicitly set, hence the bad keys below work).
    # Expect any LIVE provider: Gemini answers, or — if its free-tier quota is 429-walled —
    # it auto-fails-over to Nova. Both are live and correct; the stage demo can't tell.
    ok1, r1 = _run_stage("Stage 1 (primary healthy)   ", base, "live-")
    ok2, r2 = _run_stage("Stage 2 (primary broken)    ",
                         {**base, "GEMINI_API_KEY": "BAD-KEY-INVALID"}, "live-bedrock")
    ok3, r3 = _run_stage("Stage 3 (both broken)       ",
                         {**base, "GEMINI_API_KEY": "BAD-KEY-INVALID",
                          "BEDROCK_MODEL_ID": "bogus.nonexistent-model-v9:0"}, "cached")

    grades = {r.get("grade") for r in (r1, r2, r3) if r.get("grade")}
    grade_stable = len(grades) == 1
    print(f"  grade stable across all stages: {grade_stable} ({sorted(grades)})")

    passed = ok1 and ok2 and ok3 and grade_stable
    print("RESULT:", "PASS — chain degrades safely, grade invariant." if passed
          else "FAIL — see stages above.")
    return 0 if passed else 1


if __name__ == "__main__":
    if "--worker" in sys.argv:
        _worker()
    else:
        sys.exit(main())
