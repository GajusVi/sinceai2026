"""Autofill (steward/suggest.py): colleagues' first messages, same role and plant, ranked by people, private until shared."""

from dataclasses import replace

from steward.auth import account
from steward.suggest import Suggestions, match

INTENT = {"text": "How efficiently is this plant running?", "sites": ["Plant-B"], "metric_ids": ["on_time_in_full"]}


MANAGER = account("Manager07")  # Plant-B
COLLEAGUE = replace(MANAGER, username="Manager08")  # same role, same plant
ELSEWHERE = replace(MANAGER, username="Manager09", plant="Plant-C")
WORKER, BUILDER = account("Worker21"), account("Builder12")


def test_typed_words_match_word_starts_and_forgive_one_typo():
    assert match("xar ne", "Xarelto net sales in Germany") > 0
    assert match("net sales germny xarelto", "Xarelto net sales in Germany") > 0  # one typo in a longer query
    assert match("eylea", "Xarelto net sales in Germany") == 0
    assert match("", "anything") == 1.0


def test_a_request_shows_to_colleagues_only_after_two_people_asked(tmp_path):
    same = [MANAGER, COLLEAGUE]
    s = Suggestions(tmp_path, seed=[])
    s.record(same[0], INTENT["text"], INTENT)
    assert s.for_user(same[0]) == [] and s.intent_for(same[0], INTENT["text"]) is None  # one person: private
    s.record(same[0], INTENT["text"], INTENT)  # the same person again is not a second person
    assert s.for_user(same[0]) == []
    s.record(same[1], "how efficiently is THIS plant running", INTENT)  # same words, other case and punctuation
    top = s.for_user(same[0])
    assert [x.text for x in top] == [INTENT["text"]] and top[0].people == 2
    assert s.intent_for(same[0], INTENT["text"])["sites"] == ["Plant-B"]


def test_other_plants_and_other_roles_never_see_it_builders_do(tmp_path):
    s = Suggestions(tmp_path, seed=[])
    for m in (MANAGER, COLLEAGUE):
        s.record(m, INTENT["text"], INTENT)
    assert s.for_user(ELSEWHERE) == [] and s.intent_for(ELSEWHERE, INTENT["text"]) is None
    assert s.for_user(WORKER) == []
    assert [x.text for x in s.for_user(BUILDER)] == [INTENT["text"]]


def test_seed_ranks_by_how_often_it_was_asked_and_filters_by_typing(tmp_path):
    s = Suggestions(tmp_path, seed=[("Kerendia report for EMEA", 3), ("Xarelto commercial workbook", 22)])
    manager = MANAGER
    assert [x.text for x in s.for_user(manager)] == ["Xarelto commercial workbook", "Kerendia report for EMEA"]
    assert [x.text for x in s.for_user(manager, typed="keren")] == ["Kerendia report for EMEA"]
    assert s.for_user(manager, seed=False) == [] and s.for_user(WORKER) == []
    assert s.for_user(manager)[0].intent is None  # a seed starts the normal interview


def test_the_data_pack_seed_loads():
    seed = Suggestions("/nonexistent").seed()
    assert len(seed) >= 5 and seed[0][1] >= seed[-1][1]


def test_a_picked_colleague_request_skips_the_interview_in_the_app(tmp_path, monkeypatch):
    """End to end: two Plant-B managers confirmed a request; Manager07 sees it as a chip and gets the dashboard
    without a single interview question (same request, same answer)."""
    from datetime import date
    from pathlib import Path

    from streamlit.testing.v1 import AppTest

    from steward import Steward
    from steward.config import Settings

    monkeypatch.setenv("STEWARD_USE_LLM", "off")
    monkeypatch.setenv("STEWARD_DATA_DIR", str(tmp_path))
    settings = replace(Settings.from_env(), use_llm="off", data_dir=tmp_path, as_of=date(2026, 11, 6))
    iv = Steward(settings=settings).interviewer
    text = "How efficiently is this plant running?"
    state = iv.finish_with_defaults(iv.start(text, home_plant="Plant-B"))
    s = Suggestions(tmp_path, seed=[])
    for m in (COLLEAGUE, replace(MANAGER, username="Manager10")):
        s.record(m, state.intent.text, state.intent.model_dump(mode="json"))

    import streamlit as st

    st.cache_resource.clear()  # the app's Steward is cached across tests: this one reads tmp_path
    app = str(Path(__file__).resolve().parents[2] / "frontend" / "steward_app.py")
    at = AppTest.from_file(app, default_timeout=180)
    at.session_state["user"] = MANAGER
    at.run()
    chip = next(b for b in at.button if b.label == text)
    assert "Asked by 2 people" in (chip.help or "")
    chip.click().run()
    assert not at.exception
    said = [m["content"] for m in at.session_state["messages"] if m["role"] == "assistant"]
    assert "asked exactly this before" in said[0]  # no question: straight to the read-back
    assert at.session_state["interview"] is None and at.session_state["result"] is not None
    assert len(Suggestions(tmp_path, seed=[]).for_user(MANAGER)[0].text) and s.for_user(MANAGER)[0].people == 3
