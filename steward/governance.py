"""Human approval. Nothing in the catalog changes until a person approves a verdict, and every decision is logged."""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

from .catalog import CHANGES_FILE, Catalog
from .models import (
    Artifact,
    ArtifactMetric,
    ArtifactStatus,
    GapKind,
    JournalAction,
    JournalEntry,
    StewardResult,
    Verdict,
)

JOURNAL_FILE = "journal.jsonl"


class Governance:
    def __init__(self, catalog: Catalog, data_dir: Path):
        self.catalog = catalog
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def approve(self, result: StewardResult, actor: str, owner: str | None = None) -> JournalEntry:
        decision = result.decision
        best = decision.best
        created: Artifact | None = None

        if decision.verdict == Verdict.CLARIFY:
            raise ValueError("Cannot approve a question without a metric: clarify the question first.")
        blocks = [r for r in (result.spec.lint if result.spec else []) if r.status == "block"]
        if blocks:  # W6 lint gate: a block means approve is disabled
            raise ValueError("Blocked by the lint gate: " + "; ".join(f"{r.rule_id} {r.message}" for r in blocks))
        if decision.verdict == Verdict.EXTEND:
            created = self._extend(best.artifact, result, owner)
        elif decision.verdict == Verdict.CREATE:
            if not owner:
                raise ValueError("A new report needs an owner.")
            created = self._create(result, owner)

        self._save_spec(result)
        return self._log(
            result,
            actor,
            JournalAction.APPROVED,
            created_artifact_id=created.id if created else None,
        )

    def reject(self, result: StewardResult, actor: str, reason: str) -> JournalEntry:
        if not reason.strip():
            raise ValueError("Please give a reason for rejecting.")
        return self._log(result, actor, JournalAction.REJECTED, reason=reason)

    def propose(self, artifact_id: str, kind: str, actor: str, reason: str, detail: str = "") -> JournalEntry:
        """Journal a proposal (e.g. propose successor, retire candidate). Nothing in the catalog changes."""
        if not reason.strip():
            raise ValueError("Please give a reason for the proposal.")
        entry = JournalEntry(
            timestamp=datetime.now(timezone.utc),
            actor=actor,
            question=f"PROPOSAL (not applied): {kind} {detail} for {artifact_id}".replace("  ", " "),
            verdict=Verdict.CLARIFY,
            action=JournalAction.PROPOSED,  # recorded only, catalog unchanged
            artifact_id=artifact_id,
            reason=reason,
        )
        with open(self.data_dir / JOURNAL_FILE, "a", encoding="utf-8") as f:
            f.write(entry.model_dump_json() + "\n")
        return entry

    def entries(self) -> list[JournalEntry]:
        path = self.data_dir / JOURNAL_FILE
        if not path.exists():
            return []
        with open(path, encoding="utf-8") as f:
            return [JournalEntry.model_validate_json(line) for line in f if line.strip()]

    def _extend(self, artifact: Artifact, result: StewardResult, owner: str | None) -> Artifact:
        gaps = result.decision.best.gaps
        metrics = list(artifact.metrics)
        dimensions = list(artifact.dimensions)
        for gap in gaps:
            if gap.kind == GapKind.METRIC:
                official = self.catalog.metric(gap.key)
                metrics.append(ArtifactMetric(label=official.name, formula=official.formula))
            elif gap.kind in (GapKind.DIMENSION, GapKind.FILTER) and gap.key not in dimensions:
                dimensions.append(gap.key)

        trust_keys = {g.key for g in gaps if g.kind == GapKind.TRUST}
        new_owner = owner or artifact.owner
        extended = artifact.model_copy(
            update={
                "id": f"{artifact.family_id}-v{artifact.version + 1}",
                "metrics": metrics,
                "dimensions": dimensions,
                "version": artifact.version + 1,
                "previous_id": artifact.id,
                "owner": new_owner,
                "owner_active": bool(new_owner) and (artifact.owner_active or owner is not None),
                "certified": artifact.certified or "certification" in trust_keys,
                "last_refreshed": result.as_of,
                "views_30d": 0,
                "status": ArtifactStatus.ACTIVE,
            }
        )
        self._save_change(added=extended, superseded=artifact.id)
        return extended

    def _create(self, result: StewardResult, owner: str) -> Artifact:
        question = result.question
        slug = re.sub(r"[^a-z0-9]+", "-", "-".join(question.metrics).lower()).strip("-") or "report"
        index = sum(1 for a in self.catalog.artifacts if a.startswith(f"new-{slug}")) + 1
        artifact = Artifact(
            id=f"new-{slug}-{index:03d}",
            title=question.text.strip().rstrip("?"),
            type="report",
            description=f"Created by BI Steward for the question: {question.text}",
            domain=self.catalog.metric(question.metrics[0]).domain,
            metrics=[
                ArtifactMetric(label=self.catalog.metric(m).name, formula=self.catalog.metric(m).formula)
                for m in question.metrics
            ],
            dimensions=list(dict.fromkeys(question.dimensions + list(question.filters))),
            filters={},
            owner=owner,
            owner_active=True,
            certified=False,
            last_refreshed=result.as_of,
            views_30d=0,
            family_id=f"new-{slug}-{index:03d}",
            status=ArtifactStatus.DRAFT,
        )
        self._save_change(added=artifact)
        return artifact

    def _save_change(self, added: Artifact, superseded: str | None = None) -> None:
        path = self.data_dir / CHANGES_FILE
        changes = {"added": [], "superseded": []}
        if path.exists():
            with open(path, encoding="utf-8") as f:
                changes = json.load(f)
        changes["added"].append(json.loads(added.model_dump_json()))
        if superseded:
            changes["superseded"].append(superseded)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(changes, f, ensure_ascii=False, indent=2)

    def _log(
        self,
        result: StewardResult,
        actor: str,
        action: JournalAction,
        created_artifact_id: str | None = None,
        reason: str = "",
    ) -> JournalEntry:
        best = result.decision.best
        spec = result.spec
        entry = JournalEntry(
            timestamp=datetime.now(timezone.utc),
            actor=actor,
            question=result.question.text,
            verdict=result.decision.verdict,
            action=action,
            artifact_id=best.artifact.id if best else None,
            created_artifact_id=created_artifact_id,
            coverage=best.coverage if best else None,
            trust=best.trust if best else None,
            reason=reason,
            spec_hash=spec.provenance.get("spec_hash", "") if spec else "",
            lint=lint_summary(spec.lint) if spec else "",
            layout_source=spec.provenance.get("layout_source", "") if spec else "",
        )
        with open(self.data_dir / JOURNAL_FILE, "a", encoding="utf-8") as f:
            f.write(entry.model_dump_json() + "\n")
        return entry

    def _save_spec(self, result: StewardResult) -> None:
        """The approved spec itself, named by its hash: a journal entry always traces to the exact dashboard."""
        spec = result.spec
        if spec is None or not spec.provenance.get("spec_hash"):
            return
        folder = self.data_dir / "specs"
        folder.mkdir(exist_ok=True)
        (folder / f"{spec.provenance['spec_hash']}.json").write_text(spec.model_dump_json(indent=2), encoding="utf-8")


def lint_summary(results) -> str:
    counts = {s: sum(r.status == s for r in results) for s in ("pass", "warn", "block")}
    return ", ".join(f"{n} {s}" for s, n in counts.items()) if results else "not linted"


def today(as_of: date | None) -> date:
    return as_of or date.today()
