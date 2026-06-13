"""LLM call with automatic failover.

Primary provider is tried first; if it raises (throttling, validation, network,
missing creds, etc.) it transparently falls back to the secondary provider.
Configure with env vars:
    LLM_PRIMARY   = bedrock | gemini | openai   (default: bedrock)
    LLM_FALLBACK  = bedrock | gemini | openai   (default: gemini)
Per-provider settings (region, model, keys) are read from the same .env.
"""
import os
import logging
from dotenv import load_dotenv

load_dotenv()  # read backend/.env

log = logging.getLogger("llm")

PRIMARY = os.getenv("LLM_PRIMARY", "bedrock").lower()
FALLBACK = os.getenv("LLM_FALLBACK", "gemini").lower()

AWS_REGION = os.getenv("AWS_REGION", "ca-central-1")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "us.amazon.nova-2-lite-v1:0")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "You are a helpful assistant for our hackathon prototype. Be concise.")


def _ask_bedrock(prompt: str) -> str:
    import boto3
    from botocore.config import Config
    # Bound how long a hung Bedrock call can block: without this, boto3 waits up
    # to 60s on read before failing, burning Lambda duration before failover.
    cfg = Config(connect_timeout=5, read_timeout=15, retries={"max_attempts": 2})
    client = boto3.client("bedrock-runtime", region_name=AWS_REGION, config=cfg)
    resp = client.converse(
        modelId=BEDROCK_MODEL_ID,
        system=[{"text": SYSTEM_PROMPT}],
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 512, "temperature": 0.7},
    )
    # Nova 2 is a reasoning model: response may include a reasoningContent block
    # before the text block, so pull out the text block specifically.
    for part in resp["output"]["message"]["content"]:
        if "text" in part:
            return part["text"]
    raise RuntimeError("Bedrock returned no text block")


def _ask_gemini(prompt: str) -> str:
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    resp = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            max_output_tokens=512,
            temperature=0.7,
        ),
    )
    return resp.text


def _ask_openai(prompt: str) -> str:
    from openai import OpenAI
    client = OpenAI()  # reads OPENAI_API_KEY
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
        max_tokens=512, temperature=0.7,
    )
    return resp.choices[0].message.content


def _ask_bedrock_vision(prompt: str, images: list[bytes], system: str,
                        max_tokens: int, temperature: float) -> str:
    import boto3
    from botocore.config import Config
    cfg = Config(connect_timeout=5, read_timeout=15, retries={"max_attempts": 2})
    client = boto3.client("bedrock-runtime", region_name=AWS_REGION, config=cfg)
    content = [{"image": {"format": "jpeg", "source": {"bytes": b}}} for b in images]
    content.append({"text": prompt})
    resp = client.converse(
        modelId=BEDROCK_MODEL_ID,
        system=[{"text": system}],
        messages=[{"role": "user", "content": content}],
        inferenceConfig={"maxTokens": max_tokens, "temperature": temperature},
    )
    for part in resp["output"]["message"]["content"]:
        if "text" in part:
            return part["text"]
    raise RuntimeError("Bedrock returned no text block")


def _ask_gemini_vision(prompt: str, images: list[bytes], system: str,
                       max_tokens: int, temperature: float) -> str:
    from google import genai
    from google.genai import types
    # Bound the primary call so a hung Gemini request fails over to the Bedrock fallback
    # well inside the Lambda 30s budget (mirrors the Bedrock connect/read timeouts).
    client = genai.Client(
        api_key=os.getenv("GEMINI_API_KEY"),
        http_options=types.HttpOptions(timeout=18000),  # milliseconds
    )
    parts = [types.Part.from_bytes(data=b, mime_type="image/jpeg") for b in images]
    parts.append(types.Part.from_text(text=prompt))
    resp = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=parts,
        config=types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
            temperature=temperature,
            # Every vision caller (grade/seal/diagnose) wants a single JSON object.
            # Native JSON mode guarantees well-formed output — no fences, no prose,
            # no trailing commas — which the free-text path returned intermittently.
            response_mime_type="application/json",
            # Gemini 2.5 Flash is a thinking model: reasoning tokens count against
            # max_output_tokens, so on harder cases it would exhaust the budget mid-JSON
            # and return a truncated object. Structured extraction needs no extended
            # thinking — disable it so the whole budget goes to the JSON (also faster).
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    if not resp.text:
        raise RuntimeError("Gemini returned no text")
    return resp.text


_PROVIDERS = {"bedrock": _ask_bedrock, "gemini": _ask_gemini, "openai": _ask_openai}
_VISION_PROVIDERS = {"bedrock": _ask_bedrock_vision, "gemini": _ask_gemini_vision}

# Human-readable model id per provider, for the "model" field in AI responses.
PROVIDER_MODEL = {"bedrock": BEDROCK_MODEL_ID, "gemini": GEMINI_MODEL, "openai": OPENAI_MODEL}


def ask_llm_images(prompt: str, images: list[bytes], system: str,
                   max_tokens: int = 1024, temperature: float = 0.2) -> tuple[str, str]:
    """Multimodal ask with the same primary→fallback chain.

    Returns (text, provider) so callers can report source: live-bedrock | live-gemini.
    Raises if both vision-capable providers fail — callers fall back to cache.
    """
    order = [p for p in (PRIMARY, FALLBACK) if p in _VISION_PROVIDERS]
    if not order:
        raise RuntimeError("no vision-capable provider configured")
    last_err: Exception | None = None
    for provider in order:
        try:
            return _VISION_PROVIDERS[provider](prompt, images, system, max_tokens, temperature), provider
        except Exception as e:
            last_err = e
            log.warning("Vision provider '%s' failed (%s).", provider, e)
    raise last_err


def ask_llm(prompt: str) -> str:
    """Try the primary provider; on any failure, fall back to the secondary."""
    try:
        return _PROVIDERS[PRIMARY](prompt)
    except Exception as e:
        log.warning("Primary provider '%s' failed (%s). Falling back to '%s'.", PRIMARY, e, FALLBACK)
        if FALLBACK and FALLBACK != PRIMARY:
            try:
                return _PROVIDERS[FALLBACK](prompt)
            except Exception as e2:
                log.error("Fallback provider '%s' also failed (%s).", FALLBACK, e2)
                raise
        raise