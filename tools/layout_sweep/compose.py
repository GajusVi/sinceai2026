"""Pour a RenderedDashboard into a weighted 16:9 layout (pure HTML + Plotly), and measure the result.

Input: steward.render.RenderedDashboard (tiles / cards / gaps / figures / tables / footer). Output: one self-contained
1920x1080 page and the numbers the sweep scores. Display only: no spec, number or verdict is changed here.
"""

from __future__ import annotations

import copy
import html
import json
import statistics
from dataclasses import dataclass, field

import plotly.graph_objects as go
import plotly.io as pio

from presets import tree_for

W, H = 1920, 1080
PAD, GAP, HEAD_H = 24, 12, 62

THEMES = {
    "night": dict(bg="#09090b", panel="#121215", line="#27272a", text="#fafafa", muted="#a1a1aa", accent="#3b6bff",
                  good="#4ade80", bad="#f87171", warn="#fbbf24", gap="#52525b"),
    "day": dict(bg="#f4f4f5", panel="#ffffff", line="#e4e4e7", text="#09090b", muted="#52525b", accent="#1a4be0",
                good="#15803d", bad="#b91c1c", warn="#b45309", gap="#a1a1aa"),
}
ROLE_SCALE = {"worker": 1.35, "management": 1.0, "builder": 0.95}
FOOTER_KEYS = {"worker": (), "management": ("Owner", "Data"), "builder": ("Source model", "Owner", "Version", "Data")}


@dataclass
class Leaf:
    kind: str
    x: float
    y: float
    w: float
    h: float
    id: int = 0

    @property
    def area(self) -> float:
        return self.w * self.h


# -- geometry ------------------------------------------------------------------------------------------------------


def _number(node: dict, counter: list[int]) -> None:
    if "k" in node:
        for k in node["k"]:
            _number(k, counter)
    else:
        node["id"] = counter[0]
        counter[0] += 1


def _place(node: dict, x: float, y: float, w: float, h: float, gap: float, out: list[Leaf]) -> None:
    if "k" not in node:
        out.append(Leaf(node["t"], x, y, w, h, node["id"]))
        return
    kids, horizontal = node["k"], node["t"] == "row"
    total = sum(k["w"] for k in kids)
    room = (w if horizontal else h) - gap * (len(kids) - 1)
    pos = x if horizontal else y
    for k in kids:
        size = room * k["w"] / total
        if horizontal:
            _place(k, pos, y, size, h, gap, out)
        else:
            _place(k, x, pos, w, size, gap, out)
        pos += size + gap


def _prune(node: dict, keep: set[int]) -> dict | None:
    if "k" not in node:
        return node if node["id"] in keep else None
    kids = [c for c in (_prune(k, keep) for k in node["k"]) if c]
    return {**node, "k": kids} if kids else None


def _split_smallest(tree: dict, leaves: list[Leaf]) -> dict:
    """Split a chart slot into two unequal ones (5:4) across its long side. Prefers the smallest slot whose halves stay
    readable (>= 300 wide, >= 190 high); if none can, the biggest slot. Keeps the hierarchy and the asymmetry."""
    def halves(l: Leaf) -> tuple[bool, float, float]:
        across_w = l.w / l.h > 1.4
        small_w = (l.w - GAP) / 2.25 if across_w else l.w
        small_h = l.h if across_w else (l.h - GAP) / 2.25
        return small_w >= 300 and small_h >= 190, small_w, small_h

    charts = [l for l in leaves if l.kind == "chart"]
    fits = [l for l in charts if halves(l)[0]]
    target = min(fits, key=lambda l: l.area) if fits else max(charts, key=lambda l: l.area)

    def walk(node):
        if "k" not in node:
            if node["id"] != target.id:
                return node
            pair = [{"t": "chart", "w": 1.25}, {"t": "chart", "w": 1.0}]
            return {"t": "row" if target.w / target.h > 1.4 else "col", "w": node["w"], "k": pair}
        return {**node, "k": [walk(k) for k in node["k"]]}

    return walk(tree)


