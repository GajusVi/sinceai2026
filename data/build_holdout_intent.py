"""Pre-fill data/holdout/requests_intent.jsonl from the 10 Business_Requests templates (docs/challenge/03_DATA_PACK.md).

Expected values come from the request TEXT only (never from product_context / market_context). A template rule says what
its text names; the script applies it to the 150 requests, then picks 4 per template (2 conflicts + 2 clean where possible,
distinct product_context first). Every line was then checked by hand. Intent only, no verdicts.
Run: .venv/Scripts/python.exe data/build_holdout_intent.py   [--stats prints the conflict counts]
"""

import glob
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "holdout" / "requests_intent.jsonl"
ONCOLOGY = ["Nubeqa", "Hyrnuo"]  # Products sheet: Onc

# template (product name replaced by <P>) -> what the text names. scope: None = text silent, "global", "regions", "country_level"
T = {
    "Please create a Power BI replacement for our legacy Tableau <P> commercial workbook.": dict(
        metrics=[],
        scope=None,
        notes="Names no metric (commercial workbook replacement).",
    ),
    "Can we have a new finance dashboard for net sales, gross-to-net and budget variance by product?": dict(
        metrics=["net_sales", "gross_to_net_rate", "budget_variance"],
        scope=None,
        notes="'by product' is a breakdown, not a product filter.",
    ),
    "Can we build a launch dashboard for <P> with market access, first sales and adoption indicators?": dict(
        metrics=["market_access_coverage", "launch_adoption_index"],
        scope=None,
        notes="'first sales' is ambiguous and stays unmapped (CLARIFY).",
    ),
    "Please build a new report for market access coverage and reimbursement status by product.": dict(
        metrics=["market_access_coverage", "reimbursement_status_coverage"],
        scope=None,
        notes="'by product' is a breakdown, not a product filter.",
    ),
    "I need a dashboard comparing product performance across oncology brands and markets.": dict(
        metrics=[],
        scope=None,
        products=ONCOLOGY,
        notes="'oncology brands' = Nubeqa + Hyrnuo (Products sheet). 'performance' is ambiguous, no metric. "
        "'across markets' is a breakdown, no market filter.",
    ),
    "I need a new <P> management report for monthly performance in EMEA and North America.": dict(
        metrics=[],
        scope="regions",
        regions=["EMEA", "North America"],
        notes="'performance' is ambiguous, no metric. Two regions named.",
    ),
    "We need one executive view combining net sales, forecast accuracy and inventory coverage for Bayer Pharma.": dict(
        metrics=["net_sales", "demand_forecast_accuracy", "inventory_coverage"],
        scope=None,
        all_pharma=True,
        notes="'Bayer Pharma' = all products, so no product filter.",
    ),
    "Can you create a country-level <P> report for launch readiness and reimbursement progress?": dict(
        metrics=["reimbursement_status_coverage"],
        scope="country_level",
        notes="'launch readiness' is ambiguous and stays unmapped; 'reimbursement progress' -> reimbursement. "
        "Country level = one row per country, no country named.",
    ),
    "Create a global <P> dashboard showing sales growth, forecast variance and market access by country.": dict(
        metrics=["net_sales_growth", "forecast_variance", "market_access_coverage"],
        scope="global",
        notes="'global' scope; 'by country' is a breakdown.",
    ),
    "We need a monthly supply-risk dashboard by medicine and country.": dict(
        metrics=[],
        scope=None,
        notes="Supply risk has no canonical KPI among the 18 (Supply_Operations sheet), stays unmapped. "
        "'by medicine/country' are breakdowns.",
    ),
}


def load():
    f = glob.glob(str(ROOT / "data" / "bayer" / "*.xlsx"))[0]
    x = pd.read_excel(f, sheet_name=None)
    return x["Business_Requests"], x["Products"].product_name.tolist(), set(x["Markets"].market_id)


def label(row, names, countries):
    text, pc, mc = row.request_text, row.product_context, row.market_context
    tmpl, named = text, None
    for p in names:
        if p in text:
            named = p
            tmpl = tmpl.replace(p, "<P>")
    rule = T[tmpl]
    products = rule.get("products", [named] if named else [])
    regions = rule.get("regions", [])
    conflicts, blockers = [], 0  # severity (Gajus, T6 option C): blocker -> CLARIFY, confirm -> warning, none
    if products and pc not in products:
        conflicts.append(f"text names {'/'.join(products)}, product_context is {pc}")
        blockers += pc != "All Pharma"  # All Pharma is broader metadata, not a contradiction: confirm
    if rule.get("all_pharma") and pc != "All Pharma":
        conflicts.append(f"text says Bayer Pharma (all products), product_context is {pc}")
    scope = rule["scope"]
    if scope == "global" and mc != "Global":
        conflicts.append(f"text says global, market_context is {mc}")
        blockers += 1
    elif scope == "regions" and mc not in regions:
        conflicts.append(f"text says {' and '.join(regions)}, market_context is {mc}")
        blockers += 1
    # country-level text inside any region context is consistent (a region is made of countries): no conflict
    note = rule["notes"] + (" Conflict: " + "; ".join(conflicts) + "." if conflicts else "")
    out = dict(
        request_id=row.request_id,
        text=text,
        product_context=pc,
        market_context=mc,
        expected_products=products,
        expected_markets=[],
        expected_regions=regions,
        expected_metric_ids=rule["metrics"],
        expected_grain="month",
        metadata_conflict=bool(conflicts),
        metadata_severity="blocker" if blockers else "confirm" if conflicts else "none",
        notes=note,
    )
    return out, tmpl, any(c.startswith("text names") for c in conflicts)


def main():
    b, names, countries = load()
    rows = [label(r, names, countries) for r in b.itertuples()]
    if "--stats" in sys.argv:
        named = [x for x in rows if x[0]["expected_products"]]
        print("requests naming a product:", len(named), "| product mismatch:", sum(x[2] for x in named))
        print("all conflicts:", sum(x[0]["metadata_conflict"] for x in rows), "of", len(rows))
    if OUT.exists():  # the 40 ids are fixed once published (other tests rely on them): only relabel them
        keep = [json.loads(line)["request_id"] for line in OUT.read_text(encoding="utf-8").splitlines()]
        by_id = {r["request_id"]: r for r, _, _ in rows}
        OUT.write_text("".join(json.dumps(by_id[i], ensure_ascii=False) + "\n" for i in keep), encoding="utf-8")
        print(f"relabelled {len(keep)} lines in {OUT.relative_to(ROOT)}")
        return
    picked = []
    for tmpl in T:
        grp = [r for r, t, _ in rows if t == tmpl]
        take, seen = [], set()
        for want in (True, True, False, False):
            pool = [r for r in grp if r["metadata_conflict"] == want and r not in take]
            pool.sort(key=lambda r: (r["product_context"] in seen, r["request_id"]))
            if pool:
                take.append(pool[0])
                seen.add(pool[0]["product_context"])
        for r in sorted(grp, key=lambda r: r["request_id"]):  # top up if one pool was short
            if len(take) < 4 and r not in take:
                take.append(r)
        picked += sorted(take, key=lambda r: r["request_id"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in picked), encoding="utf-8")
    print(f"wrote {len(picked)} lines to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
