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
            return load_catalog(self.catalog_dir, ROOT_DIR / "catalog" / "bayer", self.data_dir, self.as_of)
        if os.getenv("STEWARD_CATALOG", "").lower() == "datapack":
            return load_catalog(DEFAULT_XLSX, self.catalog_dir / "bayer", self.data_dir, self.as_of)
        return Catalog.load(self.catalog_dir, self.data_dir)

    def ask(self, text: str, context: dict[str, str] | None = None) -> StewardResult:
        """`context` = request metadata ({"product": ..., "market": ...}). Text that contradicts it (blocker) forces
        CLARIFY; metadata only broader or narrower than the text (confirm) adds a warning Evidence, the verdict follows
        the text.

        AI-first (Sat 7 Nov): with an LLM on the data pack, the LLM reads the request into an Intent (code validates
        every id), the rules engine decides, and the LLM investigates the evidence (advisory trail). The rules parser
        is the offline fallback."""
        blocking, confirm = self._context(text, context)
        if self.llm is not None and self._on_datapack():
            result = self._ask_ai(text, blocking, confirm)
            if result is not None:
                return result
        question = self.parser.parse(text)
        question.conflicts.extend(blocking)
        hits = self.search.search(question)
        decision = decide(question, hits, self.catalog, self.as_of)
        for c in confirm:
            decision.evidence.append(Evidence(claim=f"Confirm with the requester: {c}", severity="warning"))
        explanation = self.explainer.explain(question, decision, self.as_of) + self._horizon_note(question, decision)
        return StewardResult(question=question, decision=decision, explanation=explanation, as_of=self.as_of)

    def _context(self, text: str, context: dict[str, str] | None) -> tuple[list[str], list[str]]:
        if not context:
            return [], []
        from .requests import blockers, confirmations, context_conflicts

        found = context_conflicts(text, context, self.catalog)
        return blockers(found), confirmations(found)

    def _on_datapack(self) -> bool:
        from .linking import kpi_index

        return bool(kpi_index(self.catalog)[0])

    def _ask_ai(self, text: str, blocking: list[str], confirm: list[str]) -> StewardResult | None:
        """LLM understanding -> rules decision -> LLM investigation and explanation (in parallel). None = the LLM
        understood nothing usable (no metric, product or site): the caller falls back to the rules parser."""
        state = self.interviewer.start(text, mode="expert", conflicts=blocking)
        intent = state.intent
        if not (intent.metric_ids or intent.products or intent.sites or intent.theme):
            return None
        if intent.ignored_terms and not (intent.products or intent.sites):
            # "Roundup sales in Brazil": the unknown product was set aside and the scope widened to All Pharma, so a
            # foreign product would build. The rules parser keeps the word unmapped and answers CLARIFY naming it.
            return None
        result = self.ask_intent(intent, explain=False)
        for c in confirm:
            result.decision.evidence.append(Evidence(claim=f"Confirm with the requester: {c}", severity="warning"))
        from concurrent.futures import ThreadPoolExecutor

        from .investigate import investigate

        summary, estate, gaps = self._dossier_inputs(intent)
        with ThreadPoolExecutor(max_workers=2) as pool:
            inv = pool.submit(
                investigate, self.llm, self.settings.prompts_dir, text, summary, result.decision, estate, gaps
            )
            expl = pool.submit(self.explainer.explain, result.question, result.decision, self.as_of)
            explanation = expl.result()
            investigation = inv.result()
        adopted = self._adopt_asset(intent, investigation, result)
        if adopted is not None:  # the AI found the asset the request is about: decide again on its KPIs
            result = adopted
            explanation = self.explainer.explain(result.question, result.decision, self.as_of)
        explanation += self._horizon_note(result.question, result.decision)
        return result.model_copy(update={"explanation": explanation, "investigation": investigation})

    def _dossier_inputs(self, intent) -> tuple[str, list, list[str]]:
        """What the AI investigation reads besides the decision: the understood scope, the other assets of the
        requested products (most used first) and the governed KPIs without source data."""
        from .semantic import feasibility

        gaps = [f"{m.kpi_id} {m.name}" for m in feasibility(intent).gaps]
        products = set(intent.products)
        estate = sorted(
            (a for a in self.catalog.active_artifacts() if a.product_scope in products),
            key=lambda a: -sum(u.unique_users for u in a.usage),
        )
        summary = intent.model_dump_json(include={"products", "markets", "regions", "sites", "metric_ids", "theme"})
        return summary, estate, gaps

    def investigate(self, result: StewardResult, intent) -> StewardResult:
        """The AI investigation for a result that has none yet (the interview path). No LLM: unchanged."""
        if self.llm is None or result.investigation is not None or not self._on_datapack():
            return result
        from .investigate import investigate

        summary, estate, gaps = self._dossier_inputs(intent)
        inv = investigate(
            self.llm, self.settings.prompts_dir, result.question.text, summary, result.decision, estate, gaps
        )
        return result.model_copy(update={"investigation": inv})

    def _adopt_asset(self, intent, investigation, result: StewardResult) -> StewardResult | None:
        """CLARIFY only because no metric was named ("replace our Tableau Xarelto workbook"), no open conflict, and the
        AI investigation named the asset the request is about: its canonical metrics become the request, flagged as
        an AI proposal the requester confirms. The rules engine then decides again (e.g. EXTEND + MIGRATE)."""
        from .linking import asset_metric_ids
        from .models import Verdict

        if investigation is None or not investigation.best_asset_id or intent.metric_ids or intent.conflicts:
            return None
        if result.decision.verdict != Verdict.CLARIFY:
            return None
        asset = self.catalog.artifacts.get(investigation.best_asset_id)
        metrics = sorted(asset_metric_ids(asset, self.catalog)) if asset else []
        if not metrics:
            return None
        proposed = intent.model_copy(update={"metric_ids": metrics})
        again = self.ask_intent(proposed, explain=False)
        again.decision.evidence.insert(
            0,
            Evidence(
                claim=f'AI proposal: the request is about {asset.id} "{asset.title}"; its governed KPIs are used as the '
                "scope. Confirm with the requester.",
                record_ids=[asset.id],
                severity="warning",
            ),
        )
        return again

    def _horizon_note(self, question, decision) -> str:
        """F7: a period outside the months the data covers is said out loud (evidence + a line in the answer)."""
        from .linking import kpi_index

        if not kpi_index(self.catalog)[0]:  # only the data pack has a known time range
            return ""
        from .decision.horizon import period_evidence
        from .semantic import load_frames

        months = load_frames()["dim_month"]["month"]
        found = period_evidence(question.text, question.period, months.min().date(), months.max().date())
        if found is None:
            return ""
        decision.evidence.append(found)
        return "\n\n**Note:** " + found.claim

    def ask_intent(self, intent, explain: bool = True) -> StewardResult:
        """The interview's end: the confirmed Intent goes through the same search -> decide -> explain as `ask`;
        then `build(result, intent)` makes the dashboard. A site scope (Plant-B) has no asset-level equivalent:
        search runs on the metrics and the site becomes a data filter of the dashboard (semantic._scope)."""
        question = intent.to_parsed_question(self.catalog)
        hits = self.search.search(question)
        decision = decide(question, hits, self.catalog, self.as_of)
        if intent.sites:
            decision.evidence.append(
                Evidence(
                    claim="Scope is a supply site: "
                    + ", ".join(intent.sites)
                    + " (every product and market it supplies, from Supply_Operations)",
                    severity="info",
                    record_ids=list(intent.sites),
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
        if not explain:  # _ask_ai explains in parallel with the investigation
            return StewardResult(question=question, decision=decision, explanation="", as_of=self.as_of)
        explanation = self.explainer.explain(question, decision, self.as_of) + self._horizon_note(question, decision)
        return StewardResult(question=question, decision=decision, explanation=explanation, as_of=self.as_of)

    def build(self, result: StewardResult, intent=None, user=None) -> StewardResult:
        """W3 feasibility -> W5 spec -> W6 lint. Returns a copy of `result` with `.spec` set; `.spec` stays None when the
        verdict builds nothing (CLARIFY, NOT_FEASIBLE) or on the sample catalog. Without an interview there is no Intent:
        it is derived from the parsed question."""
        from .linking import kpi_index

        if not kpi_index(self.catalog)[0]:
            return result
        from .intent import intent_from_parsed
        from .layout import Layouter
        from .semantic import feasibility
        from .specbuild import build_spec, spec_hash

        intent = intent or intent_from_parsed(result.question, self.catalog)
        layouter = Layouter(self.llm, self.settings.prompts_dir, user)  # who reads it decides the order (layout.py)
        spec = build_spec(result.decision, intent, self.catalog, feasibility(intent), layouter)
        if spec is not None:
            try:
                from .lint import lint  # Margiris's N5; until it lands the spec simply has no lint results
            except ImportError:
                pass
            else:
                spec.lint = lint(spec, self.catalog, self.as_of)
                spec.provenance["spec_hash"] = spec_hash(spec)  # lint is not part of the hash
        return result.model_copy(update={"spec": spec})

    def health(self) -> CatalogHealth:
        return catalog_health(self.catalog, self.as_of)
