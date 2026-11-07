"""The worker's Ask tab (production floor): fast info, no interview, reuse only (steward/worker.py).

Layout: a green Chat button, the suggested prompts for the worker's department, and a differently coloured Other
button that opens a three-step mini grill to request another department's data at the same plant. Answers show the
existing report on the worker's plant; what no report covers can be requested from the BI team in one click.
"""

from __future__ import annotations

import streamlit as st
import ui

from steward.auth import User, can_request
from steward.worker import (
    CADENCES,
    DEPARTMENTS,
    NEEDS,
    Suggestions,
    WorkerAnswer,
    log_request,
    open_item,
    other_plant,
    prompts_for,
    refusal,
    request_entry,
    reuse_only,
    same_request,
    sites_named,
    suggest,
)

CSS = f"""<style>
.st-key-w-chat button {{ background: {ui.GOOD} !important; color: #fff !important; border: none; }}
.st-key-w-chat button:hover {{ background: #166534 !important; }}
.st-key-w-other button {{ background: {ui.WARN} !important; color: #fff !important; border: none; }}
.st-key-w-other button:hover {{ background: #92400e !important; }}
</style>"""  # !important: steward.css styles every secondary button with a grey surface


def render(steward, user: User, supply, render_dashboard) -> None:
    st.html(CSS)
    ui.ask_hero("What do you need right now?")
    st.caption(f"{user.plant} · {user.department}. Answers come from reports that already exist.")
    granted = st.session_state.setdefault("grants", {}).get(user.username, [])
    with st.container(horizontal=True, key="w-row"):
        if st.button("Chat", key="w-chat", help="Ask in your own words"):
            st.session_state.update(w_chat=True, w_other=None)
        for i, prompt in enumerate(prompts_for(steward, user.department)):
            if st.button(prompt.label, key=f"w-p-{i}"):
                _answer_prompt(steward, user, prompt, supply)
        if st.button("Other department", key="w-other", help="Request another department's data at your plant"):
            st.session_state.update(w_other={"step": 1}, w_chat=False, w_answer=None)
    for dept in granted:  # departments a builder shared with this worker
        st.caption(f"Shared with you: {dept}")
        with st.container(horizontal=True, key=f"w-shared-{dept}"):
            for i, prompt in enumerate(prompts_for(steward, dept)):
                if st.button(prompt.label, key=f"w-s-{dept}-{i}"):
                    _answer_prompt(steward, user, prompt, supply)

    if st.session_state.get("w_chat"):
        _chat(steward, user, supply)
    if st.session_state.get("w_other"):
        _render_other(steward, user)
    answer = st.session_state.get("w_answer")
    if answer:
        _render_answer(steward, user, *answer, render_dashboard)


def _answer_prompt(steward, user: User, prompt, supply) -> None:
    st.session_state.w_other = None
    if prompt.not_governed:
        st.session_state.w_answer = (prompt.label, WorkerAnswer(not_governed=prompt.not_governed))
    else:
        st.session_state.w_answer = (prompt.label, reuse_only(steward, user, list(prompt.metric_ids), prompt.label,
                                                               supply))


def _close_chat() -> None:
    st.session_state.w_chat = False


@st.dialog("Chat", width="large", on_dismiss=_close_chat)
def _chat(steward, user: User, supply) -> None:
    """Pop-out chat. The AI answers with what to open (single KPIs or existing reports), never a new build.
    While it works, a "Thinking" bubble sits under the question. A pick closes the chat and opens the answer."""
    log = st.session_state.setdefault("w_chat_log", [])
    if not log:
        st.caption(f"Ask about {user.plant}. I point you to numbers and reports that already exist.")
    for n, m in enumerate(log):
        last = n == len(log) - 1
        ui.html(ui.message(m["role"], m["text"], new=last))
        if not m.get("items"):
            pass
        elif m.get("chosen"):  # a pick is history, not a button any more
            st.caption(f"You chose {m['chosen']}")
        elif not last:  # an older answer the user moved on from: its options, as text
            st.caption("Suggested: " + ", ".join(i.label for i in m["items"]))
        else:
            with st.container(horizontal=True, key=f"w-picks-{n}"):
                for k, item in enumerate(m["items"]):
                    if st.button(item.label, key=f"w-pick-{n}-{k}", help=item.why or None):
                        m["chosen"] = item.label
                        picked = open_item(steward, user, item.id, supply)
                        st.session_state.update(w_answer=(item.label, picked), w_chat=False)
                        st.rerun()
        if m.get("lacks"):  # the full picture needs data we do not govern: said plainly, a request is possible
            st.caption(f"Not in governed data yet, so not shown: {', '.join(m['lacks'])}. You can always ask the BI "
                       "team for it.")
            if last and not m.get("asked") and st.button("Ask the BI team for it", key=f"w-lack-{n}",
                                                         type="tertiary"):
                m["asked"] = True
                _send(steward, request_entry(user, "report", ", ".join(m["lacks"])))
    pending = st.session_state.pop("w_pending", None)
    if pending:
        slot = st.empty()
        slot.html(ui.typing("Thinking"))
        site = other_plant(user, sites_named(pending))
        answer = Suggestions(refusal(user, site)) if site else suggest(steward, user, pending, supply)
        slot.empty()
        log.append({"role": "assistant", "text": answer.reply, "items": answer.items, "lacks": answer.lacks})
        st.rerun(scope="fragment")
    with st.form("w-chat-form", clear_on_submit=True, border=False):
        text = st.text_input("Your question", placeholder="e.g. how do I plan my day?", label_visibility="collapsed")
        if st.form_submit_button("Send", type="primary") and text.strip():
            log.append({"role": "user", "text": text.strip()})
            st.session_state.w_pending = text.strip()
            st.rerun(scope="fragment")


