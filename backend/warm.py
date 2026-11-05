"""Record live outputs for the demo inputs into demo/cache (run Saturday): python -m backend.warm"""

from . import ingest, pipeline
from .config import ROOT, get_settings

if __name__ == "__main__":
    if get_settings().demo_mode:
        raise SystemExit("DEMO_MODE is on: warm needs live calls. Unset it and retry.")
    out = pipeline.score_all(ingest.load_path(ROOT / "demo" / "inputs.jsonl"), log=False)
    live = sum(o.source == "llm" for o in out)
    print(f"{live}/{len(out)} demo inputs answered live and cached in demo/cache")
    if live < len(out):
        print("Some fell back to cache/rules (rate limit or error): run it again before the demo.")
