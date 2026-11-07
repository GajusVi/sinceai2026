"""BI Steward design system for Streamlit: tokens, CSS and small HTML components (docs/steward/DESIGN.md).

Rules (from the design repos we follow): one accent (trust blue), navy ink, slate neutrals; status colours only for
status; no emoji as icons (dots, badges and chips instead); plain copy; equal edges; motion only on hover/press,
<= 180 ms ease-out, and none when the user prefers reduced motion. Every string that comes from data is escaped.
"""

from __future__ import annotations

from html import escape

import streamlit as st

INK, ACCENT, MUTED, BORDER = "#0F172A", "#0369A1", "#475569", "#E2E8F0"
GOOD, WARN, BAD, INFO = "#15803D", "#D97706", "#DC2626", "#0369A1"

CSS = f"""
<style>
:root {{
  --ink: {INK}; --accent: {ACCENT}; --muted: {MUTED}; --border: {BORDER};
  --good: {GOOD}; --warn: {WARN}; --bad: {BAD}; --surface: #FFFFFF; --soft: #F1F5F9;
  --ease: cubic-bezier(0.23, 1, 0.32, 1);
}}
.block-container {{ padding-top: 3.6rem; max-width: 1240px; }}
h1, h2, h3, h4 {{ letter-spacing: -0.015em; }}
.bs-eyebrow {{ font-size: 0.75rem; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--accent); margin-bottom: 0.25rem; }}
.bs-hero h1 {{ font-size: 1.9rem; margin: 0 0 0.35rem 0; }}
.bs-hero p {{ color: var(--muted); font-size: 1rem; margin: 0; max-width: 60ch; }}
.bs-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 0.75rem; padding: 1rem 1.1rem;
  transition: transform 160ms var(--ease), box-shadow 160ms var(--ease); }}
.bs-card:hover {{ transform: translateY(-1px); box-shadow: 0 6px 18px -10px rgba(15, 23, 42, 0.25); }}
.bs-kpi-label {{ color: var(--muted); font-size: 0.8rem; font-weight: 500; }}
.bs-kpi-value {{ font-size: 1.6rem; font-weight: 650; color: var(--ink); line-height: 1.25; margin-top: 0.2rem;
  font-variant-numeric: tabular-nums; }}
.bs-kpi-delta {{ font-size: 0.8rem; font-weight: 600; margin-top: 0.15rem; font-variant-numeric: tabular-nums; }}
.bs-gap {{ background: repeating-linear-gradient(-45deg, #F8FAFC, #F8FAFC 8px, #F1F5F9 8px, #F1F5F9 16px); }}
.bs-badge {{ display: inline-flex; align-items: center; gap: 0.35rem; font-size: 0.72rem; font-weight: 600;
  padding: 0.15rem 0.55rem; border-radius: 999px; border: 1px solid currentColor; letter-spacing: 0.02em; }}
.bs-dot {{ width: 0.5rem; height: 0.5rem; border-radius: 999px; display: inline-block; flex: none; }}
.bs-chip {{ font-family: "JetBrains Mono", ui-monospace, monospace; font-size: 0.7rem; color: var(--muted);
  background: var(--soft); border: 1px solid var(--border); border-radius: 0.35rem; padding: 0.05rem 0.4rem;
  margin-right: 0.25rem; white-space: nowrap; }}
.bs-verdict {{ display: flex; gap: 1rem; align-items: flex-start; border-left: 4px solid var(--accent);
  background: var(--surface); border-radius: 0.6rem; padding: 1rem 1.2rem; border-top: 1px solid var(--border);
  border-right: 1px solid var(--border); border-bottom: 1px solid var(--border); }}
.bs-verdict h3 {{ margin: 0; font-size: 1.15rem; }}
.bs-verdict p {{ margin: 0.3rem 0 0 0; color: var(--muted); }}
.bs-trail {{ position: relative; margin: 0.4rem 0 0 0; padding: 0; list-style: none; }}
.bs-trail li {{ position: relative; padding: 0 0 0.85rem 2.1rem; }}
.bs-trail li::before {{ content: attr(data-n); position: absolute; left: 0; top: 0; width: 1.45rem; height: 1.45rem;
  border-radius: 999px; background: var(--soft); border: 1px solid var(--border); color: var(--accent);
  font-size: 0.72rem; font-weight: 700; display: flex; align-items: center; justify-content: center; }}
.bs-trail li::after {{ content: ""; position: absolute; left: 0.7rem; top: 1.55rem; bottom: 0.1rem; width: 1px;
  background: var(--border); }}
.bs-trail li:last-child::after {{ display: none; }}
.bs-trail .f {{ color: var(--ink); font-size: 0.93rem; line-height: 1.45; }}
.bs-takeaway {{ border-radius: 0.75rem; padding: 1rem 1.2rem; background: linear-gradient(180deg, #F0F9FF, #FFFFFF);
  border: 1px solid #BAE6FD; color: var(--ink); font-size: 1rem; line-height: 1.55; }}
.bs-muted {{ color: var(--muted); font-size: 0.82rem; }}
.bs-step {{ display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap; margin: 0.2rem 0 0.8rem 0; }}
.bs-step span {{ font-size: 0.75rem; color: var(--muted); }}
.bs-step b {{ font-size: 0.75rem; color: var(--ink); background: var(--surface); border: 1px solid var(--border);
  border-radius: 999px; padding: 0.15rem 0.6rem; font-weight: 600; }}
.bs-step b.ai {{ color: var(--accent); border-color: #BAE6FD; background: #F0F9FF; }}
div[data-testid="stButton"] button {{ transition: transform 120ms var(--ease), background-color 120ms var(--ease); }}
div[data-testid="stButton"] button:active {{ transform: scale(0.98); }}
section[data-testid="stSidebar"] div[data-testid="stButton"] button {{ justify-content: flex-start; }}
section[data-testid="stSidebar"] div[data-testid="stButton"] button div,
section[data-testid="stSidebar"] div[data-testid="stButton"] button p {{ text-align: left; justify-content: flex-start;
  font-size: 0.85rem; width: 100%; }}
@media (prefers-reduced-motion: reduce) {{
  .bs-card, div[data-testid="stButton"] button {{ transition: none; }}
  .bs-card:hover {{ transform: none; }}
}}
</style>
"""

