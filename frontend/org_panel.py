"""People tab (Gajus, Sun 8 Nov): the org map. Company > plant > department > person as a cluster map with an
inspector, a ticket badge on anyone with an open ticket, and role changes a manager proposes and a builder approves.

Data and rules live in steward/orgmap.py (tested); this file only draws and wires buttons. Switch: STEWARD_PEOPLE=off
hides the tab. The tab hook in frontend/steward_app.py is one call: `org_panel.render(user, steward.data_dir, inbox)`.
"""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st
import ui

from steward import orgmap, roster
from steward.auth import User

PALETTE = {  # hex, because Plotly cannot read the CSS variables of steward.css (same zinc tokens as DESIGN.md)
    "night": {
        "bg": "#09090B",
        "panel": "#111114",
        "line": "#3F3F46",
        "ink": "#FAFAFA",
        "muted": "#A1A1AA",
        "builder": "#60A5FA",
        "management": "#FBBF24",
        "worker": "#A1A1AA",
        "ticket": "#F87171",
    },
    "day": {
        "bg": "#FFFFFF",
        "panel": "#FAFAFA",
        "line": "#A1A1AA",
        "ink": "#09090B",
        "muted": "#52525B",
        "builder": "#1D4ED8",
        "management": "#B45309",
        "worker": "#52525B",
        "ticket": "#B91C1C",
    },
}
ROLE_WORD = {"worker": "Worker", "management": "Manager", "builder": "Builder"}
FIELD_WORD = {"department": "Department", "sub_role": "Sub-role", "reports_to": "Reports to", "plant": "Plant"}
KIND_WORD = {"approval": "waiting for approval", "request": "request to the BI team"}


def known_sub_roles(role: str) -> list[str]:
    if role == "worker":
        return sorted({s for subs in roster.DEPARTMENT_SUBROLES.values() for s in subs})
    return list(roster.MANAGER_SUBROLES if role == "management" else roster.BUILDER_SUBROLES)


def figure(nodes: list[orgmap.Node], theme: str) -> go.Figure:
    """One screen: a box per plant, a block per department, a dot per person. Red ring + flag = an open ticket."""
    pal = PALETTE[theme]
    shapes, labels = [], {"x": [], "y": [], "text": [], "size": []}
    for n in nodes:
        if n.kind in ("plant", "department"):
            shapes.append(
                {
                    "type": "rect",
                    "x0": n.x - (0.3 if n.kind == "department" else 0.45),
                    "y0": n.y - 0.1,
                    "x1": n.x + n.w - (0.3 if n.kind == "department" else 0.45),
                    "y1": n.y + n.h - 0.1,
                    "line": {
                        "color": pal["line"],
                        "width": 1 if n.kind == "department" else 0.6,
                        "dash": "solid" if n.kind == "department" else "dot",
                    },
                    "layer": "below",
                }
            )
        if n.kind in ("plant", "department", "company"):
            labels["x"].append(n.x - (0.2 if n.kind == "department" else 0.45))
            labels["y"].append(n.y + (0.45 if n.kind == "department" else 0.9 if n.kind == "plant" else 0))
            labels["text"].append(n.label)
            labels["size"].append(13 if n.kind == "company" else 12 if n.kind == "plant" else 10)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=labels["x"],
            y=labels["y"],
            mode="text",
            text=labels["text"],
            textposition="middle right",
            textfont={"color": pal["ink"], "size": 11, "family": "Geist Mono, monospace"},
            hoverinfo="skip",
        )
    )
    for ticketed in (False, True):
        people = [n for n in nodes if n.kind == "person" and bool(n.tickets) == ticketed]
        if not people:
            continue
        fig.add_trace(
            go.Scatter(
                x=[n.x for n in people],
                y=[n.y for n in people],
                mode="markers+text" if ticketed else "markers",
                text=[f"⚑ {n.label.split()[0]}" for n in people] if ticketed else None,
                textposition="top center",
                textfont={"color": pal["ticket"], "size": 10, "family": "Geist Mono, monospace"},
                customdata=[n.username for n in people],
                marker={
                    "size": 17 if ticketed else 12,
                    "color": [pal[n.role] for n in people],
                    "line": {"color": pal["ticket"] if ticketed else pal["panel"], "width": 3 if ticketed else 1},
                },
                hovertext=[
                    f"{n.label} · {n.sub_role}" + (f" · {n.tickets} ticket(s)" if n.tickets else "") for n in people
                ],
                hovertemplate="%{hovertext}<br>%{customdata}<extra></extra>",
            )
        )
    xmax = max([n.x + n.w for n in nodes] or [1]) + 0.5
    ymax = max([n.y + n.h for n in nodes] or [1]) + 0.3
    fig.update_layout(
        shapes=shapes,
        height=int(max(300, min(560, (ymax + 1.5) * 34))),
        margin={"l": 0, "r": 0, "t": 4, "b": 4},
        showlegend=False,
        paper_bgcolor=pal["panel"],
        plot_bgcolor=pal["panel"],
        xaxis={"visible": False, "range": [-0.7, xmax], "fixedrange": True},
        yaxis={"visible": False, "range": [ymax, -1.8], "fixedrange": True},
    )
    return fig


