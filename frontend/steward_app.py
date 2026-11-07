"""BI Steward decision screen. Run: make ui  (Windows: .\\run.ps1 ui)"""

import dataclasses
import inspect
import os
import sys
import tempfile
from html import escape
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ui  # noqa: E402  (frontend/ui.py: design system)
import worker_view  # noqa: E402  (frontend/worker_view.py: the production-floor Ask tab)

from steward import Steward, apptoken, semantic  # noqa: E402
from steward.auth import COMPANY, DEMO_ACCOUNTS, account, can_see, login  # noqa: E402
from steward.catalog import CHANGES_FILE  # noqa: E402
from steward.explain import TemplateExplainer  # noqa: E402
from steward.governance import JOURNAL_FILE  # noqa: E402
from steward.inbox import FILE as INBOX_FILE  # noqa: E402
from steward.inbox import Inbox  # noqa: E402
from steward.intent import Intent  # noqa: E402
from steward.linking import kpi_index  # noqa: E402
from steward.models import GapKind, StewardResult, Verdict  # noqa: E402
from steward.receipts import Meter, receipts  # noqa: E402
from steward.render import render as render_spec  # noqa: E402
from steward.suggest import Suggestions  # noqa: E402
from steward.worker import log_request, other_plant, own_plant_scope, read_log, refusal  # noqa: E402

try:  # autofill while typing (requirements.in); without it the chips still work
    from streamlit_searchbox import st_searchbox
except ImportError:  # pragma: no cover - a venv set up before the dependency was added
    st_searchbox = None

EXAMPLES = [
    "What is herbicide revenue in LATAM vs plan for Q3?",
    "Net revenue by region for Q3",
    "Fungicide margin in EMEA by quarter",
    "NPS by channel",
    "OTIF by country in LATAM, monthly",
    "Logistics carbon footprint by country",
]


# Empty-state chips, in business words. Pharma only (CLAUDE.md scope), so no crop examples.
CHIPS = [
    "How are we doing in LATAM this quarter?",
    "Is supply safe for Plant-B?",
    "Xarelto net sales in Germany",
    "Net sales for Eylea in Japan",  # REUSE AST-0079 on the interview path (Donatas)
]

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

APP_MODE = apptoken.app_mode()  # started by the desktop launcher (app/main.py): native login, no browser chrome
st.set_page_config(page_title="BI Steward", layout="wide",
                   initial_sidebar_state="expanded" if APP_MODE else "collapsed")
ui.inject()
if APP_MODE:  # mechanics, not design (Donatas styles the app in steward.css): hide what makes it look like a website
    st.html("<style>[data-testid='stHeader'],[data-testid='stToolbar'],[data-testid='stStatusWidget'],"
            "[data-testid='stDecoration'],[data-testid='stSidebarCollapseButton'],footer{display:none!important}"
            ".block-container{padding-top:1.2rem}</style>")


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
        st.caption(
            "Demo login, mocked (not real authentication). Accounts:  \n"
            + "  \n".join(f"{name} / {pw} ({role})" for name, pw, role in DEMO_ACCOUNTS)
        )


if APP_MODE and st.session_state.get("user") is None and "u" in st.query_params:
    # the native login window checked the password; this signed token hands the account over (steward/apptoken.py)
    _who, _token = st.query_params.get("u", ""), st.query_params.get("t", "")
    if apptoken.verify(_who, _token) and account(_who):
        st.session_state.user = account(_who)
    st.query_params.clear()

user = st.session_state.get("user")
if user is None:
    if APP_MODE:  # the desktop app signs in from its own native window, never from a form in the page
        ui.ask_hero("Signed out")
        st.markdown(f'<a href="{os.environ.get(apptoken.ENV_LOGIN_URL, "")}" target="_top">Sign in again</a>',
                    unsafe_allow_html=True)
    else:
        render_login()
    st.stop()


@st.cache_resource
def get_steward() -> Steward:
    s = Steward()
    s.meter = Meter(s.llm)  # receipts (T2.5): AI calls and time per phase; numbers live per session
    return s


