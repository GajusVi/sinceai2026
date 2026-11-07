"""The eval's own scoring logic (not the engine): false-REUSE and correctness definitions, label loading."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "eval"))
import eval_steward as ev  # noqa: E402


def case(gold, asset=None):
    return {"gold": gold, "gold_asset": asset}


def pred(verdict, asset=None):
    return {"verdict": verdict, "asset": asset}


def test_reuse_where_label_says_otherwise_is_false_reuse():
    assert ev.is_false_reuse(case("EXTEND"), pred("REUSE", "AST-1"))
    assert ev.is_false_reuse(case(ev.NO_BUILD), pred("REUSE", "AST-1"))
    assert ev.is_false_reuse(case("REUSE", "AST-1"), pred("REUSE", "AST-2"))  # right verdict, wrong report


def test_correct_reuse_and_other_verdicts_are_not_false_reuse():
    assert not ev.is_false_reuse(case("REUSE", "AST-1"), pred("REUSE", "AST-1"))
    assert not ev.is_false_reuse(case("EXTEND"), pred("CLARIFY"))


def test_no_build_gold_accepts_anything_that_builds_nothing():
    assert ev.is_correct(case(ev.NO_BUILD), pred("CLARIFY"))
    assert ev.is_correct(case(ev.NO_BUILD), pred("NOT_FEASIBLE"))
    assert not ev.is_correct(case(ev.NO_BUILD), pred("CREATE"))
    assert not ev.is_correct(case(ev.NO_BUILD), pred("ERROR"))


def test_asset_must_match_when_the_label_names_one():
    assert ev.is_correct(case("EXTEND", "AST-1"), pred("EXTEND", "AST-1"))
    assert not ev.is_correct(case("EXTEND", "AST-1"), pred("EXTEND", "AST-2"))
    assert ev.is_correct(case("CLARIFY"), pred("CLARIFY"))


def test_labelled_cases_come_from_independent_sources():
    cases, pending = ev.labelled_cases()
    sources = {c["source"] for c in cases}
    assert {"golden", "blocker", "negative"} <= sources
    assert all(c["gold"] == "CLARIFY" for c in cases if c["source"] == "blocker")
    assert "holdout_verdicts" in pending
