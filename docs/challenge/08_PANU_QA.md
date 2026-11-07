# Panu Q&A (Sat 7 Nov, morning slot at Joki): takeaways and what we did about them

Source: `08_PANU_QA_transcript.txt` (speech-to-text, heavily garbled; paraphrased here, not quoted).
The transcript's first paragraph is probably the end of another team's conversation.

## What Panu said
1. **Grill-me must exist, but short.** Going straight from a prompt to a finished dashboard is "in most cases not
   feasible", yet if it is too hard nobody uses it. The exact number of questions does not matter; it cannot be 50.
   Our confidence-threshold early stop is fine.
2. **Predefined, governed KPIs first: "exactly the way to go".** Everyone inventing their own KPIs makes an
   organisation unmanageable. If the KPIs are not defined, that is an org problem no system solves.
3. **Search what exists, tweak before building.** IT wants to minimise the maintenance vector: small changes to
   existing assets beat new ones.
4. **One person approves** before anything new enters the system.
5. **"How efficient is my plant running?" is a valid, typically ambiguous question.** Good that we wrote our own
   examples; some data-pack requests are too polished.
6. **Next: catalog functionality.** Where do assets live and how do people reach them, as their number grows.
   Two populations, two experiences:
   - **Production floor (viewers):** find it fast, understand it, decide quickly; they do not care how it was built.
   - **Builders (IT):** maintain; the asset's life cycle; are my assets healthy; problems; backend data fixes.
   Tailoring the catalog per group adds value to the pitch.
7. **Pilot metrics:** survey both groups (builders: better than today's workflow?). Quantitative is hard here;
   argue qualitatively why ours is better.
8. **Judging:** very little time per submission. Show the main pipeline in a logical sequence: the intermediate
   steps, the inputs and outputs of each, and the benefit compared with other teams.
9. (Opening fragment, possibly another team) **Ownership:** if the owner leaves, who owns the asset and why does it
   exist; it must be explainable, part of the pipeline.

## What we built in response (Sat afternoon, see NOTES.md for commits)
- **Roles + mock login** (`steward/auth.py`): Worker (one plant + department), Management (own plant), Builder (IT,
  whole company). Demo accounts: Builder12/Admin123, Manager07/Manage123, Worker21|22/Worker123.
- **Worker = fast info, reuse only, no interview** (`steward/worker.py`, `frontend/worker_view.py`): department
  buttons, pop-out chat where the AI picks existing dashboards or single KPIs (validated, never a new build), honest
  "not in governed data yet" line, quiet request link, duplicate requests merged (+N). Other plants refused.
- **Builder side:** approval queue with requester attached, requests from the floor (grant / start / decline),
  journal signed "approver, requested by requester".
- **Department -> KPI map:** AI drafts, code validates ids, builder approves; workers read only the approved map
  (`steward/departments.py`).
- **Large synthetic pack** for scale tests (`tools/make_large_pack.py`, `make pack-large`, `make bayer-large`).

## Still open against his list
- Point 6, builder side: a "my assets" health view per builder (life cycle, failed refresh, owner gone, usage trend).
- Point 8: one pipeline slide with inputs/outputs per step (pitch, Donatas).
- Handoff queues live in the browser session: requests do not reach another person's browser yet (shared store
  needed before a multi-user test on a hosted instance).