def selected_username(event) -> str:
    try:
        points = event.selection.points
    except AttributeError:
        return ""
    for point in points or []:
        value = point.get("customdata")
        if isinstance(value, (list, tuple)):
            value = value[0] if value else ""
        if value:
            return str(value)
    return ""


def render(user: User, data_dir, inbox) -> None:
    changes = orgmap.Changes(data_dir)
    everyone = orgmap.people(data_dir)
    shown = orgmap.visible(user, everyone)
    if not shown:
        st.caption("This tab is for managers and the BI team.")
        return
    ticket_map = orgmap.tickets(inbox)
    open_changes = changes.proposals("open")

    scope = "the whole company" if user.role == "builder" else " and ".join(user.plants)
    ui.section(f"People · {scope}")
    ui.big_numbers(
        [
            (str(len(shown)), "people on the map"),
            (str(sum(1 for p in shown if ticket_map.get(p.username))), "have an open ticket"),
            (str(len(open_changes)), "role changes waiting for approval"),
        ]
    )
    st.caption("Synthetic roster: invented names. A red flag on a person = an open ticket in the shared inbox.")

    plants = sorted({p.plant for p in shown if p.role != "builder"})
    c1, c2, c3 = st.columns([2, 2, 3])
    plant = c1.selectbox("Plant", ["All", *plants], key="org-plant")
    only_tickets = c2.toggle("Only people with a ticket", key="org-tickets")
    names = {f"{p.name} ({p.username})": p.username for p in shown}
    picked = c3.selectbox("Find a person", ["", *names], key="org-find", format_func=lambda s: s or "Type a name...")

    visible = [p for p in shown if (plant == "All" or p.plant == plant or p.role == "builder" and plant == "All")]
    if only_tickets:
        visible = [p for p in visible if ticket_map.get(p.username)]
    nodes = orgmap.layout(visible, ticket_map)

    if nodes:
        event = st.plotly_chart(
            figure(nodes, ui.theme()),
            key="org-graph",
            on_select="rerun",
            selection_mode="points",
            theme=None,
            config={"displayModeBar": False},
        )
        st.caption(
            "Amber = manager · blue = builder · grey = worker · red ring and ⚑ = open ticket. "
            "Click a dot to inspect it."
        )
    else:
        event = None
        st.caption("Nobody matches these filters.")
    username = names.get(picked) or (selected_username(event) if event is not None else "")
    by_name = {p.username: p for p in shown}
    if username in by_name:
        inspector(user, by_name[username], shown, ticket_map, changes, data_dir)
    else:
        st.caption("Click a person on the map, or search above.")

    proposals_block(user, changes, shown)


