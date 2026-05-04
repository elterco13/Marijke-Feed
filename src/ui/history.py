"""
Search history page.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd

from src.db.models import SearchRun, Profile, Result
from src.db.session import get_session


def render_history() -> None:
    st.markdown('<div class="section-header">📅 Search History</div>', unsafe_allow_html=True)

    with get_session() as session:
        runs = (
            session.query(SearchRun, Profile)
            .join(Profile, SearchRun.profile_id == Profile.id)
            .order_by(SearchRun.started_at.desc())
            .limit(50)
            .all()
        )
        history_data = []
        for run, profile in runs:
            duration = None
            if run.started_at and run.finished_at:
                duration = int((run.finished_at - run.started_at).total_seconds())

            history_data.append({
                "Run #": run.id,
                "Feed": profile.name,
                "Status": run.status,
                "Started": run.started_at.strftime("%Y-%m-%d %H:%M") if run.started_at else "",
                "Duration (s)": duration,
                "Raw Results": run.total_raw_results,
                "Normalized": run.total_normalized_results,
                "Deduped": run.total_deduped_results,
                "Notes": run.notes or "",
                "_run_id": run.id,
            })

    if not history_data:
        st.info("No search runs yet. Use **Run Search** to get started.")
        return

    # Summary metrics
    total_runs = len(history_data)
    done_runs = sum(1 for r in history_data if r["Status"] == "done")
    total_results = sum(r["Deduped"] for r in history_data)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Runs", total_runs)
    with col2:
        st.metric("Successful Runs", done_runs)
    with col3:
        st.metric("Total Results Stored", total_results)

    st.divider()

    # Display table
    display_df = pd.DataFrame([
        {k: v for k, v in r.items() if not k.startswith("_")}
        for r in history_data
    ])

    def _style_status(val):
        if val == "done":
            return "color: #10b981; font-weight: bold;"
        elif val == "error":
            return "color: #ef4444; font-weight: bold;"
        elif val == "running":
            return "color: #22d3ee; font-weight: bold;"
        return ""

    styled_df = display_df.style.map(_style_status, subset=["Status"])
    st.dataframe(styled_df, use_container_width=True, hide_index=True)

    st.divider()

    # View/delete run
    st.markdown("**Run Actions**")
    run_options = {f"Run #{r['Run #']} — {r['Feed']} — {r['Started']}": r["_run_id"] for r in history_data}
    selected = st.selectbox("Select Run", list(run_options.keys()), key="history_select")
    run_id = run_options[selected]

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if st.button("📊 View Results", key="history_view"):
            st.session_state["view_run_id"] = run_id
            st.session_state["current_page"] = "Results"
            st.rerun()

    with col_b:
        if st.button("📄 View Report", key="history_report"):
            st.session_state["view_run_id"] = run_id
            st.session_state["current_page"] = "Report View"
            st.rerun()

    with col_c:
        if st.button("🗑️ Delete Run", key="history_delete"):
            st.session_state[f"confirm_delete_run_{run_id}"] = True

    if st.session_state.get(f"confirm_delete_run_{run_id}"):
        st.warning("⚠️ This will permanently delete this run and all its results.")
        cc1, cc2 = st.columns(2)
        with cc1:
            if st.button("Yes, delete", key=f"confirm_del_run_{run_id}"):
                _delete_run(run_id)
                st.session_state.pop(f"confirm_delete_run_{run_id}", None)
                st.rerun()
        with cc2:
            if st.button("Cancel", key=f"cancel_del_run_{run_id}"):
                st.session_state.pop(f"confirm_delete_run_{run_id}", None)


def _delete_run(run_id: int) -> None:
    with get_session() as session:
        session.query(Result).filter(Result.run_id == run_id).delete()
        run = session.query(SearchRun).get(run_id)
        if run:
            session.delete(run)
        session.commit()
    st.success(f"Run #{run_id} deleted.")
