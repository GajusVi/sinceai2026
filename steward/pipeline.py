from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from .catalog import Catalog
from .config import ROOT_DIR, Settings
from .decision import decide
from .explain import get_explainer
from .governance import Governance, today
from .health import CatalogHealth, catalog_health
from .llm import get_llm
from .models import Evidence, StewardResult
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
        self.catalog = self._load_catalog()
        self.search = CatalogSearch(self.catalog, self.embedder)
        self.parser = get_parser(self.catalog, self.llm, self.settings.prompts_dir)
        self.explainer = get_explainer(self.catalog, self.llm, self.settings.prompts_dir)
        self.governance = Governance(self.catalog, self.data_dir)
        from .interview import Interviewer  # grill-me: novice users are interviewed before anything is decided

        self.interviewer = Interviewer(self.catalog, self.llm, self.settings.prompts_dir)

    def _load_catalog(self) -> Catalog:
        """STEWARD_CATALOG=datapack (or catalog_dir = the .xlsx) uses the Bayer data pack and catalog/bayer/."""
        from .datapack import DEFAULT_XLSX, load_catalog  # lazy: pandas only needed for the data pack

        if self.catalog_dir.suffix == ".xlsx":
            return load_catalog(self.catalog_dir, ROOT_DIR / "catalog" / "bayer", self.data_dir)
        if os.getenv("STEWARD_CATALOG", "").lower() == "datapack":
            return load_catalog(DEFAULT_XLSX, self.catalog_dir / "bayer", self.data_dir)
        return Catalog.load(self.catalog_dir, self.data_dir)

    def ask(self, text: str, context: dict[str, str] | None = None) -> StewardResult:
        """`context` = request metadata ({"product": ..., "market": ...}). Text that contradicts it (blocker) forces
        CLARIFY; metadata only broader or narrower than the text (confirm) adds a warning Evidence, the verdict follows
        the text."""
        question = self.parser.parse(text)
        confirm: list[str] = []
        if context:
            from .requests import blockers, confirmations, context_conflicts

            found = context_conflicts(text, context, self.catalog)
            question.conflicts.extend(blockers(found))
            confirm = confirmations(found)
        hits = self.search.search(question)
        decision = decide(question, hits, self.catalog, self.as_of)
        for c in confirm:
            decision.evidence.append(Evidence(claim=f"Confirm with the requester: {c}", severity="warning"))
        explanation = self.explainer.explain(question, decision, self.as_of)
        return StewardResult(question=question, decision=decision, explanation=explanation, as_of=self.as_of)

    def ask_intent(self, intent) -> StewardResult:
        """The interview's end: the confirmed Intent goes through the same search -> decide -> explain as `ask`;
        then `build(result, intent)` makes the dashboard. A site scope (Plant-B) has no asset-level equivalent:
        search runs on the metrics and the site becomes a data filter of the dashboard (semantic._scope)."""
        question = intent.to_parsed_question()
        hits = self.search.search(question)
        decision = decide(question, hits, self.catalog, self.as_of)
        if intent.sites:
            decision.evidence.append(
                Evidence(
                    claim="Scope is a supply site: " + ", ".join(intent.sites)
                    + " (every product and market it supplies, from Supply_Operations)",
                    severity="info", record_ids=list(intent.sites),
                )
            )
        if intent.ignored_terms:
            decision.evidence.append(
                Evidence(claim="Not used (not a governed term): " + ", ".join(intent.ignored_terms), severity="info")
            )
        theme = self.interviewer.themes.get(intent.theme, {})
        if theme.get("not_governed"):
            decision.evidence.append(
                Evidence(
                    claim="Not measured in governed data yet (a domain owner must define it first): "
                    + ", ".join(theme["not_governed"]),
                    severity="info",
                )
            )
        explanation = self.explainer.explain(question, decision, self.as_of)
        return StewardResult(question=question, decision=decision, explanation=explanation, as_of=self.as_of)

    def build(self, result: StewardResult, intent=None) -> StewardResult:
        """W3 feasibility -> W5 spec -> W6 lint. Returns a copy of `result` with `.spec` set; `.spec` stays None when the
        verdict builds nothing (CLARIFY, NOT_FEASIBLE) or on the sample catalog. Without an interview there is no Intent:
        it is derived from the parsed question."""
        from .linking import kpi_index

        if not kpi_index(self.catalog)[0]:
            return result
        from .intent import intent_from_parsed
        from .semantic import feasibility
        from .specbuild import build_spec, spec_hash

        intent = intent or intent_from_parsed(result.question, self.catalog)
        spec = build_spec(result.decision, intent, self.catalog, feasibility(intent))
        if spec is not None:
            try:
                from .lint import lint  # Margiris's N5; until it lands the spec simply has no lint results
            except ImportError:
                pass
            else:
                spec.lint = lint(spec, self.catalog)
                spec.provenance["spec_hash"] = spec_hash(spec)  # lint is not part of the hash
        return result.model_copy(update={"spec": spec})

    def health(self) -> CatalogHealth:
        return catalog_health(self.catalog, self.as_of)