def inspector(user: User, person, shown, ticket_map, changes: orgmap.Changes, data_dir) -> None:
    ui.section(person.name)
    boss = next((p for p in shown if p.username == person.reports_to), None)
    reports = [p for p in shown if p.reports_to == person.username]
    ui.html(
        f"<div>{ui.badge(ROLE_WORD[person.role])} {ui.badge(person.sub_role or '-')} "
        f"{ui.chips([person.username])}</div>"
    )
    rows = {
        "Plant": person.plant if person.role != "builder" else "Whole company",
        "Department": person.department or "-",
        "Reports to": f"{boss.name} ({boss.sub_role})" if boss else "-",
        "Direct reports": str(len(reports)),
        "Location": person.location,
    }
    st.caption("  ·  ".join(f"{k}: {v}" for k, v in rows.items()))
    tickets = ticket_map.get(person.username, [])
    if tickets:
        st.markdown(f"**⚑ {len(tickets)} open ticket(s)**")
        for t in tickets:
            st.caption(f"{KIND_WORD.get(t['kind'], t['kind'])}: {t['text']} ({t['at'][:16].replace('T', ' ')})")
    else:
        st.caption("No open tickets.")
    if person.username == user.username or user.role not in ("management", "builder"):
        return
    if user.role == "management" and person.role == "builder":
        return
    verb = "Change" if user.role == "builder" else "Propose a change"
    with st.expander(verb, expanded=False):
        with st.form(f"org-form-{person.username}", border=False):
            field = st.selectbox(
                "What",
                [f for f in orgmap.EDITABLE if not (f == "department" and person.role != "worker")],
                format_func=lambda f: FIELD_WORD[f],
            )
            if field == "department":
                from steward.worker import DEPARTMENTS

                value = st.selectbox("New department", [d for d in DEPARTMENTS if d != person.department])
            elif field == "plant":
                value = st.selectbox("New plant", [p for p in roster.PLANTS if p != person.plant])
            elif field == "reports_to":
                value = st.selectbox(
                    "New boss",
                    [
                        p.username
                        for p in shown
                        if p.role in ("management", "builder") and p.username != person.username
                    ],
                    format_func=lambda u: f"{next(p.name for p in shown if p.username == u)} ({u})",
                )
            else:
                value = st.selectbox("New sub-role", [s for s in known_sub_roles(person.role) if s != person.sub_role])
            reason = st.text_input("Why", placeholder="one line, goes in the log")
            if st.form_submit_button("Apply now" if user.role == "builder" else "Send to the BI team", type="primary"):
                try:
                    if user.role == "builder":
                        changes.apply_now(user, person, field, value, reason)
                        st.session_state["org-flash"] = f"{person.name}: {FIELD_WORD[field].lower()} changed."
                    else:
                        changes.propose(user, person, field, value, reason)
                        st.session_state["org-flash"] = "Sent. A builder approves it; it is in the log."
                    st.rerun()
                except ValueError as why:
                    st.error(str(why))


def proposals_block(user: User, changes: orgmap.Changes, shown) -> None:
    flash = st.session_state.pop("org-flash", "")
    if flash:
        st.success(flash)
    visible = {p.username for p in shown}
    mine = [
        c
        for c in changes.proposals(None)
        if c["target"] in visible and (user.role == "builder" or c["by"] == user.username)
    ]
    waiting = [c for c in mine if c["status"] == "open"]
    ui.section(
        f"Role changes waiting for approval ({len(waiting)})"
        if user.role == "builder"
        else f"Your proposals ({len(mine)})"
    )
    if not waiting and user.role == "builder":
        st.caption("Nothing waiting.")
    for c in waiting if user.role == "builder" else []:
        st.markdown(
            f"**{c['target_name']}** · {FIELD_WORD[c['field']].lower()}: {c['old'] or '-'} → **{c['new']}**  "
            f"(by {c['by']}{' · ' + c['reason'] if c['reason'] else ''})"
        )
        a, b, _ = st.columns([1, 1, 4])
        for label, approve, col in (("Approve", True, a), ("Decline", False, b)):
            if col.button(label, key=f"org-{label}-{c['id']}"):
                try:
                    changes.decide(c["id"], user, approve)
                    st.rerun()
                except ValueError as why:
                    st.error(str(why))
    if user.role != "builder" and mine:
        ui.table(
            [
                {
                    "Person": c["target_name"],
                    "Change": f"{FIELD_WORD[c['field']]}: {c['old'] or '-'} → {c['new']}",
                    "Status": c["status"],
                    "Decided by": c.get("decided_by", ""),
                }
                for c in mine
            ],
            hide_index=True,
        )
    log = [j for j in changes.journal() if j.get("target") in visible][-12:]
    if log:
        ui.section("Change log")
        ui.table(
            [
                {
                    "When": j["at"][:16].replace("T", " "),
                    "Action": j["action"],
                    "Person": j.get("target_name") or j["target"],
                    "Change": f"{FIELD_WORD.get(j['field'], j['field'])}: {j.get('old') or '-'} → {j['new']}",
                    "By": j.get("decided_by") or j["by"],
                }
                for j in reversed(log)
            ],
            hide_index=True,
        )
