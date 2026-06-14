"""Delta-Grader: multimodal condition grading against an item's own day-0 photos.

The LLM is a perception layer only — it returns structured condition facts
(validated against GradeCore); all rupee math happens downstream in vrs.py.
Chain: Bedrock Nova 2 Lite → Gemini 2.5 Flash → committed cached response.
Invalid JSON gets one retry with the validation error in the prompt.
"""
import base64
import binascii
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
    "A = same physical condition as day-0 with no new wear; differences limited to "
    "lighting, camera angle, distance, background, or image quality must NOT lower the grade. "
    "B = light wear: minor scuffs, sole dirt or creasing; cleans up after a wipe. "
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
    # Two-way identity (MT12 NEW 10): catalog_matches_day0 is whether the seller's
    # CATALOG photo matches the DAY-0 unit (seller-side honesty); same_unit is
    # whether the CURRENT unit matches DAY-0 (customer-side honesty). Optional so a
    # model that omits it doesn't fail the parse — absence is treated as "matches".
    catalog_matches_day0: SameUnit | None = None
    grade: Literal["A", "B", "C", "D"]
    defects: list[Defect]
    completeness: list[CompletenessItem]
    usage_detected: bool
    confidence: float = Field(..., ge=0, le=1)
    justification: str


class CacheMiss(Exception):
    """Both live providers failed (or were skipped) and no cached response exists."""


class ImageTooLarge(Exception):
    """An uploaded current photo exceeds the decoded-size cap."""


# Uploaded current photos are decoded server-side. Caps bound abuse of the public
# endpoint AND keep the request under the Lambda Function URL's 6 MB limit. The
# frontend downscales to ~1024px/~300 KB before sending; this is the hard ceiling.
MAX_UPLOAD_BYTES = 1_500_000  # ~1.5 MB per image, decoded


def _decode_uploads(images_b64: list[str]) -> list[bytes]:
    """Decode base64 current-photo uploads to raw bytes, enforcing the size cap.

    Accepts an optional ``data:image/...;base64,`` prefix. Raises ImageTooLarge if
    any decoded image is over the cap, ValueError on malformed base64.
    """
    out: list[bytes] = []
    for s in images_b64:
        if "," in s and s.strip().startswith("data:"):
            s = s.split(",", 1)[1]
        try:
            raw = base64.b64decode(s, validate=True)
        except (binascii.Error, ValueError) as e:
            raise ValueError(f"invalid base64 image: {e}")
        if len(raw) > MAX_UPLOAD_BYTES:
            raise ImageTooLarge(f"image is {len(raw)} bytes (cap {MAX_UPLOAD_BYTES})")
        out.append(raw)
    return out


