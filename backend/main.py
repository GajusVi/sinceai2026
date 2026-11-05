"""FastAPI surface for integrations and the submission README. The Streamlit UI imports the
pipeline directly (one process = fewer things to break on stage)."""

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import PlainTextResponse

from . import audit, ingest, pipeline
from .config import get_settings
from .models import Item, Review, ScoredItem

app = FastAPI(title="SinceAI 2026 decision layer")


@app.get("/health")
def health() -> dict:
    s = get_settings()
    _, _, model = s.resolved()
    return {
        "ok": True,
        "provider": s.llm_provider,
        "model": model,
        "llm_ready": s.llm_ready(),
        "demo_mode": s.demo_mode,
    }


@app.post("/score", response_model=list[ScoredItem])
def score(items: list[Item]) -> list[ScoredItem]:
    return pipeline.score_all(items)


@app.post("/ingest", response_model=list[ScoredItem])
async def ingest_file(file: UploadFile = File(...)) -> list[ScoredItem]:
    return pipeline.score_all(ingest.load(file.filename or "upload.txt", await file.read()))


@app.post("/review")
def review(r: Review) -> dict:
    audit.log_review(r)
    return {"ok": True}


@app.get("/audit")
def audit_log(limit: int = 500) -> list[dict]:
    return audit.fetch(limit)


@app.get("/audit.csv", response_class=PlainTextResponse)
def audit_csv() -> str:
    return audit.to_csv(audit.fetch(10_000))
