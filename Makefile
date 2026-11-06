PY := .venv/bin/python
.PHONY: extras setup ui demo bayer ui-old ask api eval warm test lint ping models hack unhack freeze

setup:      ## install/repair everything (idempotent)
	./setup_mac.sh

extras:     ## track extras: forecasting, privacy, routing, graphs (uses ./wheelhouse if offline)
	uv pip install --python $(PY) --find-links wheelhouse -r requirements-extras.in

ui:         ## BI Steward screen (LLM if a key is in .env, else rules + templates)
	$(PY) -m streamlit run frontend/steward_app.py

demo:       ## BI Steward screen with the LLM forced off (stage-safe, no network)
	STEWARD_USE_LLM=off $(PY) -m streamlit run frontend/steward_app.py

bayer:      ## BI Steward on the Bayer data pack (360 assets)
	STEWARD_CATALOG=datapack $(PY) -m streamlit run frontend/steward_app.py

ask:        ## one question from the terminal: make ask Q="Net sales by market"
	$(PY) -m steward "$(Q)"

ui-old:     ## pre-event scaffold screen (backend/), kept until removed
	$(PY) -m streamlit run frontend/app.py

api:        ## FastAPI on :8000 (docs at /docs)
	$(PY) -m uvicorn backend.main:app --reload --port 8000

eval:       ## hold-out accuracy / F1 / misses -> eval/results.json
	$(PY) eval/eval.py

warm:       ## record live outputs for demo inputs + hold-out into demo/cache (run Saturday)
	$(PY) -m backend.warm && $(PY) eval/eval.py

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
