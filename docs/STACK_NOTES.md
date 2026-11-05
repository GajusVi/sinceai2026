# Stack notes and gotchas

## Streamlit
- Row selection: `st.dataframe(df, on_select="rerun", selection_mode="single-row")` → `event.selection.rows`.
- Keep scored results in `st.session_state`, or every click re-scores.
- Every widget inside a loop needs a unique `key=`.
- Headless UI test: `streamlit.testing.v1.AppTest` (see tests/test_smoke.py).
- Theme lives in `.streamlit/config.toml` (flat, green accent).

## FastAPI
- Interactive docs at `http://127.0.0.1:8000/docs` once `make api` runs: good screenshot for the README.
- File upload needs `python-multipart` (installed).

## Retrieval
- `Index().build(texts, ids).search(query, k)` returns `(id, score, text)`.
- fastembed model `BAAI/bge-small-en-v1.5` is cached in `./models` by setup. For Finnish text, swap `EMBED_MODEL` to a multilingual model (e.g. `intfloat/multilingual-e5-small`) and re-run setup once on good Wi-Fi.

## Numbers beat LLMs on numbers
- Forecasting: `statsmodels` (ExponentialSmoothing, SARIMAX). Classification on tabular data: scikit-learn (`HistGradientBoostingClassifier`).
- Use the LLM to explain the number, not to compute it.

## Intel Mac
- No torch beyond 2.2.2 (and it needs numpy < 2). Not installed on purpose.
- Offline reinstall: `uv pip install --offline -r requirements.lock.txt` uses uv's cache in ~/.cache/uv. Mac only: the lock pins uvloop, which has no Windows build.

## Demo safety
- `make warm` on Saturday with the real key: records outputs for demo inputs into demo/cache.
- `make demo` on Sunday: replays them; items missing from the cache fall back to rules (source = rules), never crash.

## Track extras (make extras) — checked 5 Nov 2026 on Intel macOS / Py 3.11
- Forecast attributions: `lgb_model.predict(X, pred_contrib=True)` (last column = bias). No shap (needs numba; no Intel-Mac wheels for current numba).
- Intervals: MAPIE v1 `SplitConformalRegressor` / `ConformalizedQuantileRegressor` (docs/vendor/mapie-README.md).
- Differential privacy: OpenDP (`import opendp.prelude as dp; dp.enable_features("contrib")`). diffprivlib is broken on scikit-learn 1.9.
- Federated learning: Flower + scikit-learn, template in docs/vendor/flower-quickstart-sklearn/. Offline demo data with no download: `sklearn.datasets.load_breast_cancer()` (features computed from imaging), split across 3 fake hospitals.
- Routing: OR-Tools VRP sample in docs/vendor/ortools-vrp_capacity.py.
- Offline: wheels for all extras are in ./wheelhouse (380 MB).
