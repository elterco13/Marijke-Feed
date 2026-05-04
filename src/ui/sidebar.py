"""
Sidebar navigation component.
"""

from __future__ import annotations

import streamlit as st


PAGES = [
    ("🏠", "Home"),
    ("🔍", "Run Search"),
    ("📊", "Results"),
    ("📄", "Report View"),
    ("🗂️", "Feed Builder"),
    ("📅", "History"),
    ("⚙️", "Settings"),
]


def render_sidebar() -> str:
    """Render the navigation sidebar and return the selected page name."""
    with st.sidebar:
        st.markdown("""
        <div style="text-align:center; padding: 16px 0 24px 0;">
            <div style="font-size: 2.5rem;">🐠</div>
            <div style="color: #22d3ee; font-weight: 800; font-size: 1.05rem; margin-top: 4px;">
                Aquarium Science Monitor
            </div>
            <div style="color: #475569; font-size: 0.72rem; margin-top: 2px;">
                Internal Science Intelligence Tool
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        if "current_page" not in st.session_state:
            st.session_state.current_page = "Home"

        for icon, page_name in PAGES:
            is_active = st.session_state.current_page == page_name
            btn_style = "primary" if is_active else "secondary"
            label = f"{icon} {page_name}"
            if st.button(label, key=f"nav_{page_name}", use_container_width=True, type=btn_style):
                st.session_state.current_page = page_name
                st.rerun()

        st.divider()

        # Quick stats
        _render_quick_stats()

    return st.session_state.current_page


def _render_quick_stats() -> None:
    """Render quick stats in sidebar footer."""
    try:
        from src.db.session import get_session
        from src.db.models import SearchRun, Result, Profile

        with get_session() as session:
            total_runs = session.query(SearchRun).count()
            total_results = session.query(Result).count()
            total_profiles = session.query(Profile).count()

        st.markdown(f"""
        <div style="color:#475569; font-size:0.72rem; text-align:center; padding: 8px 0;">
            <div>📁 {total_profiles} profiles</div>
            <div>🔄 {total_runs} runs · {total_results} results</div>
        </div>
        """, unsafe_allow_html=True)
    except Exception:
        pass
