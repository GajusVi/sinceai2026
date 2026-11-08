"""frontend/estate_panel.py: the builder repair-plan panel.
Pure helpers first, then one real render in Streamlit's AppTest."""

import sys
from datetime import date
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "frontend"))  # the app imports `ui` and its panels as top-level modules

import estate_panel as ep  # noqa: E402

from steward import estate_view as ev  # noqa: E402
from steward.config import ROOT_DIR  # noqa: E402
from steward.datapack import DEFAULT_XLSX, load_catalog  # noqa: E402

pytestmark = pytest.mark.filterwarnings("ignore")


@pytest.fixture(scope="module")
def catalog(tmp_path_factory):
    return load_catalog(DEFAULT_XLSX, ROOT_DIR / "catalog" / "bayer", tmp_path_factory.mktemp("d"), date(2026, 11, 7))


@pytest.fixture(scope="module")
def view(catalog):
    return ev.estate_view(catalog)


def test_headline_leads_with_the_certified_reports_on_a_failed_refresh(view):
    numbers = ep.headline(view)
    assert [n for n, _ in numbers] == ["16", "14", "13"]
    assert "certified" in numbers[0][1] and "69 reports" in numbers[1][1] and "65 reports" in numbers[2][1]
    assert "21 have none" in numbers[2][1]


def test_action_rows_are_numbered_ranked_and_readable(view):
    rows = ep.action_rows(view, 5)
    assert [r["#"] for r in rows] == [1, 2, 3, 4, 5] and len(ep.action_rows(view)) == len(view.actions)
    assert [r["reports"] for r in rows] == sorted((r["reports"] for r in rows), reverse=True)
    assert {r["kind"] for r in ep.action_rows(view)} == {"fix refresh", "reassign owner"}
    assert all(r["do this"] for r in rows)


def test_owner_picker_lists_people_with_the_biggest_problem_first(view):
    options = ep.owner_options(view)
    assert options and all(o.startswith("OWN-") for o, _ in options)  # the nobody-owner is not a person
    assert "OWN-059" in dict(options)["OWN-059"] and "Mika Virtanen" in dict(options)["OWN-059"]
    counts = [int(label.split("(")[1].split()[0]) for _, label in options if "(" in label]
    assert counts == sorted(counts, reverse=True)


def test_asset_rows_use_plain_words(catalog, view):
    owner = ep.owner_options(view)[0][0]
    rows = ep.asset_rows(ev.my_assets(catalog, owner))
    assert rows and set(rows[0]) == {"id", "report", "certificate", "needs", "users / month (last 3)", "trend"}
    assert all("_" not in r["needs"] for r in rows)  # FAILED_REFRESH is shown as 'refresh failed'


APP = """
import sys, tempfile
from datetime import date
from pathlib import Path
import streamlit as st
sys.path.insert(0, r"{root}")
sys.path.insert(0, r"{root}/frontend")
import estate_panel
from steward.config import ROOT_DIR
from steward.datapack import DEFAULT_XLSX, load_catalog

@st.cache_resource
def cat():
    return load_catalog(DEFAULT_XLSX, ROOT_DIR / "catalog" / "bayer", Path(tempfile.mkdtemp()), date(2026, 11, 7))

estate_panel.render(cat())
"""


def test_the_panel_renders_and_the_picker_changes_the_table():
    app = AppTest.from_string(APP.format(root=str(ROOT).replace("\\", "/")), default_timeout=120).run()
    assert not app.exception
    assert any("Repair plan" in m.value for m in app.markdown)
    shown = [m.value for m in app.markdown]
    assert any("16" in v and "certified reports sit on a refresh that has failed" in v for v in shown)
    assert app.selectbox(key="estate_owner").index == 0  # the person with the biggest problem is shown first
    app.selectbox(key="estate_owner").select_index(1).run()
    assert not app.exception and app.selectbox(key="estate_owner").index == 1
