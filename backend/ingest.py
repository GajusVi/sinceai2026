"""Turn whatever the company hands over (csv, xlsx, jsonl, json, pdf, docx, txt) into Items."""

import io
import json
from pathlib import Path

import pandas as pd

from .models import Item

TEXT_HINTS = ["text", "description", "body", "message", "content", "summary", "comment", "notes", "subject"]
ID_HINTS = ["id", "ticket_id", "case_id", "number", "key"]


def _pick(cols: list[str], hints: list[str]) -> str | None:
    low = {c.lower(): c for c in cols}
    for h in hints:
        if h in low:
            return low[h]
    for h in hints:
        for lc, c in low.items():
            if h in lc:
                return c
    return None


def from_dataframe(df: pd.DataFrame, text_col: str | None = None, id_col: str | None = None) -> list[Item]:
    df = df.fillna("")
    text_col = text_col or _pick(list(df.columns), TEXT_HINTS)
    if text_col is None:  # no obvious text column: join all string columns
        df["_text"] = df.astype(str).agg(" | ".join, axis=1)
        text_col = "_text"
    id_col = id_col or _pick(list(df.columns), ID_HINTS)
    items = []
    for i, row in df.iterrows():
        meta = {k: v for k, v in row.items() if k not in (text_col, "_text")}
        items.append(Item(id=str(row[id_col]) if id_col else f"row-{i}", text=str(row[text_col]), meta=meta))
    return items


def _doc_text(name: str, data: bytes) -> str:
    suffix = Path(name).suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader

        return "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(data)).pages)
    if suffix == ".docx":
        from docx import Document

        return "\n".join(p.text for p in Document(io.BytesIO(data)).paragraphs)
    return data.decode("utf-8", errors="replace")


def load(name: str, data: bytes) -> list[Item]:
    suffix = Path(name).suffix.lower()
    if suffix == ".csv":
        return from_dataframe(pd.read_csv(io.BytesIO(data)))
    if suffix in (".xlsx", ".xls"):
        return from_dataframe(pd.read_excel(io.BytesIO(data)))
    if suffix == ".jsonl":
        rows = [json.loads(line) for line in data.decode().splitlines() if line.strip()]
        return from_dataframe(pd.DataFrame(rows))
    if suffix == ".json":
        obj = json.loads(data)
        return from_dataframe(pd.DataFrame(obj if isinstance(obj, list) else [obj]))
    return [Item(id=Path(name).stem, text=_doc_text(name, data), meta={"file": name})]


def load_path(path: str | Path) -> list[Item]:
    p = Path(path)
    return load(p.name, p.read_bytes())
