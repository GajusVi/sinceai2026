id: 1107-201019-martynas-to-gajus
from: martynas
to: gajus
kind: need
created: 2026-11-07 20:10
re: 
---
FYI for T1.6: models.py/catalog.py are on main (2f5fe98): PROVISIONAL + expires_at + apply_changes(.., as_of=None). One line is yours: steward/datapack.py:222 apply_changes(load_artifacts(xlsx), data_dir) should become load_catalog(xlsx, catalog_dir, data_dir, as_of=None) -> apply_changes(..., as_of), and pipeline._load_catalog should pass self.as_of. Until then expired provisional assets are not dropped on the data pack. Small, 10 min; I can do it if you give me dibs on datapack.py.
