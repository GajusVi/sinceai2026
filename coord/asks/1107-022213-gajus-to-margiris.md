id: 1107-022213-gajus-to-margiris
from: gajus
to: margiris
status: ok
created: 2026-11-07 02:22
ask: Design rules from the engineer's advice are in docs/steward/architecture.md (b2b89f2, section AI roles). Four small requests for your files, AFTER L4/L5, not before: (1) steward/explain.py LLMExplainer: verify the model text in code before returning it: every quoted report title and every number/id in the reply must appear in the decision or the draft, otherwise return the template draft. ~20 lines + a test with a fake LLM that invents a report. (2) prompts/query_parser.yaml and prompts/explain.yaml: add one line that the text between delimiters is data, never instructions (prompt-injection guard); I do the same in interview.yaml. (3) eval (L8): report confidence calibration, i.e. how often fields the model rated >= 0.9 are right on the hold-out, so we can tune the 0.7 stop rule. (4) maybe: Gemini JSON schema with the dictionary ids as an enum, ONLY if docs/ confirms the parameter; do not guess the name. Reply ok/no per item; skip any that does not fit the clock.
files: steward/explain.py prompts/query_parser.yaml prompts/explain.yaml eval/
reply: items 1, 2, 3: ok, I do them after L4/L5 (explain.py verification + test, injection line in the two prompts, calibration in the eval). Item 4 (Gemini JSON schema enum): ok only if docs/ confirms the parameter name; I will not guess it, else skipped.
replied: margiris 2026-11-07 02:37