steward = get_steward()
inbox = Inbox(steward.data_dir)  # shared handoffs: approvals, floor requests, grants, notices (T2.3)
suggestions = Suggestions()  # autofill memory: user app-data folder, survives restarts and Reset demo
if not st.session_state.get("inbox_id"):  # e.g. after the desktop app's Log out link: nothing stays stuck in review
    inbox.release_reviews_of(user.label)


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

# Workspace pages by role (steward/auth.py ACTIONS): maintenance is the BI team's, the journal is management's and up.
TABS = [
    ("Ask", "ask"),
    ("Catalog health", "maintain"),
    ("Orphan rescue", "maintain"),
    ("Journal", "view_journal"),
    ("Catalog", "view"),
]
_names = [name for name, action in TABS if user.can(action)]
PLANTS = "all (company)" if user.plants == COMPANY else ", ".join(user.plants)

with st.sidebar:
    st.markdown("#### BI Steward")
    with st.container(key="bs-rail"):  # left navigation rail (T2.6); Donatas styles .st-key-bs-rail
        PAGE = st.radio("Workspace", _names, key="nav", label_visibility="collapsed")
    st.caption(f"{llm_label()} · data {steward.as_of}")
    with st.container(key="bs-user"):  # styled by Donatas (.st-key-bs-user): the compact user card
        st.markdown(f"**{user.username}** · {user.role.capitalize()}")
        st.caption(
            f"{user.name}, {user.location}  \nPlant: {PLANTS}"
            + (f"  \nDepartment: {user.department}" if user.department else "")
        )
    if APP_MODE:  # back to the native login window (the launcher's page); this session ends with the page
        st.markdown(f'<a class="bs-logout" href="{os.environ.get(apptoken.ENV_LOGIN_URL, "")}" target="_top">'
                    "Log out</a>", unsafe_allow_html=True)
    elif st.button("Log out", width="stretch"):  # the approval queue stays: the demo hands it to a builder
        if st.session_state.get("inbox_id"):  # an undecided review goes back to the queue
            inbox.release(st.session_state["inbox_id"])
        for key in ("user", "messages", "interview", "result", "result_intent", "novice_result", "requested_by",
                    "inbox_id"):
            st.session_state.pop(key, None)
        st.rerun()
    actor = user.label
    if user.can("expert_mode"):
        st.toggle("Expert mode: skip the interview", key="expert_mode")
    else:
        st.session_state.expert_mode = False
    st.divider()
    if user.can("maintain") and st.button("Reset demo", width="stretch"):
        for name in (CHANGES_FILE, JOURNAL_FILE, INBOX_FILE):  # not the autofill memory: it is kept on purpose
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
        st.session_state.phases = {}  # receipts: this request's time and AI calls per phase
    if st.session_state.get("expert_mode"):
        with _phase("decide"):  # expert: understanding, search, decision and explanation in one call
            asked = steward.ask(text)
        with _phase("build"):
            built = steward.build(asked, None, user)
        _finish(built, novice=False)  # W3-W6: the dashboard this decision implies
        remember(text, "expert", built)
        return
    state = st.session_state.get("interview")
    with _phase("understand"):
        if state is not None and not state.done:
            state = steward.interviewer.answer(state, text)
        else:
            st.session_state.result = None
            state = reused(text)
            st.session_state.request_path = "reused" if state is not None else "interview"
            if state is None:
                # T3.1: a manager is never asked "which plant?" about their own plant
                home = user.plant if user is not None and user.role == "management" else ""
                state = steward.interviewer.start(text, home_plant=home)
    site = other_plant(user, state.intent.sites)
    if site:  # management: own plant (and granted ones) only; the rest goes through a builder
        st.session_state.interview = None
        messages.append({"role": "assistant", "content": refusal(user, site)})
        suggestions.log(user, state.intent.text or text, "interview", "REFUSED", state.intent.model_dump(mode="json"),
                        other_plant=site)
        return
    _continue(state)


