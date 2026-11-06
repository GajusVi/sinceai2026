"""BI Steward decision screen. Run: make ui  (Windows: .\\run.ps1 ui)"""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from steward import Steward  # noqa: E402
from steward.catalog import CHANGES_FILE  # noqa: E402
from steward.explain import TemplateExplainer  # noqa: E402
from steward.governance import JOURNAL_FILE  # noqa: E402
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
    "CONSOLIDATE": "Consolidate duplicates",
    "NOT_FEASIBLE": "Not possible with governed data",
}

SEVERITY_ICONS = {"info": "🔵", "warning": "🟠", "blocker": "🔴"}

# C3 evidence shape. Shown only while decision.evidence is empty, and always labelled as a sample.
FAKE_EVIDENCE = [
    {
        "claim": "Report is tagged Active but has had no viewers for 90 days",
        "rule_id": "RULE-003",
        "record_ids": ["RPT-0142"],
        "value": "0 views / 90 d",
        "severity": "warning",
    },
    {
        "claim": "Same KPI is defined in two reports with different formulas",
        "rule_id": "RULE-007",
        "record_ids": ["RPT-0142", "RPT-0288"],
        "value": "2 definitions",
        "severity": "blocker",
    },
    {
        "claim": "Owner is active and the role is staffed",
        "rule_id": "RULE-011",
        "record_ids": ["USR-0031"],
        "value": "trust +0.20",
        "severity": "info",
    },
]

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
    st.caption(
        "Language model: "
        + (
            {"claude": f"Claude ({steward.llm.model})", "gemini": f"Gemini ({steward.llm.model})"}[steward.llm.provider]
            if steward.llm
            else "off, using rules and templates"
        )
    )
    actor = st.text_input("Your name", value="demo-user")
    st.toggle("Expert mode: skip the interview", key="expert_mode")
    st.divider()
    st.caption("Example questions")
    for example in EXAMPLES:
        if st.button(example, width="stretch"):
            st.session_state.pending_question = example
    st.divider()
    if st.button("Reset demo", width="stretch"):
        for name in (CHANGES_FILE, JOURNAL_FILE):
            (steward.data_dir / name).unlink(missing_ok=True)
        st.cache_resource.clear()
        st.session_state.clear()
        st.rerun()


def verdict_title(verdict) -> str:
    return VERDICT_TITLES.get(verdict, getattr(verdict, "value", str(verdict)))


def ask(text: str) -> None:
    """Run one question; keep chat history (question, one-line verdict) and the latest full result."""
    result = steward.ask(text)
    best = result.decision.best
    summary = verdict_title(result.decision.verdict) + (f": {best.artifact.title}" if best else "")
    st.session_state.setdefault("messages", []).extend(
        [{"role": "user", "content": text}, {"role": "assistant", "content": summary}]
    )
    st.session_state.result = result


def render_evidence(decision) -> None:
    items = list(getattr(decision, "evidence", []) or [])
    sample = not items
    if sample:
        items = FAKE_EVIDENCE
    st.markdown("#### Evidence")
    for item in items:
        e = item if isinstance(item, dict) else item.model_dump()
        sev = str(getattr(e["severity"], "value", e["severity"])).lower()
        with st.container(border=True):
            st.markdown(f"{SEVERITY_ICONS.get(sev, '⚪')} **{e['claim']}**")
            st.caption(
                f"`{e['rule_id']}` · {sev} · records: {', '.join(map(str, e['record_ids'])) or 'none'} · value: {e['value']}"
            )
    if sample:
        st.caption("Sample evidence: not from the engine yet.")


