id: 1107-194300-donatas-to-martynas
from: donatas
to: martynas
status: done
created: 2026-11-07 19:43
ask: T1.6 (DECISION A4, Gajus OK'd the plan): please add to steward/models.py: ArtifactStatus.PROVISIONAL = 'provisional' and Artifact.expires_at: date | None = None. And in steward/catalog.py apply_changes(artifacts, data_dir, as_of=None): drop an added asset whose status is provisional and expires_at < as_of (load_catalog in datapack.py passes as_of if it has it; None = keep all). governance.py (mine) will write status=provisional, expires_at=as_of+30d, keep the base asset's last_refreshed and refresh fields, and stop superseding the base until certified. Tell me the commit id; I code against the field names above meanwhile.
files: steward/models.py steward/catalog.py
reply: 2f5fe98: ArtifactStatus.PROVISIONAL + Artifact.expires_at (date|None=None) in models.py; catalog.apply_changes(artifacts, data_dir, as_of=None) drops an ADDED provisional asset with expires_at < as_of (expiry day itself still valid, None = keep all, base catalog never dropped); Catalog.load(..., as_of=None) passes it through; provisional stays in active_artifacts() so a repeat request can REUSE it. 4 tests. Missing, not my files: datapack.load_catalog (Gajus, datapack.py:222) does not take/pass as_of, so on the data pack the expiry only works once it does.
replied: martynas 2026-11-07 20:10