def _build_prompt(item: dict, n_catalog: int, n_day0: int, n_current: int) -> str:
    checklist = CHECKLISTS.get(item["category"], [])
    schema = (
        '{"same_unit": {"verified": bool, "confidence": 0.0-1.0}, '
        '"catalog_matches_day0": {"verified": bool, "confidence": 0.0-1.0}, '
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
        "1. same_unit: is the CURRENT item physically the same unit and the same product as "
        "the DAY-0 photos (brand, model, colorway, markings, wear pattern, label/serial positions)? "
        "If it is clearly a different product or not the product at all, set verified=false. "
        "Give a confidence 0-1.\n"
        "1b. catalog_matches_day0: does the seller's CATALOG listing photo show the same product "
        "as the DAY-0 unit (brand, model, colorway)? If the catalog advertises a clearly different "
        "product than what was delivered, set verified=false. Give a confidence 0-1.\n"
        "2. defects: list ONLY genuine physical condition changes from day-0 — new scuffs, "
        "scratches, stains, soiling, tears, fading, deformation, or missing/added parts. Name the "
        "specific area (e.g. 'toe-box-left', 'sole-heel'), describe it, rate severity "
        "minor/moderate/major. Do NOT report differences caused by lighting, camera angle, distance, "
        "background, shadows, or image quality. If the unit's physical condition matches day-0 once "
        "those capture differences are ignored, return an empty list.\n"
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


def _grade_live(item: dict, current_override: list[bytes] | None = None) -> tuple[GradeCore, str]:
    """One live grading pass + one retry-with-error. Returns (core, provider).

    Catalog + day-0 (the baseline) always come from the seed. The CURRENT set is the
    uploaded photos when ``current_override`` is given (the agent's live capture),
    else the seeded current photos.
    """
    imgs = seed.item_images(item["item_id"])
    if current_override:
        current = current_override
    else:
        current = [p.read_bytes() for p in imgs["current"]]
    if not current:
        raise FileNotFoundError(f"no current photos for {item['item_id']}")
    images = [p.read_bytes() for p in imgs["catalog"] + imgs["day0"]] + current
    prompt = _build_prompt(item, len(imgs["catalog"]), len(imgs["day0"]), len(current))

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


def grade_item(item_id: str, force_cached: bool = False,
               current_images: list[str] | None = None) -> dict:
    """Full /grade flow. Raises KeyError for unknown items, CacheMiss if nothing can
    answer, ImageTooLarge / ValueError for bad uploads.

    ``current_images`` (base64) are the agent's freshly-captured current photos. When
    present we grade the *uploaded* photos live (catalog + day-0 baseline from seed).
    They're decoded up front so a bad upload fails fast — before any LLM call — and a
    live failure still falls back to cache.
    """
    item = seed.get_item(item_id)
    if item is None:
        raise KeyError(item_id)

    override = _decode_uploads(current_images) if current_images else None

    t0 = time.monotonic()
    core = None
    source = model = ""
    graded_uploaded = False

    if not force_cached:
        try:
            graded, provider = _grade_live(item, override)
            core = graded.model_dump()
            source, model = f"live-{provider}", PROVIDER_MODEL[provider]
            graded_uploaded = override is not None
        except Exception as e:
            log.warning("Live grading failed for %s (%s) — trying cache.", item_id, e)

    if core is None:
        cached = seed.cached_response(item_id, "grade")
        if cached is None:
            raise CacheMiss(item_id)
        core = {k: v for k, v in cached.items() if k != "model"}
        source, model = "cached", cached.get("model", PROVIDER_MODEL["bedrock"])

    # Fault attribution (MT12 NEW 10) — two-way identity check decides whose fault a
    # mismatch is, and whether the item can be returned:
    #   • CATALOG ≠ DAY-0   → SELLER's fault (listed the wrong product); buyer CAN return.
    #   • CATALOG == DAY-0 but CURRENT ≠ DAY-0 → CUSTOMER's fault (swapped the unit);
    #     NOT returnable + flagged for human review.
    su = core["same_unit"]
    cat = core.get("catalog_matches_day0")
    catalog_ok = True if not cat else bool(cat.get("verified", True))
    same_ok = bool(su["verified"])

    if not catalog_ok:
        fault_attribution = "seller"
        returnable = True
    elif not same_ok:
        fault_attribution = "customer"
        returnable = False
    else:
        fault_attribution = "none"
        returnable = True

    # Trust gate: a grade is only trustworthy if the model confirmed this is the same
    # unit/product as day-0. A different product (or a non-product image) must NOT pass
    # as a clean letter grade — it gets flagged for human review with the reason surfaced.
    if fault_attribution == "seller":
        review_reason = "Catalog photo doesn't match the delivered unit — seller listing error, flagged for review."
    elif fault_attribution == "customer":
        review_reason = "Returned item isn't the unit that was delivered — not eligible for return, flagged for review."
    elif su["confidence"] < 0.50:
        review_reason = "Low confidence the item matches day-0 — flagged for manual review."
    elif core["confidence"] < 0.70:
        review_reason = "Low overall grading confidence — flagged for manual review."
    else:
        review_reason = None

    result = {
        "item_id": item_id,
        **core,
        "fault_attribution": fault_attribution,
        "returnable": returnable,
        "needs_human_review": review_reason is not None,
        "review_reason": review_reason,
        "source": source,
        "model": model,
        "graded_uploaded_photos": graded_uploaded,
        "latency_ms": int((time.monotonic() - t0) * 1000),
    }
    passport.append_event(item_id, "GRADED", {
        "grade": result["grade"], "confidence": result["confidence"],
        "defects": result["defects"], "same_unit": result["same_unit"],
        "usage_detected": result["usage_detected"], "justification": result["justification"],
        "source": source,
    })
    return result
