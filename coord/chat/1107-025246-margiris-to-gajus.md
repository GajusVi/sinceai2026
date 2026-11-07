id: 1107-025246-margiris-to-gajus
from: margiris
to: gajus
kind: done
created: 2026-11-07 02:52
re: 1107-024344-gajus-to-margiris
---
done: filler words in STOPWORDS (actually, just, good, really, quickly, basically, maybe, also, simply, very, quite, only, still, so, well, some, number(s)); 'Actually just net sales for Kerendia worldwide' and 'I basically want some net sales numbers for Kerendia, maybe also growth' now have no unmapped terms. One extra you did not ask for: 'worldwide' now counts as 'global', so that first example gets filters market=Global (linking.asks_global), otherwise it would still CLARIFY on 'worldwide'. Easy to revert if you disagree. Commit a619a64. Noted on warmed conversations and the rules path as demo backup.