def arrange(tree: dict, n_charts: int, has_kpi: bool, has_table: bool, box: tuple[float, float, float, float], gap: float):
    """Place the tree, keep the slots that have content (the n biggest chart slots, one KPI slot, one table slot),
    place again so the freed space flows to the neighbours. Returns (leaves, dropped_charts)."""
    tree = copy.deepcopy(tree)
    for _ in range(8):  # a preset with fewer chart slots than charts splits its smallest slot, never drops a chart
        _number(tree, [0])
        first: list[Leaf] = []
        _place(tree, *box, gap, first)
        if sum(l.kind == "chart" for l in first) >= n_charts or not any(l.kind == "chart" for l in first):
            break
        tree = _split_smallest(tree, first)
    keep = set()
    charts = sorted((l for l in first if l.kind == "chart"), key=lambda l: -l.area)
    keep |= {l.id for l in charts[:n_charts]}
    if has_kpi:
        keep |= {next(l.id for l in first if l.kind == "kpi")} if any(l.kind == "kpi" for l in first) else set()
    if has_table and any(l.kind == "table" for l in first):
        keep.add(next(l.id for l in first if l.kind == "table"))
    pruned = _prune(tree, keep)
    leaves: list[Leaf] = []
    if pruned:
        _place(pruned, *box, gap, leaves)
    return leaves, max(0, n_charts - len(charts))


# -- content -------------------------------------------------------------------------------------------------------


def kpis_of(dash) -> list[dict]:
    out = []
    for t in dash.tiles:
        out.append(dict(title=t.title, value=t.value, delta=t.delta, tone=t.tone, status=t.status, note=t.note))
    for c in dash.cards:
        out.append(dict(title=c.title, value=c.value, delta=c.comparison, tone=c.tone, status="neutral", note=c.note))
    for g in dash.gaps:
        out.append(dict(title=g.name, value="Not measured yet", delta="", tone="neutral", status="gap", note=g.reason))
    return out


def chart_kind(fig: go.Figure) -> str:
    if fig.layout.barmode == "stack":
        return "share"
    if fig.data and isinstance(fig.data[0], go.Scatter):
        return "trend"
    notes = " ".join(getattr(a, "text", "") or "" for a in (fig.layout.annotations or []))
    if "target" in notes:
        return "bullet"
    if fig.layout.shapes:
        return "diverging"
    return "rank"


IMPORTANCE = {"trend": 90, "diverging": 80, "bullet": 70, "rank": 60, "share": 40}


def ranked_charts(dash) -> list[tuple[str, go.Figure, str]]:
    items = [(title, fig, chart_kind(fig)) for title, fig in dash.figures]
    bonus = lambda it: 15 if it[2] == "trend" and len(it[1].data) > 1 else 0  # a trend against forecast leads
    return sorted(items, key=lambda it: -(IMPORTANCE[it[2]] + bonus(it)))


# -- html pieces ---------------------------------------------------------------------------------------------------


def _esc(x) -> str:
    return html.escape(str(x))


