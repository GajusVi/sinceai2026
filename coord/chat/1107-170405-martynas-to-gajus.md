id: 1107-170405-martynas-to-gajus
from: martynas
to: gajus
kind: question
created: 2026-11-07 17:04
re: 
---
DIBS + PROPOSAL (Martynas, dynamic dashboard, data + contract side). I agree with Margiris' proposal (1107-164716) as THE layout contract: Visual.step:int=0 and Visual.question:str='' in steward/spec.py, additive and defaulted (hierarchy = reading order; her layout.py proposes, validates, falls back to the template). Drop my tier/size idea. MY PART: (1) steward/semantic.py: profile(frames, spec) -> per measure/dimension months of history, member count, null share, gap flag; it goes into Margiris' ctx and decides which forms are legal (line needs >= 6 months, bar 3-20 members, table > 20; thresholds in config.py as assumptions). (2) steward/pbip.py: positions visuals in step order (same order as render), Visual.question becomes the visual title once the contract is agreed, gaps never exported as numbers. (3) measures.json: nothing new unless layout needs a field. FILES: steward/spec.py (field add), steward/semantic.py, steward/pbip.py, tests/bi_steward/test_pbip.py + new tests/bi_steward/test_profile.py; OWNERS already lists these as martynas. TESTS: profile on REQ-0001 + a gap case; pbip order equals step order; no gap as number. ESCALATE/ASK: OK to add step+question to spec.py now? I will not edit spec.py until you answer.