def _names(steward, metric_ids: list[str]) -> str:
    return ", ".join(steward.catalog.metrics[m].name for m in metric_ids if m in steward.catalog.metrics)


def _render_answer(steward, user: User, label: str, answer: WorkerAnswer, render_dashboard) -> None:
    ui.section(label)
    if answer.refused:
        st.warning(answer.refused)
        return
    if answer.result is not None:
        a = answer.result.decision.best.artifact
        st.caption(f"From the existing report {a.title} ({a.id}), owner {a.owner or 'not set'}, refreshed "
                   f"{a.last_refreshed}. Numbers use the governed definitions, filtered to {user.plant}.")
        render_dashboard(answer.result, governance=False, takeaway=False)
    need = answer.not_governed or _names(steward, answer.missing)
    if answer.not_governed:
        st.info(f"{answer.not_governed.capitalize()} is not measured in governed data yet, so there is no report "
                "to open. The BI team can take it to the data owner.")
    elif answer.missing:
        st.info(f"Not in any report you can open yet: {need}.")
    elif answer.result is None:
        st.info("I could not match that to a number we report. Try one of the buttons, or ask the BI team.")
        need = label
    if answer.not_governed or answer.missing or answer.result is None:
        if st.button("Ask the BI team for it", key=f"w-req-{label}", type="tertiary"):
            _send(steward, request_entry(user, "report", need))


def _render_other(steward, user: User) -> None:
    """Mini grill, three short steps: which department, what exactly, how often. Then one request for a builder."""
    state = st.session_state.w_other
    step = state["step"]
    ui.section(f"Request another department's data · step {min(step, 3)} of 3")
    if step == 1:
        st.write("Which department's data do you need?")
        options = [d for d in DEPARTMENTS if can_request(user, user.plant, d)[0]]
        _choices(options, "dept", 2)
    elif step == 2:
        st.write(f"What do you need from {state['dept']}?")
        _choices(NEEDS.get(state["dept"], []), "need", 3)
        other = st.text_input("Something else", key="w-other-text")
        if st.button("Use this", key="w-other-text-ok") and other.strip():
            st.session_state.w_other.update(need=other.strip(), step=3)
            st.rerun()
    elif step == 3:
        st.write("How often do you need it?")
        _choices(CADENCES, "cadence", 4)
    else:
        summary = (f"{user.username}, {user.department} at {user.plant}, needs {state['dept']} data: "
                   f"{state['need']}, {state['cadence'].lower()}.")
        st.write(f"Request for the BI team: {summary}")
        send, cancel, _ = st.columns([1, 1, 3])
        if send.button("Send request", type="primary", key="w-other-send"):
            _send(steward, request_entry(user, "access", state["need"], state["dept"], state["cadence"]))
            st.session_state.w_other = None
        if cancel.button("Cancel", key="w-other-cancel"):
            st.session_state.w_other = None
            st.rerun()


def _choices(options: list[str], field: str, next_step: int) -> None:
    with st.container(horizontal=True, key=f"w-choice-{field}"):
        for option in options:
            if st.button(option, key=f"w-{field}-{option}"):
                st.session_state.w_other.update({field: option, "step": next_step})
                st.rerun()


def _send(steward, entry: dict) -> None:
    """One card per need per plant: a second worker asking for the same thing joins the open request (+1)."""
    requests = st.session_state.setdefault("floor_requests", [])
    existing = same_request(requests, entry)
    if existing:
        if entry["username"] != existing["username"] and entry["username"] not in existing.setdefault("also", []):
            existing["also"].append(entry["username"])
            log_request(steward.data_dir, existing, "open", entry["who"])
        st.info(f"Already asked for by {existing['username']}. You were added to that request, so the BI team "
                f"sees {1 + len(existing.get('also', []))} people need it.")
        return
    requests.append(entry)
    log_request(steward.data_dir, entry, "open", entry["who"])
    st.success("Sent to the BI team. A builder picks it up and you see the result here.")
