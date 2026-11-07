# Stage seed for the steward data dir (T1.6)

`make demo` / `make ui` copy this folder to a fresh temporary `STEWARD_DATA_DIR` at start, so rehearsal approvals
(journal.jsonl, catalog_changes.json, specs/, floor_requests.jsonl) never reach the stage run.

Empty on purpose: the stage starts from the data pack as delivered. To stage a prepared state (e.g. one approved
request in the journal), put the files here and commit them; never copy data/steward/ in blindly.
