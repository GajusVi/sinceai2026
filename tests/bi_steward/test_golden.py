"""The verdict contract (T3.7: replaces the invented sample catalog's 8 goldens): every human-labelled data-pack case
(eval_steward.labelled_cases, independent sources) gets its labelled verdict and report, on both paths (rules parser and
Intent). Change a verdict on purpose -> update the label in the same commit."""

import os
import sys
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "eval"))
import eval_steward as ev  # noqa: E402

CASES, _ = ev.labelled_cases()


@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    from steward import Steward
    from steward.config import Settings

    old = os.environ.get("STEWARD_CATALOG")
    os.environ["STEWARD_CATALOG"] = "datapack"
    settings = replace(Settings.from_env(), use_llm="off", as_of=date(2026, 11, 6))
    yield Steward(settings=settings, data_dir=tmp_path_factory.mktemp("golden"))
    if old is None:
        os.environ.pop("STEWARD_CATALOG", None)
    else:
        os.environ["STEWARD_CATALOG"] = old


def test_there_are_enough_labelled_cases():
    assert len(CASES) >= 60


@pytest.mark.parametrize("path", ["rules", "intent"])
def test_every_labelled_case_gets_its_verdict(pack, path):
    misses = []
    for case in CASES:
        pred = ev.predict(pack, case, path)
        if not ev.is_correct(case, pred):
            misses.append(f"{case['text']!r}: want {case['gold']} {case['gold_asset'] or ''}, got {pred}")
    assert not misses, "\n".join(misses)