def render_result(result: StewardResult) -> None:
    decision = result.decision
    st.subheader(verdict_title(decision.verdict))
    st.markdown(result.explanation)

    render_evidence(decision)

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
        st.dataframe(
            [
                {
                    "lifecycle label (claimed)": best.artifact.status.value,
                    "usage (observed)": "not wired yet",
                    "match": "-",
                }
            ],
            width="stretch",
            hide_index=True,
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

    if decision.verdict not in APPROVE_LABELS:
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


@st.cache_resource(show_spinner="Computing catalog health ...")
def _health(_steward: Steward, catalog_key: tuple):
    return _steward.health()


def get_health():
    """health() takes ~45 s on the 360-asset data pack (linking.scan), so there it runs on request and is cached."""
    on_datapack = any(a.platform for a in steward.catalog.artifacts.values())
    if on_datapack and not st.session_state.get("health_requested"):
        return None
    return _health(steward, tuple(steward.catalog.artifacts))


@st.cache_data
def load_owners() -> dict[str, dict]:
    import pandas as pd

    from steward.datapack import DEFAULT_XLSX

    return pd.read_excel(DEFAULT_XLSX, sheet_name="Owners").set_index("owner_id").to_dict("index")


@st.cache_data
def usage_cutoffs(_artifacts: dict, key: int) -> tuple[float, float]:
    """Average monthly unique users: the 20th and 80th percentile over all assets that have usage."""
    avgs = sorted(sum(m.unique_users for m in a.usage) / len(a.usage) for a in _artifacts.values() if a.usage)
    return avgs[int(len(avgs) * 0.2)], avgs[int(len(avgs) * 0.8)]


def usage_tier(artifact) -> str:
    if not artifact.usage:
        return "no usage data"
    low, high = usage_cutoffs(steward.catalog.artifacts, len(steward.catalog.artifacts))
    avg = sum(m.unique_users for m in artifact.usage) / len(artifact.usage)
    tier = "low (bottom 20%)" if avg <= low else "high (top 20%)" if avg >= high else "medium"
    return f"{tier}: {avg:.0f} users/month"


def render_orphan_rescue() -> None:
    artifacts = steward.catalog.artifacts
    if not any(a.platform for a in artifacts.values()):
        st.info("Run `make bayer` to load the Bayer data pack (Windows: `.\\run.ps1 bayer`).")
        return
    owners = load_owners()
    ids = list(artifacts)
    default = ids.index("AST-0091") if "AST-0091" in artifacts else 0
    asset_id = st.selectbox(
        "Asset (search by id or name)", ids, index=default, format_func=lambda i: f"{i}: {artifacts[i].title}"
    )
    a = artifacts[asset_id]
    st.subheader(f"{a.title} ({a.id})")
    st.caption(
        f"{a.type} on {a.platform} · product {a.product_scope} · market {a.market_scope} · created {a.created_date}"
    )

    col_owner, col_trust, col_usage = st.columns(3)
    with col_owner:
        st.markdown("#### Owner")
        status_color = {"active": "green", "inactive": "red"}.get(a.owner_status, "red")
        st.markdown(f"**{a.owner or 'No owner'}** ({a.owner_id or 'none'})")
        st.markdown(f"Role: {a.owner_role or '-'} · Scope: {a.owner_scope or '-'}")
        st.markdown(f"Status: :{status_color}[{a.owner_status or 'missing'}]")
        if a.successor_candidates:
            st.markdown("**Successor candidates**")
            for oid in a.successor_candidates:
                o = owners.get(oid, {})
                st.markdown(f"- {o.get('owner_name', oid)} ({oid}) · {o.get('role', '')} · {o.get('scope', '')}")
        elif a.owner_status != "active":
            st.caption("No successor candidates: the role is vacant.")
    with col_trust:
        st.markdown("#### Trust")
        refresh_color = {"healthy": "green", "warning": "orange", "failed": "red"}.get(a.refresh_status, "gray")
        st.markdown(f"Endorsement: **{a.endorsement}**")
        st.markdown(
            f"Model {a.model_id}: refresh :{refresh_color}[{a.refresh_status or 'unknown'}] · endorsement {a.model_endorsement or '-'}"
        )
        st.markdown(f"Platform: {a.platform}")
    with col_usage:
        st.markdown("#### Usage")
        if a.usage:
            st.line_chart({m.month.strftime("%Y-%m"): m.unique_users for m in a.usage}, y_label="unique users / month")
        else:
            st.caption("No usage rows since creation.")

    st.markdown("#### Signals and data quality")
    chips = [f":orange-badge[{x}]" for x in a.signals] + [f":gray-badge[{x.split(':')[0]}]" for x in a.data_quality]
    st.markdown(" ".join(chips) if chips else "None.")

    st.markdown("#### Claimed vs observed")
    st.dataframe(
        [{"lifecycle (claimed in data pack)": a.lifecycle_claimed, "usage (observed)": usage_tier(a)}],
        width="stretch",
        hide_index=True,
    )
    for flag in a.data_quality:
        if flag.startswith("NAME_SCOPE_MISMATCH"):
            st.warning(
                f"Name vs scope: the name ends in a different market than market_scope ({flag.split(':', 1)[1]}). "
                "Scope is taken from the fields, not the name."
            )

    st.markdown("#### Proposals (journal only, nothing is changed)")
    reason = st.text_input("Reason (required)", key=f"orphan_reason_{a.id}")
    c1, c2 = st.columns(2)
    with c1:
        candidate = (
            st.selectbox(
                "Successor",
                a.successor_candidates,
                format_func=lambda i: f"{owners.get(i, {}).get('owner_name', i)} ({i})",
                key=f"orphan_succ_{a.id}",
            )
            if a.successor_candidates
            else None
        )
        if st.button("Propose successor", disabled=candidate is None, width="stretch"):
            try:
                steward.governance.propose(a.id, "propose successor", actor, reason, detail=candidate)
            except ValueError as error:
                st.error(str(error))
            else:
                st.success("Proposal recorded in the journal (not applied).")
    with c2:
        if st.button("Retire candidate", width="stretch"):
            try:
                steward.governance.propose(a.id, "retire candidate", actor, reason)
            except ValueError as error:
                st.error(str(error))
            else:
                st.success("Proposal recorded in the journal (not applied).")


tab_ask, tab_health, tab_orphan, tab_journal, tab_catalog = st.tabs(
    ["Ask", "Catalog health", "Orphan rescue", "Journal", "Catalog"]
)

with tab_ask:
    typed = st.chat_input("Ask a business question, e.g. " + EXAMPLES[0])
    question = typed or st.session_state.pop("pending_question", None)
    if question and question.strip():
        ask(question.strip())
    for message in st.session_state.get("messages", []):
        with st.chat_message(message["role"]):
            st.write(message["content"])
    if st.session_state.get("result"):
        render_result(st.session_state.result)

with tab_health:
    health = get_health()
    if health is None:
        st.info("Computing the catalog health takes about a minute on the Bayer data pack (it is cached afterwards).")
        if st.button("Compute catalog health"):
            st.session_state.health_requested = True
            st.rerun()
    else:
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


with tab_orphan:
    render_orphan_rescue()

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
                    "decision": "proposal" if e.question.startswith("PROPOSAL") else e.action.value,
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
