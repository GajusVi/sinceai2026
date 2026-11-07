"""One LLM entry point. Structured output = JSON validated by Pydantic, one repair retry.

Every successful live output is written to demo/cache/ keyed by (system, user, schema).
Live mode always calls the model (so eval measures the current model); the cache is read only
in DEMO_MODE=1 (never touches the network) or as a fallback when the live call fails.

Provider chain: LLM_PROVIDER (e.g. aitta) -> LLM_FALLBACK_PROVIDER (e.g. gemini) -> callers fall back to rules.
Only transport failures (network, 429, 5xx, timeout, auth) move to the fallback; invalid JSON does not.
The cache key ignores the provider, so a fallback answer is cached like any other.
"""

import hashlib
import json
import logging
import re
from collections.abc import Callable
from functools import lru_cache
from typing import TypeVar

from openai import OpenAI
from pydantic import BaseModel, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from .config import PROVIDERS, ROOT, Settings, get_settings

T = TypeVar("T", bound=BaseModel)
CACHE_DIR = ROOT / "demo" / "cache"


log = logging.getLogger(__name__)


class LLMError(RuntimeError):
    pass


class LLMTransportError(LLMError):
    """The provider could not be reached or refused the call (network, 429, 5xx, timeout, auth): the fallback may try."""


class _FallbackEnv(BaseSettings):
    """LLM_FALLBACK_PROVIDER from the environment or .env (backend/config.py is not changed for this)."""

    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    llm_fallback_provider: str | None = None


@lru_cache
def _make_client(base_url: str, api_key: str, timeout: float, retries: int) -> OpenAI:
    return OpenAI(base_url=base_url, api_key=api_key, timeout=timeout, max_retries=retries)


def _client(s: Settings | None = None) -> OpenAI:
    s = s or get_settings()
    base_url, api_key, _ = s.resolved()
    return _make_client(base_url, api_key, s.llm_timeout_s, s.llm_max_retries)


def _extra(s: Settings | None = None) -> dict:
    """Provider-specific request options. Gemini 3 always reasons; 'low' keeps replies fast."""
    return {"reasoning_effort": "low"} if (s or get_settings()).llm_provider == "gemini" else {}


def fallback_settings(s: Settings | None = None) -> Settings | None:
    """Settings of the fallback provider, or None when none is set, it equals the primary, or it is not configured.
    The primary's LLM_MODEL / LLM_BASE_URL / LLM_API_KEY overrides do not carry over."""
    s = s or get_settings()
    name = (_FallbackEnv().llm_fallback_provider or "").strip().lower()
    if not name or name == s.llm_provider or name not in PROVIDERS:
        return None
    fb = s.model_copy(update={"llm_provider": name, "llm_model": None, "llm_base_url": None, "llm_api_key": None})
    return fb if fb.llm_ready() else None


def _with_fallback(call: Callable[[Settings], T]) -> T:
    """call(settings) on the primary provider; on a transport failure once more on the fallback provider."""
    s = get_settings()
    try:
        result = call(s)
        log.info("llm answered: %s", s.llm_provider)
        return result
    except LLMTransportError as primary_error:
        fb = fallback_settings(s)
        if fb is None:
            raise
        log.warning("llm %s failed (%s); retrying on %s", s.llm_provider, primary_error, fb.llm_provider)
        result = call(fb)
        log.info("llm answered: %s (fallback)", fb.llm_provider)
        return result


TEXT_TAG = "chat_text"  # cache tag of plain-text calls (JSON calls use the schema name)


def _text_path(messages: list[dict]):
    return CACHE_DIR / f"{_cache_key('', json.dumps(messages, sort_keys=True), TEXT_TAG)}.txt"


def chat_text(messages: list[dict], temperature: float = 0.0) -> str:
    """Plain-text completion through the provider chain. Cached like complete_json (demo/cache/<key>.txt); DEMO_MODE
    replays the cache and never touches the network. Temperature 0: the same request reads the same on stage."""
    s = get_settings()
    path = _text_path(messages)
    if s.demo_mode:
        if path.exists():
            return path.read_text(encoding="utf-8")
        raise LLMError("DEMO_MODE: no cached text for this input")

    def call(cfg: Settings) -> str:
        model = cfg.resolved()[2]
        try:
            resp = _client(cfg).chat.completions.create(
                model=model, messages=messages, temperature=temperature, max_tokens=cfg.llm_max_tokens, **_extra(cfg)
            )
        except Exception as e:
            raise LLMTransportError(f"{type(e).__name__}: {e}") from e
        return (resp.choices[0].message.content or "").strip()

    text = _with_fallback(call)
    if text:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return text


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

    sys_full = (
        f"{system}\n\nReply with ONLY one JSON object that validates against this JSON Schema. "
        f"No prose, no markdown.\n{json.dumps(schema.model_json_schema())}"
    )

    def call(cfg: Settings) -> T:
        model = cfg.resolved()[2]
        messages = [{"role": "system", "content": sys_full}, {"role": "user", "content": user}]
        last_err: Exception | None = None
        for _ in range(2):  # first try + one repair
            try:
                resp = _client(cfg).chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=cfg.llm_max_tokens,
                    **_extra(cfg),
                )
            except Exception as e:  # network, auth, rate limit after SDK retries
                raise LLMTransportError(f"{type(e).__name__}: {e}") from e
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
            return obj
        raise LLMError(f"invalid JSON after repair: {last_err}")

    obj = _with_fallback(call)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(obj.model_dump_json(indent=2), encoding="utf-8")
    return obj


def _explain(e: Exception) -> str:
    resp = getattr(e, "response", None)
    body = (getattr(resp, "text", "") or "").strip()
    return f"{type(e).__name__}: {body[:600] or e}"


def ping() -> str:
    """Quick connectivity check: `python -m backend.llm`."""
    s = get_settings()
    base, _, model = s.resolved()
    if not model:
        raise SystemExit(
            f"No model set for LLM_PROVIDER={s.llm_provider}: add LLM_MODEL=... to .env (`make models` lists them)"
        )
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