TONE = {"good": GOOD, "bad": BAD, "neutral": MUTED, "warn": WARN, "info": INFO}
SEVERITY = {"info": INFO, "warning": WARN, "blocker": BAD}
VERDICT_COLOUR = {
    "REUSE": GOOD,
    "EXTEND": ACCENT,
    "CONSOLIDATE": ACCENT,
    "CREATE": INK,
    "CLARIFY": WARN,
    "NOT_FEASIBLE": BAD,
}


def inject() -> None:
    st.html(CSS)


def html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def badge(text: str, colour: str = ACCENT) -> str:
    return (
        f'<span class="bs-badge" style="color:{colour}"><span class="bs-dot" style="background:{colour}"></span>'
        f"{escape(text)}</span>"
    )


def chips(ids: list[str]) -> str:
    return "".join(f'<span class="bs-chip">{escape(i)}</span>' for i in ids)


def hero(eyebrow: str, title: str, text: str) -> None:
    html(
        f'<div class="bs-hero"><div class="bs-eyebrow">{escape(eyebrow)}</div><h1>{escape(title)}</h1>'
        f"<p>{escape(text)}</p></div>"
    )


def pipeline_steps(steps: list[tuple[str, bool]]) -> None:
    """The flow as a row of pills; AI steps are tinted so it is visible where the model works."""
    parts = []
    for i, (label, ai) in enumerate(steps):
        if i:
            parts.append("<span>&rarr;</span>")
        parts.append(f'<b class="{"ai" if ai else ""}">{escape(label)}</b>')
    html('<div class="bs-step">' + "".join(parts) + "</div>")


def verdict_banner(verdict: str, title: str, text: str, extra: str = "") -> None:
    colour = VERDICT_COLOUR.get(verdict, ACCENT)
    html(
        f'<div class="bs-verdict" style="border-left-color:{colour}"><div>'
        f"{badge(verdict.replace('_', ' '), colour)}<h3 style='margin-top:0.45rem'>{escape(title)}</h3>"
        f"<p>{escape(text)}</p>{extra}</div></div>"
    )


def kpi_card(title: str, value: str, delta: str = "", tone: str = "neutral", note: str = "") -> str:
    colour = TONE.get(tone, MUTED)
    delta_html = f'<div class="bs-kpi-delta" style="color:{colour}">{escape(delta)}</div>' if delta else ""
    note_html = f'<div class="bs-muted" style="margin-top:0.3rem">{escape(note)}</div>' if note else ""
    return (
        f'<div class="bs-card"><div class="bs-kpi-label">{escape(title)}</div>'
        f'<div class="bs-kpi-value">{escape(value)}</div>{delta_html}{note_html}</div>'
    )


def gap_card(title: str, reason: str) -> str:
    return (
        f'<div class="bs-card bs-gap"><div class="bs-kpi-label">{escape(title)}</div>'
        f'<div class="bs-kpi-value" style="color:{MUTED};font-size:1.05rem">Not measured yet</div>'
        f'<div class="bs-muted" style="margin-top:0.3rem">{escape(reason)}</div></div>'
    )


def card_row(cards: list[str], per_row: int = 4) -> None:
    for start in range(0, len(cards), per_row):
        cols = st.columns(per_row)
        for col, markup in zip(cols, cards[start : start + per_row], strict=False):
            with col:
                html(markup)


def trail(steps: list[tuple[str, list[str]]]) -> str:
    items = "".join(
        f'<li data-n="{n}"><div class="f">{escape(finding)}</div>'
        f'<div style="margin-top:0.25rem">{chips(ids)}</div></li>'
        for n, (finding, ids) in enumerate(steps, 1)
    )
    return f'<ol class="bs-trail">{items}</ol>'


def takeaway(text: str) -> None:
    html(f'<div class="bs-eyebrow">AI takeaway</div><div class="bs-takeaway">{escape(text)}</div>')


def evidence_line(claim: str, severity: str, rule_id: str | None, ids: list[str], value: str | None) -> str:
    colour = SEVERITY.get(severity, MUTED)
    meta = " · ".join(x for x in (rule_id or "", value or "") if x)
    return (
        '<div style="display:flex;gap:0.6rem;align-items:flex-start;padding:0.45rem 0;'
        f'border-bottom:1px solid {BORDER}">'
        f'<span class="bs-dot" style="background:{colour};margin-top:0.45rem"></span><div>'
        f'<div style="font-size:0.92rem">{escape(claim)}</div>'
        f'<div class="bs-muted">{escape(meta)} {chips(ids)}</div></div></div>'
    )
