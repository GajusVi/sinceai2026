"""Builder health, root-cause view (DECISION T3.2, Panu point 6): what to fix first and one
person's reports.

The data comes from steward/estate_view.py. The Catalog health tab calls `render(catalog, retire_ids)` once; nothing
here touches the verdict, the journal or the catalog: it only reads.
"""

from __future__ import annotations

import streamlit as st
import ui

from steward.decision import lifecycle
from steward.estate_view import EstateView, MyAssets, estate_view, my_assets

ISSUE_WORDS = {
    "FAILED_REFRESH": "refresh failed",
    "REFRESH_WARNING": "refresh warning",
    "NO_ACTIVE_OWNER": "no active owner",
    "RETIRE_CANDIDATE": "retire candidate",
    "LOW_USAGE": "little use",
}
KIND_WORDS = {"FIX_REFRESH": "fix refresh", "REASSIGN_OWNER": "reassign owner"}
TOP = 8


def headline(view: EstateView) -> list[tuple[str, str]]:
    """The three numbers of the tab. The first is the finding: a certificate on a report whose data does not refresh."""
    return [
        (str(len(view.certified_on_failed_refresh)), "certified reports sit on a refresh that has failed"),
        (str(view.failing_models), f"failing models take down {view.failed_refresh_assets} reports"),
        (
            str(view.inactive_owners),
            f"owners have left; {view.inactive_owner_assets} reports need a new one, {view.no_owner_assets} have none",
        ),
    ]


def action_rows(view: EstateView, limit: int | None = None) -> list[dict]:
    actions = view.actions if limit is None else view.actions[:limit]
    return [
        {
            "#": i,
            "do this": a.text,
            "reports": len(a.heals),
            "certified": a.certified_heals,
            "kind": KIND_WORDS.get(a.kind, a.kind),
        }
        for i, a in enumerate(actions, 1)
    ]


def owner_options(view: EstateView) -> list[tuple[str, str]]:
    """(owner id, label): people who own reports that need something, the biggest problem first."""
    people = lifecycle.reference().owners
    counts: dict[str, int] = {}
    for f in view.owner_fixes:
        if f.owner_id:
            counts[f.owner_id] = counts.get(f.owner_id, 0) + len(f.assets)
    for m in view.model_fixes:  # active owners whose reports sit on a failing model
        for owner in m.owner_ids:
            counts.setdefault(owner, 0)
    out = []
    for owner_id, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        p = people.get(owner_id, {})
        who = f"{owner_id} · {p.get('owner_name', '?')} · {p.get('role', '?')}"
        out.append((owner_id, f"{who} ({n} reports need a new owner)" if n else who))
    return out


def asset_rows(mine: MyAssets) -> list[dict]:
    return [
        {
            "id": a.id,
            "report": a.title,
            "certificate": a.endorsement,
            "needs": ", ".join(ISSUE_WORDS.get(i, i) for i in a.issues) or "healthy",
            "users / month (last 3)": a.users_last_3m if a.users_last_3m is not None else "-",
            "trend": a.trend,
        }
        for a in mine.assets
    ]


def render(catalog, retire_ids: set[str] | frozenset[str] = frozenset()) -> None:
    view = estate_view(catalog)
    ui.section("Repair plan: fix the causes, not the reports")
    ui.big_numbers(headline(view))
    st.caption(
        "Each line is one action and says how many reports it puts right. Start at the top. "
        "Nothing is assigned here: a proposed successor still has to accept."
    )
    ui.table(action_rows(view, TOP), width="stretch", hide_index=True)
    if len(view.actions) > TOP:
        with st.expander(f"All {len(view.actions)} actions"):
            ui.table(action_rows(view), width="stretch", hide_index=True, height=360)

    ui.section("Reports of one person")
    options = owner_options(view)
    if not options:
        st.caption("No report needs an owner or a refresh fix.")
        return
    owner_by_label = {label: owner_id for owner_id, label in options}
    owner = owner_by_label[st.selectbox("Owner", list(owner_by_label), key="estate_owner")]
    mine = my_assets(catalog, owner, frozenset(retire_ids))
    st.caption(f"{mine.needing_attention} of {mine.total} reports of this person need attention, the worst first.")
    ui.table(asset_rows(mine), width="stretch", hide_index=True)