def _tile_grid(leaf: Leaf, n: int) -> tuple[int, int]:
    best, best_score = (1, n), 1e9
    for cols in range(1, n + 1):
        rows = -(-n // cols)
        tw, th = (leaf.w - GAP * (cols - 1)) / cols, (leaf.h - GAP * (rows - 1)) / rows
        score = abs(tw / max(th, 1) - 1.9) + (0.15 if rows * cols - n > 1 else 0)
        if score < best_score:
            best, best_score = (cols, rows), score
    return best


def kpi_html(leaf: Leaf, items: list[dict], scale: float, th: dict) -> str:
    if not items:
        return ""
    cols, rows = _tile_grid(leaf, len(items))
    tw, tile_h = (leaf.w - GAP * (cols - 1)) / cols, (leaf.h - GAP * (rows - 1)) / rows
    vfs = max(18, min(tw * 0.16, tile_h * 0.36, 68 * scale))
    tfs = max(10.5, min(vfs * 0.34, 15 * scale))
    cells = []
    for it in items:
        status = it["status"]
        edge = {"ok": th["good"], "warn": th["warn"], "breach": th["bad"], "gap": th["gap"]}.get(status, th["line"])
        badge = {"ok": "ON TARGET", "warn": "WATCH", "breach": "BREACH"}.get(status, "")
        dcol = {"good": th["good"], "bad": th["bad"]}.get(it["tone"], th["muted"])
        is_gap = status == "gap"
        value_fs = vfs * (0.42 if is_gap else 1)
        value_fs = max(12.0, min(value_fs, (tw - 34) / (0.62 * max(len(str(it["value"])), 1))))  # never wider than the tile
        cells.append(
            f'<div class="tile{" gap" if is_gap else ""}" style="border-left:3px {"dashed" if is_gap else "solid"} {edge}">'
            f'<div class="tt" data-fit style="font-size:{tfs:.1f}px">{_esc(it["title"])}'
            f'{f"<span class=badge style=color:{edge}>{badge}</span>" if badge else ""}</div>'
            f'<div class="tv" data-fit style="font-size:{value_fs:.1f}px">{_esc(it["value"])}</div>'
            f'<div class="td" data-fit style="font-size:{max(10.5, tfs):.1f}px;color:{dcol}">{_esc(it["delta"] or it["note"] if is_gap else it["delta"])}</div>'
            "</div>"
        )
    return (f'<div class="kpis" style="{_box(leaf)};grid-template-columns:repeat({cols},1fr);'
            f'grid-template-rows:repeat({rows},1fr)">{"".join(cells)}</div>')


def _box(l: Leaf) -> str:
    return f"left:{l.x:.1f}px;top:{l.y:.1f}px;width:{l.w:.1f}px;height:{l.h:.1f}px"


def table_html(leaf: Leaf, title: str, df, scale: float) -> str:
    fs = 12.5 * min(scale, 1.15)
    row_h = fs * 2.3
    avail = leaf.h - 34 - 8 - fs * 2.2  # panel title, bottom pad, header row
    fit = max(int(avail // row_h), 1)
    room = fit if len(df) <= fit else max(int((avail - 26) // row_h), 1)  # leave a line for "+N more"
    shown, more = df.head(room), max(0, len(df) - room)
    head = "".join(f"<th>{_esc(c)}</th>" for c in df.columns)
    body = "".join(
        "<tr>" + "".join(f'<td class="{"n" if i else ""}">{_esc(v)}</td>' for i, v in enumerate(r)) + "</tr>"
        for r in shown.itertuples(index=False)
    )
    tail = f'<div class="more">+{more} more rows</div>' if more else ""
    return (f'<section class="panel" style="{_box(leaf)}"><h3 data-fit>{_esc(title)}</h3>'
            f'<div class="tbl" data-fit style="font-size:{fs:.1f}px"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>{tail}</div></section>')


def style_fig(fig: go.Figure, kind: str, w: float, h: float, th: dict, scale: float) -> dict:
    f = go.Figure(fig)
    small = w < 460 or h < 230
    ax = th["muted"]
    fs = (10 if small else 11.5) * min(scale, 1.25)
    f.update_layout(title=None, width=int(w), height=int(h), margin=dict(l=6, r=14, t={"trend": 30, "bullet": 22}.get(kind, 8), b=26),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(size=fs, color=ax),
                    showlegend=(kind == "trend" and len(f.data) > 1 and not small),
                    legend=dict(orientation="h", x=1, xanchor="right", y=1.0, yanchor="bottom", font=dict(size=fs, color=ax)))
    f.update_xaxes(title_text=None, automargin=True, tickfont=dict(size=fs, color=ax), gridcolor=th["line"],
                   zerolinecolor=th["line"], linecolor=th["line"], nticks=6 if w > 520 else 4)
    f.update_yaxes(title_text=None, automargin=True, tickfont=dict(size=fs, color=ax), gridcolor=th["line"],
                   zerolinecolor=th["line"], linecolor=th["line"])
    if kind == "share":
        f.update_traces(width=0.42)
    if kind in ("rank", "bullet"):
        _zoom_bars(f, th)
    return json.loads(pio.to_json(f))


def _zoom_bars(f: go.Figure, th: dict) -> None:
    """Horizontal bars on a zoomed axis: the dynamics between close values stay readable. The axis start is printed
    under the chart, because a bar that does not start at zero overstates every difference. Diverging and 100% bars
    keep their zero. Ranges always include the target line."""
    xs = [float(v) for tr in f.data if tr.type == "bar" and tr.orientation == "h" for v in (tr.x if tr.x is not None else []) if v is not None]
    xs += [float(s.x0) for s in (f.layout.shapes or []) if s.x0 is not None]
    if len(xs) < 3 or min(xs) < 0:
        return
    lo, hi = min(xs), max(xs)
    span = (hi - lo) or abs(hi) or 1.0
    start = max(0.0, lo - 0.45 * span)
    if start <= 0.05 * hi:  # already close to zero: nothing to zoom
        return
    start = float(f"{start:.2g}") if start < 10 else float(int(start))
    f.update_xaxes(range=[start, hi + 0.08 * span], title_text=f"axis starts at {start:g}",
                   title_font=dict(size=10, color=th["muted"]), title_standoff=2)
    f.update_layout(margin=dict(b=40))


def chart_html(leaf: Leaf, idx: int, title: str, fig, kind: str, th: dict, scale: float, payloads: list) -> str:
    body_w, body_h = leaf.w - 20, leaf.h - 44
    payloads.append((f"p{idx}", style_fig(fig, kind, body_w, body_h, th, scale)))
    return (f'<section class="panel" style="{_box(leaf)}"><h3 data-fit style="font-size:{max(10.5, min(13.5 * min(scale, 1.2), (leaf.w - 24) / (0.56 * max(len(title), 1)))):.1f}px">{_esc(title)}</h3>'
            f'<div id="p{idx}" class="plot"></div></section>')


# -- page ------------------------------------------------------------------------------------------------------------

CSS = """
@font-face{font-family:'Instrument Sans';src:url(../assets/InstrumentSans-Regular.ttf);font-weight:400}
@font-face{font-family:'Instrument Sans';src:url(../assets/InstrumentSans-Bold.ttf);font-weight:700}
@font-face{font-family:'Geist Mono';src:url(../assets/GeistMono-Regular.ttf);font-weight:400}
@font-face{font-family:'Geist Mono';src:url(../assets/GeistMono-Medium.ttf);font-weight:500}
*{box-sizing:border-box;margin:0}
html,body{width:1920px;height:1080px;overflow:hidden;background:var(--bg);color:var(--text);font-family:'Instrument Sans',sans-serif}
.canvas{position:relative;width:1920px;height:1080px}
.head{position:absolute;left:24px;right:24px;top:18px;height:44px;display:flex;align-items:flex-end;justify-content:space-between}
.head h1{font-size:24px;font-weight:700;letter-spacing:-.01em}
.head>div{min-width:0;flex:1;overflow:hidden}
.head h1,.head .sub{white-space:nowrap;overflow:hidden}
.head .sub{font:400 12px 'Geist Mono',monospace;color:var(--muted);margin-top:2px}
.head .tag{font:400 11px 'Geist Mono',monospace;color:var(--muted);text-align:right}
.panel{position:absolute;background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:10px 10px 8px;overflow:hidden}
.panel h3{font-size:13.5px;font-weight:700;color:var(--text);min-height:24px;line-height:1.25;white-space:nowrap}
.plot{position:absolute;left:10px;top:34px;right:10px;bottom:10px}
.kpis{position:absolute;display:grid;gap:12px}
.tile{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:8px 14px;display:flex;flex-direction:column;justify-content:center;gap:3px;overflow:hidden;min-width:0}
.tile>*{flex:none}
.tile.gap{background:repeating-linear-gradient(135deg,var(--panel),var(--panel) 6px,var(--line) 6px,var(--line) 7px)}
.tt{color:var(--muted);line-height:1.2;overflow-wrap:break-word}
.badge{font:500 9.5px 'Geist Mono',monospace;margin-left:8px;letter-spacing:.04em;white-space:nowrap}
.tv{font-family:'Geist Mono',monospace;font-weight:500;letter-spacing:-.03em;white-space:nowrap;line-height:1.32}
.td{font-family:'Geist Mono',monospace;line-height:1.2;overflow-wrap:break-word}
.tbl{position:absolute;left:10px;right:10px;top:34px;bottom:8px;overflow:hidden}
table{width:100%;border-collapse:collapse}
th{font:500 .8em 'Geist Mono',monospace;color:var(--muted);text-align:left;padding:4px 6px;border-bottom:1px solid var(--line);text-transform:uppercase;letter-spacing:.04em}
td{padding:.5em 6px;border-bottom:1px solid var(--line);white-space:nowrap}
td.n{font-family:'Geist Mono',monospace;text-align:right}
th:not(:first-child){text-align:right}
.more{color:var(--muted);font:400 .85em 'Geist Mono',monospace;padding:6px}
.foot{position:absolute;left:24px;right:24px;bottom:12px;display:flex;gap:28px;font:400 11px 'Geist Mono',monospace;color:var(--muted);white-space:nowrap;overflow:hidden}
.foot b{color:var(--text);font-weight:500;margin-right:6px}
"""


# Text never collides: before the charts are drawn, every tile shrinks its fonts until label, value and delta fit
# (labels wrap at word boundaries); a chart title shrinks to one line, else wraps and pushes its chart down; the
# table, heading and footer shrink to their width. Floors keep text legible.
FIT_JS = """(function(){
const over=(e,wOnly)=>e.scrollWidth>e.clientWidth+1||(!wOnly&&e.scrollHeight>e.clientHeight+1);
const fs=e=>parseFloat(getComputedStyle(e).fontSize);
function shrink(box,els,min,wOnly){for(let i=0;i<60;i++){
 if(!over(box,wOnly)&&!els.some(e=>e.clientWidth&&e.scrollWidth>e.clientWidth+1))return;
 let moved=false;for(const e of els){const f=fs(e);if(f>min){e.style.fontSize=Math.max(min,f*0.95)+'px';moved=true}}
 if(!moved)return;}}
for(const t of document.querySelectorAll('.tile')){const els=[...t.querySelectorAll('.tt,.tv,.td,.badge')];shrink(t,els,9,false);}
for(const s of document.querySelectorAll('section.panel')){const h=s.querySelector('h3');if(!h)continue;
 shrink(h,[h],11,true);
 if(over(h,true)){h.style.whiteSpace='normal';h.style.overflowWrap='break-word';}
 const extra=Math.max(0,h.offsetHeight-24);const body=s.querySelector('.plot,.tbl');
 if(extra&&body){body.style.top=(34+extra)+'px';const p=P.find(x=>x[0]===body.id);
  if(p)p[1].layout.height=Math.max(80,p[1].layout.height-extra);}}
for(const t of document.querySelectorAll('.tbl'))shrink(t,[t],9,true);
for(const e of document.querySelectorAll('.head h1,.head .sub'))shrink(e,[e],10,true);
const f=document.querySelector('.foot');if(f)shrink(f,[f],9,true);
})();"""


def build(dash, preset: str, params: dict, role: str, theme: str, meta: dict) -> tuple[str, dict]:
    """-> (html, metrics). `params`: hero (0.55-0.72), kpi_band, flip, gap."""
    th = THEMES[theme]
    scale = ROLE_SCALE[role]
    gap = params.get("gap", GAP)
    foot_keys = FOOTER_KEYS[role]
    foot_h = 30 if foot_keys else 0
    box = (PAD, HEAD_H + 8, W - 2 * PAD, H - HEAD_H - 8 - PAD - foot_h)
    items = kpis_of(dash)
    charts = ranked_charts(dash)
    tbl = dash.tables[0] if dash.tables else None
    if role == "worker" or (tbl is not None and tbl[1].empty):
        tbl = None  # an exceptions table with no rows does not get a panel
    leaves, dropped = arrange(tree_for(preset, params), len(charts), bool(items), tbl is not None, box, gap)

    parts, payloads = [], []
    chart_leaves = sorted((l for l in leaves if l.kind == "chart"), key=lambda l: -l.area)
    placed = []
    for n, (leaf, (title, fig, kind)) in enumerate(zip(chart_leaves, charts)):
        parts.append(chart_html(leaf, n, title, fig, kind, th, scale, payloads))
        placed.append((leaf, kind, title))
    for leaf in leaves:
        if leaf.kind == "kpi":
            parts.append(kpi_html(leaf, items, scale, th))
        elif leaf.kind == "table" and tbl is not None:
            parts.append(table_html(leaf, tbl[0], tbl[1], scale))

    footer = "".join(f"<span><b>{_esc(k)}</b>{_esc(v)}</span>" for k, v in dash.footer if k in foot_keys)
    scope = " · ".join(f"{k}: {v}" for k, v in dash.filters.items()) or "whole portfolio"
    tag = f'{_esc(meta.get("preset", preset))} · hero {params.get("hero", 0):.2f} · {role} · {theme}'
    page = (
        f"<!doctype html><html><head><meta charset=utf-8><style>:root{{--bg:{th['bg']};--panel:{th['panel']};--line:{th['line']};"
        f"--text:{th['text']};--muted:{th['muted']}}}{CSS}</style><script src='../assets/plotly.min.js'></script></head><body>"
        f"<div class=canvas><div class=head><div><h1 data-fit>{_esc(dash.title)}</h1><div class=sub>{_esc(scope)} · {_esc(meta.get('as_of', ''))}</div></div>"
        f"<div class=tag>{tag}</div></div>{''.join(parts)}<div class=foot>{footer}</div></div>"
        f"<script>const P={json.dumps(payloads)};{FIT_JS}Promise.all(P.map(([id,f])=>Plotly.newPlot(id,f.data,f.layout,{{staticPlot:true,displayModeBar:false}}))).then(()=>{{window.__done=true}});"
        f"if(!P.length)window.__done=true;</script></body></html>"
    )
    return page, metrics(placed, leaves, dropped, len(charts))


# -- measuring ---------------------------------------------------------------------------------------------------------


def metrics(placed: list, leaves: list[Leaf], dropped: int, n_charts: int) -> dict:
    """Layout facts. asymmetry = coefficient of variation of chart areas (0 = every chart the same size, the AI look)."""
    areas = [l.area for l, _, _ in placed]
    total = sum(areas) or 1
    hero = max(placed, key=lambda p: p[0].area)[0] if placed else None
    by_read = sorted((l for l, _, _ in placed), key=lambda l: (round(l.y / 60), l.x))
    asym = (statistics.pstdev(areas) / statistics.mean(areas)) if len(areas) > 1 else 0.0
    return dict(
        n_charts=len(placed), dropped_charts=dropped,
        hero_share=round(hero.area / total, 3) if hero else 0.0,
        asymmetry=round(asym, 3),
        min_w=round(min((l.w for l in leaves if l.kind == "chart"), default=0)),
        min_h=round(min((l.h for l in leaves if l.kind == "chart"), default=0)),
        max_aspect=round(max((l.w / l.h for l in leaves if l.kind == "chart"), default=0), 2),
        hero_reads_first=bool(hero and by_read and by_read[0].id == hero.id),
        kpi_first=bool(leaves) and any(l.kind == "kpi" and (l.y <= HEAD_H + 40 or l.x <= PAD + 4) for l in leaves),
        has_table=any(l.kind == "table" for l in leaves),
        hero_kind=max(placed, key=lambda p: p[0].area)[1] if placed else "",
        covered=round(sum(l.area for l in leaves) / (W * H), 3),
    )


def score(m: dict, overflow: int) -> float:
    """0-100. Enterprise look = a clear hero, unequal weights, readable cells, KPI first, nothing clipped."""
    s = 0.0
    n = m["n_charts"]
    if n >= 3:
        s += 25 * min(1.0, m["asymmetry"] / 0.45)  # unequal chart sizes
        s += 20 * max(0.0, 1 - abs(m["hero_share"] - 0.40) / 0.25)  # the hero holds ~40% of the chart area
    elif n == 2:
        s += 25 * min(1.0, m["asymmetry"] / 0.35)
        s += 20 * max(0.0, 1 - abs(m["hero_share"] - 0.62) / 0.25)
    else:
        s += 45  # one chart: nothing to weigh
    s += 20 * min(1.0, min(m["min_w"] / 330, m["min_h"] / 190)) if n else 20
    s += 10 * (1.0 if 0.9 <= m["max_aspect"] <= 4.2 or not n else 0.4)
    s += 10 * (1.0 if m["hero_reads_first"] else 0.4)
    s += 5 * (1.0 if m["kpi_first"] else 0.3)
    s += 10 * max(0.0, 1 - overflow / 3)
    s -= 8 * m["dropped_charts"]
    return round(max(0.0, min(100.0, s)), 1)
