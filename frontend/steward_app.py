"""BI Steward decision screen. Run: make ui  (Windows: .\\run.ps1 ui)"""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from steward import Steward  # noqa: E402
from steward.explain import TemplateExplainer  # noqa: E402
from steward.models import GapKind, StewardResult, Verdict  # noqa: E402

EXAMPLES = [
    "What is herbicide revenue in LATAM vs plan for Q3?",
    "Net revenue by region for Q3",
    "Fungicide margin in EMEA by quarter",
    "NPS by channel",
    "OTIF by country in LATAM, monthly",
    "Logistics carbon footprint by country",
]

VERDICT_TITLES = {
    Verdict.REUSE: "Reuse as is",
    Verdict.EXTEND: "Extend an existing report",
    Verdict.CREATE: "Create a new report",
    Verdict.CLARIFY: "Clarify the question",
}

APPROVE_LABELS = {
    Verdict.REUSE: "Open this report",
    Verdict.EXTEND: "Approve the extension",
    Verdict.CREATE: "Create the report",
}

st.set_page_config(page_title="BI Steward", layout="wide")


@st.cache_resource
def get_steward() -> Steward:
    return Steward()


steward = get_steward()
labels = TemplateExplainer(steward.catalog)

with st.sidebar:
    st.title("BI Steward")
    st.caption(f"Reference date for freshness checks: {steward.as_of}")
    st.caption("Language model: " + ({"claude": f"Claude ({steward.llm.model})", "gemini": f"Gemini ({steward.llm.model})"}[steward.llm.provider] if steward.llm else "off, using rules and templates"))
    actor = st.text_input("Your name", value="demo-user")
    st.divider()
    st.caption("Example questions")
    for example in EXAMPLES:
        if st.button(example, width="stretch"):
            st.session_state.question = example
            st.session_state.result = steward.ask(example)


def render_result(result: StewardResult) -> None:
    decision = result.decision
    st.subheader(VERDICT_TITLES[decision.verdict])
    st.markdown(result.explanation)

    with st.expander("How the question was understood"):
        q = result.question
        st.write(
            {
                "metrics": [steward.catalog.metric(m).name for m in q.metrics],
                "filters": {d: steward.catalog.dimension_value_label(d, v) for d, v in q.filters.items()},
                "breakdowns": [steward.catalog.dimension(d).name for d in q.dimensions],
                "period": q.period,
                "parser": q.parser,
            }
        )

    if decision.best:
        best = decision.best
        st.markdown(f"#### Recommended report: {best.artifact.title}")
        c1, c2, c3 = st.columns(3)
        c1.metric("Question coverage", f"{best.coverage:.0%}")
        c2.metric("Trust", f"{best.trust:.2f}")
        c3.metric("Views (30 days)", best.artifact.views_30d)
        st.caption(
            f"Owner: {best.artifact.owner or 'none'} · "
            f"{'certified' if best.artifact.certified else 'not certified'} · "
            f"refreshed {best.artifact.last_refreshed}"
        )
        missing = [labels.gap_label(g) for g in best.gaps]
        if missing:
            st.markdown("**Missing:** " + ", ".join(missing))

    if decision.alternatives:
        with st.expander(f"Other candidates ({len(decision.alternatives)})"):
            st.dataframe(
                [
                    {
                        "report": c.artifact.title,
                        "coverage": f"{c.coverage:.0%}",
                        "trust": c.trust,
                        "compatible": "yes" if c.compatible else "no",
                        "missing": ", ".join(labels.gap_label(g) for g in c.gaps if g.kind != GapKind.TRUST),
                    }
                    for c in decision.alternatives
                ],
                width="stretch",
                hide_index=True,
            )

    with st.expander("Why this verdict"):
        for reason in decision.reasons:
            st.write("- " + reason)

    if decision.verdict == Verdict.CLARIFY:
        return

    st.divider()
    st.markdown("#### Human decision")
    owner = None
    if decision.verdict == Verdict.CREATE or (decision.best and not decision.best.artifact.has_owner):
        owner = st.text_input("Report owner", key="owner")
    col_ok, col_no = st.columns(2)
    with col_ok:
        if st.button(APPROVE_LABELS[decision.verdict], type="primary", width="stretch"):
            try:
                entry = steward.governance.approve(result, actor=actor, owner=owner or None)
            except ValueError as error:
                st.error(str(error))
            else:
                steward.reload()
                created = f" New artifact: {entry.created_artifact_id}." if entry.created_artifact_id else ""
                st.success("Decision recorded in the journal." + created)
                st.session_state.result = None
    with col_no:
        reason = st.text_input("Reason for rejecting", key="reject_reason")
        if st.button("Reject", width="stretch"):
            try:
                steward.governance.reject(result, actor=actor, reason=reason)
            except ValueError as error:
                st.error(str(error))
            else:
                st.info("Rejection recorded in the journal. The catalog was not changed.")
                st.session_state.result = None


tab_ask, tab_health, tab_journal, tab_catalog = st.tabs(["Ask", "Catalog health", "Journal", "Catalog"])

with tab_ask:
    question = st.text_input("Business question", key="question", placeholder=EXAMPLES[0])
    if st.button("Ask", type="primary") and question.strip():
        st.session_state.result = steward.ask(question)
    if st.session_state.get("result"):
        render_result(st.session_state.result)

with tab_health:
    health = steward.health()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Reports in catalog", health.total)
    c2.metric("Certified", health.certified)
    c3.metric("Duplicates", len(health.duplicates))
    c4.metric("Retirement candidates", len(health.retire))

    st.markdown("#### Candidates for retirement")
    st.dataframe(
        [{"report": r.title, "id": r.artifact_id, "why": "; ".join(r.reasons)} for r in health.retire],
        width="stretch",
        hide_index=True,
    )
    st.markdown("#### Duplicates")
    st.dataframe(
        [
            {
                "keep": steward.catalog.artifact(p.keep_id).title,
                "duplicate": steward.catalog.artifact(p.duplicate_id).title,
                "similarity": f"{p.similarity:.0%}",
            }
            for p in health.duplicates
        ],
        width="stretch",
        hide_index=True,
    )

with tab_journal:
    entries = steward.governance.entries()
    if entries:
        st.dataframe(
            [
                {
                    "when": e.timestamp.strftime("%Y-%m-%d %H:%M"),
                    "who": e.actor,
                    "question": e.question,
                    "verdict": e.verdict.value,
                    "decision": "approved" if e.action.value == "approved" else "rejected",
                    "report": e.artifact_id,
                    "created": e.created_artifact_id,
                    "reason": e.reason,
                }
                for e in reversed(entries)
            ],
            width="stretch",
            hide_index=True,
        )
    else:
        st.caption("No decisions yet.")

with tab_catalog:
    st.dataframe(
        [
            {
                "id": a.id,
                "title": a.title,
                "domain": a.domain,
                "owner": a.owner,
                "certified": a.certified,
                "refreshed": a.last_refreshed,
                "views": a.views_30d,
                "status": a.status.value,
                "version": a.version,
            }
            for a in steward.catalog.artifacts.values()
        ],
        width="stretch",
        hide_index=True,
    )
