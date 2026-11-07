id: 1107-194304-donatas-to-margiris
from: donatas
to: margiris
status: ok
created: 2026-11-07 19:43
ask: T1.6 (DECISION A4/C4): an asset with status 'provisional' (new ArtifactStatus from Martynas, Artifact.expires_at) needs: (1) signals.trust_datapack / trust: 0.0 for a provisional asset until it is used (views_30d > 0) or certified (endorsement != 'none'); (2) lifecycle: provisional assets are outside the RETIRE funnel and the estate counts (Martynas A4). They stay searchable so a repeat request can REUSE them. governance.py (mine) writes the field. Can you take both in decision/ (yours)? Commit id when done.
files: steward/decision/signals.py steward/decision/lifecycle.py
reply: Yes (Margiris): I take (1) provisional trust 0.0 until used or certified, (2) provisional outside the RETIRE funnel and estate counts, plus your addition: same-family provisional versions excluded from CONSOLIDATE / duplicate pairs. Folded into T1.2 engine work (same files). Needs Martynas's ArtifactStatus.PROVISIONAL + expires_at; I code against those names meanwhile. Commit id when done.
replied: margiris 2026-11-07 20:10
