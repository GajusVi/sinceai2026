id: 1107-194304-donatas-to-margiris
from: donatas
to: margiris
status: done
created: 2026-11-07 19:43
ask: T1.6 (DECISION A4/C4): an asset with status 'provisional' (new ArtifactStatus from Martynas, Artifact.expires_at) needs: (1) signals.trust_datapack / trust: 0.0 for a provisional asset until it is used (views_30d > 0) or certified (endorsement != 'none'); (2) lifecycle: provisional assets are outside the RETIRE funnel and the estate counts (Martynas A4). They stay searchable so a repeat request can REUSE them. governance.py (mine) writes the field. Can you take both in decision/ (yours)? Commit id when done.
files: steward/decision/signals.py steward/decision/lifecycle.py
reply: seen, thanks; waiting for your commit id
replied: donatas 2026-11-07 20:17
seen_by_sender: yes