def typeahead_options(term: str) -> list[tuple[str, str]]:
    """While typing the first message: the typed words first (Enter asks them), then matching requests this person's
    team asked (then the data pack's), most asked first."""
    term = term.strip()
    if not term:
        return []
    hits = suggestions.for_user(user, typed=term, k=6) if len(term) >= 2 else []
    options = [(f"Ask: {term}", term)] if term.lower() not in {s.text.lower() for s in hits} else []
    return options + [(f"{s.text}  ·  asked by {s.people}", s.text) for s in hits]


def render_typeahead() -> None:
    if st_searchbox is None:
        return
    _, mid, _ = st.columns([1, 2.2, 1])  # the chat box's width
    with mid, st.container(key="bs-typeahead"):
        picked = st_searchbox(
            typeahead_options,
            placeholder="Ask in your own words: your team's requests appear as you type",
            key="typeahead",
            clear_on_submit=True,
            debounce=200,
        )
    if picked:
        st.session_state.pending_question = picked
        st.session_state.pop("typeahead", None)
        st.rerun()


def reused(text: str):
    """Autofill: the same words as a request colleagues (same role and plant) already confirmed -> their Intent, no
    interview and no AI call. None: nothing learned for this person, so the interview runs as usual."""
    from steward.interview import InterviewState

    known = suggestions.intent_for(user, text)
    if not known:
        return None
    try:
        intent = Intent(**known)
    except Exception:  # noqa: BLE001 - an entry from an older Intent shape: interview instead
        return None
    where = "BI team" if user.role == "builder" else user.plant
    state = InterviewState(intent=intent, turns=[("user", text)], question=None)
    state.notes.append(f"Colleagues ({where}) asked exactly this before; I'm using the setup they confirmed.")
    return state


def skip_to_defaults() -> None:
    """ "Skip - use recommended": fill every open question with its default and build."""
    state = st.session_state.get("interview")
    if state is None or state.done:
        return
    st.session_state.messages.append({"role": "user", "content": "Use the recommended setup"})
    with _phase("understand"):
        state = steward.interviewer.finish_with_defaults(state)
    _continue(state)


def _continue(state) -> None:
    st.session_state.interview = state
    if not state.done:
        st.session_state.messages.append({"role": "assistant", "content": state.question})
        return
    st.session_state.interview = None
    state.intent = own_plant_scope(user, state.intent)  # management: no plant named -> own plant (supply data)
    st.session_state.messages.append({"role": "assistant", "content": understood(state)})
    with _phase("decide"):
        result = steward.ask_intent(state.intent)
    with _phase("explain"):
        result = steward.investigate(result, state.intent)
    with _phase("build"):
        result = steward.build(result, state.intent, user)
    _finish(result, novice=True, intent=state.intent)
    remember(state.intent.text, st.session_state.pop("request_path", "interview"), result, state.intent)


def remember(text: str, path: str, result: StewardResult, intent=None) -> None:
    """Autofill memory: every first message goes to the backtest log, whatever came of it; a request that ended in
    a build also becomes a suggestion for colleagues (same role and plant)."""
    verdict = result.decision.verdict.value
    dumped = intent.model_dump(mode="json") if intent is not None else None
    best = result.decision.best.artifact.id if result.decision.best else None
    phases = st.session_state.get("phases") or {}
    llm = sum(p.get("llm", 0) for p in phases.values())
    suggestions.log(user, text, path, verdict, dumped, best, llm_calls=llm, spec=result.spec is not None)
    if dumped and text and verdict in ("REUSE", "EXTEND", "CREATE", "CONSOLIDATE"):
        suggestions.record(user, text, dumped)


def _phase(name: str):
    """Time + AI calls of one step, kept in this session (the engine and its meter are shared)."""
    return steward.meter.phase(name, into=st.session_state.setdefault("phases", {}))


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
    st.session_state.result_phases = dict(st.session_state.get("phases") or {})


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
    return (f"{notes} " if notes else "") + f"Got it: {scope}, showing {', '.join(names) or 'the key numbers'}." + (
        consequence(intent)
    )


