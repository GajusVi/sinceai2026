"""Business_Requests from the data pack, and the text-vs-metadata check (trap 1).

The request metadata (product_context, market_context) contradicts the request text in most rows. Text wins.
Decision T6 (option C), each conflict has a severity:
- blocker: a different product, or "global" text against a region/country context -> ParsedQuestion.conflicts -> CLARIFY.
- confirm: the metadata is broader or narrower than the text (All Pharma vs named products, "Bayer Pharma" vs one
  product, "oncology brands" vs one of them) -> warning Evidence, the interview asks one question, the verdict follows the text.
Country-level text inside a region context is consistent, not a conflict.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

import pandas as pd

from .catalog import Catalog
from .config import ROOT_DIR
from .datapack import DEFAULT_XLSX
from .linking import find_terms

REGIONS_FILE = ROOT_DIR / "catalog" / "bayer" / "regions.json"
ALL_PHARMA = "All Pharma"
_GLOBAL = re.compile(r"(?<!\w)global")  # "global" as a market term; the dictionary has no Global value
_BAYER_PHARMA = re.compile(r"(?<!\w)bayer pharma")

Severity = Literal["blocker", "confirm"]


@dataclass(frozen=True)
class ContextConflict:
    severity: Severity
    message: str

    def __str__(self) -> str:
        return self.message


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


def context_conflicts(text: str, context: dict[str, str], catalog: Catalog) -> list[ContextConflict]:
    """Product and market/region the text names versus what the request metadata claims. Empty list = consistent."""
    terms = find_terms(text, catalog)
    normalized = text.lower().replace("\u2019", "").replace("'", "")
    conflicts: list[ContextConflict] = []

    named = _labels(terms, catalog, "product")
    products = named + [p for p in _area_products(normalized, xlsx_products()) if p not in named]
    claimed = context.get("product", "")
    if products and claimed:
        if claimed == ALL_PHARMA:
            conflicts.append(
                ContextConflict("confirm", f"the request metadata says {claimed} but the text names {_join(products)}: confirm the scope")
            )
        elif claimed not in products:
            conflicts.append(
                ContextConflict("blocker", f"the text names {_join(products)}, the request metadata says {claimed}")
            )
    elif _BAYER_PHARMA.search(normalized) and claimed and claimed != ALL_PHARMA:
        conflicts.append(
            ContextConflict("confirm", f"the text says Bayer Pharma, the request metadata says only {claimed}: confirm the scope")
        )

    claimed_market = context.get("market", "")
    places = {t.id for t in terms if t.kind == "value" and t.dimension in ("market", "region")}
    if _GLOBAL.search(normalized) and claimed_market not in ("", "Global"):
        conflicts.append(ContextConflict("blocker", f"the text says global, the request metadata says {claimed_market}"))
    elif places and claimed_market and not any(_nested(claimed_market, n) for n in places):
        conflicts.append(
            ContextConflict("blocker", f"the text names {_join(sorted(places))}, the request metadata says {claimed_market}")
        )
    return conflicts


def blockers(conflicts: list[ContextConflict]) -> list[str]:
    return [c.message for c in conflicts if c.severity == "blocker"]


def confirmations(conflicts: list[ContextConflict]) -> list[str]:
    return [c.message for c in conflicts if c.severity == "confirm"]


def severity_of(conflicts: list[ContextConflict]) -> str:
    """blocker > confirm > none: what the request as a whole needs."""
    if any(c.severity == "blocker" for c in conflicts):
        return "blocker"
    return "confirm" if conflicts else "none"


@lru_cache(maxsize=1)
def xlsx_products(xlsx: Path = DEFAULT_XLSX) -> dict[str, list[str]]:
    """therapeutic area -> product names, from the Products sheet ("Oncology" -> Nubeqa, Hyrnuo)."""
    df = pd.read_excel(xlsx, sheet_name="Products")
    areas: dict[str, list[str]] = {}
    for r in df.itertuples(index=False):
        areas.setdefault(r.therapeutic_area, []).append(r.product_name)
    return areas


def _area_products(normalized_text: str, areas: dict[str, list[str]]) -> list[str]:
    """Products behind a therapeutic-area word in the text. Word-start match on the first word, apostrophes dropped."""
    found: list[str] = []
    for area, names in areas.items():
        stem = re.sub(r"[^a-z ]", "", area.lower()).split()[0][:6]
        if re.search(rf"(?<!\w){re.escape(stem)}", normalized_text):
            found += [n for n in names if n not in found]
    return found


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
