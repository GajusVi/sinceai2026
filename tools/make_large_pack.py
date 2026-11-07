"""Generate a large synthetic data pack with EXACTLY the structure of the Bayer pack (same 24 sheets, same columns).

The original pack is kept inside the new one as a subset: every original row, id and planted trap stays, so the
verdict contract and the traps still hold. On top of it the script adds, by cloning original rows as templates:
  - a longer history: Product_Market_Monthly and Asset_Usage go back to --start (default 2021-01),
  - more assets (and their KPI maps, usage, lineage, signals, data-quality findings, migration rows),
  - more owners, workspaces, semantic models, launch milestones and business requests,
  - more plants: extra Supply_Operations rows (same columns) for Plant-D, Plant-E, ... as additional supply sources,
  - more spread: --noise multiplies the standard deviation of every generated number.
Products, Markets and KPI_Catalog are copied unchanged: the governed KPI bindings (catalog/bayer/measures.json) and
the parser dictionaries (catalog/bayer/dimensions.json) depend on them.

Usage:  .venv/bin/python tools/make_large_pack.py                 (large: 5,000 assets, 2021-01..2026-10, 10 plants)
        .venv/bin/python tools/make_large_pack.py --assets 1500 --start 2023-01 --plants 6 --noise 1.5
Then:   STEWARD_DATAPACK_XLSX=data/bayer_large/Bayer_Large_Synthetic_Pack.xlsx make bayer
The output is not committed (data/bayer_large/ is in .gitignore): run the script, it is seeded and reproducible.
"""

from __future__ import annotations

import argparse
import string
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data" / "bayer" / "Bayer_Pharmaceuticals_SinceAI_2026_FINAL_Builder_Data_Pack.xlsx"
OUT = ROOT / "data" / "bayer_large" / "Bayer_Large_Synthetic_Pack.xlsx"
COPIED = ["START_HERE", "Public_References", "Products", "Markets", "KPI_Catalog", "Market_Access",
          "Governance_Rules", "Data_Dictionary", "Package_Overview"]  # unchanged (layout sheets keep their header)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--assets", type=int, default=5000, help="total assets incl. the original 360 (max 9999)")
    p.add_argument("--start", default="2021-01", help="first month of the monthly history (original starts 2026-01)")
    p.add_argument("--plants", type=int, default=10, help="Plant-A.. count incl. the original A-C (max 26)")
    p.add_argument("--requests", type=int, default=2000, help="total business requests incl. the original 150")
    p.add_argument("--noise", type=float, default=2.0, help="std-dev multiplier for generated numbers")
    p.add_argument("--seed", type=int, default=2026)
    p.add_argument("--out", type=Path, default=OUT)
    a = p.parse_args()
    sheets = pd.read_excel(SOURCE, sheet_name=None)
    order = list(sheets)
    g = Generator(sheets, a)
    new = g.run()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(a.out, engine="openpyxl") as xl:
        for name in order:
            frame = sheets[name] if name in COPIED else new[name]
            frame.to_excel(xl, sheet_name=name, index=False)
    print(f"wrote {a.out}")
    for name in order:
        print(f"  {name:24} {len(sheets[name]):>6} -> {len(sheets[name] if name in COPIED else new[name]):>7} rows")