def consequence(intent) -> str:
    """T3.1 confirmation: what the answer will cost before it runs (how many existing reports are checked first)."""
    from steward.decision import fit

    index = fit.coverage_index(steward.catalog)
    carriers = set().union(*(index.get(m, set()) for m in intent.metric_ids)) if intent.metric_ids else set()
    if not carriers:
        return ""
    return f" {len(carriers)} existing reports already carry these numbers; I check them before building anything."


def plain_outcome(result: StewardResult) -> str:
    """What happened, for someone who does not know what REUSE or a KPI id is."""
    verdict = getattr(result.decision.verdict, "value", result.decision.verdict)
    best = result.decision.best
    title = f"'{best.artifact.title}'" if best else "an existing report"
    if result.spec is None:
        if verdict == "NOT_FEASIBLE":
            return (
                "Those numbers aren't in official data yet, so I can't show anything reliable. "
                "The BI team can see what's missing under the details."
            )
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
    themed = "theme" in inspect.signature(render_spec).parameters and hasattr(ui, "theme")  # Donatas: day | night
    dash = render_spec(spec, frames, filters, theme=ui.theme()) if themed else render_spec(spec, frames, filters)

    text = get_takeaway(key, tuple(sorted(filters.items())), result.question.text, dash) if takeaway else ""
    if text:
        ui.lead(text)
    if getattr(dash, "archetype", "") == "OVERVIEW":  # Donatas (Gajus OK 1108-011104): band, tiles, 12-column grid
        scope = " · ".join(f"{k} {v}" for k, v in spec.filters.items()) or "Bayer Pharma"
        ui.overview(dash, key, scope=scope, as_of=str(steward.as_of), verdict=verdict_word(result))
        dash = dataclasses.replace(dash, cards=[], gaps=[], figures=[], tables=[])  # the template blocks draw nothing
    cards = [ui.kpi_card(c.title, c.value, c.comparison, c.tone, c.note) for c in dash.cards]
    gaps = [ui.gap_card(g.title, g.reason) for g in dash.gaps]
    if governance:  # expert: every tile, denser
        ui.card_row(cards + gaps, per_row=5)
    else:  # the requester: the few KPIs that matter (3 to 5 tiles), a governed gap stays visible
        keep = max(2, 5 - len(gaps))  # every labelled gap stays visible; the KPI tiles make room
        tiles = cards[:keep] + gaps
        ui.card_row(tiles, per_row=min(5, max(3, len(tiles))))
    cut = [p for p in spec.provenance.get("layout_hidden", "").split("; ") if p]
    if not governance:
        cut += [c.title for c in dash.cards[max(2, 5 - len(dash.gaps)) :]]
    if cut:  # never a silent drop (Martynas's review): say what this view leaves out
        st.caption(f"Not shown for your role: {', '.join(dict.fromkeys(cut))}.")
    if text:
        st.caption("Summary written by the AI from these numbers; every figure in it is checked against them.")
    figures = dash.figures if governance else dash.figures[:2]
    fig_cols = st.columns(2)
    for i, (_title, fig) in enumerate(figures):
        fig_cols[i % 2].plotly_chart(fig, use_container_width=True, key=f"fig_{key}_{i}", theme=None)
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
        "Market",
        markets,
        index=_index(markets, spec.filters.get("market", "Global")),
        format_func=lambda m: m if m == "Global" else f"{market_names[m]} ({m})",
        key=f"flt_m_{key}",
    )
    first, last = c3.select_slider("Months", options=months, value=(months[0], months[-1]), key=f"flt_t_{key}")
    return {
        "product": "All Pharma" if product == "All products" else product,
        "market": market,
        "month_from": first,
        "month_to": last,
    }


