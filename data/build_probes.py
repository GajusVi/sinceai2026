"""Single-KPI probes with an INDEPENDENT oracle (DECISION T1.3, Martynas).

980 probes = 7 products x 14 markets x 10 bindable KPIs, e.g. "Hyrnuo inventory coverage in China". For each, the right
answer is computed from the data pack with the BUILD_PLAN rules (section 11 / 2.3 trust, 2.2 retire, 2.4 scope), NOT by
the engine. This module imports nothing from `steward` except inside `run_engine` (guarded by a test), so the labels
cannot be tuned to the engine. Labels are frozen with the baseline run BEFORE the T1.2 "does it already exist" PR.

Two label columns:
- `today`: the rule the engine implemented at the baseline (REUSE = covering Power BI asset, trust >= 0.6).
- `c2a`: the rule Gajus decided (C2=A): also not on a failed refresh and not on the retire list. The retire list is the
  independent subset of BUILD_PLAN 2.2 whose reason is "no active owner" (11 assets); the engine adds 10 more through the
  "duplicate of a more trusted asset" reason (needs MinHash). `run_engine` reports mismatches that this explains.

Usage:
  python data/build_probes.py              write data/holdout/probes.jsonl
  python data/build_probes.py --baseline   also run the engine (rules mode, both paths) -> probes_baseline.json
"""

from __future__ import annotations

import glob
import itertools
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "holdout" / "probes.jsonl"
BASELINE = ROOT / "data" / "holdout" / "probes_baseline.json"
AS_OF = pd.Timestamp("2026-11-07")
REUSE_MIN_TRUST = 0.6  # BUILD_PLAN 11.1
# Monthly or snapshot KPIs the semantic layer can compute per product x market (the 6 gap KPIs and the asset-level
# KPI-051/054 are not probe material).
KPIS = ["KPI-001", "KPI-004", "KPI-006", "KPI-010", "KPI-014", "KPI-016", "KPI-020", "KPI-027", "KPI-031", "KPI-042"]


def load(xlsx: str | None = None) -> dict[str, pd.DataFrame]:
    path = xlsx or glob.glob(str(ROOT / "data" / "bayer" / "*.xlsx"))[0]
    return pd.read_excel(path, sheet_name=None)


