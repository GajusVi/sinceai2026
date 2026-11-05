"""One LLM entry point. Structured output = JSON validated by Pydantic, one repair retry.

Every successful live output is written to demo/cache/ keyed by (system, user, schema).
Live mode always calls the model (so eval measures the current model); the cache is read only
in DEMO_MODE=1 (never touches the network) or as a fallback when the live call fails.
"""

import hashlib
import json
import re
from collections.abc import Callable
from functools import lru_cache
from typing import TypeVar

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from .config import ROOT, get_settings

T = TypeVar("T", bound=BaseModel)
CACHE_DIR = ROOT / "demo" / "cache"


class LLMError(RuntimeError):
    pass


@lru_cache
def _client() -> OpenAI:
    s = get_settings()
    base_url, api_key, _ = s.resolved()
    return OpenAI(base_url=base_url, api_key=api_key, timeout=s.llm_timeout_s, max_retries=s.llm_max_retries)


def _extra() -> dict:
    """Provider-specific request options. Gemini 3 always reasons; 'low' keeps replies fast."""
    return {"reasoning_effort": "low"} if get_settings().llm_provider == "gemini" else {}


def _cache_key(system: str, user: str, tag: str) -> str:
    return hashlib.sha256(f"{tag}\x00{system}\x00{user}".encode()).hexdigest()[:24]


def _extract_json(text: str) -> str:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.S)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in response")
    return text[start : end + 1]


def cached(system: str, user: str, schema: type[T]) -> T | None:
    path = CACHE_DIR / f"{_cache_key(system, user, schema.__name__)}.json"
    return schema.model_validate_json(path.read_text(encoding="utf-8")) if path.exists() else None


def complete_json(
    system: str, user: str, schema: type[T], temperature: float = 0.0, check: Callable[[T], None] | None = None
) -> T:
    """Live call (DEMO_MODE: cache replay only). `check` may raise ValueError to trigger the repair retry."""
    s = get_settings()
    key = _cache_key(system, user, schema.__name__)
    path = CACHE_DIR / f"{key}.json"
    if s.demo_mode:
        if path.exists():
            return schema.model_validate_json(path.read_text(encoding="utf-8"))
        raise LLMError("DEMO_MODE: no cached output for this input")
    if not s.llm_ready():
        raise LLMError(f"LLM not configured for provider {s.llm_provider!r} (key or model missing)")

    _, _, model = s.resolved()
    sys_full = (
        f"{system}\n\nReply with ONLY one JSON object that validates against this JSON Schema. "
        f"No prose, no markdown.\n{json.dumps(schema.model_json_schema())}"
    )
    messages = [{"role": "system", "content": sys_full}, {"role": "user", "content": user}]
    last_err: Exception | None = None
    for _ in range(2):  # first try + one repair
        try:
            resp = _client().chat.completions.create(
                model=model, messages=messages, temperature=temperature, max_tokens=s.llm_max_tokens, **_extra()
            )
        except Exception as e:  # network, auth, rate limit after SDK retries
            raise LLMError(f"{type(e).__name__}: {e}") from e
        text = resp.choices[0].message.content or ""
        try:
            obj = schema.model_validate_json(_extract_json(text))
            if check:
                check(obj)
        except (ValidationError, ValueError) as e:
            last_err = e
            messages += [
                {"role": "assistant", "content": text},
                {"role": "user", "content": f"Invalid: {e}. Return only the corrected JSON object."},
            ]
            continue
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(obj.model_dump_json(indent=2), encoding="utf-8")
        return obj
    raise LLMError(f"invalid JSON after repair: {last_err}")


def _explain(e: Exception) -> str:
    resp = getattr(e, "response", None)
    body = (getattr(resp, "text", "") or "").strip()
    return f"{type(e).__name__}: {body[:600] or e}"


def ping() -> str:
    """Quick connectivity check: `python -m backend.llm`."""
    s = get_settings()
    base, _, model = s.resolved()
    if not model:
        raise SystemExit(f"No model set for LLM_PROVIDER={s.llm_provider}: add LLM_MODEL=... to .env (`make models` lists them)")
    try:
        resp = _client().chat.completions.create(
            model=model, messages=[{"role": "user", "content": "Reply with the word: ok"}], max_tokens=512, **_extra()
        )
    except Exception as e:
        raise SystemExit(f"{s.llm_provider} @ {base} model={model} -> {_explain(e)}") from None
    return f"{s.llm_provider} @ {base} model={model}: {resp.choices[0].message.content!r}"


def list_models() -> list[str]:
    """Model IDs the active provider exposes: `python -m backend.llm models` (or `make models`)."""
    try:
        return sorted(m.id for m in _client().models.list())
    except Exception as e:
        raise SystemExit(_explain(e)) from None


if __name__ == "__main__":
    import sys

    if sys.argv[1:] == ["models"]:
        print("\n".join(list_models()))
    else:
        print(ping())
