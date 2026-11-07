"""BI Steward decision screen. Run: make ui  (Windows: .\\run.ps1 ui)"""

import sys
import tempfile
from html import escape
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ui  # noqa: E402  (frontend/ui.py: design system)
import worker_view  # noqa: E402  (frontend/worker_view.py: the production-floor Ask tab)

from steward import Steward, semantic  # noqa: E402
from steward.auth import COMPANY, DEMO_ACCOUNTS, can_see, login  # noqa: E402
from steward.catalog import CHANGES_FILE  # noqa: E402
from steward.explain import TemplateExplainer  # noqa: E402
from steward.governance import JOURNAL_FILE  # noqa: E402
from steward.linking import kpi_index  # noqa: E402
from steward.models import GapKind, StewardResult, Verdict  # noqa: E402
from steward.render import render as render_spec  # noqa: E402
from steward.worker import log_request, other_plant, read_log, refusal  # noqa: E402

EXAMPLES = [
    "What is herbicide revenue in LATAM vs plan for Q3?",
    "Net revenue by region for Q3",
    "Fungicide margin in EMEA by quarter",
    "NPS by channel",
    "OTIF by country in LATAM, monthly",
    "Logistics carbon footprint by country",
]

BAYER_EXAMPLES = [
    "How efficiently is this plant running?",
    "I'm a shareholder: how is the business doing in Europe?",
    "Create a global Nubeqa dashboard showing sales growth, forecast variance and market access by country.",
    "Net sales for Eylea in Japan",
    "Net sales and OTIF for Hyrnuo in China",
    "Net sales for Xarelto in Brazil by month",
    "Net sales, gross-to-net and budget variance by product",
    "Inventory coverage for Xarelto in Germany",
]

# Empty-state chips, in business words. Pharma only (CLAUDE.md scope), so no crop examples.
CHIPS = ["How are we doing in LATAM this quarter?", "Is supply safe for Plant-B?", "Xarelto net sales in Germany"]

LINT_COLOURS = {"pass": ui.GOOD, "warn": ui.WARN, "block": ui.BAD}

VERDICT_TITLES = {
    Verdict.REUSE: "Reuse as is",
    Verdict.EXTEND: "Extend an existing report",
    Verdict.CREATE: "Create a new report",
    Verdict.CLARIFY: "Clarify the question",
    "CONSOLIDATE": "Consolidate duplicates",
    "NOT_FEASIBLE": "Not possible with governed data",
}

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

st.set_page_config(page_title="BI Steward", layout="wide", initial_sidebar_state="collapsed")
ui.inject()


