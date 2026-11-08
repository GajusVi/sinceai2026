"""Layout sweep: N weighted 16:9 dashboards from the real BI Steward pipeline, one PNG each, scored.

    python tools/layout_sweep/sweep.py --n 100 --out out/layout_sweep

Needs: pip install plotly pandas pydantic openpyxl rapidfuzz scikit-learn playwright pillow (+ playwright's chromium).
Content comes from the real pipeline (Steward.build + render.render, LLM off), so numbers, verdicts and governance
footers are the app's own. Only the arrangement varies: preset (weights), hero ratio, KPI band, flip, gap, theme, role.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import shutil
import sys
import tempfile
import warnings
from dataclasses import replace
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ROOT = Path(os.environ.get("STEWARD_ROOT") or HERE.parents[1])
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")

import compose  # noqa: E402
from presets import BASELINE, PRESETS  # noqa: E402

ACCOUNTS = {"worker": ("Worker21", "Worker123"), "management": ("Manager07", "Manage123"), "builder": ("Builder12", "Admin123")}
QUESTIONS = {
    "worker": ["How is Plant-B doing?", "LATAM this quarter", "Nubeqa sales growth and forecast variance by country",
               "Global net sales by product vs forecast"],
    "management": ["How is Plant-B doing?", "How is Plant-A doing?", "LATAM this quarter", "Show me OTIF and inventory for Plant-B",
                   "How efficient is my plant running?", "Nubeqa sales growth and forecast variance by country"],
    "builder": ["How is Plant-B doing?", "How is Plant-A doing?", "LATAM this quarter", "Show me OTIF and inventory for Plant-B",
                "How efficient is my plant running?",
                "Create a global Nubeqa dashboard showing sales growth, forecast variance and market access by country."],
}
QUOTA = {"worker": 0.2, "management": 0.4, "builder": 0.4}


def pipeline():
    from steward import Steward, semantic
    from steward.auth import login
    from steward.config import Settings
    from steward.render import render

    steward = Steward(settings=replace(Settings.from_env(), use_llm="off", data_dir=Path(tempfile.mkdtemp()), as_of=date(2026, 11, 6)))
    frames = semantic.load_frames()

    def dashboards(question: str, role: str):
        state = steward.interviewer.start(question)
        intent = steward.interviewer.finish_with_defaults(state).intent
        spec = steward.build(steward.ask_intent(intent), intent, login(*ACCOUNTS[role])).spec
        return spec, {th: render(spec, frames, theme=th) for th in ("night", "day")}

    return dashboards


def plan(n: int, seed: int) -> list[dict]:
    """n variants, stratified by role; every preset of a role's pool is used before any repeats."""
    rng = random.Random(seed)
    out: list[dict] = []
    for role, share in QUOTA.items():
        count = round(n * share)
        pool = [p for p in PRESETS if role in p.roles]
        cases = QUESTIONS[role]
        combos = [(p.name, q, t) for p in pool for q in cases for t in ("night", "day")]
        rng.shuffle(combos)
        combos.sort(key=lambda c: (c[2] == "day") != (len(out) % 2 == 0))  # mild theme alternation, stable otherwise
        picked, seen = [], set()
        for c in combos:  # first pass: one per preset
            if c[0] not in seen:
                picked.append(c)
                seen.add(c[0])
        rest = [c for c in combos if c not in picked]
        rng.shuffle(rest)
        picked += rest
        for name, q, theme in picked[:count]:
            out.append(dict(role=role, preset=name, question=q, theme=theme,
                            params=dict(hero=round(rng.uniform(0.56, 0.72), 2), kpi_band=round(rng.uniform(0.9, 1.3), 2),
                                        flip=rng.random() < 0.3, gap=rng.choice([8, 10, 12, 14]))))
    return out[:n]


def baselines() -> list[dict]:
    """Today's equal grid (reference) and, for the same content, two weighted layouts (extra=True: not in the stats)."""
    p = dict(hero=0.62, kpi_band=1.0, flip=False, gap=12)
    cases = (("management", "How is Plant-B doing?"), ("builder", "How is Plant-A doing?"), ("management", "How efficient is my plant running?"))
    out = [dict(role=r, preset=BASELINE.name, question=q, theme="night", params=p) for r, q in cases]
    for r, q in cases:
        for name in ("hero_left_stack", "kpi_rail_left"):
            out.append(dict(role=r, preset=name, question=q, theme="night", params=p, extra=True))
    return out


