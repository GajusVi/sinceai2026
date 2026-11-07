"""Data horizon: a period the data does not cover is flagged in the answer, never answered as if it did.

"Net sales in 2031" or "Q3 2025" against a data pack that runs Jan-Oct 2026 used to build a dashboard without a word.
"""

from __future__ import annotations

import re
from datetime import date

from ..models import Evidence


def period_evidence(text: str, period: str | None, first: date, last: date) -> Evidence | None:
    """A warning when a year or quarter named in `text` lies entirely outside [first, last] (months)."""
    asked = ""
    if period and (m := re.fullmatch(r"(\d{4})-Q([1-4])", period)):
        year, quarter = int(m.group(1)), int(m.group(2))
        start, end = date(year, 3 * quarter - 2, 1), date(year, 3 * quarter, 1)
        if end < first or start > last:
            asked = f"Q{quarter} {year}"
    else:
        years = [int(y) for y in re.findall(r"\b(20\d{2})\b", text)]
        outside = [y for y in years if y < first.year or y > last.year]
        if outside:
            asked = str(outside[0])
    if not asked:
        return None
    return Evidence(
        claim=(
            f"You asked for {asked}, which is outside the data: it covers {first:%b %Y} to {last:%b %Y}. "
            "A dashboard built from this answer shows those months only."
        ),
        rule_id="DATA",
        severity="warning",
        value=f"{first:%Y-%m} to {last:%Y-%m}",
    )
