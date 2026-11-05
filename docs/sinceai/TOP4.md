# Shortlist: what we would build (pre-briefing plan, 6 Nov)

Select in this order at 17:00: 1. Bayer  2. Lindstrom  3. Fonecta  4. Europress (Lindstrom first if Bayer looks crowded).
These are guesses from the Thursday summaries. Replace with the real brief after 19:30 (put the files in data/brief/).

## Bayer: health, safety and environment observations
- Default build (low risk): safety observation triage. User: site HSE manager. Free-text reports in; category, severity,
  likely root cause, duplicates out, in a priority queue; approve assigns a corrective action and owner.
  This is the existing scaffold: change LABELS in backend/pipeline.py and USER_ROLE in backend/config.py.
- Stretch: leading-indicator hazard radar. Embeddings + clustering per site/team, trend alerts with statsmodels,
  weekly brief with quoted evidence. Do not claim "precedes incidents" without enough incident history.
- Proof: F1 vs HSE-team labels on a held-out set; minutes per report before vs after.

## Lindstrom: textile sustainability insights
- Default build: traceable customer impact report. Contract (items, wash cycles, delivery distance) + Lindstrom
  lifecycle factors in; CO2e and water per year vs buy-and-own out, every figure traceable to its factor and source.
  Plus a claim checker that flags vague wording ("eco-friendly") with no evidence behind it.
- Stretch: what-if simulator (garment lifetime, wash temperature, routes, recycling share) with numpy Monte Carlo
  bands and Plotly sliders.
- Proof: report in minutes instead of hours; 100% of figures traceable. Depends on Lindstrom sharing its factors.

## Fonecta: keeping local business information accurate
- Default build: listing freshness checker. Listings + sources (websites, registry extracts) in; fields likely stale
  (hours, phone, address, closed?) with evidence and a suggested fix, in the approve/reject queue. rapidfuzz for matching.
- Stretch: entity resolution across sources + a model ranking which listings go stale next month.
- Proof: precision of "stale" flags on a labelled sample; listings checked per hour before vs after.

## Europress: insights from smart waste equipment
- Default build: pickup planner. Compactor/baler telemetry (fill level, press cycles, alarms) in; predicted full date
  per unit, a schedule that avoids half-empty trips and overflows, alerts for odd units. LightGBM + mapie (extras).
- Stretch: fault early-warning (anomaly ranking unless labelled failures exist) + OR-Tools routing (docs/vendor).
- Proof: trips avoided vs fixed schedule in a backtest x cost per trip; overflow days avoided.

## Same for all four
Keep the decision layer: typed objects -> score with confidence and reason -> queue -> approve/reject -> audit log.
Every euro figure on screen must come from the company or be labelled as an assumption.
