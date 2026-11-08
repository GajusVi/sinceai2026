"""BI Steward design system for Streamlit: tokens and small HTML components (docs/steward/DESIGN.md).

Dark, dense, one surface with the login globe: zinc panels, 1 px lines, mono for numbers and ids. The look lives in
frontend/steward.css (injected once); these tokens mirror it and .streamlit/config.toml. Verdict colours appear only on
the verdict and are tuned for the dark panel (contrast >= 4.5:1 on #111114). Every string from data is escaped.
"""

from __future__ import annotations

from html import escape
from pathlib import Path

import streamlit as st

# Colours are CSS variables, so day / night is one switch in CSS (steward.css: night, plus a day block).
# Hex values per theme and their contrast: docs/steward/DESIGN.md.
BG, PANEL, RAISED, LINE = "var(--bg)", "var(--panel)", "var(--raised)", "var(--line)"
INK, MUTED, FAINT = "var(--ink)", "var(--muted)", "var(--faint)"
ACCENT, FOCUS, ACCENT_TEXT = "var(--accent)", "var(--focus)", "var(--accent-text)"
SURFACE = RAISED
GOOD, WARN, BAD, INFO = "var(--reuse)", "var(--amber)", "var(--rescue)", "var(--extend)"

# The verdict word and its colour (spec.change_type MIGRATE / RESCUE override the verdict's word).
VERDICT_COLOUR = {
    "REUSE": GOOD,
    "EXTEND": ACCENT_TEXT,
    "CONSOLIDATE": WARN,
    "MIGRATE": WARN,
    "CREATE": INK,
    "RESCUE": BAD,
    "CLARIFY": "var(--grey)",
    "NOT_FEASIBLE": "var(--grey)",
}
TONE = {"good": GOOD, "bad": BAD, "neutral": MUTED, "warn": WARN, "info": MUTED}
SEVERITY = {"info": MUTED, "warning": WARN, "blocker": BAD}

CSS_FILE = Path(__file__).with_name("steward.css")


def theme() -> str:
    """'night' (default) or 'day'. Starts from ?theme= (the desktop login hands its choice over), then the toggle."""
    if "bs_day" not in st.session_state:
        st.session_state.bs_day = st.query_params.get("theme") == "day"
    return "day" if st.session_state.bs_day else "night"


def inject() -> None:
    """The stylesheet for the current theme, and the day / night toggle at the bottom of the sidebar.
    Streamlit 1.67 has no runtime theme API (st.context.theme is read-only), so the switch is CSS variables."""
    marker = '<div class="bs-day"></div>' if theme() == "day" else ""  # steward.css scopes the day tokens on it
    st.html(f"<style>{CSS_FILE.read_text(encoding='utf-8')}</style>{marker}")
    with st.sidebar.container(key="bs-theme"):  # moved to the bottom of the sidebar by steward.css (order)
        st.toggle("Day theme", key="bs_day")


# Table cells per theme (st.dataframe draws on a canvas: CSS cannot reach it, a pandas Styler can).
TABLE = {
    "night": {"background-color": "#111114", "color": "#fafafa", "border-color": "#27272a"},
    "day": {"background-color": "#ffffff", "color": "#09090b", "border-color": "#e4e4e7"},
}


def table(data, **kwargs):
    """st.dataframe in the current theme. Cells take our tokens through a pandas Styler; sorting, search and download
    still work (they act on the underlying data). Header row and toolbar keep Streamlit's own (config.toml) theme:
    a Styler cannot reach them (checked 8 Nov: Styler table_styles for th are sent but the grid ignores them). Floats are shown as plain numbers (Styler would print 6 decimals); column_config
    formatting still wins. Every other st.dataframe argument passes through."""
    import pandas as pd

    df = data if isinstance(data, pd.DataFrame) else pd.DataFrame(data)
    styler = df.style.set_properties(**TABLE[theme()])
    floats = [c for c in df.columns if pd.api.types.is_float_dtype(df[c])]
    if floats:
        styler = styler.format(lambda v: "" if pd.isna(v) else f"{v:,.10g}", subset=floats)
    return st.dataframe(styler, **kwargs)


def html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def badge(text: str, colour: str = MUTED) -> str:
    return f'<span class="bs-badge" style="color:{colour}">{escape(text)}</span>'


def chips(ids: list[str]) -> str:
    return "".join(f'<span class="bs-chip">{escape(i)}</span>' for i in ids)


def ask_hero(question: str) -> None:
    html(f'<div class="bs-ask"><h1>{escape(question)}</h1></div>')


