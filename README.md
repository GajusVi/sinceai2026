# SinceAI 2026 workspace: BI Steward (Bayer challenge)

For any business question, BI Steward first looks for what already exists, checks whether it can be trusted,
and only then allows something new: REUSE, EXTEND, CREATE or CLARIFY, approved by a human and journaled.
Challenge notes: docs/challenge/. Design: docs/steward/architecture.md.

## How it works

**The Dashboard Factory (plan v2).** Every request ends in one governed decision and the dashboard that decision implies.
Yellow steps use a language model; everything else is deterministic Python. Gates stop the flow until they pass.

```mermaid
flowchart TD
    IN["W0 Request<br/>chat, voice, request form, orphan asset, estate finding"]:::user
    INT["W1 Interview<br/>situation questions until the intent is clear"]:::llm
    KPI["W2 KPI resolution<br/>words to canonical KPI ids, variants flagged"]:::code
    FEA{"W3 Feasibility<br/>can governed data answer it?"}:::code
    EV{"W4 Evidence + verdict<br/>reuse before build"}:::code
    SPEC["W5 Spec<br/>dashboard for the verdict: reuse, extend,<br/>consolidate, create, migrate, rescue"]:::llm
    LINT{"W6 Lint gate<br/>RULE-001..008, focus, data"}:::code
    REN["W7 Render<br/>KPI cards, trend, breakdown, exceptions,<br/>governance footer"]:::code
    HUM{"W8 Human approval<br/>reason required"}:::user
    PUB["W9 Publish<br/>new version, journal, lineage, .PBIP"]:::code

    IN --> INT --> KPI --> FEA
    FEA -->|"no measure buildable: NOT_FEASIBLE + nearest offer"| INT
    FEA -->|buildable| EV
    EV -->|"CLARIFY"| INT
    EV -->|"REUSE / EXTEND / CONSOLIDATE / CREATE"| SPEC --> LINT
    LINT -->|"block: fix the spec"| SPEC
    LINT -->|"pass / warn"| REN --> HUM
    HUM -->|approve| PUB
    HUM -->|"reject, journaled"| IN

    classDef llm fill:#fff3bf,stroke:#b08900
    classDef code fill:#d3f9d8,stroke:#2b8a3e
    classDef user fill:#ffe8cc,stroke:#d9480f
```

The three diagrams below are the detail of W4-W8 as first designed:
Diagrams from Vlada's bi-steward skeleton, drawn before the Bayer brief was released. The flow is still how the app works;
the herbicide/LATAM example comes from the invented sample catalog (Crop Science, out of scope for the challenge), and the
current build adds the intake check, KPI-id matching on the data pack and the Orphan rescue tab. Full write-up: docs/steward/architecture.md.

**The whole flow.** Solid arrows are the question; dashed lines are reads from and writes to the catalog.

```mermaid
flowchart TD
    Q["1. A person asks a question<br/>'Herbicide revenue in LATAM vs plan for Q3'"]
    P["2. The system understands the question<br/>metrics, filters, period"]
    S["3. The system searches for similar reports<br/>by words, by meaning and by metrics"]
    D["4. The system compares what it found<br/>and picks one verdict"]
    E["5. The system explains the verdict<br/>in plain language, with reasons"]
    H{"6. Does the person agree?"}
    YES["Catalog is updated<br/>report reused, extended or created with an owner"]
    NO["Catalog stays unchanged"]
    LOG[("Journal<br/>question, verdict, who decided and why")]

    CAT[("Catalog<br/>reports and official metric definitions")]

    Q --> P --> S --> D --> E --> H
    H -->|Yes| YES
    H -->|No| NO
    YES --> LOG
    NO --> LOG

    CAT -.->|reads| S
    CAT -.->|reads| D
    YES -.->|writes| CAT
```

**Step 4: choosing the verdict.** A conflict is a warning shown with any verdict. A question with no known metric gets CLARIFY.

```mermaid
flowchart TD
    D["Step 4. What already exists in the catalog?"]
    D -->|"A report answers the question and is trustworthy"| REUSE["Reuse as is"]
    D -->|"A report almost fits; a filter or breakdown is missing"| EXT["Extend the existing one"]
    D -->|"Nothing similar exists"| CREATE["Propose a new report"]
    D -->|"The same metric is calculated differently in different reports"| CONF["Show the conflict; do not mix the numbers"]

    REUSE --> NEXT["Then step 5: explain and ask the human"]
    EXT --> NEXT
    CREATE --> NEXT
    CONF --> NEXT
```

**Steps 5-6: what the human sees.** Reject needs a reason; both outcomes are journaled.

```mermaid
flowchart TD
    SCREEN["Decision screen"]

    SCREEN --> TEXT["Text:<br/>Extend the Finance report 'Global Net Revenue vs Plan'.<br/>It is certified and was refreshed yesterday.<br/>Only the 'herbicides' filter is missing.<br/>Do not compare it with the LATAM Sales Dashboard:<br/>revenue there is calculated before discounts."]

    TEXT --> BUTTONS{"The person chooses"}

    BUTTONS -->|Approve the extension| YES["A new version of the same report is added to the catalog<br/>with the 'herbicides' filter and the Finance owner"]
    BUTTONS -->|Reject| NO["The catalog stays as it was"]

    YES --> LOG[("The journal records:<br/>question, verdict, who clicked and why")]
    NO --> LOG
```

After `git pull`: nothing to install. `make test`, then `make ui` (Windows: `.\run.ps1 test`, `.\run.ps1 ui`).

## First run (once, on good Wi-Fi)
```bash
cd ~/SinceAI2026 && ./setup_mac.sh --all
```
Then add one API key to `.env` and run `make ping`.

## Windows teammates
```powershell
winget install --id Git.Git -e; winget install --id GitHub.cli -e   # then reopen PowerShell
gh auth login
cd $HOME; gh repo clone GajusVi/sinceai2026 SinceAI2026; cd SinceAI2026
powershell -ExecutionPolicy Bypass -File .\setup_windows.ps1
notepad .env        # paste your own GEMINI_API_KEY, save
.\run.ps1 ping; .\run.ps1 ui
```
`run.ps1` replaces `make` on Windows: `.\run.ps1 ui | demo | api | eval | ping | models | test`.

## Daily commands
| Command | What |
| --- | --- |
| `make ui` | BI Steward screen (LLM if key, else rules) |
| `make demo` | same screen, LLM off, no network |
| `make ask Q="..."` | one question in the terminal |
| `make ui-old` | pre-event scaffold screen |
| `make eval` | hold-out accuracy, F1, misses |
| `make warm` | record live outputs into demo/cache (Saturday) |
| `make api` | FastAPI on :8000, docs at /docs |
| `make hack` / `make unhack` | keep the Mac awake, network check |

## Friday edits, in order
1. `backend/pipeline.py`: `LABELS`, `URGENT`, prompt.
2. `.env`: `USER_ROLE=`.
3. `backend/models.py`: rename `Item` to the company's noun, add fields the UI needs.
4. `frontend/app.py`: `TITLE`, `TAGLINE`.
5. `demo/inputs.jsonl`: 5-10 real inputs (one wow, one messy, one edge case).
6. `eval/holdout.jsonl`: 20-50 labelled examples, before tuning anything.

Files: `CLAUDE.md` (architecture, rules) · `NOTES.md` (team, decisions) · `CHALLENGE_PICK.md` · `submission/` · `docs/`.
