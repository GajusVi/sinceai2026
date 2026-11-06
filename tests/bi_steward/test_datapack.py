import pytest

from steward.datapack import load_artifacts

pytestmark = pytest.mark.filterwarnings("ignore")


@pytest.fixture(scope="module")
def arts():
    return {a.id: a for a in load_artifacts()}


def test_counts_match_data_pack_doc(arts):
    assert len(arts) == 360
    assert sum(a.platform == "Tableau" for a in arts.values()) == 94
    assert sum(a.platform == "Power BI" for a in arts.values()) == 266
    assert sum(a.owner_status == "" for a in arts.values()) == 21  # missing owner
    assert sum(a.owner_status == "inactive" for a in arts.values()) == 65


def test_every_asset_has_kpis_model_and_lineage(arts):
    assert all(a.kpi_ids and a.model_id and a.upstream_ids for a in arts.values())
    assert sum(len(a.kpi_ids) for a in arts.values()) == 1454


def test_usage_counts_only_months_from_creation(arts):
    for a in arts.values():
        assert all(u.month >= a.created_date.replace(day=1) for u in a.usage)
    early = [a for a in arts.values() if "USAGE_BEFORE_CREATED" in a.data_quality]
    assert early
    # total usage rows: 3600 in the pack, the rest are reported as data quality, not silently kept
    assert sum(len(a.usage) for a in arts.values()) < 3600


def test_claimed_vs_observed_and_scope_from_fields(arts):
    a = arts["AST-0009"]  # "Nubeqa Supply - US" is scoped Global (trap 18)
    assert a.market_scope == "Global" and any(d.startswith("NAME_SCOPE_MISMATCH") for d in a.data_quality)
    assert "market" in a.dimensions and "market" not in a.filters
    assert a.lifecycle_claimed in {"active", "candidate_retire", "legacy"}
    assert a.status.value == "active"  # the claim never changes our status


def test_successors_only_for_inactive_owners(arts):
    inactive = [a for a in arts.values() if a.owner_status == "inactive"]
    assert all(a.owner_id not in a.successor_candidates for a in inactive)
    assert sum(bool(a.successor_candidates) for a in inactive) > 0
    assert all(not a.successor_candidates for a in arts.values() if a.owner_status in ("active", ""))