def oracle_assets(x: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """One row per asset: platform, scopes, canonical KPI ids (exact / any variant), trust, refresh, retire flag."""
    a = x["Analytics_Assets"].copy()
    kpis = x["KPI_Catalog"].set_index("kpi_id")
    canon_id = kpis[kpis.definition_status == "canonical"].reset_index().set_index("canonical_metric").kpi_id
    m = x["Asset_KPI_Map"].copy()
    m["canon"] = m.kpi_id.map(kpis.canonical_metric).map(canon_id)
    m["exact"] = m.kpi_id.map(kpis.definition_status) == "canonical"
    a["canon_all"] = a.asset_id.map(m.groupby("asset_id").canon.apply(lambda s: sorted(set(s.dropna()))))
    a["canon_exact"] = a.asset_id.map(m[m.exact].groupby("asset_id").kpi_id.apply(sorted))
    for col in ("canon_all", "canon_exact"):
        a[col] = a[col].apply(lambda v: v if isinstance(v, list) else [])

    owners = x["Owners"].set_index("owner_id")
    staffed_roles = set(owners[owners.status == "active"].role)
    a["owner_status"] = a.owner_id.map(owners.status)
    a["owner_role"] = a.owner_id.map(owners.role)
    a["refresh"] = a.model_id.map(x["Semantic_Models"].set_index("model_id").refresh_status)

    u = x["Asset_Usage"].copy()
    u["m"] = pd.to_datetime(u.month)
    a["created"] = pd.to_datetime(a.created_date)
    u = u.merge(a[["asset_id", "created"]], on="asset_id")
    u = u[u.m >= u.created.dt.to_period("M").dt.to_timestamp()]  # months after creation only (BUILD_PLAN 2.2)
    a["avg_users"] = a.asset_id.map(u.groupby("asset_id").unique_users.mean())

    sig = x["Governance_Signals"]
    open_high = sig[(sig.severity == "high") & (sig.status == "open")].groupby("asset_id").size()
    a["open_high"] = a.asset_id.map(open_high).fillna(0)

    def trust(r) -> float:  # BUILD_PLAN 2.3 / 11.3
        t = {"certified": 0.40, "promoted": 0.25}.get(r.endorsement, 0.0)
        if r.owner_status == "active":
            t += 0.20
        elif r.owner_status == "inactive" and r.owner_role in staffed_roles:
            t += 0.10
        t += {"healthy": 0.25, "warning": 0.10}.get(r.refresh, 0.0)
        t += 0.15 if (r.avg_users or 0) >= 50 else 0.05 if (r.avg_users or 0) >= 10 else 0.0
        return round(max(0.0, t - 0.10 * r.open_high), 2)

    a["trust"] = a.apply(trust, axis=1)
    a["retire"] = a.asset_id.isin(_retire_no_active_owner(x, a, u))
    return a


def _retire_no_active_owner(x: dict[str, pd.DataFrame], a: pd.DataFrame, u: pd.DataFrame) -> set[str]:
    """BUILD_PLAN 2.2 with the reason 'no active owner': old enough, low use (bottom 20% of its type, < 10 users in each
    of the last 3 months), no subscriptions in those months, no downstream asset."""
    old = a.created <= AS_OF - pd.DateOffset(months=3)
    cut = a.groupby("asset_type").avg_users.transform(lambda s: s.quantile(0.20))
    last3 = sorted(u.m.unique())[-3:]
    recent = u[u.m.isin(last3)].groupby("asset_id").agg(peak=("unique_users", "max"), subs=("subscriptions", "sum"))
    low = (a.avg_users <= cut) & (a.asset_id.map(recent.peak).fillna(0) < 10)
    lin = x["Lineage_Edges"]
    dependants = set(lin[lin.edge_type == "ASSET_TO_ASSET"].source_id)
    quiet = (a.asset_id.map(recent.subs).fillna(0) == 0) & ~a.asset_id.isin(dependants)
    return set(a[old & low & quiet & (a.owner_status != "active")].asset_id)


def expected(assets: pd.DataFrame, product: str, market: str, kpi: str, rule: str) -> dict:
    """The oracle's answer for one probe. `acceptable` = verdicts that count as correct."""
    fits = assets[assets.product_scope.isin([product, "All Pharma"]) & assets.market_scope.isin([market, "Global"])]
    covering = fits[fits.canon_all.apply(lambda s: kpi in s)]
    ok = covering[(covering.platform == "Power BI") & covering.canon_exact.apply(lambda s: kpi in s)]
    ok = ok[ok.trust >= REUSE_MIN_TRUST]
    healthy = lambda d: d[(d.refresh != "failed") & ~d.retire]  # noqa: E731
    if rule == "c2a":
        ok = healthy(ok)
    if len(ok):
        return {"verdict": "REUSE", "acceptable": ["REUSE"], "assets": sorted(ok.asset_id)}
    if len(covering):
        exact = covering[covering.canon_exact.apply(lambda s: kpi in s)]
        if exact.empty:
            # Only a VARIANT of the KPI is carried. BUILD_PLAN 11.1 lists "a variant KPI to swap to canonical" as an EXTEND
            # gap, but it also counts coverage "via approved KPI ids", so the plan is ambiguous: both verdicts are accepted.
            return {"verdict": "EXTEND", "acceptable": ["EXTEND", "CREATE"], "assets": sorted(covering.asset_id),
                    "variant_only": True}
        base = healthy(exact) if rule == "c2a" else exact
        if len(base):
            return {"verdict": "EXTEND", "acceptable": ["EXTEND"], "assets": sorted(base.asset_id)}
        # only failed-refresh / retiring assets cover it: EXTEND on them is demoted, an honest CREATE is also right
        return {"verdict": "EXTEND", "acceptable": ["EXTEND", "CREATE"], "assets": sorted(exact.asset_id)}
    return {"verdict": "CREATE", "acceptable": ["CREATE"], "assets": []}


def build(xlsx: str | None = None) -> list[dict]:
    x = load(xlsx)
    assets = oracle_assets(x)
    products = x["Products"].product_name.tolist()
    markets = x["Markets"].set_index("market_id").market_name.to_dict()
    names = x["KPI_Catalog"].set_index("kpi_id").kpi_name.to_dict()
    rows = []
    for n, (p, m, k) in enumerate(itertools.product(products, markets, KPIS), 1):
        rows.append(
            {
                "id": f"P-{n:04d}",
                "text": f"{p} {names[k].lower()} in {markets[m]}",
                "product": p,
                "market": m,
                "kpi_id": k,
                "today": expected(assets, p, m, k, "today"),
                "c2a": expected(assets, p, m, k, "c2a"),
            }
        )
    return rows


def write(rows: list[dict]) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n", encoding="utf-8")


# -- engine side (the only place `steward` is imported) -------------------------------------------------------------


def run_engine(rows: list[dict]) -> dict:
    import os
    import warnings

    os.environ.setdefault("STEWARD_CATALOG", "datapack")
    os.environ["STEWARD_USE_LLM"] = "off"
    warnings.filterwarnings("ignore")
    sys.path.insert(0, str(ROOT))
    from steward.decision import lifecycle
    from steward.intent import intent_from_parsed
    from steward.pipeline import Steward

    s = Steward()
    est = lifecycle.estate(s.catalog, s.as_of)
    engine_retire = set(est.retire) | set(est.human_review)
    per: dict[str, dict] = {}
    for r in rows:
        q = s.ask(r["text"])
        d = q.decision
        expert = (d.verdict.value, d.best.artifact.id if d.best else None)
        if d.verdict.value == "CLARIFY":
            intent = ("CLARIFY", None)
        else:
            d2 = s.ask_intent(intent_from_parsed(q.question, s.catalog)).decision
            intent = (d2.verdict.value, d2.best.artifact.id if d2.best else None)
        per[r["id"]] = {"expert": expert, "intent": intent}
    out = {"summary": {}, "engine_commit": subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True,
                                                          capture_output=True).stdout.strip(),
           "as_of": str(s.as_of), "engine_retire_only": sorted(engine_retire)}
    for rule in ("today", "c2a"):
        for path in ("expert", "intent"):
            c: Counter = Counter()
            for r in rows:
                verdict, asset = per[r["id"]][path]
                exp = r[rule]
                if verdict == "CLARIFY":
                    c["clarify"] += 1
                elif verdict == "REUSE" and (exp["verdict"] != "REUSE" or asset not in exp["assets"]):
                    c["false_reuse"] += 1
                    if exp["verdict"] == "REUSE":
                        c["false_reuse_wrong_asset"] += 1
                    elif set(exp["assets"]) <= engine_retire:
                        c["false_reuse_explained_by_engine_retire"] += 1
                elif verdict == "CREATE" and "CREATE" not in exp["acceptable"]:
                    c["false_create"] += 1
                elif verdict == "CREATE" and exp.get("variant_only"):
                    c["create_on_variant_only"] += 1  # ambiguous by the plan, reported, not counted as an error
                if exp["verdict"] == "REUSE":
                    c["expected_reuse"] += 1
                    c["reuse_found"] += verdict == "REUSE" and asset in exp["assets"]
                c[f"engine_{verdict}"] += 1
            c["probes"] = len(rows)
            out["summary"][f"{rule}/{path}"] = dict(sorted(c.items()))
    out["per_probe"] = {k: [list(v["expert"]), list(v["intent"])] for k, v in per.items()}
    return out


def main() -> None:
    rows = build()
    write(rows)
    print(f"wrote {len(rows)} probes -> {OUT}")
    for rule in ("today", "c2a"):
        print(f"  oracle[{rule}]:", dict(Counter(r[rule]["verdict"] for r in rows)))
    if "--baseline" in sys.argv:
        result = run_engine(rows)
        BASELINE.write_text(json.dumps(result, indent=1, sort_keys=True), encoding="utf-8")
        for k, v in result["summary"].items():
            print(f"  engine {k}: {v}")
        print(f"baseline -> {BASELINE} (engine {result['engine_commit']})")


if __name__ == "__main__":
    main()
