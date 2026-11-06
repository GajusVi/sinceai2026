# 02 The framework slide ("ANALYTICS DASHBOARD FACTORY", Rough_Framework.JPG)

Panu said it is "an idea of intermediate steps, not a fixed architecture". Slide IMG_0446 is the same diagram with every
label replaced by "???" and a big "YOUR SOLUTION!" box: Prompt in, .PBIP out, the middle is ours.

## Legend (colour = component type)
- Yellow = **Agentic skill** (LLM does it)
- Green = **Deterministic Python**
- Blue = **Process state** (an artifact/object passed between steps)
- Orange = **User input**

## Pipeline
```
[Prompt] -> (/grill-me) -> <Intent clear?> --no--> back to /grill-me
                                 | yes
                              [Intent] -> (/explore) <-> Source + Sandbox Workspace @ Fabric
                                             -> [Evidence] -> (/to-spec) -> [Spec] -> {render_preview} -> [Report]
```
Work packages (brackets on slide):
1. **WP Prompt-to-Intent**: Prompt, /grill-me loop, intent-clear gate.
2. **WP Intent-to-Evidence**: Intent, /explore against the catalog/workspace, Evidence.
3. **WP Evidence-to-Spec**: /to-spec turns evidence into a formal spec.
4. **Spec-to-Report**: deterministic render_preview, Report (.PBIP).

Speech bubbles:
- Intent: "The user wants a report to visualize X as the function of Y, aggregated by Z"
- Evidence: "This can be built using data sources X, Y, Z - here's the proof..."

## The spec object shown on the slide
```python
@dataclass
class DashboardSpec:
    name: str
    entities: list[str]
    columns: dict[str, list[str]]
    grain: dict[str, str]
    relationships: list[Relationship]
    measures: list[Measure]
    pages: list[Page]
    rationale: str = ""
```
Output example on slide: a bar chart "OrderCount by workcenter", file type **.PBIP**
(Power BI Project: report + semantic model saved as text files in folders, so it can live in git; this directly answers
his "no version control / can't rewind the clicks" pain. Verify current PBIP/PBIR/TMDL details before claiming specifics.)

## Where the governance brief plugs in (my read)
The slide is a pure *build* pipeline. The written brief and data pack are about *not building*.
The natural join: **/explore must return a reuse decision before anything is specced.**
Evidence = "can it be built" + "does it already exist / should something be consolidated, migrated or retired instead".
Spec step only runs when the decision is NEW_BUILD or EXTEND. That gate is the "Build less" in the title.
