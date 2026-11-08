"""The three picks, one per role, each matched to its prompt. Rendered at 2x.

    python tools/layout_sweep/finals.py --out out/layout_sweep/final
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import compose  # noqa: E402
import sweep  # noqa: E402  (sets up STEWARD_ROOT / sys.path)
import worker_mobile  # noqa: E402

PICKS = [
    # id, role, prompt, how it is shown
    dict(id="worker", role="worker", question="How is Plant-A doing?", plant="Plant-A", prompt="Is supply safe at my plant?", device="phone 430x932"),
    dict(id="management", role="management", question="How is Plant-B doing?", prompt="How is Plant-B doing?",
         preset="hero_left_stack", params=dict(hero=0.62, kpi_band=1.0, flip=False, gap=12), device="big screen 1920x1080"),
    dict(id="builder", role="builder", prompt="Create a global Nubeqa dashboard showing sales growth, forecast variance and market access by country.",
         question="Create a global Nubeqa dashboard showing sales growth, forecast variance and market access by country.",
         preset="triptych", params=dict(hero=0.62, kpi_band=1.0, flip=False, gap=12), device="desktop 1920x1080"),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(sweep.ROOT / "out" / "layout_sweep" / "final"))
    ap.add_argument("--theme", default="night")
    args = ap.parse_args()
    out = Path(args.out)
    (out / "html").mkdir(parents=True, exist_ok=True)
    sweep.assets(out)
    build = sweep.pipeline()
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for pick in PICKS:
            spec, dashes = build(pick["question"], pick["role"])
            dash = dashes[args.theme]
            if pick["id"] == "worker":
                _, mgr = build(pick["question"], "management")  # same scope, same governed statuses
                html_doc = worker_mobile.build(dash, mgr[args.theme].tiles, pick["plant"], args.theme)
                size = (worker_mobile.PW, worker_mobile.PH)
            else:
                html_doc, _ = compose.build(dash, pick["preset"], pick["params"], pick["role"], args.theme, dict(as_of="synthetic data pack"))
                html_doc = re.sub(r"<div class=tag>.*?</div></div>", "</div>", html_doc, count=1)  # no debug tag
                size = (compose.W, compose.H)
            path = out / "html" / f"{pick['id']}.html"
            path.write_text(html_doc, encoding="utf-8")
            page = browser.new_page(viewport={"width": size[0], "height": size[1]}, device_scale_factor=2)
            page.goto(path.as_uri())
            page.wait_for_function("window.__done===true", timeout=30000)
            page.screenshot(path=str(out / f"{pick['id']}.png"))
            page.close()
            print(pick["id"], size, "->", out / f"{pick['id']}.png", flush=True)
        browser.close()


if __name__ == "__main__":
    main()
