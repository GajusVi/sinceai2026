"""Generate catalog/bayer/{metrics,dimensions,regions}.json from the data pack.
Run: .venv/Scripts/python.exe data/build_bayer_dictionaries.py"""
import json
import re
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
XLSX = ROOT / "data/bayer/Bayer_Pharmaceuticals_SinceAI_2026_FINAL_Builder_Data_Pack.xlsx"
OUT = ROOT / "catalog/bayer"

# Hand-written, lowercase word-start stems. NOT synonyms (must CLARIFY): coverage, forecast,
# performance, first sales, readiness.
SYNONYMS = {
    "Net Sales": ["net sales", "sales", "revenue", "turnover"],
    "Net Sales Growth": ["sales growth", "growth"],
    "Demand Forecast Accuracy": ["forecast accuracy"],
    "Demand Forecast Bias": ["forecast bias"],
    "Units Shipped": ["units shipped", "units", "volume", "shipments"],
    "Inventory Coverage": ["inventory coverage", "inventory", "stock cover", "weeks of supply"],
    "On-Time In-Full": ["otif", "on-time in-full", "on time in full"],
    "Launch Adoption Index": ["launch adoption", "adoption", "uptake"],
    "Market Access Coverage": ["market access"],
    "Reimbursement Status Coverage": ["reimbursement"],
    "Gross-to-Net Rate": ["gross-to-net", "gross to net", "gtn"],
    "Operating Contribution": ["operating contribution", "contribution"],
    "Budget Variance": ["budget variance", "vs budget", "budget"],
    "Forecast Variance": ["forecast variance", "vs forecast"],
    "Commercial Reach Index": ["commercial reach"],
    "Digital Engagement Index": ["digital engagement"],
    "Report Adoption": ["report adoption", "report usage"],
    "Certified Asset Share": ["certified asset share", "certification rate"],
}
PRODUCT_SYN = {"P-NUB": ["nubeqa"], "P-KER": ["kerendia"], "P-EYL": ["eylea"], "P-XAR": ["xarelto"],
               "P-LYN": ["lynkuet"], "P-BEY": ["beyonttra"], "P-HYR": ["hyrnuo"]}
MARKET_EXTRA = {
    "US": ["usa", "united states"], "UK": ["britain", "great britain"], "BR": ["brasil", "brasilien", "brésil"],
    "DE": ["deutschland"], "SE": ["sverige"], "FI": ["suomi"], "IT": ["italia"], "ES": ["españa", "espana"],
}
REGION_SYN = {"EMEA": ["emea", "europe"], "North America": ["north america"],
              "Asia Pacific": ["asia pacific", "apac"], "Latin America": ["latin america", "latam"]}


def rows(wb, name):
    it = wb[name].iter_rows(values_only=True)
    head = next(it)
    return [dict(zip(head, r)) for r in it if r[0] is not None]


def slug(s):
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def main():
    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    kpis = rows(wb, "KPI_Catalog")
    metrics = []
    for k in kpis:
        if k["definition_status"] != "canonical":
            continue
        name = k["canonical_metric"]
        assert name in SYNONYMS, name
        variants = [
            {"kpi_id": v["kpi_id"], "kpi_name": v["kpi_name"], "definition_status": v["definition_status"],
             "approval_status": v["approval_status"], "owner_id": v["owner_id"]}
            for v in kpis if v["canonical_metric"] == name and v["kpi_id"] != k["kpi_id"]
        ]
        metrics.append({
            "id": slug(name), "name": name, "kpi_id": k["kpi_id"],
            "formula": f"governed definition {k['kpi_id']} (synthetic: no formula in data pack)",
            "owner": k["owner_id"], "domain": k["domain"], "unit": k["unit"],
            "synonyms": SYNONYMS[name], "variants": variants,
        })
    assert len(metrics) == 18, len(metrics)
    (OUT / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    products = rows(wb, "Products")
    markets = rows(wb, "Markets")
    dims = [
        {"id": "product", "name": "Product", "synonyms": ["by product", "product", "brand", "medicine"],
         "values": [{"id": p["product_id"], "label": p["product_name"],
                     "synonyms": PRODUCT_SYN[p["product_id"]]} for p in products]},
        {"id": "market", "name": "Market", "synonyms": ["by market", "market", "country", "countries"],
         "values": [{"id": m["market_id"], "label": m["market_name"],
                     "synonyms": [m["market_name"].lower()] + MARKET_EXTRA.get(m["market_id"], [])} for m in markets]},
        {"id": "region", "name": "Region", "synonyms": ["by region", "region"],
         "values": [{"id": r, "label": r, "synonyms": s} for r, s in REGION_SYN.items()]},
        {"id": "month", "name": "Month", "synonyms": ["by month", "monthly", "month"], "values": []},
        {"id": "quarter", "name": "Quarter", "synonyms": ["by quarter", "quarterly", "quarter"], "values": []},
    ]
    (OUT / "dimensions.json").write_text(json.dumps(dims, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    regions = {}
    for m in markets:
        regions.setdefault(m["region"], []).append(m["market_id"])
    assert set(regions) == set(REGION_SYN)
    (OUT / "regions.json").write_text(json.dumps(regions, indent=2) + "\n", encoding="utf-8")
    print(len(metrics), "metrics;", sum(len(m["variants"]) for m in metrics), "variants;", regions)


main()
