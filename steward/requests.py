"""Business_Requests from the data pack, and the text-vs-metadata check (trap 1).

The request metadata (product_context, market_context) contradicts the request text in most rows. Text wins:
a contradiction goes to ParsedQuestion.conflicts, and the engine answers CLARIFY (blocker evidence).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .catalog import Catalog
from .config import ROOT_DIR
from .datapack import DEFAULT_XLSX
from .linking import find_terms

REGIONS_FILE = ROOT_DIR / "catalog" / "bayer" / "regions.json"


@dataclass(frozen=True)
class BusinessRequest:
    request_id: str
    text: str
    product_context: str
    market_context: str

    @property
    def context(self) -> dict[str, str]:
        return {"product": self.product_context, "market": self.market_context}


def load_requests(xlsx: Path = DEFAULT_XLSX) -> list[BusinessRequest]:
    df = pd.read_excel(xlsx, sheet_name="Business_Requests")
    return [
        BusinessRequest(r.request_id, r.request_text, str(r.product_context), str(r.market_context))
        for r in df.itertuples(index=False)
    ]


def context_conflicts(text: str, context: dict[str, str], catalog: Catalog) -> list[str]:
    """Product and market/region the text names versus what the request metadata claims. Empty list = consistent."""
    terms = find_terms(text, catalog)
    conflicts = []

    products = _labels(terms, catalog, "product")
    claimed_product = context.get("product", "")
    if products and claimed_product and claimed_product not in products:
        conflicts.append(f"the text names {_join(products)}, the request metadata says {claimed_product}")

    claimed_market = context.get("market", "")
    named = {t.id for t in terms if t.kind == "value" and t.dimension in ("market", "region")}
    if named and claimed_market and not any(_nested(claimed_market, n) for n in named):
        conflicts.append(f"the text names {_join(sorted(named))}, the request metadata says {claimed_market}")
    return conflicts


def _labels(terms, catalog: Catalog, dimension: str) -> list[str]:
    seen: list[str] = []
    for t in terms:
        if t.kind == "value" and t.dimension == dimension:
            label = catalog.dimension_value_label(dimension, t.id)
            if label not in seen:
                seen.append(label)
    return seen


def _nested(a: str, b: str) -> bool:
    """Same place, or one is a region that contains the other ("DE" inside "EMEA"). "Global" contains everything."""
    if a == b or "Global" in (a, b):
        return True
    regions = json.loads(REGIONS_FILE.read_text(encoding="utf-8"))
    return a in regions.get(b, []) or b in regions.get(a, [])


def _join(items: list[str]) -> str:
    return " and ".join(items)
