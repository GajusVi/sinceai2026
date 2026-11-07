"""PROVISIONAL assets (DECISION C4/A4): searchable until expires_at, then dropped; the base catalog is never touched."""

import json
from datetime import date

from steward.catalog import CHANGES_FILE, apply_changes
from steward.config import ROOT_DIR
from steward.datapack import DEFAULT_XLSX, load_artifacts, load_catalog
from steward.models import Artifact, ArtifactStatus

BAYER = ROOT_DIR / "catalog" / "bayer"


def _base() -> list[Artifact]:
    return load_artifacts(DEFAULT_XLSX)  # the data pack: no dependency on the invented sample catalog


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


def test_provisional_stays_searchable_and_load_catalog_passes_as_of(tmp_path):
    base = _base()
    _write(tmp_path, [_added(base, "NEW-LIVE", ArtifactStatus.PROVISIONAL, date(2026, 12, 1))])
    live = load_catalog(DEFAULT_XLSX, BAYER, tmp_path, as_of=date(2026, 11, 7))
    assert "NEW-LIVE" in {a.id for a in live.active_artifacts()}  # a repeat request can REUSE it
    gone = load_catalog(DEFAULT_XLSX, BAYER, tmp_path, as_of=date(2027, 1, 1))
    assert "NEW-LIVE" not in gone.artifacts