def render_tables(tables) -> None:
    for title, table in tables:
        st.markdown(f"**{title}**")
        if table.empty:
            st.caption("No rows past the threshold for this selection.")
        else:
            ui.table(table, hide_index=True, width="stretch")


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
            ui.html(
                f"{ui.badge(r.status.upper(), LINT_COLOURS.get(r.status, ui.MUTED))} "
                f"<b>{r.rule_id}</b> <span class='bs-muted'>{escape(r.message)}</span>"
            )
    else:
        st.caption("The lint gate is not available yet; nothing blocks approval.")
    st.download_button(
        "Download spec JSON",
        spec.model_dump_json(indent=2),
        file_name=f"spec_{key}.json",
        mime="application/json",
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
    spec_key = spec.provenance.get("spec_hash", "spec")
    st.download_button(
        "Download .PBIP (draft)",
        data,
        file_name=path.name,
        mime="application/zip",
        key=f"dl_pbip_{spec_key}",
    )
    if st.checkbox(
        "Live refresh: the report loads its data from this app (needs this app running)", key=f"pbip_live_{spec_key}"
    ):
        from steward import pbip_server  # the service starts here, on first use, inside this process

        try:
            live = pbip_server.register(spec, steward.data_dir, pbip_server.ensure_running(steward.data_dir))
            with tempfile.TemporaryDirectory() as tmp:
                live_path = export_pbip(spec, frames, Path(tmp), live=live)
                live_data = live_path.read_bytes()
            st.download_button(
                "Download .PBIP with live refresh",
                live_data,
                file_name=live_path.name,
                mime="application/zip",
                key=f"dl_pbip_live_{spec_key}",
            )
            st.caption(
                f"Start this app first, open the file in Power BI Desktop, click Refresh. The first Refresh asks for "
                f"credentials for {live.base_url}: choose Anonymous. Not a login: the key only separates exports."
            )
        except RuntimeError as exc:
            st.caption(str(exc))
    st.caption(
        "Checked in Power BI Desktop 2.159 (the REQ-0001 export and all 12 governed measures). "
        "Infeasible KPIs (gaps) are not in the model."
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
        render_receipts(result)
        render_human_decision(result)
        st.write("")
        if st.toggle("Show details for the BI team", key="show_details"):
            render_ai(result, expanded=True)
            render_details(result, dashboard=True)
        return
    ui.ruling(
        verdict_title(result.decision.verdict) + (f": {best.artifact.title}" if best else ""),
        word,
        verdict_reason(result),
        ids=[best.artifact.id] if best else None,
    )
    ui.section("Why")
    ui.why(why_sentences(result))
    render_receipts(result)
    render_ai(result)
    render_details(result, dashboard=False)
    render_dashboard(result)
    render_human_decision(result)


def render_receipts(result: StewardResult) -> None:
    """The chain, one line per step: what went in, what came out, why, what it cost (T2.5, the pipeline slide).
    The Decide line carries the gate checklist. Donatas styles .st-key-bs-receipts."""
    rows = receipts(result, st.session_state.get("result_intent"), steward.catalog, steward.as_of,
                    st.session_state.get("result_phases"))
    ui.section("How this was decided")
    with st.container(key="bs-receipts"):
        for n, r in enumerate(rows, 1):
            cost = []
            if r.ms is not None:
                cost.append(f"{r.ms / 1000:.1f} s" if r.ms >= 1000 else f"{r.ms:.0f} ms")
            if r.llm_calls:
                cost.append(f"{r.llm_calls} AI call{'s' if r.llm_calls > 1 else ''}")
            meta = " · ".join(cost)
            st.markdown(
                f"**{n}. {r.step}**  {escape(r.inp)} → **{escape(r.out)}**"
                + (f"  \n{escape(r.why)}" if r.why else "")
                + (f"  \n:gray[{meta}]" if meta else "")
                + (f"  \n:red[{escape(r.failed)}]" if r.failed else "")
            )
            if r.gates:
                with st.expander(f"Checklist for {r.ids[0] if r.ids else 'the best report'} "
                                 f"({sum(g.ok for g in r.gates)}/{len(r.gates)} pass)"):
                    for g in r.gates:
                        mark = ":green[✓]" if g.ok else ":red[✗]"
                        action = f" → *{g.action}*" if g.action and not g.ok else ""
                        st.markdown(f"{mark} {g.name}" + (f" · {escape(g.detail)}" if g.detail else "") + action)


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
        ui.table(
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
            ui.table(
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
                if st.session_state.get("inbox_id"):
                    inbox.decide(st.session_state.pop("inbox_id"), "approved", actor, detail=created.strip())
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
                if st.session_state.get("inbox_id"):
                    inbox.decide(st.session_state.pop("inbox_id"), "sent_back", actor, reason=reason)
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
    if inbox.is_waiting(user.username, result):
        st.info("Sent to the BI team. A builder reviews it, then approves it or sends it back; you see the outcome "
                "here when you next open the app.")
        return
    label = "Request this from the BI team" if user.role == "worker" else "Send to the BI team for approval"
    if st.button(label, type="primary"):
        inbox.send(result, st.session_state.get("result_intent"), bool(st.session_state.get("novice_result")), user)
        st.rerun()
    st.caption("Only a builder (BI team) can approve. It reaches every builder, in any browser.")


def render_queue() -> None:
    """Builders: requests waiting for approval, oldest first. Review opens the ruling with its requester."""
    if st.session_state.get("inbox_id") and not st.session_state.get("result"):  # left a review undecided
        inbox.release(st.session_state.pop("inbox_id"))
    if not user.can("approve") or st.session_state.get("result"):
        return
    render_floor_requests()
    queue = inbox.open_approvals()
    if not queue:
        return
    ui.section(f"Waiting for your approval ({len(queue)})")
    for item in queue:
        text, col = st.columns([5, 1])
        text.markdown(
            f"**{item['question']}**  \n"
            f"{verdict_title(Verdict(item['verdict']))} · from {item['from']}, {item['plant']}"
        )
        if col.button("Review", key=f"review_{item['id']}", width="stretch"):
            taken = inbox.take(item["id"], actor)
            if taken is None:  # another builder opened it first
                st.rerun()
            row, taken_result, taken_intent = taken
            st.session_state.update(
                result=taken_result,
                result_intent=taken_intent,
                novice_result=row["novice"],
                requested_by=row["from"],
                inbox_id=row["id"],
                result_phases={},  # the requester's timings are not ours to show
                interview=None,
                messages=[
                    {"role": "user", "content": row["question"]},
                    {"role": "assistant", "content": f"Request from {row['from']} at {row['plant']}."},
                ],
            )
            st.rerun()


def render_floor_requests() -> None:
    """Builders: requests from the production floor (steward/worker.py). Access to another department -> grant or
    decline (demo: any builder grants). A missing number -> start it: the full pipeline runs, requester attached."""
    requests = inbox.floor("open")
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
                _decide_request(req, "granted")
        else:
            also = f" +{len(req['also'])} more" if req.get("also") else ""
            who = f"{req['username']}{also} ({req['from_department']}, {req['plant']})"
            text.markdown(f"**{req['need']}** for {who}  \nNo report they can open has it yet")
            if ok.button("Start it", key=f"start_{i}", width="stretch"):
                if req.get("metric_ids"):  # structured: run the chain on the governed ids and the plant (C9)
                    intent = Intent(
                        text=f"{req['need']} for {req['plant']}", metric_ids=req["metric_ids"], sites=[req["plant"]],
                        decision_supported="monitor",
                        confidence={"metric_ids": 1.0, "sites": 1.0, "decision_supported": 1.0},
                    )
                    st.session_state.update(
                        result=steward.build(steward.ask_intent(intent), intent, user),
                        result_intent=intent, novice_result=True, requested_by=req["who"], interview=None,
                        result_phases={},
                        messages=[{"role": "user", "content": intent.text},
                                  {"role": "assistant", "content": f"Request from {req['who']} at {req['plant']}."}],
                    )
                else:  # free text only (not governed yet): the interview starts from the words
                    st.session_state.update(
                        pending_question=f"{req['need']} for {req['plant']}",
                        next_requested_by=req["who"],
                        interview=None,
                        messages=[],
                        result=None,
                    )
                _decide_request(req, "started")
        if no.button("Decline", key=f"decline_{i}", width="stretch"):
            _decide_request(req, "declined")


def _decide_request(req: dict, status: str) -> None:
    inbox.decide_floor(req["id"], status, actor)  # grants and the requester's notice live in the shared inbox
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
    ui.table(
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


with st.container(key="bs-topbar", horizontal=True):  # top bar (T2.6); Donatas styles .st-key-bs-topbar
    st.markdown(f"**{PAGE}**")
    st.caption(f"{user.username} · {user.role.capitalize()} · {PLANTS}")
    st.caption("AI: " + llm_label())
for _notice in inbox.pop_notices(user.username):  # outcomes of this user's requests, from another browser too
    st.info(_notice)
st.html("<style>[class*='st-key-bs-hidden-']{display:none!important}</style>")
_tabs = {name: st.container(key=("bs-page-" if name == PAGE else "bs-hidden-") + name.lower().replace(" ", "-"))
         for name in _names}
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
        if st.button(
            SKIP_LABEL,
            key=f"opt_{state.questions_asked}_skip",
            type="tertiary",
            help="Answer every remaining question with the recommended choice",
        ):
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
        if not st.session_state.get("messages") and st_searchbox is not None:
            # the first message is typed in the autofill box (render_typeahead): one visible input, not two
            st.html('<style>[data-testid="stChatInput"]{display:none}</style>')
        below = st.container()
        question = (
            typed or st.session_state.pop("pending_answer", None) or st.session_state.pop("pending_question", None)
        )
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
                render_typeahead()
            else:
                render_messages()
                render_options()
                if st.session_state.get("result"):
                    render_result(st.session_state.result)
        if not st.session_state.get("messages"):
            # autofill: colleagues' requests (same role and plant) first, the curated examples fill the row
            learned = [(s.text, f"Asked by {s.people} people in your team") for s in suggestions.for_user(user, seed=False)]
            known = {c for c, _ in learned}
            chips = (learned + [(c, None) for c in CHIPS if c not in known])[:4]
            with below, st.container(horizontal=True, key="bs-examples"):
                for chip, why in chips:
                    if st.button(chip, key=f"chip_{chip}", help=why):
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
        rows.append(
            {
                "id": a.id,
                "report": a.title,
                "views (30 days)": a.views_30d,
                "non-canonical KPIs": len(variants),
                "owner": a.owner or "missing",
                "owner status": "active" if owner_ok else (a.owner_status or "missing"),
                "platform": a.platform or "-",
                "retire candidate": a.id in retire,
            }
        )
    ui.big_numbers(
        [
            (f"{low:,}", f"of {len(rows):,} reports have under 1,000 views in 30 days"),
            (f"{variant_assets:,}", "reports use a non-canonical KPI definition"),
            (f"{no_owner:,}", "reports have a missing or inactive owner"),
        ]
    )
    st.caption(
        f"{len(health.duplicates)} likely duplicate pairs, {len(health.retire)} retirement candidates. "
        "Sort any column by clicking its header."
    )
    ui.table(rows, width="stretch", hide_index=True, height=520)


def render_department_map() -> None:
    """Builders: which KPIs each plant department sees first. The AI drafts, the builder edits and approves; workers
    read only the approved map (steward/departments.py). Relevance only: access stays in steward/auth.py."""
    from steward import departments
    from steward.worker import DEPARTMENTS

    ui.section("Floor KPIs per department")
    state = departments.state(steward.data_dir)
    approved, draft = state.get("approved"), state.get("draft")
    st.caption(f"Approved by {approved['by']} on {approved['at'][:16].replace('T', ' ')}. Workers see this map."
               if approved else "Not approved yet: workers see the built-in defaults.")
    if st.button("Draft with AI", key="dept_draft"):
        with st.spinner("The AI is drafting the map from the governed KPI list"):
            proposal = departments.propose(steward.llm, steward.settings.prompts_dir, steward.catalog, DEPARTMENTS)
        departments.save_draft(steward.data_dir, proposal, actor)
        st.rerun()
    base = (draft or approved or {}).get("map") or departments.defaults()
    if draft:
        who = "the AI" if draft["source"] == "ai" else "the defaults (no AI model connected)"
        st.caption(f"Draft from {who}, opened by {draft['by']}. Check it, edit it, then approve.")
    names = {m.id: m.name for m in steward.catalog.metrics.values()}
    version = (draft or approved or {}).get("at", "default")
    edited, cols = {}, st.columns(2)
    for i, dept in enumerate(DEPARTMENTS):
        with cols[i % 2]:
            edited[dept] = st.multiselect(dept, options=list(names), format_func=names.get, max_selections=4,
                                          default=[m for m in base.get(dept, []) if m in names],
                                          key=f"dept_{dept}_{version}")
            reasons = [f"{names[m]}: {draft['why'][f'{m}@{dept}']}" for m in edited[dept]
                       if draft and draft.get("why", {}).get(f"{m}@{dept}")]
            if reasons:
                st.caption(" · ".join(reasons))
            if draft and draft.get("missing", {}).get(dept):
                st.caption("Not governed yet: " + ", ".join(draft["missing"][dept]))
    if st.button("Approve for the floor", type="primary", key="dept_approve"):
        departments.approve(steward.data_dir, edited, actor, steward.catalog)
        st.success("Approved. Workers in these departments now see these KPIs first.")
        st.rerun()
    if state.get("log"):
        with st.expander("Change log"):
            ui.table(list(reversed(state["log"])), width="stretch", hide_index=True)


if tab_health is not None:
    with tab_health:
        render_health()
        render_department_map()

if tab_orphan is not None:
    with tab_orphan:
        render_orphan_rescue()


def render_journal() -> None:
    entries = steward.governance.entries()
    if entries:
        ui.timeline(
            [
                (e.timestamp.strftime("%d %b %H:%M"), e.question, e.verdict.value, e.action.value, e.actor)
                for e in reversed(entries)
            ]
        )
        with st.expander("All journal fields (spec hash, lint, ids)"):
            ui.table(
                [
                    {
                        "when": e.timestamp.strftime("%Y-%m-%d %H:%M"),
                        "who": e.actor,
                        "question": e.question,
                        "verdict": e.verdict.value,
                        "decision": e.action.value,
                        "report": e.artifact_id,
                        "created": e.created_artifact_id,
                        "reason": e.reason,
                        "spec": e.spec_hash,
                        "lint": e.lint,
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
                ui.table(
                    [
                        {
                            k: r.get(k)
                            for k in (
                                "logged_at",
                                "who",
                                "kind",
                                "department",
                                "need",
                                "cadence",
                                "status",
                                "decided_by",
                            )
                        }
                        for r in reversed(floor_log)
                    ],
                    width="stretch",
                    hide_index=True,
                )

with tab_catalog:
    term = st.text_input("Search the catalog", placeholder="Report name, id, owner or domain").strip().lower()
    catalog_rows = [
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
        if can_see(user, a.product_scope, a.market_scope, supply_rows())
    ]
    if user.plants != COMPANY:
        st.caption(
            f"Reports for {', '.join(user.plants)}: the products and markets your plant supplies. "
            "Other plants and company-wide reports come through a builder."
        )
    if term:
        catalog_rows = [r for r in catalog_rows if any(term in str(v).lower() for v in r.values())]
    st.caption(f"{len(catalog_rows):,} reports")
    ui.table(catalog_rows, width="stretch", hide_index=True, height=560)
