"""Delta-Grader: multimodal condition grading against an item's own day-0 photos.

The LLM is a perception layer only — it returns structured condition facts
(validated against GradeCore); all rupee math happens downstream in vrs.py.
Chain: Bedrock Nova 2 Lite → Gemini 2.5 Flash → committed cached response.
Invalid JSON gets one retry with the validation error in the prompt.
"""
import json
import logging
import time
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from . import passport, seed
from .llm import PROVIDER_MODEL, ask_llm_images

log = logging.getLogger("grading")

GRADING_SYSTEM = (
    "You are a meticulous returns inspector for an e-commerce marketplace. "
    "You compare photos and output ONLY a single JSON object matching the requested schema — "
    "no markdown, no code fences, no commentary."
)

# Per-category completeness checklists the inspector verifies against.
CHECKLISTS = {
    "footwear": ["original box", "spare laces"],
    "electronics": ["original box", "charger or power adapter", "user manual"],
    "apparel": ["price tag attached", "original packaging"],
    "appliances": ["original box", "accessories", "user manual"],
    "books": ["cover intact"],
    "home": ["original box", "lid or cap"],
    "bags": ["tags", "rain cover"],
}

RUBRIC = (
    "A = like new, indistinguishable from day-0. "
    "B = light wear: minor scuffs, sole dirt or creasing; clean after a wipe. "
    "C = clearly visible wear or soiling but structurally intact and fully functional "
    "(heavy but cleanable soiling is C, not D). "
    "D = damaged, torn, broken, or missing essential parts."
)


class SameUnit(BaseModel):
    verified: bool
    confidence: float = Field(..., ge=0, le=1)


class Defect(BaseModel):
    area: str
    description: str
    severity: Literal["minor", "moderate", "major"]


class CompletenessItem(BaseModel):
    item: str
    present: bool


class GradeCore(BaseModel):
    """What the model must return — the perception facts."""
    same_unit: SameUnit
    grade: Literal["A", "B", "C", "D"]
    defects: list[Defect]
    completeness: list[CompletenessItem]
    usage_detected: bool
    confidence: float = Field(..., ge=0, le=1)
    justification: str


class CacheMiss(Exception):
    """Both live providers failed (or were skipped) and no cached response exists."""


def _build_prompt(item: dict, n_catalog: int, n_day0: int, n_current: int) -> str:
    checklist = CHECKLISTS.get(item["category"], [])
    schema = (
        '{"same_unit": {"verified": bool, "confidence": 0.0-1.0}, '
        '"grade": "A"|"B"|"C"|"D", '
        '"defects": [{"area": str, "description": str, "severity": "minor"|"moderate"|"major"}], '
        '"completeness": [{"item": str, "present": bool}], '
        '"usage_detected": bool, "confidence": 0.0-1.0, "justification": str}'
    )
    return (
        f"Item: {item['title']} (category: {item['category']}).\n"
        f"Image order: image 1{'-' + str(n_catalog) if n_catalog > 1 else ''} = CATALOG listing photo; "
        f"next {n_day0} = DAY-0 photos of this exact unit taken at delivery; "
        f"last {n_current} = CURRENT photos taken now, at return initiation.\n\n"
        "Compare the CURRENT photos against the CATALOG image and the DAY-0 photos of this unit. Tasks:\n"
        "1. same_unit: is the CURRENT item physically the same unit as DAY-0 "
        "(model, colorway, markings, wear pattern, label/serial positions)? Give a confidence 0-1.\n"
        "2. defects: every visible difference from day-0 condition — name the specific area "
        "(e.g. 'toe-box-left', 'sole-heel'), describe it, rate severity minor/moderate/major. "
        "Empty list only if truly indistinguishable from day-0.\n"
        f"3. completeness: for each of {json.dumps(checklist)}, say whether it is visibly present "
        "in the CURRENT photos (not visible = false).\n"
        f"4. grade using this rubric strictly: {RUBRIC}\n"
        "5. usage_detected: true if the item shows signs of having been worn or used (not just unboxed).\n"
        "6. confidence 0-1 for the overall assessment, and a one-line justification a customer would trust.\n\n"
        f"Return ONLY this JSON, nothing else: {schema}"
    )


def _parse_core(text: str) -> GradeCore:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in model output")
    return GradeCore.model_validate(json.loads(text[start:end + 1]))


def _grade_live(item: dict) -> tuple[GradeCore, str]:
    """One live grading pass + one retry-with-error. Returns (core, provider)."""
    imgs = seed.item_images(item["item_id"])
    images = [p.read_bytes() for p in imgs["catalog"] + imgs["day0"] + imgs["current"]]
    if not imgs["current"]:
        raise FileNotFoundError(f"no current photos for {item['item_id']}")
    prompt = _build_prompt(item, len(imgs["catalog"]), len(imgs["day0"]), len(imgs["current"]))

    text, provider = ask_llm_images(prompt, images, GRADING_SYSTEM)
    try:
        return _parse_core(text), provider
    except (ValueError, ValidationError, json.JSONDecodeError) as e:
        log.warning("Invalid grading JSON (%s) — retrying with the error in the prompt.", e)
        retry_prompt = (
            f"{prompt}\n\nYour previous output was invalid: {e}\n"
            f"Previous output: {text[:1500]}\nReturn ONLY the corrected JSON."
        )
        text, provider = ask_llm_images(retry_prompt, images, GRADING_SYSTEM)
        return _parse_core(text), provider


def grade_item(item_id: str, force_cached: bool = False) -> dict:
    """Full /grade flow. Raises KeyError for unknown items, CacheMiss if nothing can answer."""
    item = seed.get_item(item_id)
    if item is None:
        raise KeyError(item_id)

    t0 = time.monotonic()
    core = None
    source = model = ""

    if not force_cached:
        try:
            graded, provider = _grade_live(item)
            core = graded.model_dump()
            source, model = f"live-{provider}", PROVIDER_MODEL[provider]
        except Exception as e:
            log.warning("Live grading failed for %s (%s) — trying cache.", item_id, e)

    if core is None:
        cached = seed.cached_response(item_id, "grade")
        if cached is None:
            raise CacheMiss(item_id)
        core = {k: v for k, v in cached.items() if k != "model"}
        source, model = "cached", cached.get("model", PROVIDER_MODEL["bedrock"])

    result = {
        "item_id": item_id,
        **core,
        "needs_human_review": core["confidence"] < 0.70,
        "source": source,
        "model": model,
        "latency_ms": int((time.monotonic() - t0) * 1000),
    }
    passport.append_event(item_id, "GRADED", {
        "grade": result["grade"], "confidence": result["confidence"],
        "defects": result["defects"], "same_unit": result["same_unit"],
        "usage_detected": result["usage_detected"], "justification": result["justification"],
        "source": source,
    })
    return result