def message(role: str, text: str, new: bool = False, counter: str = "") -> str:
    """One conversation row: a small mono speaker label, then the text (rows join into one panel in steward.css)."""
    who = "me" if role == "user" else "ai"
    label = "You" if role == "user" else "Steward"
    count = f'<div class="bs-count">{escape(counter)}</div>' if counter else ""
    return (f'<div class="bs-msg {who}{" new" if new else ""}"><span class="who">{label}</span>'
            f'<div class="t">{count}{escape(text)}</div></div>')


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
        f'<div class="bs-verdict" style="border-left-color:{colour}">'
        f'<span class="w" style="color:{colour}">{escape(word.replace("_", " "))}</span>'
        f'<span class="r">{escape(reason)}</span>{tail}</div></div>'
    )


def lead(text: str) -> None:
    html(f'<p class="bs-lead">{escape(text)}</p>')


def why(sentences: list[str]) -> None:
    html('<div class="bs-why">' + "".join(f"<p>{escape(s)}</p>" for s in sentences if s) + "</div>")


def kpi_card(title: str, value: str, delta: str = "", tone: str = "neutral", note: str = "") -> str:
    """Tremor-like card. The arrow follows the sign of the delta; the colour follows the tone that render.py set
    (good / bad), so a falling number is only red when it is bad for the business; neutral stays grey."""
    colour = TONE.get(tone, MUTED)
    arrow = {"+": "\u25b2 ", "-": "\u25bc ", "\u2212": "\u25bc "}.get(delta.strip()[:1], "") if delta else ""
    delta_html = f'<div class="bs-kpi-delta" style="color:{colour}">{arrow}{escape(delta)}</div>' if delta else ""
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


# -- OVERVIEW dashboards (render.RenderedDashboard.archetype == "OVERVIEW"): header band, status tiles, 12-column grid ----
STATUS = {"ok": ("var(--reuse)", "OK"), "warn": ("var(--amber)", "WATCH"), "breach": ("var(--rescue)", "BREACH"),
          "neutral": ("var(--line)", ""), "gap": ("var(--grey)", "NO DATA")}


def header_band(title: str, scope: str, as_of: str, verdict: str) -> None:
    colour = VERDICT_COLOUR.get(verdict, INK)
    word = f'<span class="w" style="color:{colour}">{escape(verdict.replace("_", " "))}</span>' if verdict else ""
    html(
        f'<div class="bs-band"><div><div class="bs-band-title">{escape(title)}</div>'
        f'<div class="bs-band-meta">{escape(scope)} · data as of {escape(as_of)}</div></div>{word}</div>'
    )


def tiles(items) -> str:
    """The KPI strip: one tile per measure, a 3 px status edge and a mono status word (only where a governed threshold
    exists); neutral tiles get no colour; a gap tile says 'Not measured yet' and why."""
    out = []
    for t in items:
        colour, word = STATUS.get(t.status, STATUS["neutral"])
        arrow = {"+": "\u25b2 ", "-": "\u25bc "}.get((t.delta or " ").strip()[:1], "") if t.delta else ""
        delta = (f'<div class="bs-kpi-delta" style="color:{TONE.get(t.tone, MUTED)}">{arrow}{escape(t.delta)}</div>'
                 if t.delta else "")
        status = f'<span class="bs-tile-status" style="color:{colour}">{word}</span>' if word else ""
        note = f'<div class="bs-muted" style="margin-top:0.25rem">{escape(t.note)}</div>' if t.note else ""
        out.append(
            f'<div class="bs-tile bs-{escape(t.status)}" style="border-left-color:{colour}">'
            f'<div class="bs-kpi-label">{escape(t.title)}{status}</div>'
            f'<div class="bs-kpi-value">{escape(t.value)}</div>{delta}{note}</div>'
        )
    return '<div class="bs-tiles">' + "".join(out) + "</div>"


def overview(dash, key: str, scope: str = "", as_of: str = "", verdict: str = "") -> None:
    """Draw an OVERVIEW dashboard: header band, then the grid rows in order (strip, charts, table), each cell its span
    of 12 columns. Charts keep render.py's own day/night template (theme=None)."""
    header_band(dash.title, scope, as_of, "")  # the verdict chip is already in the verdict bar above (V6)
    rows: dict[int, list] = {}
    for cell in dash.grid:
        rows.setdefault(cell.row, []).append(cell)
    for r in sorted(rows):
        cells = rows[r]
        cols = st.columns([c.span for c in cells]) if len(cells) > 1 else [st.container()]
        for col, cell in zip(cols, cells, strict=True):
            with col:
                if cell.kind == "strip":
                    html(tiles(dash.tiles))
                elif cell.kind == "figure":
                    st.plotly_chart(dash.figures[cell.index][1], use_container_width=True, theme=None,
                                    key=f"ov_{key}_{r}_{cell.index}")
                elif cell.kind == "table":
                    title, frame = dash.tables[cell.index]
                    section(title)
                    if frame.empty:
                        st.caption("No rows past the threshold for this selection.")
                    else:
                        table(frame, hide_index=True, width="content")  # value next to its label (V7)
