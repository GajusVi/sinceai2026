id: 1107-004512-gajus-to-margiris
from: gajus
to: margiris
kind: breaks
created: 2026-11-07 00:45
re: 
---
At ff3f563 the rules parser returns CLARIFY for 9 of 10 Business_Requests templates because ordinary words land in unmapped_terms: Power BI, Tableau, workbook, finance, performance, supply risk, launch, executive, Bayer Pharma (steward/config.py STOPWORDS / linking.py). Not a test failure, but it blocks the D5 hold-out and the demo. Need a stopword or phrase fix before S3 Sat 12:00. Already under Requests in NOTES.
