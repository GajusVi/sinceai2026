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

BLUE, GREY, GOOD, BAD = "#2a6ebb", "#9aa3ad", "#1f7a4d", "#b3382c"
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
class RenderedDashboard:
    title: str
    cards: list[CardView] = field(default_factory=list)
    gaps: list[GapView] = field(default_factory=list)
    figures: list[tuple[str, go.Figure]] = field(default_factory=list)
    tables: list[tuple[str, pd.DataFrame]] = field(default_factory=list)
    footer: list[tuple[str, str]] = field(default_factory=list)
    dq: list[str] = field(default_factory=list)
    filters: dict[str, str] = field(default_factory=dict)


def render(
    spec: DashboardSpec, frames: dict[str, pd.DataFrame], filters: dict[str, str] | None = None
) -> RenderedDashboard:
    """`filters` (product / market / region / month_from / month_to) override the spec's own filters."""
    effective = {**spec.filters, **(filters or {})}
    out = RenderedDashboard(title=spec.name, filters=effective)
    measures = {m.name: m for m in spec.measures}
    dq: list[str] = []
    for page in spec.pages:
        for v in page.visuals:
            ms = [measures[n] for n in v.measures if n in measures]
            if not ms:
                continue
            if v.type == "card":
                _card(out, v, ms[0], frames, effective, dq)
            elif v.type == "line" and ms[0].feasible:
                _line(out, v, ms[0], frames, effective, dq)
            elif v.type == "bar" and ms[0].feasible:
                _bar(out, v, ms[0], frames, effective, dq)
            elif v.type == "table" and ms[0].feasible:
                _table(out, v, ms[0], frames, effective, dq)
    out.dq = list(dict.fromkeys(dq))
    out.footer = _footer(spec)
    return out


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


def _line(out, v: Visual, m: Measure, frames, filters, dq) -> None:
    try:
        series = _series(m, frames, filters, dq)
    except ValueError:
        return
    fig = go.Figure(
        go.Scatter(x=series.index, y=series.values, mode="lines+markers", name=m.name, line=dict(color=BLUE))
    )
    if v.comparison == "forecast":
        fc = semantic.forecast(frames, filters, by="month").sort_values("month")
        fig.add_trace(
            go.Scatter(x=fc["month"], y=fc["value"], mode="lines", name="Forecast", line=dict(color=GREY, dash="dash"))
        )
    fig.update_layout(**_layout(v.title, m))
    out.figures.append((v.title, fig))


def _bar(out, v: Visual, m: Measure, frames, filters, dq) -> None:
    dim = v.dimension or "market"
    if m.kpi_id in semantic.ASSET_LEVEL_KPIS:
        return
    try:
        frame = semantic.compute(m, frames, filters, by=dim)
    except ValueError:
        return
    dq += frame.attrs.get("dq", [])
    frame = _labelled(frame, dim, frames).sort_values("value", ascending=True).tail(15)
    fig = go.Figure(go.Bar(x=frame["value"], y=frame["label"], orientation="h", marker_color=BLUE, name=m.name))
    fig.update_layout(**_layout(v.title, m, xaxis_title=m.unit))
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


def _layout(title: str, m: Measure, **extra) -> dict:
    return dict(
        title=dict(text=title, x=0, font=dict(size=15)),
        template="plotly_white",
        height=320,
        margin=dict(l=10, r=10, t=50, b=10),
        legend=dict(orientation="h", y=-0.15),
        yaxis_title=extra.pop("yaxis_title", m.unit),
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
