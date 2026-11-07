from dataclasses import replace
from datetime import date

import pytest

from steward import Steward
from steward.config import Settings

AS_OF = date(2026, 11, 6)


@pytest.fixture
def steward(tmp_path) -> Steward:
    settings = replace(Settings.from_env(), use_llm="off", data_dir=tmp_path, as_of=AS_OF)
    return Steward(settings=settings)


@pytest.fixture(autouse=True)
def _layout_cache(tmp_path, monkeypatch):
    """Layout proposals persist on disk (steward/layout.py CACHE_DIR): tests write to a tmp dir, never the repo."""
    from steward import layout

    monkeypatch.setattr(layout, "CACHE_DIR", tmp_path / "layout_cache")
