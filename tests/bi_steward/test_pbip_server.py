"""Live-refresh data service for exported PBIP files (steward/pbip_server.py)."""

import base64
import json
import re
import urllib.error
import urllib.request
import zlib

import pandas as pd
import pytest

from steward import pbip_server
from steward.pbip import build_files
from steward.spec import DashboardSpec, Measure, Page, Relationship, Visual


@pytest.fixture
def frames():
    return {
        "fact_pmm": pd.DataFrame(
            {
                "product_id": ["P-NUB", "P-NUB"],
                "market_id": ["DE", "FR"],
                "month": pd.to_datetime(["2026-01-01", "2026-02-01"]),
                "net_sales": [1.5, None],
                "units": [3, 4],
            }
        ),
        "dim_product": pd.DataFrame({"product_id": ["P-NUB"], "product_name": ["Nubeqa"]}),
    }


@pytest.fixture
def spec():
    return DashboardSpec(
        name="Nubeqa net sales (draft)",
        entities=["fact_pmm", "dim_product"],
        columns={
            "fact_pmm": ["product_id", "market_id", "month", "net_sales", "units"],
            "dim_product": ["product_id", "product_name"],
        },
        relationships=[Relationship(from_entity="fact_pmm", to_entity="dim_product", key="product_id")],
        measures=[Measure(name="Net Sales", kpi_id="KPI-001", expression="SUM(fact_pmm[net_sales])", format="#,##0.0")],
        pages=[Page(name="p", visuals=[Visual(type="card", title="Net sales", measures=["Net Sales"])])],
    )


@pytest.fixture
def served(tmp_path, spec, frames):
    server, base = pbip_server.start(tmp_path, port=0, frames_loader=lambda: frames)
    source = pbip_server.register(spec, tmp_path, base)
    yield source, tmp_path
    server.shutdown()
    server.server_close()


def _get(url: str):
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_payload_equals_the_rows_the_embedded_export_carries(spec, frames):
    fact = build_files(spec, frames)["Nubeqa_net_sales_draft.SemanticModel/definition/tables/fact_pmm.tmdl"]
    encoded = re.search(r'Binary.FromText\("([^"]+)"', fact).group(1)
    embedded = json.loads(zlib.decompress(base64.b64decode(encoded), -15))
    payload = pbip_server.table_payload(spec, frames, "fact_pmm")
    assert payload["rows"] == embedded
    assert payload["columns"] == ["product_id", "market_id", "month", "net_sales", "units"]


def test_server_returns_the_table_with_the_right_key(served, spec, frames):
    source, _ = served
    status, body = _get(f"{source.table_url('fact_pmm')}?key={source.key}")
    assert status == 200 and body == pbip_server.table_payload(spec, frames, "fact_pmm")
    status, body = _get(f"{source.table_url('dim_product')}?key={source.key}")
    assert status == 200 and body["rows"] == [["P-NUB", "Nubeqa"]]


def test_wrong_or_missing_key_is_403_and_unknown_things_are_404(served):
    source, _ = served
    assert _get(f"{source.table_url('fact_pmm')}?key=nope")[0] == 403
    assert _get(source.table_url("fact_pmm"))[0] == 403
    other = source.table_url("fact_pmm").replace(source.id, "0" * 16)
    assert _get(f"{other}?key={pbip_server.key_for(served[1], '0' * 16)}")[0] == 404  # right key, no such decision
    assert _get(f"{source.table_url('no_such_table')}?key={source.key}")[0] == 404
    assert _get(f"{source.base_url}/pbip/../../etc/passwd?key={source.key}")[0] == 404
    assert _get(f"{source.base_url}/other")[0] == 404


def test_a_revoked_decision_answers_410_so_refresh_fails(served):
    source, data_dir = served
    assert _get(f"{source.table_url('fact_pmm')}?key={source.key}")[0] == 200
    pbip_server.revoke(data_dir, source.id)
    status, body = _get(f"{source.table_url('fact_pmm')}?key={source.key}")
    assert status == 410 and "revoked" in body["error"]


def test_keys_are_per_decision_stable_across_restarts_and_the_server_is_local(tmp_path, spec, frames):
    a = pbip_server.key_for(tmp_path, "a" * 16)
    assert a != pbip_server.key_for(tmp_path, "b" * 16)
    assert a == pbip_server.key_for(tmp_path, "a" * 16)  # the secret persists in the data dir
    server, base = pbip_server.start(tmp_path, port=0, frames_loader=lambda: frames)
    try:
        assert base.startswith("http://127.0.0.1:") and server.server_address[0] == "127.0.0.1"
    finally:
        server.shutdown()
        server.server_close()


def test_spec_id_uses_the_pipeline_hash_when_it_is_one(spec):
    assert pbip_server.spec_id(spec) == pbip_server.spec_id(spec) and len(pbip_server.spec_id(spec)) == 16
    spec.provenance["spec_hash"] = "0123456789abcdef"
    assert pbip_server.spec_id(spec) == "0123456789abcdef"


# -- the live export itself (pbip.build_files(..., live=...)) -------------------------------------------------------

SM = "Nubeqa_net_sales_draft.SemanticModel/definition/tables/{}.tmdl"


def _embedded_rows(files: dict, table: str):
    encoded = re.search(r'Binary.FromText\("([^"]+)"', files[SM.format(table)]).group(1)
    return json.loads(zlib.decompress(base64.b64decode(encoded), -15))


def test_live_export_loads_from_the_app_and_embeds_no_data(served, spec, frames):
    source, _ = served
    files = build_files(spec, frames, live=source)
    for table in ("fact_pmm", "dim_product"):
        tmdl = files[SM.format(table)]
        assert f'Web.Contents("{source.table_url(table)}", [Query = [key = "{source.key}"]])' in tmdl
        assert "Binary.FromText" not in tmdl and "Table.FromRows(Raw[rows]" in tmdl
        assert "Table.TransformColumnTypes(Source" in tmdl  # same typing step as the embedded export
    assert "LIVE-REFRESH" in files["README.txt"] and source.base_url in files["README.txt"]
    assert "Anonymous" in files["README.txt"]


def test_everything_except_the_tables_and_readme_is_identical_to_the_embedded_export(served, spec, frames):
    source, _ = served
    embedded, live = build_files(spec, frames), build_files(spec, frames, live=source)
    assert set(embedded) == set(live)
    differing = {p for p in embedded if embedded[p] != live[p]}
    assert differing == {SM.format("fact_pmm"), SM.format("dim_product"), "README.txt"}


def test_simulated_refresh_gets_exactly_the_embedded_rows(served, spec, frames):
    """What Desktop does on Refresh: take the URL and key from the generated model and load them."""
    source, _ = served
    embedded, live = build_files(spec, frames), build_files(spec, frames, live=source)
    for table in ("fact_pmm", "dim_product"):
        url, key = re.search(r'Web.Contents\("([^"]+)", \[Query = \[key = "([^"]+)"\]\]\)', live[SM.format(table)]).groups()
        status, body = _get(f"{url}?key={key}")
        assert status == 200
        assert body["rows"] == _embedded_rows(embedded, table), table


def test_live_export_is_deterministic_and_named_apart(served, spec, frames, tmp_path):
    from steward.pbip import export_pbip

    source, _ = served
    assert build_files(spec, frames, live=source) == build_files(spec, frames, live=source)
    live_zip = export_pbip(spec, frames, tmp_path, live=source)
    plain_zip = export_pbip(spec, frames, tmp_path)
    assert live_zip.name.endswith(".live.pbip.zip") and plain_zip.name.endswith(".pbip.zip") and live_zip != plain_zip
