# 01 Challenge: "Build Less, Build Better: AI for Governed Analytics" (Bayer)

Contact: **Panu Aho**, panu.aho@bayer.com, onsite at Joki on Saturday (he gave the briefing talk; transcript mangles his name).
Bayer Turku site = manufacturing plant (women's health: IUDs, implants). He is a senior data scientist / analytics person there.

## Official brief (written)
- **Problem:** self-service BI gives speed but also dashboard sprawl, duplicate logic, unclear ownership, tech debt.
  Bayer's Tableau -> Power BI migration exposed it. AI agents will make sprawl worse unless governed.
- **Build:** prototype that helps create, **reuse, maintain or retire** analytics products while keeping governance + business value.
- **Guiding question:** how can agents turn business questions into *fewer, better, maintainable, governed* analytics products
  without multiplying dashboards, inconsistent KPIs and tech debt?
- **Suggested AI:** agentic workflows; LLM/RAG over BI metadata; semantic/KPI mapping; duplicate detection; usage/lifecycle scoring;
  governance checks; human-in-the-loop approval; reuse/consolidate/retire recommendations.
  *"Focus on a working end-to-end prototype rather than model complexity."*
- **Data:** synthetic only. Data pack provided (see 03). Own synthetic data allowed if assumptions documented.

## Scoring (memorise this)
| Weight | Criterion |
| --- | --- |
| 30% | Problem fit & business value |
| 25% | Governance & maintainability |
| 20% | Technical quality & meaningful AI use |
| 15% | Usability for business AND IT |
| 10% | Scalability & demo quality |

"Strong solutions reduce analytics sprawl while preserving ownership, KPI consistency, human oversight and lifecycle control."
=> 55% of the score is fit + governance. AI sophistication is only 20%.

## Required submission
1. Working prototype, at least ONE end-to-end workflow (not slides).
2. Short pitch/demo (event: ~2 min video, English narration, captions, screen recording, label mocks, never invent numbers).
3. Source repo.
4. Brief README/architecture note covering: **data assumptions, AI approach, governance controls, enterprise-BI integration**.

## What Panu emphasised verbally (the talk, beyond the written brief)
- The end artifact he pictures: a **fixed set of KPIs on a screen the shift sees when they walk in**, no prompting each morning.
  Conversational AI is NOT the end-user interface; agents belong in the *creation* process.
- Today's pain #1 (users): requirement gathering. Business person can't specify; analyst doesn't know the domain;
  build -> "no, that's all wrong" -> loop. Tedious, error-prone, long lead time. Everyone has Power BI licences, few can use them.
- Pain #2 (IT): point-and-click artifacts have **no version control, no git, no record of how it was built**.
  "Guy who left 3 years ago built this crucial dashboard, IT please fix it" is the nightmare. Backend changes break orphaned reports.
- Pain #3 (governance): 1000x citizen developers with agents = thousands of unowned dashboards. Must be limited.
- **"The focus is on the process", not the amount of content.** Humans can only take in the crucial things; don't put 20 screens on the wall.
- Explicitly referenced the **"grill-me" skill** (agent interviews you question after question until all open points are exhausted),
  but adapted for a NON-technical user: ask about their situation ("what do you need to decide when you walk in?"), never "what is the spec?".
- Exploration step uses an existing **curated data catalog / semantic models**; if the catalog can't support the intent,
  there must be a **feedback loop back to the user** ("what you ask is not feasible, adjust intent").
- Spec depends on target tool; for Power BI: report -> pages -> visuals; semantic model -> tables, filters, relationships (1:1, 1:many).
- If earlier steps are good, the **final render can be plain deterministic code, no AI needed**.
- Target users: anyone in a plant: manufacturing, quality control, supply chain/logistics, HR, finance, IT. Not about rank.
- Asked "medical decision support?" -> he liked it as a direction, but the data pack's START_HERE puts clinical decision support OUT OF SCOPE. Don't go there.
- Human factors (designing the dashboard to steer decisions well) is in scope.

## Scope limits (from data pack START_HERE)
Out: clinical decision support, treatment recommendations, pharmacovigilance, patient profiling, real Bayer systems,
any claim synthetic figures are real Bayer performance. Pharma (Rx) only: no Crop Science, no Consumer Health.
