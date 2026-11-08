"""Worker view: answer first, phone portrait (430x932). Workers are on the floor with a phone or tablet, not a wall screen.

Display only. The verdict is a rule over statuses the app already computes (render._status with the governed floors in
specbuild.EXCEPTIONS): any breach -> No, else any warn -> Watch, else Yes. A KPI without a governed threshold shows
"no target set" and never colours the verdict. Nothing is estimated and no LLM is involved.
"""

from __future__ import annotations

import json

import plotly.io as pio

import compose
from compose import THEMES, _esc, style_fig

PW, PH = 430, 932
FLOORS = {"KPI-020": (90.0, "%"), "KPI-016": (4.0, " weeks")}  # = specbuild.EXCEPTIONS: below = breach
WANTED = ("on-time in-full", "inventory coverage", "demand forecast accuracy")  # worker.SUPPLY, in this order

CSS = """
@font-face{font-family:'Instrument Sans';src:url(../assets/InstrumentSans-Regular.ttf);font-weight:400}
@font-face{font-family:'Instrument Sans';src:url(../assets/InstrumentSans-Bold.ttf);font-weight:700}
@font-face{font-family:'Geist Mono';src:url(../assets/GeistMono-Regular.ttf);font-weight:400}
@font-face{font-family:'Geist Mono';src:url(../assets/GeistMono-Medium.ttf);font-weight:500}
*{box-sizing:border-box;margin:0}
html,body{width:430px;height:932px;overflow:hidden;background:var(--bg);color:var(--text);font-family:'Instrument Sans',sans-serif}
.app{padding:18px 16px 14px;height:932px;display:flex;flex-direction:column;gap:10px}
.top .where{font:400 11.5px 'Geist Mono',monospace;color:var(--muted)}
.top h1{font-size:23px;font-weight:700;letter-spacing:-.01em;margin-top:3px}
.verdict{background:var(--panel);border:1px solid var(--line);border-left:7px solid var(--vc);border-radius:8px;padding:14px 16px;display:flex;align-items:center;gap:16px}
.verdict .big{font:700 66px/1 'Instrument Sans',sans-serif;color:var(--vc);letter-spacing:-.02em}
.verdict .why{font-size:15px;line-height:1.35}
.verdict .why small{display:block;color:var(--muted);font:400 11.5px 'Geist Mono',monospace;margin-top:6px}
.row{background:var(--panel);border:1px solid var(--line);border-left:4px solid var(--c);border-radius:8px;padding:10px 14px;display:flex;justify-content:space-between;align-items:center;min-height:86px}
.row .l{min-width:0}
.row .t{font-size:13px;color:var(--muted)}
.row .v{font:500 34px/1.15 'Geist Mono',monospace;letter-spacing:-.03em}
.row .r{text-align:right;font:400 11.5px 'Geist Mono',monospace;color:var(--muted);line-height:1.5}
.chip{display:inline-block;font:500 10.5px 'Geist Mono',monospace;letter-spacing:.05em;color:var(--c);border:1px solid var(--c);border-radius:4px;padding:1px 6px;margin-bottom:3px}
.trend{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:10px 12px 6px;flex:1;min-height:0;display:flex;flex-direction:column}
.trend h3{font-size:13px;font-weight:700;height:22px}
.trend #p{flex:1;min-height:0}
.note{font:400 10.5px 'Geist Mono',monospace;color:var(--muted);line-height:1.4}
"""


def _row_status(tile) -> str:
    return tile.status if tile is not None else "neutral"


