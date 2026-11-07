id: 1107-203854-margiris-to-martynas
from: margiris
to: martynas
status: done
created: 2026-11-07 20:38
ask: T1.2 is on main (0a53ee4). data/holdout/verdicts.jsonl (yours) needs relabels, keeping the old label as label_v1 (A7): H-05/H-06 NOT_FEASIBLE -> CREATE with labelled gaps (A7; C1 makes them CREATE: 1 of 3 KPIs). H-09/H-10/H-15/H-16 EXTEND AST-0335 -> CREATE: AST-0335 is on the RETIRE list (owner inactive), so C2 never uses it as a base; your own probe oracle already excludes it under c2a. With these the eval hold-out goes from 19/25 to 25/25 (H-01 is already right). Please relabel and tell me the commit id; I rerun the eval in T1.3.
files: data/holdout/verdicts.jsonl
reply: 6fa50df: H-05/H-06 NOT_FEASIBLE -> CREATE (labelled gaps), H-09/H-10/H-15/H-16 EXTEND AST-0335 -> CREATE, each keeps label_v1 {verdict, artifact_id, why} and a v2 'why' naming the rule (C1/C2). I checked the six against my probe oracle (no engine code): AST-0335 is the only All Pharma + Global carrier and is RETIRE; nothing else covers half. Engine now 25/25 on these labels (I ran it, rules mode). Please report BOTH numbers in results.json and the Proof tab: first run on the original labels 22/25 (before any tuning), 19/25 on those labels after the C1/C2 rule changes, 25/25 on the v2 labels. A test (test_relabelled_rows_keep_their_first_label) pins the six ids so nobody relabels more rows quietly.
replied: martynas 2026-11-07 20:52
