"""Provider chain: primary -> LLM_FALLBACK_PROVIDER on a transport failure, same cache key, nothing else falls back."""

import logging
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from backend import llm
from backend.config import Settings


class Answer(BaseModel):
    ok: bool


class FakeClient:
    """Stands in for the OpenAI client: raises or returns a fixed text, and counts its calls."""

    def __init__(self, text=None, error=None):
        self.text, self.error, self.calls = text, error, 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.text))])


@pytest.fixture
def chain(monkeypatch, tmp_path):
    """aitta (fake, failing by default) -> gemini (fake, answers)."""
    settings = Settings(
        _env_file=None,
        demo_mode=False,
        llm_provider="aitta",
        aitta_api_key="a",
        aitta_model="m-aitta",
        gemini_api_key="g",
        gemini_model="m-gem",
    )
    clients = {"aitta": FakeClient(error=ConnectionError("429 rate limit")), "gemini": FakeClient(text='{"ok": true}')}
    monkeypatch.setattr(llm, "get_settings", lambda: settings)
    monkeypatch.setattr(llm, "_client", lambda s=None: clients[(s or settings).llm_provider])
    monkeypatch.setattr(llm, "CACHE_DIR", tmp_path)
    monkeypatch.setenv("LLM_FALLBACK_PROVIDER", "gemini")
    return clients


def test_json_call_moves_to_the_fallback_and_logs_who_answered(chain, caplog):
    caplog.set_level(logging.INFO, logger="backend.llm")
    assert llm.complete_json("sys", "user", Answer) == Answer(ok=True)
    assert chain["aitta"].calls == 1 and chain["gemini"].calls == 1
    assert "retrying on gemini" in caplog.text and "llm answered: gemini (fallback)" in caplog.text


def test_cache_key_does_not_depend_on_the_provider(chain, tmp_path):
    llm.complete_json("sys", "user", Answer)
    assert [p.name for p in tmp_path.glob("*.json")] == [f"{llm._cache_key('sys', 'user', 'Answer')}.json"]


def test_text_call_uses_the_same_chain(chain):
    chain["gemini"].text = "hello"
    assert llm.chat_text([{"role": "user", "content": "hi"}]) == "hello"
    assert chain["aitta"].calls == 1 and chain["gemini"].calls == 1


def test_primary_answer_never_touches_the_fallback(chain):
    chain["aitta"].error, chain["aitta"].text = None, '{"ok": false}'
    assert llm.complete_json("sys", "user", Answer) == Answer(ok=False)
    assert chain["gemini"].calls == 0


def test_without_a_fallback_the_error_surfaces(chain, monkeypatch):
    monkeypatch.setenv("LLM_FALLBACK_PROVIDER", "")
    with pytest.raises(llm.LLMTransportError):
        llm.complete_json("sys", "user", Answer)
    assert chain["gemini"].calls == 0


def test_both_failing_raises_so_the_caller_can_use_rules(chain):
    chain["gemini"].error = TimeoutError("down")
    with pytest.raises(llm.LLMError):
        llm.complete_json("sys", "user", Answer)


def test_invalid_json_is_not_a_transport_failure(chain):
    chain["aitta"].error, chain["aitta"].text = None, "not json"
    with pytest.raises(llm.LLMError, match="invalid JSON"):
        llm.complete_json("sys", "user", Answer)
    assert chain["gemini"].calls == 0
