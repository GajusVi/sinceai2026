"""AI takeaway (AI-first step 4): the LLM reads the numbers the rendered dashboard shows and writes the headline.

Code computes every number (render.py); the model may only quote them. Validation: every number in the text must
appear in the facts exactly (digits compared without thousands separators). A failed check or no LLM -> "".
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from .prompts import render_prompt
from .render import RenderedDashboard

logger = logging.getLogger(__name__)
_NUMBER = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")
MAX_TABLE_ROWS = 5


def facts(rendered: RenderedDashboard) -> str:
    lines = []
    for c in rendered.cards:
        lines.append(
            f"- {c.title}: {c.value}"
            + (f" ({c.comparison})" if c.comparison else "")
            + (f" note: {c.note}" if c.note else "")
        )
    for g in rendered.gaps:
        lines.append(f"- {g.title}: GAP, not measured in governed data ({g.reason})")
    for title, table in rendered.tables:
        if table.empty:
            lines.append(f"- {title}: none")
            continue
        rows = table.head(MAX_TABLE_ROWS).to_dict("records")
        lines.append(
            f"- {title} ({len(table)} rows, worst first): "
            + "; ".join(", ".join(f"{k} {v}" for k, v in r.items()) for r in rows)
        )
    return "\n".join(lines)


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "").lstrip("+-") for n in _NUMBER.findall(text)}


def validate(text: str, known: str) -> str:
    """The text, or "" if it quotes a number the facts do not contain."""
    text = " ".join(str(text).split())
    if not text or _numbers(text) - _numbers(known):
        return ""
    return text


def takeaway(llm, prompts_dir: Path, question: str, rendered: RenderedDashboard) -> str:
    if llm is None or not (rendered.cards or rendered.tables):
        return ""
    known = facts(rendered)
    try:
        raw = llm.generate_json(
            render_prompt(
                prompts_dir,
                "takeaway",
                question=question,
                title=rendered.title,
                filters=", ".join(f"{k} {v}" for k, v in rendered.filters.items()) or "none",
                facts=known,
            )
        )
        return validate(raw.get("takeaway", ""), known)
    except Exception:
        logger.warning("llm_takeaway_failed", exc_info=True)
        return ""
