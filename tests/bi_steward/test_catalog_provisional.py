"""PROVISIONAL assets (DECISION C4/A4): searchable until expires_at, then dropped; the base catalog is never touched."""

import json
from datetime import date

from steward.catalog import CHANGES_FILE, Catalog, apply_changes
from steward.config import ROOT_DIR
from steward.models import Artifact, ArtifactStatus


def _base() -> list[Artifact]:
    return [Artifact.model_validate(a) for a in json.loads((ROOT_DIR / "catalog" / "artifacts.json").read_text("utf-8"))]


def _added(base: list[Artifact], new_id: str, status: ArtifactStatus, expires: date | None) -> dict:
    return base[0].model_copy(update={"id": new_id, "status": status, "expires_at": expires}).model_dump(mode="json")


def _write(tmp_path, added: list[dict], superseded: list[str] | None = None):
    (tmp_path / CHANGES_FILE).write_text(json.dumps({"added": added, "superseded": superseded or []}), "utf-8")


def test_provisional_status_and_expiry_field_exist_and_default_to_none():
    assert ArtifactStatus.PROVISIONAL.value == "provisional"
    assert _base()[0].expires_at is None


def test_expired_provisional_is_dropped_but_a_live_one_and_other_statuses_stay(tmp_path):
    base = _base()
    _write(
        tmp_path,
        [
            _added(base, "NEW-EXPIRED", ArtifactStatus.PROVISIONAL, date(2026, 11, 1)),
            _added(base, "NEW-LIVE", ArtifactStatus.PROVISIONAL, date(2026, 12, 1)),
            _added(base, "NEW-ACTIVE-OLD-DATE", ArtifactStatus.ACTIVE, date(2026, 1, 1)),  # only provisional expires
            _added(base, "NEW-NO-DATE", ArtifactStatus.PROVISIONAL, None),
        ],
    )
    ids = {a.id for a in apply_changes(base, tmp_path, as_of=date(2026, 11, 7))}
    assert "NEW-EXPIRED" not in ids
    assert {"NEW-LIVE", "NEW-ACTIVE-OLD-DATE", "NEW-NO-DATE"} <= ids
    assert {a.id for a in base} <= ids  # the base catalog is never dropped


def test_without_as_of_everything_is_kept_and_the_expiry_day_itself_is_still_valid(tmp_path):
    base = _base()
    _write(tmp_path, [_added(base, "NEW-EXPIRED", ArtifactStatus.PROVISIONAL, date(2026, 11, 1))])
    assert "NEW-EXPIRED" in {a.id for a in apply_changes(base, tmp_path)}  # None = keep all
    assert "NEW-EXPIRED" in {a.id for a in apply_changes(base, tmp_path, as_of=date(2026, 11, 1))}  # expires_at < as_of
    assert "NEW-EXPIRED" not in {a.id for a in apply_changes(base, tmp_path, as_of=date(2026, 11, 2))}


def test_provisional_stays_searchable_and_catalog_load_passes_as_of(tmp_path):
    base = _base()
    _write(tmp_path, [_added(base, "NEW-LIVE", ArtifactStatus.PROVISIONAL, date(2026, 12, 1))])
    live = Catalog.load(ROOT_DIR / "catalog", tmp_path, as_of=date(2026, 11, 7))
    assert "NEW-LIVE" in {a.id for a in live.active_artifacts()}  # a repeat request can REUSE it
    gone = Catalog.load(ROOT_DIR / "catalog", tmp_path, as_of=date(2027, 1, 1))
    assert "NEW-LIVE" not in gone.artifacts