def assets(out: Path) -> None:
    import plotly

    a = out / "assets"
    a.mkdir(parents=True, exist_ok=True)
    shutil.copy(Path(plotly.__file__).parent / "package_data" / "plotly.min.js", a / "plotly.min.js")
    fonts = ROOT / "frontend" / "static" / "fonts"
    for f in ("InstrumentSans-Regular.ttf", "InstrumentSans-Bold.ttf", "GeistMono-Regular.ttf", "GeistMono-Medium.ttf"):
        if (fonts / f).exists():
            shutil.copy(fonts / f, a / f)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=str(ROOT / "out" / "layout_sweep"))
    args = ap.parse_args()
    out = Path(args.out)
    for d in ("html", "png"):
        (out / d).mkdir(parents=True, exist_ok=True)
    assets(out)

    build = pipeline()
    cache: dict[tuple[str, str], tuple] = {}
    variants = baselines() + plan(args.n, args.seed)
    from playwright.sync_api import sync_playwright

    rows = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": compose.W, "height": compose.H})
        for i, v in enumerate(variants):
            key = (v["role"], v["question"])
            if key not in cache:
                cache[key] = build(v["question"], v["role"])
            spec, dashes = cache[key]
            dash = dashes[v["theme"]]
            vid = f"{'base' if v['preset'] == BASELINE.name else 'pair' if v.get('extra') else 'v'}{i:03d}"
            html_doc, m = compose.build(dash, v["preset"], v["params"], v["role"], v["theme"],
                                        dict(preset=v["preset"], as_of="synthetic data pack"))
            (out / "html" / f"{vid}.html").write_text(html_doc, encoding="utf-8")
            page.goto((out / "html" / f"{vid}.html").as_uri())
            page.wait_for_function("window.__done===true", timeout=30000)
            overflow = page.evaluate("[...document.querySelectorAll('[data-fit]')].filter(e=>e.scrollWidth>e.clientWidth+1||(e.classList.contains('tbl')&&e.scrollHeight>e.clientHeight+1)).length")
            page.screenshot(path=str(out / "png" / f"{vid}.png"))
            row = dict(id=vid, role=v["role"], preset=v["preset"], theme=v["theme"], question=v["question"],
                       archetype=getattr(spec, "archetype", "") or "template", extra=bool(v.get("extra")), **v["params"], **m, overflow=overflow,
                       score=compose.score(m, overflow))
            rows.append(row)
            print(f"{vid} {v['role']:<10} {v['preset']:<20} {v['theme']:<5} score={row['score']:>5} asym={m['asymmetry']:.2f} hero={m['hero_share']:.2f} ovf={overflow}", flush=True)
        browser.close()

    (out / "results.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    with open(out / "results.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    report(rows, out)


def report(rows: list[dict], out: Path) -> None:
    from collections import defaultdict
    from statistics import mean

    swept = [r for r in rows if r["preset"] != BASELINE.name and not r["extra"]]
    base = [r for r in rows if r["preset"] == BASELINE.name]
    by_preset, by_role = defaultdict(list), defaultdict(list)
    for r in swept:
        by_preset[r["preset"]].append(r["score"])
        by_role[r["role"]].append(r["score"])
    lines = ["# Layout sweep", "", f"{len(swept)} weighted variants + {len(base)} baseline (today's equal grid).", "",
             f"Baseline mean score: **{mean(r['score'] for r in base):.1f}**  (asymmetry {mean(r['asymmetry'] for r in base):.2f}) ",
             f"Sweep mean score: **{mean(r['score'] for r in swept):.1f}**  (asymmetry {mean(r['asymmetry'] for r in swept):.2f})", "",
             "## By role", *[f"- {k}: {mean(v):.1f} over {len(v)}" for k, v in by_role.items()], "", "## By preset (mean score)",
             *[f"- {k}: {mean(v):.1f} over {len(v)}" for k, v in sorted(by_preset.items(), key=lambda kv: -mean(kv[1]))], "",
             "## Top 10", *[f"- {r['id']} {r['role']} {r['preset']} {r['theme']} hero={r['hero']} score={r['score']}" for r in sorted(swept, key=lambda r: -r["score"])[:10]], "",
             "## Bottom 5", *[f"- {r['id']} {r['role']} {r['preset']} {r['theme']} score={r['score']} dropped={r['dropped_charts']} overflow={r['overflow']}" for r in sorted(swept, key=lambda r: r["score"])[:5]]]
    (out / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    sheets(rows, out)
    gallery(rows, out)


def sheets(rows: list[dict], out: Path) -> None:
    """Contact sheets (4 x 3 thumbnails) per role, best first, plus baseline vs best."""
    from PIL import Image, ImageDraw, ImageFont

    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 15)
    except OSError:
        font = ImageFont.load_default()
    tw, th_, cap = 640, 360, 24
    for role in ("worker", "management", "builder"):
        picks = sorted((r for r in rows if r["role"] == role and r["preset"] != BASELINE.name and not r["extra"]), key=lambda r: -r["score"])
        for s in range(0, len(picks), 12):
            chunk = picks[s:s + 12]
            sheet = Image.new("RGB", (4 * tw, 3 * (th_ + cap)), "#18181b")
            d = ImageDraw.Draw(sheet)
            for j, r in enumerate(chunk):
                img = Image.open(out / "png" / f"{r['id']}.png").convert("RGB").resize((tw, th_), Image.LANCZOS)
                x, y = (j % 4) * tw, (j // 4) * (th_ + cap)
                sheet.paste(img, (x, y + cap))
                d.text((x + 6, y + 3), f"{r['id']} {r['preset']} {r['theme']} score {r['score']}", fill="#fafafa", font=font)
            sheet.save(out / f"sheet_{role}_{s // 12 + 1}.png")
    for n, b in enumerate(r for r in rows if r["preset"] == BASELINE.name):
        mates = [r for r in rows if r["extra"] and r["question"] == b["question"] and r["role"] == b["role"]]
        shots = [("TODAY (equal grid)", b)] + [(f"WEIGHTED: {m['preset']}", m) for m in mates]
        pair = Image.new("RGB", (len(shots) * 960, 540 + cap), "#18181b")
        d = ImageDraw.Draw(pair)
        for j, (label, r) in enumerate(shots):
            pair.paste(Image.open(out / "png" / f"{r['id']}.png").convert("RGB").resize((960, 540), Image.LANCZOS), (j * 960, cap))
            d.text((j * 960 + 6, 3), f"{label} · score {r['score']} · {r['role']}", fill="#fafafa", font=font)
        pair.save(out / f"before_after_{n + 1}.png")


def gallery(rows: list[dict], out: Path) -> None:
    cards = "".join(
        f'<figure data-role="{r["role"]}"><a href="png/{r["id"]}.png"><img loading=lazy src="png/{r["id"]}.png"></a>'
        f'<figcaption><b>{r["score"]}</b> {r["id"]} · {r["role"]} · {r["preset"]} · {r["theme"]} · hero {r["hero"]}<br>'
        f'<span>{r["question"][:70]}</span></figcaption></figure>' for r in sorted(rows, key=lambda r: -r["score"]))
    (out / "gallery.html").write_text(
        "<!doctype html><meta charset=utf-8><title>Layout sweep</title><style>body{background:#09090b;color:#fafafa;font:14px system-ui;margin:16px}"
        ".g{display:grid;grid-template-columns:repeat(auto-fill,minmax(420px,1fr));gap:14px}figure{margin:0}img{width:100%;border:1px solid #27272a;border-radius:4px}"
        "figcaption{font:12px ui-monospace,monospace;color:#a1a1aa;margin-top:4px}figcaption b{color:#4ade80}</style>"
        f"<h1>Layout sweep: {len(rows)} dashboards, best first</h1><div class=g>{cards}</div>", encoding="utf-8")


if __name__ == "__main__":
    main()
