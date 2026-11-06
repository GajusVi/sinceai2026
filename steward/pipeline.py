from __future__ import annotations

from datetime import date
from pathlib import Path

from .catalog import Catalog
from .config import Settings
from .decision import decide
from .explain import get_explainer
from .governance import Governance, today
from .health import CatalogHealth, catalog_health
from .llm import get_llm
from .models import StewardResult
from .query_parser import get_parser
from .search import CatalogSearch
from .search.semantic import Embedder, GeminiEmbedder


class Steward:
    """The whole flow: question -> parse -> search -> decide -> explain. Approval goes through `governance`."""

    def __init__(
        self,
        settings: Settings | None = None,
        catalog_dir: Path | None = None,
        data_dir: Path | None = None,
        as_of: date | None = None,
        embedder: Embedder | None = None,
    ):
        self.settings = settings or Settings.from_env()
        self.catalog_dir = catalog_dir or self.settings.catalog_dir
        self.data_dir = data_dir or self.settings.data_dir
        self.as_of = today(as_of or self.settings.as_of)
        self.llm = get_llm(self.settings)
        self.embedder = embedder or (GeminiEmbedder(self.llm) if self.llm and self.llm.supports_embeddings else None)
        self.reload()

    def reload(self) -> None:
        self.catalog = Catalog.load(self.catalog_dir, self.data_dir)
        self.search = CatalogSearch(self.catalog, self.embedder)
        self.parser = get_parser(self.catalog, self.llm, self.settings.prompts_dir)
        self.explainer = get_explainer(self.catalog, self.llm, self.settings.prompts_dir)
        self.governance = Governance(self.catalog, self.data_dir)

    def ask(self, text: str) -> StewardResult:
        question = self.parser.parse(text)
        hits = self.search.search(question)
        decision = decide(question, hits, self.catalog, self.as_of)
        explanation = self.explainer.explain(question, decision, self.as_of)
        return StewardResult(question=question, decision=decision, explanation=explanation, as_of=self.as_of)

    def health(self) -> CatalogHealth:
        return catalog_health(self.catalog, self.as_of)
