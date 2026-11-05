"""Decision screen: queue on the left, evidence on the right, approve/reject, export, audit trail.
Run: make ui   (or: make demo  -> DEMO_MODE replays cached outputs)"""

import json
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import audit, ingest, pipeline  # noqa: E402
from backend.config import ROOT, get_settings  # noqa: E402
from backend.models import Review  # noqa: E402

TITLE = "Product name"  # FRIDAY: name + one-line value statement with the number
TAGLINE = "For [user], turns [input] into [decision] so they can [benefit]."

st.set_page_config(page_title=TITLE, layout="wide")
st.markdown(
    """<style>
    .block-container {padding-top: 1.6rem; max-width: 1400px;}
    h1, h2, h3 {letter-spacing: -0.01em;}
    div[data-testid="stMetricValue"] {font-size: 1.9rem;}
    </style>""",
    unsafe_allow_html=True,
)

s = get_settings()
_, _, model = s.resolved()

with st.sidebar:
    st.subheader("Data")
    src = st.radio("Source", ["Demo inputs", "Upload file"], label_visibility="collapsed")
    uploaded = st.file_uploader("csv, xlsx, jsonl, json, pdf, docx, txt") if src == "Upload file" else None
    run = st.button("Score items", type="primary", use_container_width=True)
    st.divider()
    st.caption(
        f"Model: **{s.llm_provider} / {model or 'unset'}**  \n"
        f"LLM ready: **{s.llm_ready()}**  \nDemo mode: **{s.demo_mode}**"
    )
    if st.button("Reset audit log", use_container_width=True):
        audit.reset()
        st.session_state.pop("scored", None)

if run:
    if uploaded is not None:
        items = ingest.load(uploaded.name, uploaded.getvalue())
    else:
        items = ingest.load_path(ROOT / "demo" / "inputs.jsonl")
    with st.spinner(f"Scoring {len(items)} items"):
        st.session_state.scored = pipeline.score_all(items)

st.title(TITLE)
st.caption(TAGLINE)

scored = st.session_state.get("scored", [])
tab_queue, tab_proof, tab_audit = st.tabs(["Queue", "Proof", "Audit trail"])

with tab_queue:
    if not scored:
        st.info("Press **Score items** in the sidebar.")
    else:
        verdicts = audit.latest_verdicts()
        df = pd.DataFrame(
            [
                {
                    "Priority": r.decision.priority,
                    "Label": r.decision.label,
                    "Confidence": round(r.decision.confidence, 2),
                    "Item": r.item.text[:90],
                    "Status": verdicts.get(r.item.id, "open"),
                    "Source": r.source,
                }
                for r in scored
            ]
        )
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Items", len(df))
        m2.metric("Act now (P4-5)", int((df.Priority >= 4).sum()))
        m3.metric("Reviewed", int((df.Status != "open").sum()))
        m4.metric("Avg confidence", f"{df.Confidence.mean():.0%}")

        left, right = st.columns([3, 2], gap="large")
        with left:
            sel = st.dataframe(
                df,
                hide_index=True,
                use_container_width=True,
                height=520,
                on_select="rerun",
                selection_mode="single-row",
                column_config={"Confidence": st.column_config.ProgressColumn(min_value=0, max_value=1, format="%.2f")},
            )
        rows = sel.selection.rows if sel and sel.selection else []
        idx = rows[0] if rows else 0
        r = scored[idx]
        with right:
            d = r.decision
            st.subheader(f"{d.label.title()} · P{d.priority}")
            st.caption(f"{r.item.id} · confidence {d.confidence:.0%} · source {r.source}")
            st.markdown(f"**Recommended action:** {d.suggested_action}")
            st.markdown(f"**Why:** {d.reason}")
            if d.evidence:
                st.markdown("**Evidence**")
                for q in d.evidence:
                    st.markdown(f"> {q}")
            with st.expander("Full input"):
                st.write(r.item.text)
                if r.item.meta:
                    st.json(r.item.meta, expanded=False)
            note = st.text_input("Note (optional)", key=f"note-{r.item.id}")
            a, b = st.columns(2)
            if a.button("Approve", type="primary", use_container_width=True, key=f"ok-{r.item.id}"):
                audit.log_review(Review(item_id=r.item.id, verdict="approve", note=note))
                st.rerun()
            if b.button("Reject", use_container_width=True, key=f"no-{r.item.id}"):
                audit.log_review(Review(item_id=r.item.id, verdict="reject", note=note))
                st.rerun()

        approved = [x for x in scored if verdicts.get(x.item.id) == "approve"]
        if approved:
            out = pd.DataFrame([{"id": x.item.id, **x.decision.model_dump()} for x in approved])
            st.download_button("Export approved (CSV)", out.to_csv(index=False), "approved.csv", "text/csv")

with tab_proof:
    res_path = ROOT / "eval" / "results.json"
    if res_path.exists():
        res = json.loads(res_path.read_text(encoding="utf-8"))
        c1, c2, c3 = st.columns(3)
        c1.metric("Accuracy (hold-out)", f"{res['accuracy']:.0%}")
        c2.metric("Macro F1", f"{res['macro_f1']:.2f}")
        c3.metric("Hold-out size", res["n"])
        if res.get("misses"):
            st.markdown("**Misses (honest list)**")
            st.dataframe(pd.DataFrame(res["misses"]), hide_index=True, use_container_width=True)
    else:
        st.caption("Run `make eval` to fill this tab.")

    st.markdown("#### Euro impact")
    st.caption("Placeholder assumptions, not company data. Replace with the company's figures before quoting.")
    c1, c2, c3 = st.columns(3)
    vol = c1.number_input("Items per month (assumption)", value=2000, step=100)
    mins = c2.number_input("Minutes saved per item (assumption)", value=4.0, step=0.5)
    rate = c3.number_input("Loaded cost €/hour (assumption)", value=45, step=5)
    yearly = vol * 12 * mins / 60 * rate
    st.metric("Annual saving", f"€{yearly:,.0f}")
    st.caption(f"{vol:,} items/month × 12 × {mins} min ÷ 60 × €{rate}/h = €{yearly:,.0f}/year")

    if scored:
        fig = px.histogram(
            pd.DataFrame([x.decision.model_dump() for x in scored]), x="label", color_discrete_sequence=["#0E5E3B"]
        )
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=0, r=0, t=10, b=0), bargap=0.3)
        st.plotly_chart(fig, use_container_width=True)

with tab_audit:
    rows = audit.fetch()
    st.caption("Every model output and every human decision, timestamped (UTC).")
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True, height=480)
    st.download_button("Download audit trail (CSV)", audit.to_csv(rows), "audit.csv", "text/csv")
