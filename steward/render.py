"""Renderer (W7): DashboardSpec + governed data + filters -> RenderedDashboard. Deterministic, Plotly only, no LLM.

NIGHT draft by Gajus (Sat 7 Nov); back to Donatas at 08:00. Rules baked in:
- a measure with feasible=False is a gap card (grey, with its reason) and is NEVER computed (DATA rule);
- every figure comes from steward.semantic.compute on the synthetic data pack, and the footer says so;
- cards: a "forecast" comparison shows the period total against the forecast, a "prior_month" comparison shows the
  latest month against the month before. No comparison = the value over the selected period.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
import plotly.graph_objects as go

from . import semantic
from .spec import DashboardSpec, Measure, Visual

# Chart templates (docs/steward/DESIGN.md, same tokens as frontend/ui.py and steward.css). Night: actual in the focus
# blue on the dark panel; day: the accent blue on white. Transparent ground so a chart sits on its panel. Fixed values
# only: the same spec + the same theme gives the same figure.
TEMPLATES = {
    "night": dict(actual="#3b6bff", forecast="#a1a1aa", grid="#27272a", axis="#a1a1aa", title="#fafafa",
                  good="#4ade80", bad="#f87171", warn="#fbbf24",
                  parts=["#3b6bff", "#6b8cff", "#9db4ff", "#c7d2fe", "#52525b"]),
    "day": dict(actual="#1a4be0", forecast="#71717a", grid="#e4e4e7", axis="#52525b", title="#09090b",
                good="#15803d", bad="#b91c1c", warn="#b45309",
                parts=["#1a4be0", "#4f73e8", "#8aa2f0", "#c7d2fe", "#a1a1aa"]),
}
BLUE, GREY = TEMPLATES["night"]["actual"], TEMPLATES["night"]["forecast"]
GOOD, BAD = "#4ade80", "#f87171"
MONO = "Geist Mono, ui-monospace, SF Mono, Menlo, Consolas, monospace"
SANS = "Instrument Sans, -apple-system, Segoe UI, sans-serif"
DIM_LABEL_COLUMN = {"market": "market_id", "product": "product_name", "region": "region"}


@dataclass
class CardView:
    title: str
    kpi_id: str
    value: str
    comparison: str = ""  # "+3.1% vs forecast"
    tone: str = "neutral"  # good | bad | neutral
    note: str = ""


@dataclass
class GapView:
    title: str
    kpi_id: str
    name: str
    reason: str


@dataclass
class TileView:
    """One status tile of an OVERVIEW KPI strip. status: ok | warn | breach (only where a governed threshold exists)
    | neutral (no governed threshold: no colour is invented) | gap (governed KPI without source data)."""

    title: str
    kpi_id: str
    value: str
    delta: str = ""
    tone: str = "neutral"
    status: str = "neutral"
    note: str = ""


@dataclass
class GridCell:
    """Where one rendered visual sits on the 12-column OVERVIEW grid. kind: strip | figure | table; index points into
    RenderedDashboard.figures / .tables (the strip is RenderedDashboard.tiles)."""

    row: int
    span: int
    kind: str
    index: int = 0
    title: str = ""


@dataclass
class RenderedDashboard:
    title: str
    cards: list[CardView] = field(default_factory=list)
    gaps: list[GapView] = field(default_factory=list)
    figures: list[tuple[str, go.Figure]] = field(default_factory=list)
    tables: list[tuple[str, pd.DataFrame]] = field(default_factory=list)
    footer: list[tuple[str, str]] = field(default_factory=list)
    dq: list[str] = field(default_factory=list)
    filters: dict[str, str] = field(default_factory=dict)
    archetype: str = ""  # "" = today's template (cards row + charts); "OVERVIEW" = the grid below
    tiles: list[TileView] = field(default_factory=list)
    grid: list[GridCell] = field(default_factory=list)


def render(
    spec: DashboardSpec, frames: dict[str, pd.DataFrame], filters: dict[str, str] | None = None, theme: str = "night"
) -> RenderedDashboard:
    """`filters` (product / market / region / month_from / month_to) override the spec's own filters.
    `theme` ('night' default, or 'day') picks the chart template; the numbers never depend on it."""
    pal = TEMPLATES.get(theme, TEMPLATES["night"])
    effective = {**spec.filters, **(filters or {})}
    out = RenderedDashboard(title=spec.name, filters=effective, archetype=getattr(spec, "archetype", "") or "")
    measures = {m.name: m for m in spec.measures}
    dq: list[str] = []
    for page in spec.pages:
        for v in page.visuals:
            ms = [measures[n] for n in v.measures if n in measures]
            if not ms:
                continue
            before = (len(out.figures), len(out.tables), len(out.tiles))
            if v.type == "kpi_strip":
                _strip(out, ms, frames, effective, dq)
            elif v.type == "bullet" and ms[0].feasible:
                _bullet(out, v, ms[0], frames, effective, dq, pal)
            elif v.type == "diverging_bar" and ms[0].feasible:
                _diverging(out, v, ms[0], frames, effective, dq, pal)
            elif v.type == "stacked_100" and ms[0].feasible:
                _stacked(out, v, ms[0], frames, effective, dq, pal)
            elif v.type == "card":
                _card(out, v, ms[0], frames, effective, dq)
            elif v.type == "line" and ms[0].feasible:
                _line(out, v, ms[0], frames, effective, dq, pal)
            elif v.type == "bar" and ms[0].feasible:
                _bar(out, v, ms[0], frames, effective, dq, pal)
            elif v.type == "table" and ms[0].feasible:
                _table(out, v, ms[0], frames, effective, dq)
            _place(out, v, before, dq)
    out.dq = list(dict.fromkeys(dq))
    out.footer = _footer(spec)
    return out


# -- OVERVIEW: grid placement, status tiles, bullet / diverging / 100% charts --------------------------------------


def _place(out: RenderedDashboard, v: Visual, before: tuple[int, int, int], dq: list[str]) -> None:
    """Record grid position for visuals that carry one (OVERVIEW). A visual that drew nothing gets no cell, and says so."""
    span, row = getattr(v, "span", None), getattr(v, "row", None)
    if not span:
        return
    figures, tables, tiles = before
    if len(out.tiles) > tiles:
        out.grid.append(GridCell(row or 1, span, "strip", tiles, v.title))
    elif len(out.figures) > figures:
        out.grid.append(GridCell(row or 1, span, "figure", figures, v.title))
    elif len(out.tables) > tables:
        out.grid.append(GridCell(row or 1, span, "table", tables, v.title))
    else:
        dq.append(f'"{v.title}" was not drawn: no data for this selection')


def _thresholds() -> tuple[dict[str, float], float]:
    """Governed thresholds, one source: specbuild.EXCEPTIONS. Floors (below = breach) and the forecast band (+/- %)."""
    from .specbuild import EXCEPTIONS

    floors = {k: EXCEPTIONS[k][0] for k in ("KPI-020", "KPI-016") if k in EXCEPTIONS}
    return floors, EXCEPTIONS.get("KPI-042", (10.0, ""))[0]


def _status(kpi_id: str, value: float | None, pct_off: float | None) -> str:
    floors, band = _thresholds()
    if kpi_id in floors and value is not None:
        floor = floors[kpi_id]
        return "breach" if value < floor else "warn" if value < floor * 1.05 else "ok"
    if kpi_id == "KPI-042" and pct_off is not None:
        return "breach" if abs(pct_off) > band else "warn" if abs(pct_off) > band * 0.75 else "ok"
    return "neutral"


def _strip(out: RenderedDashboard, ms: list[Measure], frames, filters, dq) -> None:
    from .specbuild import COMPARED_TO_FORECAST

    for m in ms[:8]:
        title = m.name
        if not m.feasible:  # a gap is a labelled tile, never a number
            out.tiles.append(TileView(title, m.kpi_id, "Not measured yet", status="gap", note=m.gap_reason))
            continue
        monthly = semantic.grain_of(m.kpi_id) == "month"
        comparison = "forecast" if m.kpi_id in COMPARED_TO_FORECAST else ("prior_month" if monthly else None)
        probe = Visual(type="card", title=title, measures=[m.name], comparison=comparison)
        try:
            value, delta, tone = _card_numbers(probe, m, frames, filters, dq)
            raw, pct = _raw(m, comparison, frames, filters, dq)
        except ValueError as e:
            out.tiles.append(TileView(title, m.kpi_id, "n/a", note=str(e)))
            continue
        out.tiles.append(TileView(title, m.kpi_id, value, delta, tone, _status(m.kpi_id, raw, pct)))


def _raw(m: Measure, comparison: str | None, frames, filters, dq) -> tuple[float | None, float | None]:
    """The number the status is judged on: the latest month for monthly KPIs, else the period value; % off forecast."""
    if comparison == "prior_month":
        series = _series(m, frames, filters, dq)
        return (float(series.iloc[-1]) if len(series) else None), None
    total = _one(m, frames, filters, dq)
    if m.kpi_id == "KPI-042":
        fc = float(semantic.forecast(frames, filters, exclude_zero=True)["value"].iloc[0])
        return total, (total / fc * 100 if fc else None)
    return total, None


def _by(m: Measure, dim: str, frames, filters, dq) -> pd.DataFrame:
    frame = semantic.compute(m, frames, filters, by=dim)
    dq += frame.attrs.get("dq", [])
    return _labelled(frame, dim, frames)


def _bullet(out, v: Visual, m: Measure, frames, filters, dq, pal: dict = TEMPLATES["night"]) -> None:
    """A rate against its governed target, per member: a bar to the value, coloured by status, and the target line."""
    dim, target = v.dimension or "product", v.threshold
    try:
        frame = _by(m, dim, frames, filters, dq).sort_values("value", ascending=True).tail(12)
    except ValueError:
        return
    colours = [pal[{"breach": "bad", "warn": "warn"}.get(_status(m.kpi_id, x, None), "actual")] for x in frame["value"]]
    fig = go.Figure(go.Bar(x=frame["value"], y=frame["label"], orientation="h", marker_color=colours, name=m.name))
    if target is not None:
        fig.add_vline(x=target, line=dict(color=pal["title"], width=1.5, dash="dot"),
                      annotation=dict(text=f"target {target:g}", font=dict(family=MONO, size=10, color=pal["axis"])))
    fig.update_layout(**_layout(v.title, m, pal, xaxis_title=m.unit), showlegend=False)
    out.figures.append((v.title, fig))


def _diverging(out, v: Visual, m: Measure, frames, filters, dq, pal: dict = TEMPLATES["night"]) -> None:
    """A variance per member around zero: above in the good colour, below in the bad one, worst first."""
    dim = v.dimension or "market"
    try:
        frame = _by(m, dim, frames, filters, dq)
    except ValueError:
        return
    frame = frame.reindex(frame["value"].abs().sort_values().index).tail(12)
    colours = [pal["good"] if x >= 0 else pal["bad"] for x in frame["value"]]
    fig = go.Figure(go.Bar(x=frame["value"], y=frame["label"], orientation="h", marker_color=colours, name=m.name))
    fig.add_vline(x=0, line=dict(color=pal["axis"], width=1))
    fig.update_layout(**_layout(v.title, m, pal, xaxis_title=m.unit), showlegend=False)
    out.figures.append((v.title, fig))


def _stacked(out, v: Visual, m: Measure, frames, filters, dq, pal: dict = TEMPLATES["night"]) -> None:
    """Share of the total in one 100% bar, only for 5 parts or fewer (never a pie); more parts become a ranked bar."""
    dim = v.dimension or "region"
    try:
        frame = _by(m, dim, frames, filters, dq).sort_values("value", ascending=False)
    except ValueError:
        return
    total = float(frame["value"].sum())
    if len(frame) > 5 or total <= 0 or (frame["value"] < 0).any():
        _bar(out, v.model_copy(update={"dimension": dim}), m, frames, filters, dq, pal)
        return
    fig = go.Figure()
    for i, (label, value) in enumerate(zip(frame["label"], frame["value"], strict=True)):
        share = value / total * 100
        fig.add_trace(go.Bar(x=[share], y=[""], orientation="h", name=str(label), marker_color=pal["parts"][i],
                             text=[f"{label} {share:.0f}%"], textposition="inside", insidetextanchor="middle",
                             textfont=dict(family=MONO, size=11, color="#ffffff" if i < 2 else pal["title"])))
    fig.update_layout(**{**_layout(v.title, m, pal, xaxis_title="% of total"), "height": 180}, barmode="stack")
    fig.update_xaxes(range=[0, 100])
    out.figures.append((v.title, fig))


# -- cards ---------------------------------------------------------------------------------------------------------


def _card(out: RenderedDashboard, v: Visual, m: Measure, frames, filters, dq) -> None:
    if not m.feasible:  # a gap is never a number
        out.gaps.append(GapView(v.title, m.kpi_id, m.name, m.gap_reason))
        return
    try:
        value, comparison, tone = _card_numbers(v, m, frames, filters, dq)
    except ValueError as e:
        out.cards.append(CardView(v.title, m.kpi_id, "n/a", note=str(e)))
        return
    out.cards.append(CardView(v.title, m.kpi_id, value, comparison, tone))


def _card_numbers(v: Visual, m: Measure, frames, filters, dq) -> tuple[str, str, str]:
    if v.comparison == "forecast":
        total = _one(m, frames, filters, dq)
        exclude = m.kpi_id == "KPI-042"
        fc = float(semantic.forecast(frames, filters, exclude_zero=exclude)["value"].iloc[0])
        if m.kpi_id == "KPI-042":  # the value IS the gap to forecast
            pct = total / fc * 100 if fc else float("nan")
            return semantic.display(m.kpi_id, total), f"{pct:+.1f}% of forecast", "good" if total >= 0 else "bad"
        delta = total - fc
        pct = delta / fc * 100 if fc else float("nan")
        return semantic.display(m.kpi_id, total), f"{pct:+.1f}% vs forecast", "good" if delta >= 0 else "bad"
    if v.comparison == "prior_month":
        series = _series(m, frames, filters, dq)
        if len(series) >= 2:
            last, before = float(series.iloc[-1]), float(series.iloc[-2])
            delta = last - before
            text = (
                f"{delta * 100:+.1f} pp vs last month"
                if semantic.is_fraction(m.kpi_id)
                else f"{delta:+,.1f} vs last month"
            )
            return semantic.display(m.kpi_id, last), text, "neutral"
    return semantic.display(m.kpi_id, _one(m, frames, filters, dq)), "", "neutral"


def _one(m: Measure, frames, filters, dq) -> float:
    frame = semantic.compute(m, frames, filters)
    dq += frame.attrs.get("dq", [])
    if frame.empty:
        raise ValueError("no data for this selection")
    return float(frame["value"].iloc[0])


def _series(m: Measure, frames, filters, dq) -> pd.Series:
    frame = semantic.compute(m, frames, filters, by="month")
    dq += frame.attrs.get("dq", [])
    return frame.sort_values("month").set_index("month")["value"]


# -- figures and tables --------------------------------------------------------------------------------------------


def _line(out, v: Visual, m: Measure, frames, filters, dq, pal: dict = TEMPLATES["night"]) -> None:
    try:
        series = _series(m, frames, filters, dq)
    except ValueError:
        return
    fig = go.Figure(
        go.Scatter(x=series.index, y=series.values, mode="lines+markers", name=m.name, line=dict(color=pal["actual"]))
    )
    if v.comparison == "forecast":
        fc = semantic.forecast(frames, filters, by="month").sort_values("month")
        fig.add_trace(
            go.Scatter(x=fc["month"], y=fc["value"], mode="lines", name="Forecast", line=dict(color=pal["forecast"], dash="dash"))
        )
    fig.update_layout(**_layout(v.title, m, pal))
    out.figures.append((v.title, fig))


def _bar(out, v: Visual, m: Measure, frames, filters, dq, pal: dict = TEMPLATES["night"]) -> None:
    dim = v.dimension or "market"
    if m.kpi_id in semantic.ASSET_LEVEL_KPIS:
        return
    try:
        frame = semantic.compute(m, frames, filters, by=dim)
    except ValueError:
        return
    dq += frame.attrs.get("dq", [])
    frame = _labelled(frame, dim, frames).sort_values("value", ascending=True).tail(15)
    fig = go.Figure(go.Bar(x=frame["value"], y=frame["label"], orientation="h", marker_color=pal["actual"], name=m.name))
    fig.update_layout(**_layout(v.title, m, pal, xaxis_title=m.unit))
    out.figures.append((v.title, fig))


def _table(out, v: Visual, m: Measure, frames, filters, dq) -> None:
    dim, threshold = v.dimension or "market", v.threshold or 0.0
    try:
        if m.kpi_id == "KPI-042":  # |variance| as % of forecast above the threshold, worst first
            var = semantic.compute(m, frames, filters, by=dim)
            fc = semantic.forecast(frames, filters, by=dim, exclude_zero=True)
            key = var.columns[0]
            joined = var.merge(fc, on=key, suffixes=("", "_fc"))
            joined["pct"] = joined["value"] / joined["value_fc"] * 100
            rows = joined[joined["pct"].abs() > threshold].sort_values("pct", key=abs, ascending=False)
            rows = _labelled(rows.rename(columns={"value": "variance"}), dim, frames, value_col="variance")
            table = pd.DataFrame(
                {
                    _dim_title(dim): rows["label"],
                    "Variance (EUR M)": rows["variance"].round(1),
                    "Off forecast (%)": rows["pct"].round(1),
                }
            )
        else:  # OTIF / inventory: below the threshold, lowest first
            frame = semantic.compute(m, frames, filters, by=dim)
            dq += frame.attrs.get("dq", [])
            rows = _labelled(frame, dim, frames)
            rows = rows[rows["value"] < threshold].sort_values("value")
            table = pd.DataFrame({_dim_title(dim): rows["label"], m.name: rows["value"].round(1)})
    except ValueError:
        return
    out.tables.append((v.title, table.reset_index(drop=True)))


def _labelled(frame: pd.DataFrame, dim: str, frames, value_col: str = "value") -> pd.DataFrame:
    """Add a readable label column: market names instead of market ids."""
    frame = frame.copy()
    key = DIM_LABEL_COLUMN[dim]
    if dim == "market":
        names = frames["dim_market"].set_index("market_id")["market_name"]
        frame["label"] = frame[key].map(names).fillna(frame[key])
    else:
        frame["label"] = frame[key]
    return frame


def _dim_title(dim: str) -> str:
    return {"market": "Country", "product": "Product", "region": "Region"}[dim]


def _layout(title: str, m: Measure, pal: dict, **extra) -> dict:
    grid, ax = pal["grid"], pal["axis"]
    axis = dict(gridcolor=grid, zerolinecolor=grid, linecolor=grid, tickfont=dict(family=MONO, size=11, color=ax),
                title=dict(font=dict(family=MONO, size=11, color=ax)))
    return dict(
        title=dict(text=title, x=0, font=dict(family=SANS, size=14, color=pal["title"])),
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=SANS, size=12, color=ax),
        height=300,
        margin=dict(l=10, r=10, t=44, b=22),
        legend=dict(orientation="h", y=-0.15, font=dict(family=MONO, size=11, color=ax)),
        xaxis=axis,
        yaxis={**axis, "title": dict(text=extra.pop("yaxis_title", m.unit), font=dict(family=MONO, size=11, color=ax))},
        **extra,
    )


# -- governance footer -----------------------------------------------------------------------------------------------


def _model_line(model_id: str, model: dict) -> str:
    if not model:
        return model_id or "none set"
    return f"{model_id}: endorsement {model.get('endorsement', '?')}, refresh {model.get('refresh_status', '?')}"


def _footer(spec: DashboardSpec) -> list[tuple[str, str]]:
    kpis = "; ".join(
        f"{m.kpi_id} {m.name} ({m.definition_status})" + ("" if m.feasible else " - no source data")
        for m in spec.measures
    )
    model = semantic.model_info(spec.source_model_id)
    owner = semantic.owner_info(spec.owner_id)
    return [
        ("KPIs", kpis),
        ("Source model", _model_line(spec.source_model_id, model)),
        (
            "Owner",
            f"{spec.owner_id} {owner.get('owner_name', '')} ({owner.get('status', '?')})"
            if spec.owner_id
            else "No owner: a human must assign one before approval",
        ),
        (
            "Version",
            f"v{spec.version} ({spec.change_type})"
            + (f", based on {', '.join(spec.base_asset_ids)}" if spec.base_asset_ids else ""),
        ),
        ("Data", spec.data_label),
    ]
