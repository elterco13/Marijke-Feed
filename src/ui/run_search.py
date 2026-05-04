"""
Run Search page — profile selection, connector toggles, and search trigger.
"""

from __future__ import annotations

import json
import threading
import time

import streamlit as st

from src.db.models import Profile, SearchRun
from src.db.session import get_session
from src.services.search_service import SearchService
from src.services.source_registry import get_all_connector_keys, get_connector_display_names
from src.services.query_builder import build_query


def render_run_search() -> None:
    st.markdown('<div class="section-header">🔍 Run Search</div>', unsafe_allow_html=True)

    # Load profiles
    with get_session() as session:
        profiles = session.query(Profile).filter_by(is_active=True).order_by(Profile.name).all()
        profile_data = [{"id": p.id, "name": p.name, "query_text": p.query_text,
                         "date_window_days": p.date_window_days, "result_limit": p.result_limit,
                         "include_preprints": p.include_preprints,
                         "enabled_connectors_json": p.enabled_connectors_json} for p in profiles]

    if not profile_data:
        st.warning("⚠️ No active feeds found. Please create a feed first.")
        if st.button("→ Go to Feed Builder"):
            st.session_state.current_page = "Feed Builder"
            st.rerun()
        return

    # Profile selector
    profile_names = [p["name"] for p in profile_data]
    selected_name = st.selectbox("Select Profile", profile_names, key="run_profile_select")
    selected_profile_data = next(p for p in profile_data if p["name"] == selected_name)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Date Window", f"{selected_profile_data['date_window_days']} days")
    with col2:
        st.metric("Max Results / Source", selected_profile_data["result_limit"])
    with col3:
        st.metric("Preprints", "Included" if selected_profile_data["include_preprints"] else "Excluded")

    with get_session() as session:
        profile_obj = session.query(Profile).get(selected_profile_data["id"])
        composed_query = build_query(profile_obj) if profile_obj else ""
        
    st.markdown(f"**Effective Query:**\n```sql\n{composed_query}\n```")

    st.divider()

    # Connector toggles
    st.markdown("**🔌 Source Connectors**")
    connector_display = get_connector_display_names()
    all_keys = get_all_connector_keys()

    default_enabled = (
        json.loads(selected_profile_data["enabled_connectors_json"])
        if selected_profile_data["enabled_connectors_json"]
        else all_keys
    )

    cols = st.columns(3)
    enabled_connectors = []
    for idx, key in enumerate(all_keys):
        display = connector_display.get(key, key)
        is_checked = key in default_enabled
        if cols[idx % 3].checkbox(display, value=is_checked, key=f"run_conn_{key}"):
            enabled_connectors.append(key)

    st.divider()

    # Run button
    col_btn, col_info = st.columns([0.3, 0.7])
    with col_btn:
        run_clicked = st.button(
            "🚀 Run Search Now",
            type="primary",
            use_container_width=True,
            disabled=st.session_state.get("search_running", False),
        )

    with col_info:
        if st.session_state.get("search_running"):
            st.markdown('<span class="run-status-running">⏳ Search in progress...</span>', unsafe_allow_html=True)
        elif st.session_state.get("last_run_result"):
            res = st.session_state["last_run_result"]
            if res.get("status") == "done":
                st.success(f"✅ Last run: {res.get('total_final', 0)} results in run #{res.get('run_id')}")
            elif res.get("status") == "error":
                st.error(f"❌ Error: {res.get('error', 'Unknown error')}")

    if run_clicked and not st.session_state.get("search_running"):
        if not enabled_connectors:
            st.error("Please enable at least one connector.")
            return

        # Load the actual profile ORM object and expunge from session
        with get_session() as session:
            profile_obj = session.query(Profile).get(selected_profile_data["id"])
            if not profile_obj:
                st.error("Profile not found.")
                return
            # Detach so it can be used outside session context
            session.expunge(profile_obj)

        # Run search with progress
        _run_search_with_progress(profile_obj, enabled_connectors)



def _run_search_with_progress(profile: Profile, enabled_connectors: list[str]) -> None:
    """Execute search with live progress display."""
    st.session_state["search_running"] = True
    st.session_state["search_progress_msg"] = "Initializing..."
    st.session_state["search_progress_pct"] = 0.0

    progress_bar = st.progress(0, text="Starting search...")
    status_placeholder = st.empty()

    messages: list[str] = []
    result_container: dict = {}

    def on_progress(msg: str, pct: float) -> None:
        messages.append(msg)

    service = SearchService(on_progress=on_progress)

    try:
        # We run synchronously (Streamlit doesn't support background threads well)
        with get_session() as session:
            profile_refreshed = session.query(Profile).get(profile.id)
            if profile_refreshed:
                session.expunge(profile_refreshed)

        if not profile_refreshed:
            raise ValueError("Profile not found in database.")

        result = service.run_search(profile_refreshed, enabled_connectors)
        result_container.update(result)

    except Exception as e:
        result_container["status"] = "error"
        result_container["error"] = str(e)

    finally:
        st.session_state["search_running"] = False
        st.session_state["last_run_result"] = result_container

        if result_container.get("status") == "done":
            progress_bar.progress(1.0, text="✅ Complete!")
            status_placeholder.success(
                f"✅ Search complete! "
                f"Raw: {result_container.get('total_raw', 0)} → "
                f"Normalized: {result_container.get('total_normalized', 0)} → "
                f"Deduped: {result_container.get('total_deduped', 0)} → "
                f"**Final: {result_container.get('total_final', 0)}**"
            )
            # Auto-navigate to results
            st.session_state["view_run_id"] = result_container.get("run_id")
        else:
            status_placeholder.error(f"❌ Error: {result_container.get('error', 'Unknown')}")

        st.rerun()