def build(worker_dash, status_tiles, plant: str, theme: str) -> str:
    """worker_dash: the worker's own dashboard (cards + one trend). status_tiles: TileView list of the same scope
    (same governed statuses, from the OVERVIEW render). -> html for a 430x932 page."""
    th = THEMES[theme]
    by_id = {t.kpi_id: t for t in status_tiles}
    cards = [c for w in WANTED for c in worker_dash.cards if w in c.title.lower()]
    colour = {"ok": th["good"], "warn": th["warn"], "breach": th["bad"], "neutral": th["gap"]}
    label = {"ok": "ON TARGET", "warn": "WATCH", "breach": "BELOW TARGET", "neutral": "NO TARGET SET"}

    rows, judged, off = [], [], []
    for c in cards:
        st = _row_status(by_id.get(c.kpi_id))
        floor, unit = FLOORS.get(c.kpi_id, (None, ""))
        if floor is not None:
            judged.append(st)
            if st in ("breach", "warn"):
                off.append((c.title.replace(f"{plant} ", ""), c.value, f"{floor:g}{unit}"))
        target = f"target {floor:g}{unit} or more" if floor is not None else "no governed target"
        rows.append(
            f'<div class="row" style="--c:{colour[st]}"><div class="l"><div class="t">{_esc(c.title.replace(plant + " ", "").capitalize())}</div>'
            f'<div class="v">{_esc(c.value)}</div></div><div class="r"><span class="chip">{label[st]}</span><br>{_esc(target)}<br>{_esc(c.comparison)}</div></div>'
        )

    state = "breach" if "breach" in judged else "warn" if "warn" in judged else "ok" if judged else "neutral"
    word = {"breach": "No", "warn": "Watch", "ok": "Yes", "neutral": "?"}[state]
    if off:
        name, value, floor = off[0]
        why = f"{name.capitalize()} is {'below' if state == 'breach' else 'close to'} target: {_esc(value)} against {_esc(floor)}."
    else:
        why = "Every check with a governed target is on target."
    n_ok = sum(s == "ok" for s in judged)

    fig = next((f for t, f in worker_dash.figures if "on-time" in t.lower()), worker_dash.figures[0][1])
    title = next((t for t, f in worker_dash.figures if f is fig), "Trend")
    payload = style_fig(fig, "trend", PW - 56, 338, th, 1.0)
    ys = [y for tr in fig.data for y in tr.y]
    floor = FLOORS["KPI-020"][0]
    if "on-time" in title.lower():  # the governed target as a line, axis stretched so the gap is visible
        payload["layout"]["shapes"] = [dict(type="line", xref="paper", x0=0, x1=1, yref="y", y0=floor, y1=floor,
                                            line=dict(color=th["bad"], width=1.5, dash="dash"))]
        payload["layout"]["annotations"] = [dict(xref="paper", x=1, xanchor="right", yref="y", y=floor, yanchor="bottom",
                                                 text=f"target {floor:g}", showarrow=False, font=dict(size=11, color=th["bad"]))]
        payload["layout"]["yaxis"]["range"] = [min(ys) - 2, floor + 3]

    return (
        f"<!doctype html><html><head><meta charset=utf-8><meta name=viewport content='width=430'><style>:root{{--bg:{th['bg']};--panel:{th['panel']};"
        f"--line:{th['line']};--text:{th['text']};--muted:{th['muted']};--vc:{colour[state]}}}{CSS}</style>"
        "<script src='../assets/plotly.min.js'></script></head><body><div class=app>"
        f"<div class=top><div class=where>{_esc(plant)} · Warehouse Ops · synthetic data</div><h1>Is supply safe at {_esc(plant)}?</h1></div>"
        f"<div class=verdict><div class=big>{word}</div><div class=why>{why}<small>{n_ok} of {len(judged)} checks on target</small></div></div>"
        f"{''.join(rows)}"
        f"<div class=trend><h3>{_esc(title)}</h3><div id=p></div></div>"
        "<div class=note>Supply only. Downtime, quality and workplace-safety numbers are not measured yet.</div></div>"
        f"<script>const F={json.dumps(payload)};Plotly.newPlot('p',F.data,F.layout,{{staticPlot:true,displayModeBar:false}}).then(()=>{{window.__done=true}});</script>"
        "</body></html>"
    )
