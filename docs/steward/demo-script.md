# Demo script

About 5 minutes. Before starting, clear `data/` and run `uv run streamlit run app.py`.

## 1. The problem (30 seconds)

> AI builds a dashboard in a minute. A year later the company has five hundred dashboards, three different "revenues" and nobody knows which one to believe. We built a system that first asks: does this already exist?

Open the **"Catalog health"** tab: 18 reports, with duplicates and retirement candidates. An ordinary catalog of an ordinary company.

## 2. The main question: extend, don't create (2 minutes)

Question: **"What is herbicide revenue in LATAM vs plan for Q3?"**

Show in order:

1. **How the question was understood**: two metrics (net revenue and plan), filters LATAM and herbicides, quarter.
2. **Verdict: extend** "Global Net Revenue vs Plan" from Finance. The report is certified, refreshed yesterday and has 420 views in 30 days. It covers 80% of the question; only the "herbicides" filter is missing.
3. **Conflict**: in "LATAM Sales Dashboard", "Revenue" is gross revenue, before discounts. The numbers from the two reports will not match, and now it is clear why.
4. **Other candidates**: LATAM Sales Dashboard was found too, but it lacks the official metric and the plan.

Click **"Approve the extension"**.

> We did not create a fourth dashboard. We extended the one people already trust.

## 3. The same question again: reuse (30 seconds)

Ask the same question again. Now the verdict is **"Reuse as is"**, pointing to the new version of the Finance report.

> The next person with this question gets a ready answer.

Open the **"Journal"** tab: who approved, when, for which question.

## 4. Nothing really exists: create with an owner (1 minute)

Question: **"Logistics carbon footprint by country"**.

Verdict **"Create a new report"**: the CO2 metric is in the official dictionary, but no report calculates it. The button does not work without an owner. Enter "Sustainability team" and click "Create the report".

> New things do get created, but immediately with an owner and the official formula. A year from now this report will not be an orphan.

## 5. Cleanup (30 seconds)

Go back to **"Catalog health"**: two copies of the margin report with no owner and an old 2025 revenue tracker. The system proposes retiring them and shows which report to keep.

## 6. Closing (30 seconds)

> AI in analytics should not generate more; it should help decide what deserves to exist. BI Steward reuses what people trust, extends what almost fits, creates new things only with an owner and removes the clutter. A human always has the final word.

## Backup questions

| Question | Verdict | What it shows |
|---|---|---|
| Net revenue by region for Q3 | REUSE | The simple case: the report already exists |
| Fungicide margin in EMEA by quarter | REUSE | Two old copies exist, but the certified original wins |
| NPS by channel | EXTEND | The report answers the question but is not certified: the extension is certification |
| OTIF by country in LATAM, monthly | REUSE + conflict | Another report calculates OTIF with a different formula |
| Show me something interesting | CLARIFY | The system does not guess; it asks for clarification |
| Какая выручка гербицидов в LATAM против плана за Q3? | EXTEND | The same question in Russian gives the same verdict |