class Generator:
    def __init__(self, s: dict[str, pd.DataFrame], a: argparse.Namespace):
        self.s, self.a = s, a
        self.rng = np.random.default_rng(a.seed)
        self.noise = a.noise
        self.end = pd.Timestamp(s["Product_Market_Monthly"]["month"].max())
        self.first_orig = pd.Timestamp(s["Product_Market_Monthly"]["month"].min())
        self.start = pd.Timestamp(a.start + "-01")
        self.products = s["Products"]
        self.markets = s["Markets"]
        self.asset_map: dict[str, str] = {}  # new asset id -> template asset id
        self.model_map: dict[str, str] = {}

    # -- helpers --------------------------------------------------------------------------------------------------
    def pick(self, values, n=None):
        values = list(values)
        idx = self.rng.integers(0, len(values), size=n)
        return values[idx] if n is None else [values[i] for i in idx]

    def clone(self, df: pd.DataFrame, n: int) -> pd.DataFrame:
        return df.iloc[self.rng.integers(0, len(df), size=n)].reset_index(drop=True).copy()

    def months(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.DatetimeIndex:
        return pd.date_range(start, end, freq="MS")

    # -- run ------------------------------------------------------------------------------------------------------
    def run(self) -> dict[str, pd.DataFrame]:
        out = {}
        scale = max(1.0, self.a.assets / len(self.s["Analytics_Assets"]))
        out["Owners"] = self.owners(min(999, int(len(self.s["Owners"]) * scale)))
        out["Workspaces"] = self.workspaces(min(99, int(len(self.s["Workspaces"]) * scale ** 0.5)))
        out["Semantic_Models"] = self.models(min(999, int(len(self.s["Semantic_Models"]) * scale)), out)
        out["Analytics_Assets"] = self.assets(min(9999, self.a.assets), out)
        out["Asset_KPI_Map"] = self.kpi_map(out)
        out["Asset_Usage"] = self.usage(out)
        out["Lineage_Edges"] = self.lineage(out)
        out["Product_Market_Monthly"] = self.pmm()
        out["Launch_Milestones"] = self.milestones(int(len(self.s["Launch_Milestones"]) * 4))
        out["Supply_Operations"] = self.supply()
        out["Data_Quality"] = self.data_quality(out)
        out["Governance_Signals"] = self.signals()
        out["Migration_Backlog"] = self.migration(out)
        out["Business_Requests"] = self.requests()
        out["Change_Log"] = self.change_log()
        return out

    def owners(self, n: int) -> pd.DataFrame:
        orig = self.s["Owners"]
        extra = self.clone(orig, n - len(orig))
        first = sorted({x.split()[0] for x in orig.owner_name})
        last = sorted({x.split()[-1] for x in orig.owner_name})
        ids = [f"OWN-{i:03d}" for i in range(len(orig) + 1, n + 1)]
        extra["owner_id"] = ids
        extra["owner_name"] = [f"{self.pick(first)} {self.pick(last)}" for _ in ids]
        extra["email"] = [f"owner{i[4:]}@synthetic.example" for i in ids]
        return pd.concat([orig, extra], ignore_index=True)

    def workspaces(self, n: int) -> pd.DataFrame:
        orig = self.s["Workspaces"]
        extra = self.clone(orig, max(0, n - len(orig)))
        extra["workspace_id"] = [f"WS-{i:03d}" for i in range(len(orig) + 1, len(orig) + len(extra) + 1)]
        letters = self.pick(list(string.ascii_uppercase), len(extra))
        extra["workspace_name"] = [f"{w} {k}" for w, k in zip(extra.workspace_name, letters, strict=True)]
        return pd.concat([orig, extra], ignore_index=True)

    def models(self, n: int, out) -> pd.DataFrame:
        orig = self.s["Semantic_Models"]
        extra = self.clone(orig, max(0, n - len(orig)))
        ids = [f"SM-{i:03d}" for i in range(len(orig) + 1, len(orig) + len(extra) + 1)]
        tmpl = orig.iloc[self.rng.integers(0, len(orig), size=len(extra))]
        self.model_map.update(dict(zip(ids, tmpl.model_id, strict=True)))
        extra = tmpl.reset_index(drop=True).copy()
        extra["model_id"] = ids
        names = zip(extra.model_name, ids, strict=True)
        extra["model_name"] = [f"{name.rsplit(' ', 1)[0]} {i[3:]}" for name, i in names]
        extra["workspace_id"] = self.pick(out["Workspaces"].workspace_id, len(extra))
        extra["owner_id"] = self.pick(out["Owners"].owner_id, len(extra))
        for col in ("table_count", "measure_count"):
            extra[col] = np.maximum(1, (extra[col] * self.rng.lognormal(0, 0.3 * self.noise, len(extra)))).astype(int)
        return pd.concat([orig, extra], ignore_index=True)

    def assets(self, n: int, out) -> pd.DataFrame:
        orig = self.s["Analytics_Assets"]
        k = n - len(orig)
        tmpl = orig.iloc[self.rng.integers(0, len(orig), size=k)].reset_index(drop=True)
        new = tmpl.copy()
        ids = [f"AST-{i:04d}" for i in range(len(orig) + 1, n + 1)]
        self.asset_map.update(dict(zip(ids, tmpl.asset_id, strict=True)))
        products = list(self.products.product_name) + ["All Pharma"]
        markets = list(self.markets.market_id) + ["Global"]
        new["asset_id"] = ids
        new["product_scope"] = self.pick(products, k)
        new["market_scope"] = self.pick(markets, k)
        new["asset_name"] = [_rename(name, old, prod) for name, old, prod in
                             zip(tmpl.asset_name, tmpl.product_scope, new.product_scope, strict=True)]
        new["workspace_id"] = self.pick(out["Workspaces"].workspace_id, k)
        new["model_id"] = self.pick(out["Semantic_Models"].model_id, k)
        new["owner_id"] = [None if pd.isna(o) else self.pick(out["Owners"].owner_id) for o in tmpl.owner_id]
        span = (self.end - pd.Timestamp("2015-01-01")).days
        created = pd.Timestamp("2015-01-01") + pd.to_timedelta(self.rng.integers(0, span - 30, k), unit="D")
        new["created_date"] = created.normalize()
        lag = self.rng.integers(0, np.maximum(1, (self.end - created).days), k)
        new["last_modified"] = (created + pd.to_timedelta(lag, unit="D")).normalize()
        new["estimated_audience"] = np.maximum(
            1, tmpl.estimated_audience * self.rng.lognormal(0, 0.4 * self.noise, k)).astype(int)
        for col in ("created_date", "last_modified"):
            new[col] = pd.to_datetime(new[col]).dt.date
        return pd.concat([orig, new], ignore_index=True)

    def kpi_map(self, out) -> pd.DataFrame:
        orig = self.s["Asset_KPI_Map"]
        by_asset = orig.groupby("asset_id")
        kpis = list(self.s["KPI_Catalog"].kpi_id)
        rows = []
        for new_id, tmpl in self.asset_map.items():
            part = by_asset.get_group(tmpl).copy() if tmpl in by_asset.groups else orig.head(0).copy()
            part["asset_id"] = new_id
            if len(part) > 1 and self.rng.random() < 0.15:  # a little drift away from the template
                part = part.drop(part.index[self.rng.integers(0, len(part))])
            if self.rng.random() < 0.15:
                extra = part.head(1).copy() if len(part) else orig.head(1).copy()
                extra["asset_id"], extra["kpi_id"], extra["usage_role"] = new_id, self.pick(kpis), "secondary"
                part = pd.concat([part, extra])
            rows.append(part.drop_duplicates(["asset_id", "kpi_id"]))
        return pd.concat([orig, *rows], ignore_index=True)

    def usage(self, out) -> pd.DataFrame:
        """Original assets: original 2026 months kept, history added before them. New assets: from their creation
        month (or --start) to the last month. Level from the template's mean, month noise scaled by --noise."""
        orig = self.s["Asset_Usage"]
        num = ["views", "unique_users", "exports", "subscriptions", "avg_load_ms", "query_errors"]
        means = orig.groupby("asset_id")[num].mean()
        assets = out["Analytics_Assets"].set_index("asset_id")
        frames = [orig]
        for asset_id, row in assets.iterrows():
            template = self.asset_map.get(asset_id, asset_id)
            created = max(pd.Timestamp(row.created_date).to_period("M").to_timestamp(), self.start)
            last = self.first_orig - pd.offsets.MonthBegin(1) if asset_id not in self.asset_map else self.end
            span = self.months(created, last)
            if not len(span):
                continue
            base = means.loc[template] * (self.rng.lognormal(0, 0.3 * self.noise) if asset_id in self.asset_map else 1)
            n = len(span)
            trend = np.linspace(self.rng.uniform(0.6, 1.4), 1.0, n)  # drifts towards today's level
            block = {"asset_id": asset_id, "month": span}
            for col in num:
                wobble = self.rng.normal(1.0, 0.18 * self.noise, n).clip(0.05)
                block[col] = np.maximum(0, base[col] * trend * wobble).round().astype(int)
            block["unique_users"] = np.minimum(block["unique_users"], block["views"])
            block["synthetic_record"] = True
            frames.append(pd.DataFrame(block))
        df = pd.concat(frames, ignore_index=True)
        df["month"] = pd.to_datetime(df["month"])
        return df.sort_values(["asset_id", "month"]).reset_index(drop=True)

    def lineage(self, out) -> pd.DataFrame:
        orig = self.s["Lineage_Edges"]
        assets = out["Analytics_Assets"]
        new = assets[assets.asset_id.isin(self.asset_map)]
        model_edges = pd.DataFrame({"source_id": new.model_id, "target_id": new.asset_id,
                                    "edge_type": "MODEL_TO_ASSET", "relationship": "semantic dependency",
                                    "synthetic_record": True})
        ids = list(new.asset_id)
        k = int(len(ids) * 56 / 360)
        derived = pd.DataFrame({"source_id": self.pick(ids, k), "target_id": self.pick(ids, k),
                                "edge_type": "ASSET_TO_ASSET", "relationship": "embedded / derived",
                                "synthetic_record": True})
        derived = derived[derived.source_id != derived.target_id]
        new_models = [m for m in out["Semantic_Models"].model_id if m in self.model_map]
        k = int(len(new_models) * 22 / 75)
        shared = pd.DataFrame({"source_id": self.pick(new_models, k), "target_id": self.pick(new_models, k),
                               "edge_type": "MODEL_TO_MODEL", "relationship": "shared upstream pharma data product",
                               "synthetic_record": True})
        shared = shared[shared.source_id != shared.target_id]
        return pd.concat([orig, model_edges, derived, shared], ignore_index=True).drop_duplicates(
            ["source_id", "target_id", "edge_type"])

    def pmm(self) -> pd.DataFrame:
        """History before the original months for every product x market pair: level and spread taken from the pair's
        original rows, a slow trend into 2026, month noise scaled by --noise."""
        orig = self.s["Product_Market_Monthly"]
        span = self.months(self.start, self.first_orig - pd.offsets.MonthBegin(1))
        if not len(span):
            return orig
        rows = []
        for (pid, mid), part in orig.groupby(["product_id", "market_id"]):
            n = len(span)
            growth = np.linspace(self.rng.uniform(0.45, 0.9), 1.0, n)  # sales grew into 2026
            sales = np.maximum(0.01, part.net_sales_m_eur_syn.mean() * growth
                               * self.rng.normal(1, 0.15 * self.noise, n)).round(2)
            fvar = self.rng.normal(part.forecast_variance_pct.mean(), max(1.0, part.forecast_variance_pct.std())
                                   * self.noise, n).round(1)
            forecast = (sales / (1 + fvar / 100)).round(2)
            units = np.maximum(0, part.units_shipped_syn.mean() * growth
                               * self.rng.normal(1, 0.2 * self.noise, n)).astype(int)
            access = np.clip(np.linspace(self.rng.uniform(5, 40), part.market_access_coverage_pct_syn.mean(), n)
                             + self.rng.normal(0, 6 * self.noise, n), 0, 100).round(1)
            otif = np.clip(self.rng.normal(part.otif_pct_syn.mean(), max(3, part.otif_pct_syn.std()) * self.noise, n),
                           40, 100).round(1)
            inv = np.clip(self.rng.normal(part.inventory_weeks_syn.mean(),
                                          max(0.8, part.inventory_weeks_syn.std()) * self.noise, n), 0.5, 26).round(2)
            zero = part.net_sales_m_eur_syn.eq(0).mean() > 0.5  # pairs not sold yet stay at zero (trap 14)
            block = pd.DataFrame({
                "product_id": pid, "market_id": mid, "month": span,
                "net_sales_m_eur_syn": 0.0 if zero else sales, "forecast_m_eur_syn": 0.0 if zero else forecast,
                "units_shipped_syn": 0 if zero else units, "forecast_variance_pct": np.nan if zero else fvar,
                "market_access_coverage_pct_syn": 0.0 if zero else access, "otif_pct_syn": 0.0 if zero else otif,
                "inventory_weeks_syn": 0.0 if zero else inv,
                "value_type": self.pick(list(orig.value_type.unique()), n), "synthetic_record": True,
            })
            rows.append(block)
        df = pd.concat([*rows, orig], ignore_index=True)
        df["month"] = pd.to_datetime(df["month"])
        return df.sort_values(["product_id", "market_id", "month"]).reset_index(drop=True)

    def milestones(self, n: int) -> pd.DataFrame:
        orig = self.s["Launch_Milestones"]
        extra = self.clone(orig, max(0, n - len(orig)))
        extra["milestone_id"] = [f"LM-{i:04d}" for i in range(len(orig) + 1, len(orig) + len(extra) + 1)]
        extra["product_id"] = self.pick(self.products.product_id, len(extra))
        extra["market_id"] = self.pick(self.markets.market_id, len(extra))
        span = (pd.Timestamp("2026-12-31") - self.start).days
        dates = self.start + pd.to_timedelta(self.rng.integers(0, span, len(extra)), unit="D")
        extra["milestone_date"] = dates.date
        done = dates < self.end
        extra["status"] = np.where(done, self.pick(["completed", "completed", "completed", "delayed"], len(extra)),
                                   self.pick(["planned", "in_progress"], len(extra)))
        return pd.concat([orig, extra], ignore_index=True)

    def supply(self) -> pd.DataFrame:
        """Original rows unchanged (Plant-A..C, External-CMO). Each extra plant becomes an additional supply source for
        a share of the product x market pairs, with its own (noisier) service levels."""
        orig = self.s["Supply_Operations"]
        letters = string.ascii_uppercase[: max(3, min(26, self.a.plants))]
        extra_plants = [f"Plant-{x}" for x in letters[3:]]
        rows = []
        for plant in extra_plants:
            part = self.clone(orig, int(len(orig) * self.rng.uniform(0.15, 0.35))).drop_duplicates(
                ["product_id", "market_id"]).copy()
            k = len(part)
            part["supply_source"] = plant
            part["otif_pct_syn"] = np.clip(self.rng.normal(part.otif_pct_syn, 6 * self.noise), 40, 100).round(1)
            part["inventory_weeks_syn"] = np.clip(self.rng.normal(part.inventory_weeks_syn, 1.5 * self.noise),
                                                  0.5, 26).round(1)
            part["forecast_accuracy_pct_syn"] = np.clip(
                self.rng.normal(part.forecast_accuracy_pct_syn, 5 * self.noise), 40, 100).round(1)
            part["risk_status"] = np.select([part.otif_pct_syn < 75, part.otif_pct_syn < 88], ["red", "amber"],
                                            "green") if k else part.risk_status
            rows.append(part)
        return pd.concat([orig, *rows], ignore_index=True)

    def _copy_for_clones(self, df: pd.DataFrame, key: str, mapping: dict[str, str]) -> pd.DataFrame:
        """Rows that belong to a template (asset or model) repeated for each of its clones, with the clone's id."""
        inverse: dict[str, list[str]] = {}
        for new_id, tmpl in mapping.items():
            inverse.setdefault(tmpl, []).append(new_id)
        parts = []
        for tmpl, part in df[df[key].isin(inverse)].groupby(key):
            for new_id in inverse[tmpl]:
                copy = part.copy()
                copy[key] = new_id
                parts.append(copy)
        return pd.concat(parts, ignore_index=True) if parts else df.head(0)

    def data_quality(self, out) -> pd.DataFrame:
        orig = self.s["Data_Quality"]
        models = self._copy_for_clones(orig[orig.sheet == "Semantic_Models"], "record_id", self.model_map)
        assets = self._copy_for_clones(orig[orig.sheet == "Analytics_Assets"], "record_id", self.asset_map)
        extra = pd.concat([models, assets], ignore_index=True)
        extra["issue_id"] = [f"DQ-{i:04d}" for i in range(len(orig) + 1, len(orig) + len(extra) + 1)]
        return pd.concat([orig, extra], ignore_index=True)

    def signals(self) -> pd.DataFrame:
        orig = self.s["Governance_Signals"]
        extra = self._copy_for_clones(orig, "asset_id", self.asset_map)
        extra["signal_id"] = [f"SIG-{i:05d}" for i in range(len(orig) + 1, len(orig) + len(extra) + 1)]
        extra["status"] = self.pick(list(orig.status), len(extra))
        return pd.concat([orig, extra], ignore_index=True)

    def migration(self, out) -> pd.DataFrame:
        orig = self.s["Migration_Backlog"]
        extra = self._copy_for_clones(orig, "source_asset_id", self.asset_map)
        if len(extra):
            assets = out["Analytics_Assets"].set_index("asset_id")
            extra["product_scope"] = assets.loc[extra.source_asset_id, "product_scope"].values
            extra["market_scope"] = assets.loc[extra.source_asset_id, "market_scope"].values
            extra["candidate_target_model_id"] = self.pick(out["Semantic_Models"].model_id, len(extra))
        return pd.concat([orig, extra], ignore_index=True)

    def requests(self) -> pd.DataFrame:
        """More requests from the same 10 templates (the hold-out stays easy to rebuild), spread over the history,
        product/market metadata sampled like the original (so text-vs-metadata conflicts keep their rate)."""
        orig = self.s["Business_Requests"]
        extra = self.clone(orig, max(0, self.a.requests - len(orig)))
        extra["request_id"] = [f"REQ-{i:04d}" for i in range(len(orig) + 1, len(orig) + len(extra) + 1)]
        span = (self.end + pd.offsets.MonthEnd(1) - self.start).days
        extra["request_date"] = (self.start + pd.to_timedelta(self.rng.integers(0, span, len(extra)), unit="D")).date
        extra["product_context"] = self.pick(list(orig.product_context), len(extra))
        extra["market_context"] = self.pick(list(orig.market_context), len(extra))
        extra["status"] = self.pick(["new", "triaged", "triaged", "done", "rejected"], len(extra))
        return pd.concat([orig, extra], ignore_index=True)

    def change_log(self) -> pd.DataFrame:
        orig = self.s["Change_Log"]
        row = {"version": 2.1, "date": pd.Timestamp.today().normalize(), "owner": "SinceAI team (synthetic)",
               "change": (f"Scaled-up synthetic copy made by tools/make_large_pack.py (seed {self.a.seed}): "
                          f"{self.a.assets} assets, history from {self.a.start}, {self.a.plants} plants, "
                          f"noise x{self.a.noise}. Original rows kept as a subset; Package_Overview counts are the "
                          "original pack's.")}
        return pd.concat([orig, pd.DataFrame([row])], ignore_index=True)


def _rename(name: str, old_scope: str, new_scope: str) -> str:
    """Asset name of a clone: the template's name with its product swapped for the clone's product scope. The
    template's suffix (- EMEA, - US, - Global) is kept, so name-vs-scope mismatches (trap 18) keep their rate."""
    if isinstance(old_scope, str) and old_scope in name:
        return name.replace(old_scope, new_scope, 1)
    return f"{new_scope} {name}"


if __name__ == "__main__":
    main()
