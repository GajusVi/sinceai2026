"""BI Steward design system for Streamlit: tokens and small HTML components (docs/steward/DESIGN.md).

Concept "the ruling": every request ends in one governed decision, typeset calmly. The look lives in
frontend/steward.css (injected once). Verdict colours appear only on the verdict; everything else is ink, grey and
one accent for primary actions. Every string that comes from data is escaped.
"""

from __future__ import annotations

from html import escape
from pathlib import Path

import streamlit as st

INK, ACCENT, MUTED, SURFACE = "#111111", "#1a4be0", "#6b6b6b", "#f4f4f4"
GOOD, WARN, BAD, INFO = "#15803d", "#b45309", "#b91c1c", "#1a4be0"

# The verdict word and its colour (spec.change_type MIGRATE / RESCUE override the verdict's word).
VERDICT_COLOUR = {
    "REUSE": GOOD,
    "EXTEND": ACCENT,
    "CONSOLIDATE": WARN,
    "MIGRATE": WARN,
    "CREATE": INK,
    "RESCUE": BAD,
    "CLARIFY": MUTED,
    "NOT_FEASIBLE": MUTED,
}
TONE = {"good": GOOD, "bad": BAD, "neutral": MUTED, "warn": WARN, "info": MUTED}
SEVERITY = {"info": MUTED, "warning": WARN, "blocker": BAD}

CSS_FILE = Path(__file__).with_name("steward.css")


def inject() -> None:
    st.html(f"<style>{CSS_FILE.read_text(encoding='utf-8')}</style>")


def html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def badge(text: str, colour: str = MUTED) -> str:
    return f'<span class="bs-badge" style="color:{colour}">{escape(text)}</span>'


def chips(ids: list[str]) -> str:
    return "".join(f'<span class="bs-chip">{escape(i)}</span>' for i in ids)


def ask_hero(question: str) -> None:
    html(f'<div class="bs-ask"><h1>{escape(question)}</h1></div>')


def message(role: str, text: str, new: bool = False, counter: str = "") -> str:
    who = "me" if role == "user" else "ai"
    count = f'<div class="bs-count">{escape(counter)}</div>' if counter else ""
    return f'<div class="bs-msg {who}{" new" if new else ""}">{count}{escape(text)}</div>'


def typing(label: str = "Thinking") -> str:
    """The AI is working: a pill with three pulsing dots (steward.css .bs-typing). Returned as HTML for a slot."""
    dots = '<span class="dots"><span></span><span></span><span></span></span>'
    return f'<div class="bs-typing">{dots}{escape(label)}</div>'


def section(title: str) -> None:
    html(f'<div class="bs-section">{escape(title)}</div>')


def ruling(headline: str, word: str, reason: str, ids: list[str] | None = None) -> None:
    """The headline sentence and the verdict strip, in one block (the strip fades in just after the headline)."""
    colour = VERDICT_COLOUR.get(word, INK)
    tail = f" {chips(ids)}" if ids else ""
    html(
        f'<div class="bs-ruling"><h1 class="bs-headline">{escape(headline)}</h1>'
        f'<div class="bs-verdict"><span class="w" style="color:{colour}">{escape(word.replace("_", " "))}</span>'
        f'<span class="r">{escape(reason)}</span>{tail}</div></div>'
    )


def lead(text: str) -> None:
    html(f'<p class="bs-lead">{escape(text)}</p>')


def why(sentences: list[str]) -> None:
    html('<div class="bs-why">' + "".join(f"<p>{escape(s)}</p>" for s in sentences if s) + "</div>")


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
        f'<div class="bs-kpi-value">Not measured yet</div>'
        f'<div class="bs-muted" style="margin-top:0.3rem">{escape(reason)}</div></div>'
    )


def card_row(cards: list[str], per_row: int = 4) -> None:
    for start in range(0, len(cards), per_row):
        cols = st.columns(per_row)
        for col, markup in zip(cols, cards[start : start + per_row], strict=False):
            with col:
                html(markup)


def skeleton(full: bool) -> None:
    """The building state: the result's shape in still fills, no spinner text."""
    if not full:
        html('<div class="bs-skel" style="height:1.4rem;width:46%;margin:0.4rem 0 1rem 0"></div>')
        return
    tiles = "".join('<div class="bs-skel" style="height:7.2rem"></div>' for _ in range(4))
    html(
        '<div style="margin-top:1.6rem"><div class="bs-skel" style="height:2.3rem;width:58%"></div>'
        '<div class="bs-skel" style="height:3rem;margin-top:0.9rem"></div>'
        f'<div class="bs-skel-row">{tiles}</div></div>'
    )


def trail(steps: list[tuple[str, list[str]]]) -> str:
    items = "".join(
        f'<li data-n="{n}"><div class="f">{escape(finding)}</div>'
        f'<div style="margin-top:0.25rem">{chips(ids)}</div></li>'
        for n, (finding, ids) in enumerate(steps, 1)
    )
    return f'<ol class="bs-trail">{items}</ol>'


def big_numbers(items: list[tuple[str, str]]) -> None:
    html(
        '<div class="bs-big">'
        + "".join(f"<div><b>{escape(v)}</b><span>{escape(t)}</span></div>" for v, t in items)
        + "</div>"
    )


def timeline(rows: list[tuple[str, str, str, str, str]]) -> None:
    """(time, request, verdict word, action, who) per decision, newest first."""
    items = "".join(
        f'<li><time>{escape(when)}</time><div><div class="q">{escape(question)}</div>'
        f'<div class="bs-muted"><span class="bs-badge" style="color:{VERDICT_COLOUR.get(verdict, INK)}">'
        f"{escape(verdict)}</span> · {escape(action)} by {escape(who)}</div></div></li>"
        for when, question, verdict, action, who in rows
    )
    html(f'<ol class="bs-tl">{items}</ol>')


def evidence_line(claim: str, severity: str, rule_id: str | None, ids: list[str], value: str | None) -> str:
    colour = SEVERITY.get(severity, MUTED)
    meta = " · ".join(x for x in (rule_id or "", value or "") if x)
    return (
        '<div style="display:flex;gap:0.6rem;align-items:flex-start;padding:0.45rem 0">'
        f'<span class="bs-dot" style="background:{colour};margin-top:0.5rem"></span><div>'
        f'<div style="font-size:0.92rem">{escape(claim)}</div>'
        f'<div class="bs-muted">{escape(meta)} {chips(ids)}</div></div></div>'
    )
