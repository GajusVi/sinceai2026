"""Weighted 16:9 dashboard layouts (asymmetric, enterprise style).

A layout is a tree. Containers split their rectangle by weight (row = left to right, col = top to bottom); leaves are
slots: "chart", "kpi" or "table". compose.py pours a RenderedDashboard into the slots: the biggest slot gets the most
important chart, slots without content are pruned and their space flows to the neighbours.

Nothing here is symmetric on purpose: a hero chart takes 55-70% of its band, small charts are 1/3 of it, and the
KPI strip is either a thin band or a narrow rail. `p` carries the knobs the sweep varies (the "rules").
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


def row(*kids, w=1.0):
    return {"t": "row", "w": w, "k": list(kids)}


def col(*kids, w=1.0):
    return {"t": "col", "w": w, "k": list(kids)}


def chart(w=1.0):
    return {"t": "chart", "w": w}


def kpi(w=1.0):
    return {"t": "kpi", "w": w}


def table(w=1.0):
    return {"t": "table", "w": w}


@dataclass(frozen=True)
class Preset:
    name: str
    roles: tuple[str, ...]  # who it suits: worker (glance) | management | builder (full story)
    build: Callable[[dict], dict]
    note: str


def _mirror(node):
    """Flip every row left-right (hero on the right)."""
    if "k" not in node:
        return node
    kids = [_mirror(k) for k in node["k"]]
    return {**node, "k": kids[::-1] if node["t"] == "row" else kids}


def hero_left_stack(p):
    h = p["hero"]
    return col(
        kpi(p["kpi_band"]),
        row(chart(h), col(chart(1), chart(1), w=1 - h), w=6),
        row(chart(3), chart(3), table(4), w=4),
    )


def kpi_rail_left(p):
    h = p["hero"]
    return row(
        kpi(2.0),
        col(
            row(chart(h), chart(1 - h), w=6),
            row(chart(5), chart(4), chart(3), w=4),
            table(2.4),
            w=10,
        ),
    )


def hero_top_full(p):
    return col(
        kpi(p["kpi_band"]),
        chart(6.5),
        row(chart(5), chart(4), table(4.5), w=4),
    )


def golden_two_col(p):
    return row(
        col(kpi(p["kpi_band"]), chart(5), chart(4), w=61.8),
        col(chart(4), table(4), chart(3), w=38.2),
    )


def triptych(p):
    return row(
        col(kpi(3.5), chart(2), w=3),
        col(chart(6), chart(3), w=6),
        col(table(5), chart(3), w=3),
    )


def kpi_band_mid(p):
    return col(
        chart(5.5),
        kpi(p["kpi_band"] * 1.1),
        row(chart(4), chart(3), chart(3), table(4), w=3.6),
    )


def mosaic_5_4_3(p):
    return col(
        kpi(p["kpi_band"]),
        row(chart(3), chart(6), chart(3), w=5),
        row(chart(6), chart(3), table(3), w=4),
    )


def table_right_rail(p):
    h = p["hero"]
    return row(
        col(kpi(p["kpi_band"]), row(chart(h), chart(1 - h), w=6), row(chart(1), chart(1), w=3.4), w=8),
        col(table(6), chart(3), w=4),
    )


def worker_glance_left(p):
    return row(col(kpi(1), w=3.4), col(chart(1), w=6.6))


def worker_glance_top(p):
    return col(kpi(2.2), row(chart(p["hero"]), chart(1 - p["hero"]), w=7.8))


def worker_golden(p):
    return row(col(kpi(1.0), w=38.2), col(chart(1.0), w=61.8))


PRESETS: list[Preset] = [
    Preset("hero_left_stack", ("management", "builder"), hero_left_stack, "KPI band; hero chart 8/12 beside two stacked; 3-up row"),
    Preset("kpi_rail_left", ("management", "builder"), kpi_rail_left, "narrow KPI rail; hero + side; 5/4/3 row; table"),
    Preset("hero_top_full", ("management", "builder"), hero_top_full, "KPI band; full-width hero; 5/4 + table"),
    Preset("golden_two_col", ("management", "builder"), golden_two_col, "61.8 / 38.2 columns"),
    Preset("triptych", ("builder",), triptych, "3/6/3 columns: KPIs | story | exceptions"),
    Preset("kpi_band_mid", ("management", "builder"), kpi_band_mid, "hero first, KPI band in the middle, detail row"),
    Preset("mosaic_5_4_3", ("management", "builder"), mosaic_5_4_3, "3/6/3 then 6/3/3 mosaic"),
    Preset("table_right_rail", ("builder",), table_right_rail, "exceptions table as a right rail"),
    Preset("worker_glance_left", ("worker",), worker_glance_left, "big numbers left, one trend right"),
    Preset("worker_glance_top", ("worker",), worker_glance_top, "numbers on top, trend below"),
    Preset("worker_golden", ("worker",), worker_golden, "numbers 38% | trend 62%"),
]
def baseline_equal(p):
    """What the app draws today (specbuild._overview_page): equal spans, same heights. Reference only, never swept."""
    return col(kpi(1), row(chart(), chart(), chart(), w=3), row(chart(), chart(), chart(), w=3), table(2))


BASELINE = Preset("baseline_equal", ("management", "builder"), baseline_equal, "today's 4/4/4 grid, for comparison")
BY_NAME = {p.name: p for p in [*PRESETS, BASELINE]}


def tree_for(name: str, p: dict) -> dict:
    """The layout tree of a preset for knobs `p` ({hero, kpi_band, flip}); fresh dicts every call."""
    tree = BY_NAME[name].build(p)
    return _mirror(tree) if p.get("flip") else tree
