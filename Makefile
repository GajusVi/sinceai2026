PY := .venv/bin/python
.PHONY: extras setup ui demo bayer pack-large bayer-large board ask eval eval-steward warm warm-layout app app-setup app-build test lint ping models hack unhack freeze

setup:      ## install/repair everything (idempotent)
	./setup_mac.sh

extras:     ## track extras: forecasting, privacy, routing, graphs (uses ./wheelhouse if offline)
	uv pip install --python $(PY) --find-links wheelhouse -r requirements-extras.in

ui:         ## BI Steward on the Bayer data pack, fresh copy of demo/steward_seed (LLM if a key is in .env, else rules + templates)
	D=$$(mktemp -d) && cp -R demo/steward_seed/. $$D && STEWARD_DATA_DIR=$$D STEWARD_CATALOG=datapack $(PY) -m streamlit run frontend/steward_app.py

demo:       ## BI Steward on the Bayer data pack, fresh copy of demo/steward_seed, LLM forced off (stage-safe, no network)
	D=$$(mktemp -d) && cp -R demo/steward_seed/. $$D && STEWARD_DATA_DIR=$$D STEWARD_CATALOG=datapack STEWARD_USE_LLM=off $(PY) -m streamlit run frontend/steward_app.py

app-setup:  ## install the desktop app tools (pywebview, pyinstaller)
	uv pip install --python $(PY) -r requirements-app.in

app:        ## BI Steward as a desktop app: native login window -> workspace (needs make app-setup)
	$(PY) app/main.py

app-build:  ## package dist/BI Steward.app (Mac) and run its self-test (login -> workspace -> log out)
	$(PY) tools/build_app.py
	BI_STEWARD_SELFTEST=build/selftest.txt STEWARD_USE_LLM=off "dist/BI Steward.app/Contents/MacOS/BI Steward"; cat build/selftest.txt

bayer:      ## BI Steward on the Bayer data pack (360 assets)
	STEWARD_CATALOG=datapack $(PY) -m streamlit run frontend/steward_app.py

pack-large: ## generate the large synthetic pack (same 24 sheets, 5,000 assets, 2021-2026, 10 plants; ~1 min)
	$(PY) tools/make_large_pack.py

bayer-large: ## BI Steward on the large synthetic pack (make pack-large first; startup ~40 s)
	STEWARD_CATALOG=datapack STEWARD_DATAPACK_XLSX=data/bayer_large/Bayer_Large_Synthetic_Pack.xlsx $(PY) -m streamlit run frontend/steward_app.py

set-webhook: ## put the Discord webhook URL from your clipboard into .env (type this, don't copy it)
	$(PY) tools/coord.py set-webhook

board-discord: ## refresh the live TEAM BOARD message in Discord (needs COORD_DISCORD_WEBHOOK in .env)
	$(PY) tools/coord.py discord

board:      ## team board: who is on what, open asks, commits you are behind on
	$(PY) tools/coord.py board

ask:        ## one question from the terminal: make ask Q="Net sales by market"
	$(PY) -m steward "$(Q)"

eval:       ## BI Steward eval -> eval/results.json (same as eval-steward)
	STEWARD_CATALOG=datapack $(PY) eval/eval_steward.py

eval-steward: ## BI Steward eval: false-REUSE, accuracy, intent F1, lint pass rate, 150-request estate (~10 s)
	STEWARD_CATALOG=datapack $(PY) eval/eval_steward.py

warm:       ## record the live AI layouts for the demo questions (same as warm-layout; Donatas only)
	$(PY) tools/warm_layout.py

warm-layout: ## cache the AI dashboard layout for the demo questions x roles (steward/layout_cache, live LLM)
	$(PY) tools/warm_layout.py

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
