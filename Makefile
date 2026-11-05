PY := .venv/bin/python
.PHONY: extras setup ui demo api eval warm test lint ping models hack unhack freeze

setup:      ## install/repair everything (idempotent)
	./setup_mac.sh

extras:     ## track extras: forecasting, privacy, routing, graphs (uses ./wheelhouse if offline)
	uv pip install --python $(PY) --find-links wheelhouse -r requirements-extras.in

ui:         ## Streamlit decision screen, live LLM
	$(PY) -m streamlit run frontend/app.py

demo:       ## same UI, replays demo/cache only (stage mode)
	DEMO_MODE=1 $(PY) -m streamlit run frontend/app.py

api:        ## FastAPI on :8000 (docs at /docs)
	$(PY) -m uvicorn backend.main:app --reload --port 8000

eval:       ## hold-out accuracy / F1 / misses -> eval/results.json
	$(PY) eval/eval.py

warm:       ## record live outputs for demo inputs + hold-out into demo/cache (run Saturday)
	$(PY) -c "from backend import ingest, pipeline; from backend.config import ROOT; [pipeline.score_all(ingest.load_path(ROOT/p), log=False) for p in ('demo/inputs.jsonl',)]" && $(PY) eval/eval.py

ping:       ## one-token call to check key + model
	$(PY) -m backend.llm

models:     ## list model IDs for the active LLM_PROVIDER
	$(PY) -m backend.llm models

test:
	DEMO_MODE=1 $(PY) -m pytest -q

lint:
	$(PY) -m ruff check . --fix && $(PY) -m ruff format .

freeze:
	uv pip freeze --python $(PY) > requirements.lock.txt

hack:       ## keep the Mac awake, check battery/disk/network
	./hackmode.sh on

unhack:
	./hackmode.sh off