def render_login() -> None:
    """Mock login (steward/auth.py): the account sets role, plant, location and department. Not real security."""
    _, mid, _ = st.columns([1, 1.1, 1])
    with mid:
        ui.ask_hero("BI Steward")
        with st.form("login"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log in", type="primary", width="stretch")
        if submitted:
            account = login(username, password)
            if account is None:
                st.error("Wrong username or password.")
            else:
                st.session_state.user = account
                st.rerun()
        st.caption("Demo login, mocked (not real authentication). Accounts:  \n"
                   + "  \n".join(f"{name} / {pw} ({role})" for name, pw, role in DEMO_ACCOUNTS))


user = st.session_state.get("user")
if user is None:
    render_login()
    st.stop()


@st.cache_resource
def get_steward() -> Steward:
    return Steward()


steward = get_steward()


def llm_label() -> str:
    """Which model answers. The "backend" client takes its provider from LLM_PROVIDER in .env (aitta, gemini, ...)."""
    llm = steward.llm
    if not llm:
        return "off, using rules and templates"
    if llm.provider == "backend":
        from backend.llm import get_settings

        return f"{get_settings().llm_provider} ({llm.model})"
    return f"{llm.provider.capitalize()} ({llm.model})"


ON_DATA_PACK = bool(kpi_index(steward.catalog)[0])  # data-pack catalog: examples and the dashboard are Bayer's
labels = TemplateExplainer(steward.catalog)

with st.sidebar:
    st.markdown("#### BI Steward")
    st.caption("Governed analytics for Bayer Pharma. Build less, build better.")
    st.caption(f"AI model: {llm_label()}  \nData as of {steward.as_of}")
    plants = "all (company)" if user.plants == COMPANY else ", ".join(user.plants)
    st.markdown(f"**{user.username}** · {user.role.capitalize()}")
    st.caption(f"{user.name}, {user.location}  \nPlant: {plants}"
               + (f"  \nDepartment: {user.department}" if user.department else ""))
    if st.button("Log out", width="stretch"):  # the approval queue stays: the demo hands it to a builder
        for key in ("user", "messages", "interview", "result", "result_intent", "novice_result", "requested_by"):
            st.session_state.pop(key, None)
        st.rerun()
    actor = user.label
    if user.can("expert_mode"):
        st.toggle("Expert mode: skip the interview", key="expert_mode")
    else:
        st.session_state.expert_mode = False
    st.divider()
    st.caption("Example questions" if user.role != "worker" else "")
    for example in (BAYER_EXAMPLES if ON_DATA_PACK else EXAMPLES) if user.role != "worker" else []:
        if st.button(example, width="stretch"):
            st.session_state.pending_question = example
            st.session_state.interview = None  # an example is a new question, not an answer
    st.divider()
    if user.can("maintain") and st.button("Reset demo", width="stretch"):
        for name in (CHANGES_FILE, JOURNAL_FILE):
            (steward.data_dir / name).unlink(missing_ok=True)
        st.cache_resource.clear()
        st.session_state.clear()
        st.session_state.user = user  # reset clears the demo data, not the login
        st.rerun()


def verdict_title(verdict) -> str:
    return VERDICT_TITLES.get(verdict, getattr(verdict, "value", str(verdict)))


def ask(text: str) -> None:
    """One chat turn. Novice (default): grill-me interview until the Intent is confirmed, then decide + dashboard.
    Expert mode: one shot through the parser, as before. Keeps chat history and the latest full result."""
    messages = st.session_state.setdefault("messages", [])
    messages.append({"role": "user", "content": text})
    if st.session_state.get("interview") is None:  # a new question: the asker's own, or a floor request picked up
        st.session_state.requested_by = st.session_state.pop("next_requested_by", None)
    if st.session_state.get("expert_mode"):
        _finish(steward.build(steward.ask(text)), novice=False)  # W3-W6: the dashboard this decision implies
        return
    state = st.session_state.get("interview")
    if state is not None and not state.done:
        state = steward.interviewer.answer(state, text)
    else:
        st.session_state.result = None
        state = steward.interviewer.start(text)
    site = other_plant(user, state.intent.sites)
    if site:  # management: own plant (and granted ones) only; the rest goes through a builder
        st.session_state.interview = None
        messages.append({"role": "assistant", "content": refusal(user, site)})
        return
    _continue(state)


def skip_to_defaults() -> None:
    """"Skip - use recommended": fill every open question with its default and build."""
    state = st.session_state.get("interview")
    if state is None or state.done:
        return
    st.session_state.messages.append({"role": "user", "content": "Use the recommended setup"})
    _continue(steward.interviewer.finish_with_defaults(state))


def _continue(state) -> None:
    st.session_state.interview = state
    if not state.done:
        st.session_state.messages.append({"role": "assistant", "content": state.question})
        return
    st.session_state.interview = None
    st.session_state.messages.append({"role": "assistant", "content": understood(state)})
    result = steward.investigate(steward.ask_intent(state.intent), state.intent)
    _finish(steward.build(result, state.intent), novice=True, intent=state.intent)


def _finish(result: StewardResult, novice: bool, intent=None) -> None:
    if novice:
        summary = plain_outcome(result)
    else:
        best = result.decision.best
        summary = verdict_title(result.decision.verdict) + (f": {best.artifact.title}" if best else "")
    st.session_state.messages.append({"role": "assistant", "content": summary, "summary": True})
    st.session_state.result = result
    st.session_state.novice_result = novice
    st.session_state.result_intent = intent


def understood(state) -> str:
    """Read the confirmed Intent back in business words before anything is decided (no ids, no jargon)."""
    intent = state.intent
    names = [steward.catalog.metrics[m].name.lower() for m in intent.metric_ids if m in steward.catalog.metrics]
    if intent.sites:
        scope = ", ".join(intent.sites)
    else:
        products = [p for p in intent.products if p != "All Pharma"]
        where = ", ".join(intent.regions or [m for m in intent.markets if m != "Global"])
        scope = (", ".join(products) or "all medicines") + (f" in {where}" if where else ", all markets")
    notes = " ".join(state.notes)
    return (f"{notes} " if notes else "") + f"Got it: {scope}, showing {', '.join(names) or 'the key numbers'}."


def plain_outcome(result: StewardResult) -> str:
    """What happened, for someone who does not know what REUSE or a KPI id is."""
    verdict = getattr(result.decision.verdict, "value", result.decision.verdict)
    best = result.decision.best
    title = f"'{best.artifact.title}'" if best else "an existing report"
    if result.spec is None:
        if verdict == "NOT_FEASIBLE":
            return ("Those numbers aren't in official data yet, so I can't show anything reliable. "
                    "The BI team can see what's missing under the details.")
        return "I couldn't build this one. The BI team can see why under the details."
    return {
        "REUSE": f"This already exists: {title}. Here it is, on official data.",
        "EXTEND": f"{title} already covers most of this. Below is its next version with what you asked for; "
                  "the report owner approves it before it goes live.",
        "CONSOLIDATE": f"Several reports overlap here. Below is one combined version based on {title}; "
                       "the BI team approves it before the duplicates are retired.",
        "CREATE": "Nothing like this exists yet, so here is a new draft on official data. "
                  "The BI team approves it before it's published.",
    }.get(verdict, "Here is your dashboard.")


def render_evidence(decision) -> None:
    items = list(getattr(decision, "evidence", []) or [])
    sample = not items
    if sample:
        items = FAKE_EVIDENCE
    st.markdown("#### Evidence")
    lines = []
    for item in items:
        e = item if isinstance(item, dict) else item.model_dump()
        sev = str(getattr(e["severity"], "value", e["severity"])).lower()
        lines.append(ui.evidence_line(e["claim"], sev, e["rule_id"], [str(i) for i in e["record_ids"]], e["value"]))
    ui.html('<div class="bs-card">' + "".join(lines) + "</div>")
    if sample:
        st.caption("Sample evidence: not from the engine yet.")


@st.cache_resource
def get_frames() -> dict:
    return semantic.load_frames()


def render_dashboard(result: StewardResult, governance: bool = True, takeaway: bool = True) -> None:
    """W5-W7 on screen: the spec's dashboard on governed data, its changes, the lint gate, the governance footer."""
    spec = result.spec
    if spec is None:
        if result.decision.verdict in (Verdict.CLARIFY, "NOT_FEASIBLE"):
            st.caption("No dashboard yet: clarify the question first.")
        return
    key = spec.provenance.get("spec_hash", "spec")
    if not governance:
        ui.section("Dashboard preview")
    else:
        st.markdown(f"#### Dashboard: {spec.name}")
        st.caption(
            f"{spec.change_type.upper()} · version {spec.version} · "
            f"layout from {spec.provenance.get('layout_source', '?')} · spec {key}"
        )
    if spec.filters.get("site"):
        st.caption(f"Site: {spec.filters['site']} (the products and markets it supplies)")

    frames = get_frames()
    filters = (
        render_filters(spec, frames, key)
        if governance
        else _in_expander("Change product, market or months", lambda: render_filters(spec, frames, key))
    )
    dash = render_spec(spec, frames, filters)

    text = get_takeaway(key, tuple(sorted(filters.items())), result.question.text, dash) if takeaway else ""
    if text:
        ui.lead(text)
    cards = [ui.kpi_card(c.title, c.value, c.comparison, c.tone, c.note) for c in dash.cards]
    gaps = [ui.gap_card(g.title, g.reason) for g in dash.gaps]
    if governance:  # expert: every tile, denser
        ui.card_row(cards + gaps, per_row=5)
    else:  # the requester: the few KPIs that matter (3 to 5 tiles), a governed gap stays visible
        tiles = cards[: 5 - min(1, len(gaps))] + gaps[:1]
        ui.card_row(tiles, per_row=max(3, len(tiles)))
    if text:
        st.caption("Summary written by the AI from these numbers; every figure in it is checked against them.")
    figures = dash.figures if governance else dash.figures[:2]
    fig_cols = st.columns(2)
    for i, (_title, fig) in enumerate(figures):
        fig_cols[i % 2].plotly_chart(fig, use_container_width=True, key=f"fig_{key}_{i}")
    if dash.tables:
        if governance:
            render_tables(dash.tables)
        else:
            _in_expander("Tables", lambda: render_tables(dash.tables))
    if dash.dq:
        with st.expander("Data quality notes"):
            for note in dash.dq:
                st.write("- " + note)
    for label, text in dash.footer:
        if governance or label == "Data":  # ids and owners: BI team only; the synthetic-data label: everyone
            st.caption(f"**{label}:** {text}")

    if governance:
        render_governance(spec)


def render_filters(spec, frames, key: str) -> dict:
    products = ["All products"] + sorted(frames["dim_product"]["product_name"])
    markets = ["Global"] + sorted(frames["dim_market"]["market_id"])
    market_names = dict(zip(frames["dim_market"]["market_id"], frames["dim_market"]["market_name"], strict=True))
    months = [m.strftime("%Y-%m") for m in sorted(frames["dim_month"]["month"])]
    c1, c2, c3 = st.columns(3)
    product = c1.selectbox("Product", products, index=_index(products, spec.filters.get("product")), key=f"flt_p_{key}")
    market = c2.selectbox(
        "Market", markets, index=_index(markets, spec.filters.get("market", "Global")),
        format_func=lambda m: m if m == "Global" else f"{market_names[m]} ({m})", key=f"flt_m_{key}",
    )
    first, last = c3.select_slider("Months", options=months, value=(months[0], months[-1]), key=f"flt_t_{key}")
    return {
        "product": "All Pharma" if product == "All products" else product,
        "market": market, "month_from": first, "month_to": last,
    }


def render_tables(tables) -> None:
    for title, table in tables:
        st.markdown(f"**{title}**")
        if table.empty:
            st.caption("No rows past the threshold for this selection.")
        else:
            st.dataframe(table, hide_index=True, width="stretch")


def _in_expander(label: str, draw):
    with st.expander(label):
        return draw()


@st.cache_data(show_spinner=False)
def get_takeaway(spec_key: str, filters: tuple, question: str, _dash) -> str:
    """One LLM call per spec and filter selection (Streamlit reruns must not call the model again)."""
    from steward.takeaway import takeaway

    return takeaway(steward.llm, steward.settings.prompts_dir, question, _dash)


def render_ai(result: StewardResult, expanded: bool = True) -> None:
    """The AI investigation: what the model checked, step by step with record ids, and whether it agrees."""
    inv = result.investigation
    if inv is None:
        if steward.llm is None:
            st.caption("AI investigation is off (no language model). The rules evidence is below.")
        return
    verdict = getattr(result.decision.verdict, "value", result.decision.verdict)
    best = result.decision.best.artifact.id if result.decision.best else "no asset"
    if inv.agrees:
        status = ui.badge("AI agrees with the rules", ui.GOOD)
    else:
        mine = " ".join(x for x in (inv.recommendation, inv.best_asset_id) if x)
        status = ui.badge(f"AI suggests {mine} (rules: {verdict} {best}): a human decides", ui.WARN)
    with st.expander("How the AI investigated this request", expanded=expanded):
        ui.html(status + ui.trail([(s.finding, s.record_ids) for s in inv.steps]))
        if inv.why:
            ui.html(f'<div class="bs-muted"><b>Why:</b> {escape(inv.why)}</div>')
        for risk in inv.risks:
            ui.html(f'<div class="bs-muted">Risk: {escape(risk)}</div>')
        if inv.dropped_steps:
            st.caption(f"{inv.dropped_steps} AI step(s) dropped: they cited records or numbers the tools did not find.")


def render_governance(spec) -> None:
    """What changes, the lint gate and the exports: for the BI team, not for the requester."""
    key = spec.provenance.get("spec_hash", "spec")
    if spec.changes:
        with st.expander(f"What changes in this version ({len(spec.changes)})", expanded=True):
            for change in spec.changes:
                st.write(f"- **{change.kind.replace('_', ' ')}**: {change.detail}  `{', '.join(change.record_ids)}`")
    st.markdown("##### Lint gate (RULE-001..008, FOCUS, DATA)")
    if spec.lint:
        for r in spec.lint:
            ui.html(f"{ui.badge(r.status.upper(), LINT_COLOURS.get(r.status, ui.MUTED))} "
                    f"<b>{r.rule_id}</b> <span class='bs-muted'>{escape(r.message)}</span>")
    else:
        st.caption("The lint gate is not available yet; nothing blocks approval.")
    st.download_button(
        "Download spec JSON", spec.model_dump_json(indent=2), file_name=f"spec_{key}.json", mime="application/json",
        key=f"dl_spec_{key}",
    )
    render_pbip_download(spec, get_frames())


def render_pbip_download(spec, frames) -> None:
    """N7: the .PBIP draft (TMDL semantic model + data). A spec that the lint gate blocks is not exported."""
    from steward.lint import can_approve
    from steward.pbip import export_pbip

    if not can_approve(spec):
        st.caption("No .PBIP export: the spec is blocked by the lint gate or has not been linted.")
        return
    with tempfile.TemporaryDirectory() as tmp:
        path = export_pbip(spec, frames, Path(tmp))
        data = path.read_bytes()
    st.download_button("Download .PBIP (draft)", data, file_name=path.name, mime="application/zip",
                       key=f"dl_pbip_{spec.provenance.get('spec_hash', 'spec')}")
    st.caption(
        "DRAFT: never opened in Power BI Desktop. Infeasible KPIs (gaps) are not in the model; "
        "the report holds no visuals yet."
    )


def _index(options: list[str], value: str | None) -> int:
    return options.index(value) if value in options else 0


def render_result(result: StewardResult) -> None:
    """The ruling, top to bottom: headline sentence, verdict strip, dashboard preview, why, approval; the BI team's
    details (ids, lint, exports, AI trail) behind a toggle. Expert: the same order, denser, ids and details open."""
    novice = st.session_state.get("novice_result")
    best = result.decision.best
    word = verdict_word(result)
    if novice:
        ui.ruling(_headline(result, st.session_state.get("result_intent")), word, verdict_reason(result))
        render_dashboard(result, governance=False)
        ui.section("Why")
        ui.why(why_sentences(result))
        render_human_decision(result)
        st.write("")
        if st.toggle("Show details for the BI team", key="show_details"):
            render_ai(result, expanded=True)
            render_details(result, dashboard=True)
        return
    ui.ruling(verdict_title(result.decision.verdict) + (f": {best.artifact.title}" if best else ""), word,
              verdict_reason(result), ids=[best.artifact.id] if best else None)
    ui.section("Why")
    ui.why(why_sentences(result))
    render_ai(result)
    render_details(result, dashboard=False)
    render_dashboard(result)
    render_human_decision(result)


def verdict_word(result: StewardResult) -> str:
    """REUSE, EXTEND, CONSOLIDATE, CREATE, or MIGRATE / RESCUE when the spec's change type says so."""
    change = (result.spec.change_type if result.spec is not None else "").upper()
    if change in ("MIGRATE", "RESCUE"):
        return change
    return str(getattr(result.decision.verdict, "value", result.decision.verdict))


def verdict_reason(result: StewardResult) -> str:
    """One line in plain words: why this verdict, naming the report it is about."""
    best = result.decision.best
    title = f"'{best.artifact.title}'" if best else "An existing report"
    word = verdict_word(result)
    if result.spec is None:
        return plain_outcome(result)
    return {
        "REUSE": f"{title} already answers this.",
        "EXTEND": f"{title} covers most of this; this is its next version.",
        "CONSOLIDATE": f"Several reports overlap; one combined version based on {title} replaces them.",
        "MIGRATE": f"{title} moves to Power BI with what you asked for.",
        "RESCUE": f"{title} answers this but has no active owner; a new owner takes it over.",
        "CREATE": "Nothing in the catalog answers this, so this is a new draft on official data.",
    }.get(word, plain_outcome(result))


def why_sentences(result: StewardResult) -> list[str]:
    """Up to three plain sentences: the rule in words, then what the AI review concluded."""
    out = [r for r in result.decision.reasons if r][:2]
    inv = result.investigation
    if inv is not None:
        if inv.agrees:
            out.append("An AI review of the same evidence agrees with this ruling.")
        else:
            out.append(f"An AI review suggests {inv.recommendation or 'a different answer'} instead; a person decides.")
    return out[:3]


def _headline(result: StewardResult, intent) -> str:
    theme = steward.interviewer.themes.get(getattr(intent, "theme", ""), {})
    if result.spec is not None and theme:
        scope = result.spec.name.split(":")[0]
        return f"{scope}: {theme['label']}"
    return result.spec.name if result.spec is not None else "No dashboard yet"


def render_details(result: StewardResult, dashboard: bool) -> None:
    decision = result.decision
    st.markdown("#### Full explanation")
    st.markdown(result.explanation)
    render_evidence(decision)
    if dashboard and result.spec is not None:
        render_governance(result.spec)

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


def render_human_decision(result: StewardResult) -> None:
    decision = result.decision
    if decision.verdict not in APPROVE_LABELS:
        return

    if not user.can("approve"):
        render_send_to_bi(result)
        return
    novice = st.session_state.get("novice_result")
    ui.section("Next step: BI team approval" if novice else "Human decision")
    requested_by = st.session_state.get("requested_by")
    if requested_by:
        st.caption(f"Requested by {requested_by}.")
    signed = f"{actor}, requested by {requested_by}" if requested_by else actor  # journal: who asked, who approved
    owner = None
    if decision.verdict == Verdict.CREATE or (decision.best and not decision.best.artifact.has_owner):
        owner = st.text_input("Report owner", key="owner")
    blocked = [r for r in (result.spec.lint if result.spec else []) if r.status == "block"]
    if blocked:
        st.error("Approve is disabled by the lint gate: " + "; ".join(f"{r.rule_id}: {r.message}" for r in blocked))
    reason = st.text_input("Reason, if you send it back", key="reject_reason")
    col_ok, col_no, _ = st.columns([1, 1, 2])
    with col_ok:
        if st.button(APPROVE_LABELS[decision.verdict], type="primary", width="stretch", disabled=bool(blocked)):
            try:
                entry = steward.governance.approve(result, actor=signed, owner=owner or None)
            except ValueError as error:
                st.error(str(error))
            else:
                steward.reload()
                created = f" New artifact: {entry.created_artifact_id}." if entry.created_artifact_id else ""
                st.success("Approved and recorded in the journal." + created)
                st.session_state.result = None
                st.session_state.pop("requested_by", None)
    with col_no:
        if st.button("Send back", width="stretch"):
            try:
                steward.governance.reject(result, actor=signed, reason=reason)
            except ValueError as error:
                st.error(str(error))
            else:
                st.info("Sent back and recorded in the journal. The catalog was not changed.")
                st.session_state.result = None
                st.session_state.pop("requested_by", None)
    st.caption("Nothing is published until someone accountable approves it. Every decision is logged.")


def render_send_to_bi(result: StewardResult) -> None:
    """Workers and management cannot approve: they hand the ruling to the BI team (a builder approves or sends back).
    Demo: the queue lives in this browser session, so log out and in as a builder to review it."""
    if result.decision.verdict == Verdict.REUSE:
        st.caption("This report already exists: use it as it is. Nothing to approve.")
        return
    ui.section("Next step: BI team approval")
    queue = st.session_state.setdefault("approval_queue", [])
    if any(item["result"] is result for item in queue):
        st.info("Sent to the BI team. A builder reviews it, then approves it or sends it back.")
        return
    label = "Request this from the BI team" if user.role == "worker" else "Send to the BI team for approval"
    if st.button(label, type="primary"):
        queue.append({
            "result": result, "intent": st.session_state.get("result_intent"),
            "novice": st.session_state.get("novice_result"), "from": user.label, "plant": user.plant,
        })
        st.rerun()
    st.caption("Only a builder (BI team) can approve. Demo: log out and log in as a builder to review it.")


def render_queue() -> None:
    """Builders: requests waiting for approval, oldest first. Review opens the ruling with its requester."""
    if not user.can("approve") or st.session_state.get("result"):
        return
    render_floor_requests()
    queue = st.session_state.get("approval_queue") or []
    if not queue:
        return
    ui.section(f"Waiting for your approval ({len(queue)})")
    for i, item in enumerate(queue):
        text, col = st.columns([5, 1])
        text.markdown(f"**{item['result'].question.text}**  \n"
                      f"{verdict_title(item['result'].decision.verdict)} · from {item['from']}, {item['plant']}")
        if col.button("Review", key=f"review_{i}", width="stretch"):
            queue.pop(i)
            st.session_state.update(
                result=item["result"], result_intent=item["intent"], novice_result=item["novice"],
                requested_by=item["from"], interview=None,
                messages=[{"role": "user", "content": item["result"].question.text},
                          {"role": "assistant", "content": f"Request from {item['from']} at {item['plant']}."}],
            )
            st.rerun()


def render_floor_requests() -> None:
    """Builders: requests from the production floor (steward/worker.py). Access to another department -> grant or
    decline (demo: any builder grants). A missing number -> start it: the full pipeline runs, requester attached."""
    requests = [r for r in st.session_state.get("floor_requests", []) if r["status"] == "open"]
    if not requests:
        return
    ui.section(f"Requests from the floor ({len(requests)})")
    for i, req in enumerate(requests):
        text, ok, no = st.columns([4, 1, 1])
        if req["kind"] == "access":
            who = f"{req['username']} ({req['from_department']}, {req['plant']})"
            who += f" +{len(req['also'])} more" if req.get("also") else ""
            text.markdown(f"**{req['department']} data for {who}**  \nNeeds: {req['need']}, {req['cadence'].lower()}")
            if ok.button("Grant", key=f"grant_{i}", width="stretch"):
                grants = st.session_state.setdefault("grants", {}).setdefault(req["username"], [])
                if req["department"] not in grants:
                    grants.append(req["department"])
                _decide_request(req, "granted")
        else:
            also = f" +{len(req['also'])} more" if req.get("also") else ""
            who = f"{req['username']}{also} ({req['from_department']}, {req['plant']})"
            text.markdown(f"**{req['need']}** for {who}  \n"
                          "No report they can open has it yet")
            if ok.button("Start it", key=f"start_{i}", width="stretch"):
                st.session_state.update(pending_question=f"{req['need']} for {req['plant']}",
                                        next_requested_by=req["who"], interview=None, messages=[], result=None)
                _decide_request(req, "started")
        if no.button("Decline", key=f"decline_{i}", width="stretch"):
            _decide_request(req, "declined")


def _decide_request(req: dict, status: str) -> None:
    req["status"] = status
    log_request(steward.data_dir, req, status, actor)
    st.rerun()


@st.cache_data
def supply_rows() -> list[tuple[str, str, str]]:
    """(product_name, market_id, site) from Supply_Operations: which plant supplies which product x market."""
    frames = get_frames()
    supply = frames["fact_supply"].merge(frames["dim_product"][["product_id", "product_name"]], on="product_id")
    return list(supply[["product_name", "market_id", "supply_source"]].itertuples(index=False, name=None))


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


# Tabs by role (steward/auth.py ACTIONS): maintenance is the BI team's, the journal is management's and up.
TABS = [("Ask", "ask"), ("Catalog health", "maintain"), ("Orphan rescue", "maintain"), ("Journal", "view_journal"),
        ("Catalog", "view")]
_names = [name for name, action in TABS if user.can(action)]
_tabs = dict(zip(_names, st.tabs(_names), strict=True))
tab_ask, tab_health, tab_orphan, tab_journal, tab_catalog = (_tabs.get(name) for name, _ in TABS)

SKIP_LABEL = "Use recommended"


def render_options() -> None:
    """The pending question's answers as flat pills, then "Use recommended" as a quiet text button."""
    state = st.session_state.get("interview")
    if state is None or state.done:
        return
    with st.container(horizontal=True, key="bs-options"):
        for i, label in enumerate(state.options):
            if st.button(label, key=f"opt_{state.questions_asked}_{i}"):
                st.session_state.pending_answer = label
                st.rerun()
        if st.button(SKIP_LABEL, key=f"opt_{state.questions_asked}_skip", type="tertiary",
                     help="Answer every remaining question with the recommended choice"):
            st.session_state.pending_skip = True
            st.rerun()


def render_messages(extra: str | None = None) -> None:
    """The conversation. The newest line rises in; the current question carries its counter. The last outcome
    line is not repeated when the ruling below says it."""
    from steward.intent import MAX_QUESTIONS

    messages = list(st.session_state.get("messages", []))
    if extra:
        messages.append({"role": "user", "content": extra})
    if st.session_state.get("result") and messages and messages[-1].get("summary"):
        messages = messages[:-1]
    state = st.session_state.get("interview")
    pending = state is not None and not state.done and not extra
    parts = []
    for n, m in enumerate(messages):
        last = n == len(messages) - 1
        counter = f"Question {state.questions_asked} of {MAX_QUESTIONS}" if pending and last else ""
        parts.append(ui.message(m["role"], m["content"], new=last, counter=counter))
    if parts:
        ui.html("".join(parts))


with tab_ask:
    if user.role == "worker":
        worker_view.render(steward, user, supply_rows(), render_dashboard)
    else:
        top = st.container()
        typed = st.chat_input("Ask in your own words")
        below = st.container()
        question = (typed or st.session_state.pop("pending_answer", None)
                    or st.session_state.pop("pending_question", None))
        skip = st.session_state.pop("pending_skip", False)
        work = skip or bool(question and question.strip())
        if work:  # the building state: the conversation so far and a still skeleton, replaced when the answer is ready
            with top:
                building = st.empty()
                with building.container():
                    render_messages(extra="Use the recommended setup" if skip else question.strip())
                    ui.html(ui.typing("Thinking"))  # the AI is working: visible under the question
                    ui.skeleton(full=skip or bool(st.session_state.get("expert_mode")))
            if skip:
                skip_to_defaults()
            else:
                ask(question.strip())
            building.empty()
        with top:
            render_queue()
            if not st.session_state.get("messages"):
                ui.ask_hero("What do you need to know?")
            else:
                render_messages()
                render_options()
                if st.session_state.get("result"):
                    render_result(st.session_state.result)
        if not st.session_state.get("messages"):
            with below, st.container(horizontal=True, key="bs-examples"):
                for chip in CHIPS if ON_DATA_PACK else EXAMPLES[:3]:
                    if st.button(chip, key=f"chip_{chip}"):
                        st.session_state.pending_question = chip
                        st.rerun()


def render_health() -> None:
    """The IT pain in three numbers from the catalog, then one sortable table."""
    from steward.linking import artifact_variants

    health = steward.health()
    retire = {r.artifact_id for r in health.retire}
    rows, low, variant_assets, no_owner = [], 0, 0, 0
    for a in steward.catalog.artifacts.values():
        variants = artifact_variants(a, steward.catalog)
        owner_ok = bool(a.owner) and a.owner_active
        low += a.views_30d < 1000
        variant_assets += bool(variants)
        no_owner += not owner_ok
        rows.append({
            "id": a.id, "report": a.title, "views (30 days)": a.views_30d,
            "non-canonical KPIs": len(variants),
            "owner": a.owner or "missing", "owner status": "active" if owner_ok else (a.owner_status or "missing"),
            "platform": a.platform or "-", "retire candidate": a.id in retire,
        })
    ui.big_numbers([
        (f"{low:,}", f"of {len(rows):,} reports have under 1,000 views in 30 days"),
        (f"{variant_assets:,}", "reports use a non-canonical KPI definition"),
        (f"{no_owner:,}", "reports have a missing or inactive owner"),
    ])
    st.caption(f"{len(health.duplicates)} likely duplicate pairs, {len(health.retire)} retirement candidates. "
               "Sort any column by clicking its header.")
    st.dataframe(rows, width="stretch", hide_index=True, height=520)


if tab_health is not None:
    with tab_health:
        render_health()

if tab_orphan is not None:
    with tab_orphan:
        render_orphan_rescue()


def render_journal() -> None:
    entries = steward.governance.entries()
    if entries:
        ui.timeline([
            (e.timestamp.strftime("%d %b %H:%M"), e.question, e.verdict.value, e.action.value, e.actor)
            for e in reversed(entries)
        ])
        with st.expander("All journal fields (spec hash, lint, ids)"):
            st.dataframe(
                [
                    {
                        "when": e.timestamp.strftime("%Y-%m-%d %H:%M"), "who": e.actor, "question": e.question,
                        "verdict": e.verdict.value, "decision": e.action.value, "report": e.artifact_id,
                        "created": e.created_artifact_id, "reason": e.reason, "spec": e.spec_hash, "lint": e.lint,
                    }
                    for e in reversed(entries)
                ],
                width="stretch",
                hide_index=True,
            )
    else:
        st.caption("No decisions yet. Approved and sent-back rulings appear here, newest first.")


if tab_journal is not None:
    with tab_journal:
        render_journal()
        floor_log = read_log(steward.data_dir)
        if floor_log:
            with st.expander(f"Requests from the floor ({len(floor_log)} log lines)"):
                st.dataframe([{k: r.get(k) for k in ("logged_at", "who", "kind", "department", "need", "cadence",
                                                    "status", "decided_by")} for r in reversed(floor_log)],
                             width="stretch", hide_index=True)

with tab_catalog:
    term = st.text_input("Search the catalog", placeholder="Report name, id, owner or domain").strip().lower()
    catalog_rows = [
        {
            "id": a.id, "title": a.title, "domain": a.domain, "owner": a.owner, "certified": a.certified,
            "refreshed": a.last_refreshed, "views": a.views_30d, "status": a.status.value, "version": a.version,
        }
        for a in steward.catalog.artifacts.values()
        if can_see(user, a.product_scope, a.market_scope, supply_rows())
    ]
    if user.plants != COMPANY:
        st.caption(f"Reports for {', '.join(user.plants)}: the products and markets your plant supplies. "
                   "Other plants and company-wide reports come through a builder.")
    if term:
        catalog_rows = [r for r in catalog_rows if any(term in str(v).lower() for v in r.values())]
    st.caption(f"{len(catalog_rows):,} reports")
    st.dataframe(catalog_rows, width="stretch", hide_index=True, height=560)
