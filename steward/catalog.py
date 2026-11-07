from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .models import Artifact, ArtifactStatus, DimensionDefinition, MetricDefinition

CHANGES_FILE = "catalog_changes.json"


class Catalog:
    """Sample catalog from `catalog/` plus approved changes from `data/catalog_changes.json`."""

    def __init__(
        self,
        artifacts: list[Artifact],
        metrics: list[MetricDefinition],
        dimensions: list[DimensionDefinition],
    ):
        self.artifacts = {a.id: a for a in artifacts}
        self.metrics = {m.id: m for m in metrics}
        self.dimensions = {d.id: d for d in dimensions}

    @classmethod
    def load(cls, catalog_dir: Path, data_dir: Path | None = None, as_of: date | None = None) -> Catalog:
        artifacts = [Artifact.model_validate(a) for a in read_json(catalog_dir / "artifacts.json")]
        metrics = [MetricDefinition.model_validate(m) for m in read_json(catalog_dir / "metrics.json")]
        dimensions = [DimensionDefinition.model_validate(d) for d in read_json(catalog_dir / "dimensions.json")]

        artifacts = apply_changes(artifacts, data_dir, as_of)
        return cls(artifacts, metrics, dimensions)

    def active_artifacts(self) -> list[Artifact]:
        return [a for a in self.artifacts.values() if a.status != ArtifactStatus.SUPERSEDED]

    def artifact(self, artifact_id: str) -> Artifact:
        return self.artifacts[artifact_id]

    def metric(self, metric_id: str) -> MetricDefinition:
        return self.metrics[metric_id]

    def dimension(self, dimension_id: str) -> DimensionDefinition:
        return self.dimensions[dimension_id]

    def dimension_value_label(self, dimension_id: str, value_id: str) -> str:
        dimension = self.dimensions.get(dimension_id)
        if dimension:
            for value in dimension.values:
                if value.id == value_id:
                    return value.label
        return value_id


def apply_changes(artifacts: list[Artifact], data_dir: Path | None, as_of: date | None = None) -> list[Artifact]:
    """Adds approved artifacts and marks superseded ones from `data_dir/catalog_changes.json`.

    A PROVISIONAL asset added by an approval (DECISION C4) is dropped once `expires_at` is before `as_of`; it stays
    searchable until then. `as_of=None` keeps everything. Assets of the base catalog are never dropped."""
    changes_path = data_dir / CHANGES_FILE if data_dir else None
    if not (changes_path and changes_path.exists()):
        return artifacts
    changes = read_json(changes_path)
    added = [Artifact.model_validate(a) for a in changes.get("added", [])]
    if as_of is not None:
        added = [
            a
            for a in added
            if not (a.status == ArtifactStatus.PROVISIONAL and a.expires_at is not None and a.expires_at < as_of)
        ]
    artifacts = artifacts + added
    superseded = set(changes.get("superseded", []))
    return [
        a.model_copy(update={"status": ArtifactStatus.SUPERSEDED}) if a.id in superseded else a for a in artifacts
    ]


def read_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)
