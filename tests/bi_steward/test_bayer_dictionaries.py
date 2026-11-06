import json
from pathlib import Path

from steward.catalog import Catalog
from steward.linking import find_terms
from steward.models import DimensionDefinition, MetricDefinition

D = Path(__file__).resolve().parents[2] / "catalog" / "bayer"


def _catalog() -> Catalog:
    load = lambda n: json.loads((D / n).read_text(encoding="utf-8"))
    return Catalog(
        [],
        [MetricDefinition.model_validate(m) for m in load("metrics.json")],
        [DimensionDefinition.model_validate(d) for d in load("dimensions.json")],
    )


def test_counts_and_bad_name_trap():
    metrics = json.loads((D / "metrics.json").read_text(encoding="utf-8"))
    assert len(metrics) == 18
    assert sum(len(m["variants"]) for m in metrics) == 38
    inv = next(m for m in metrics if m["id"] == "inventory_coverage")
    assert {"KPI-018", "KPI-019"} <= {v["kpi_id"] for v in inv["variants"]}


def test_links_products_markets_and_skips_ambiguous_terms():
    cat = _catalog()
    q = "net sales for Nubeqa in Germany by month"
    assert {(m.kind, m.id) for m in find_terms(q, cat)} >= {("metric", "net_sales"), ("value", "P-NUB"), ("value", "DE")}
    # ambiguous words must stay unlinked so they reach CLARIFY; "items" must not match IT
    assert find_terms("forecast performance coverage readiness items", cat) == []
    assert [m.id for m in find_terms("Latin America", cat)] == ["Latin America"]


def test_metric_definition_keeps_kpi_id_and_variants():
    raw = json.loads((D / "metrics.json").read_text(encoding="utf-8"))
    ms = {m["id"]: MetricDefinition.model_validate(m) for m in raw}
    inv = ms["inventory_coverage"]
    assert inv.kpi_id == "KPI-016"
    assert {"KPI-018", "KPI-019"} <= {v.kpi_id for v in inv.variants}
