"""Seal-Check (RTO lane) + Listing Diagnostics — the two non-grading vision calls.

Same perception-layer discipline and Bedrock→Gemini→cache chain as grading.py:
the model returns structured facts validated against a Pydantic schema; on any
failure (or with no photos yet) we serve the committed cached response. Today the
seeded RTO/kurta items have no photos, so these serve cache — which is exactly the
stage-safe path anyway. Live calls switch on automatically once photos land.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from . import passport, seed
from .llm import PROVIDER_MODEL, ask_llm_images

log = logging.getLogger("inspection")

SEAL_SYSTEM = (
    "You are a returns inspector verifying whether a parcel is factory-sealed and "
    "untampered. Output ONLY one JSON object matching the schema — no prose, no fences."
)
DIAGNOSE_SYSTEM = (
    "You are a catalog-quality analyst. You compare a product listing against photos "
    "of returned units and the reasons buyers gave. Output ONLY one JSON object "
    "matching the schema — no prose, no fences."
)


class CacheMiss(Exception):
    """Live providers failed/skipped and no cached response exists."""


class SealCore(BaseModel):
    sealed: bool
    tamper_evidence: str | None = None
    verdict: Literal["SEALED_NEW", "OPENED"]
    confidence: float = Field(..., ge=0, le=1)


class Discrepancy(BaseModel):
    aspect: str
    listing_shows: str
    returns_show: str


class Patch(BaseModel):
    field: str
    current_text: str
    suggested_text: str


class DiagnoseCore(BaseModel):
    returns_analyzed: int
    discrepancies: list[Discrepancy]
    patch: Patch
    projected_return_reduction_pct: int = Field(..., ge=0, le=100)


def _extract_json(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in model output")
    return json.loads(text[start:end + 1])


def _live(prompt: str, images: list[bytes], system: str, schema_model):
    """One vision pass + one retry-with-error. Returns (core, provider)."""
    text, provider = ask_llm_images(prompt, images, system)
    try:
        return schema_model.model_validate(_extract_json(text)), provider
    except (ValueError, ValidationError, json.JSONDecodeError) as e:
        log.warning("Invalid JSON (%s) — retrying with the error in the prompt.", e)
        retry = f"{prompt}\n\nYour previous output was invalid: {e}\nReturn ONLY the corrected JSON."
        text, provider = ask_llm_images(retry, images, system)
        return schema_model.model_validate(_extract_json(text)), provider


def _serve(item_id: str, call: str, core_dict, source: str, model: str, t0: float, extra: dict) -> dict:
    return {"item_id": item_id, **core_dict, **extra,
            "source": source, "model": model, "latency_ms": int((time.monotonic() - t0) * 1000)}


def seal_check(item_id: str, force_cached: bool = False) -> dict:
    item = seed.get_item(item_id)
    if item is None:
        raise KeyError(item_id)

    t0 = time.monotonic()
    core = None
    source = model = ""

    if not force_cached:
        try:
            imgs = seed.item_images(item_id)["current"]
            if not imgs:
                raise FileNotFoundError(f"no package photo for {item_id}")
            prompt = (
                f"Parcel for order {item['order']['order_id']} ({item['title']}). "
                "Inspect the photo. Is the manufacturer/marketplace seal intact and the box "
                "unopened? Report tamper_evidence (torn tape, reseal marks, dents exposing "
                "contents) or null if none. verdict SEALED_NEW only if untampered and unopened, "
                "else OPENED. Return ONLY: "
                '{"sealed": bool, "tamper_evidence": str|null, "verdict": "SEALED_NEW"|"OPENED", '
                '"confidence": 0.0-1.0}'
            )
            graded, provider = _live(prompt, [p.read_bytes() for p in imgs], SEAL_SYSTEM, SealCore)
            core, source, model = graded.model_dump(), f"live-{provider}", PROVIDER_MODEL[provider]
        except Exception as e:
            log.warning("Live seal-check failed for %s (%s) — trying cache.", item_id, e)

    if core is None:
        cached = seed.cached_response(item_id, "seal")
        if cached is None:
            raise CacheMiss(item_id)
        core = {k: v for k, v in cached.items() if k != "model"}
        source, model = "cached", cached.get("model", PROVIDER_MODEL["bedrock"])

    passport.append_event(item_id, "SEAL_CHECKED",
                          {"sealed": core["sealed"], "verdict": core["verdict"], "source": source})
    return _serve(item_id, "seal", core, source, model, t0, {})


def diagnose_listing(asin: str, force_cached: bool = False) -> dict:
    item = seed.item_by_asin(asin)
    if item is None:
        raise KeyError(asin)
    item_id = item["item_id"]

    t0 = time.monotonic()
    core = None
    source = model = ""

    if not force_cached:
        try:
            imgs = seed.item_images(item_id)
            photos = imgs["catalog"] + imgs["current"]
            if not photos:
                raise FileNotFoundError(f"no listing/return photos for {item_id}")
            prompt = (
                f"Listing: \"{item['title']}\" (ASIN {asin}). Buyers returned units citing: "
                f"\"{item.get('return_reason') or 'various'}\". The first photo is the catalog "
                "image; the rest are returned units. Find where the listing misrepresents the "
                "product (color, fit, size, material). Propose one concrete title/photo patch and "
                "estimate the % of returns it would prevent. Return ONLY: "
                '{"returns_analyzed": int, "discrepancies": [{"aspect": str, "listing_shows": str, '
                '"returns_show": str}], "patch": {"field": str, "current_text": str, '
                '"suggested_text": str}, "projected_return_reduction_pct": int}'
            )
            graded, provider = _live(prompt, [p.read_bytes() for p in photos], DIAGNOSE_SYSTEM, DiagnoseCore)
            core, source, model = graded.model_dump(), f"live-{provider}", PROVIDER_MODEL[provider]
        except Exception as e:
            log.warning("Live diagnose-listing failed for %s (%s) — trying cache.", asin, e)

    if core is None:
        cached = seed.cached_response(item_id, "diagnose")
        if cached is None:
            raise CacheMiss(asin)
        core = {k: v for k, v in cached.items() if k != "model"}
        source, model = "cached", cached.get("model", PROVIDER_MODEL["bedrock"])

    return {"asin": asin, **core, "source": source, "model": model,
            "latency_ms": int((time.monotonic() - t0) * 1000)}
