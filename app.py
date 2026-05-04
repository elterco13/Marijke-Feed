"""
Aquarium Science Monitor — Main Streamlit App Entry Point
"""

import streamlit as st
import os
from pathlib import Path
import sys
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Ensure src is on the path
sys.path.insert(0, str(Path(__file__).parent))

from src.db.init_db import initialize_database
from src.utils.logging import setup_logging
from src.ui.sidebar import render_sidebar

# Setup
setup_logging()
initialize_database()

# Page config
st.set_page_config(
    page_title="Aquarium Science Monitor",
    page_icon="🐠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    /* Main theme */
    :root {
        --primary: #0e7490;
        --primary-light: #22d3ee;
        --accent: #0891b2;
        --bg-dark: #0f172a;
        --bg-card: #1e293b;
        --bg-card-hover: #253347;
        --text-primary: #f1f5f9;
        --text-secondary: #94a3b8;
        --border: #334155;
        --success: #10b981;
        --warning: #f59e0b;
        --danger: #ef4444;
        --preprint: #8b5cf6;
    }

    /* Hide default Streamlit elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
        border-right: 1px solid #334155;
    }

    [data-testid="stSidebar"] .stMarkdown h1,
    [data-testid="stSidebar"] .stMarkdown h2,
    [data-testid="stSidebar"] .stMarkdown h3 {
        color: #22d3ee;
    }

    /* Buttons */
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s ease;
    }

    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(14, 116, 144, 0.4);
    }

    /* Cards */
    .report-card {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 16px;
        transition: all 0.2s ease;
    }

    .report-card:hover {
        border-color: #0e7490;
        box-shadow: 0 4px 20px rgba(14, 116, 144, 0.2);
        transform: translateY(-1px);
    }

    .report-card h3 {
        color: #f1f5f9;
        font-size: 1.05rem;
        font-weight: 700;
        margin: 0 0 8px 0;
        line-height: 1.4;
    }

    .report-card h3 a {
        color: #22d3ee;
        text-decoration: none;
    }

    .report-card h3 a:hover {
        color: #67e8f9;
        text-decoration: underline;
    }

    /* Badges */
    .badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 999px;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.03em;
        text-transform: uppercase;
        margin-right: 4px;
        margin-bottom: 4px;
    }

    .badge-category {
        background: rgba(14, 116, 144, 0.25);
        color: #22d3ee;
        border: 1px solid rgba(34, 211, 238, 0.3);
    }

    .badge-subcategory {
        background: rgba(8, 145, 178, 0.15);
        color: #67e8f9;
        border: 1px solid rgba(103, 232, 249, 0.2);
    }

    .badge-preprint {
        background: rgba(139, 92, 246, 0.25);
        color: #c4b5fd;
        border: 1px solid rgba(196, 181, 253, 0.3);
    }

    .badge-article {
        background: rgba(16, 185, 129, 0.2);
        color: #6ee7b7;
        border: 1px solid rgba(110, 231, 183, 0.3);
    }

    .badge-news {
        background: rgba(245, 158, 11, 0.2);
        color: #fcd34d;
        border: 1px solid rgba(252, 211, 77, 0.3);
    }

    .badge-rss {
        background: rgba(249, 115, 22, 0.2);
        color: #fdba74;
        border: 1px solid rgba(253, 186, 116, 0.3);
    }

    .badge-taxon {
        background: rgba(52, 211, 153, 0.15);
        color: #6ee7b7;
        border: 1px solid rgba(110, 231, 183, 0.25);
        font-size: 0.68rem;
    }

    /* Score indicator */
    .score-bar {
        height: 4px;
        border-radius: 2px;
        background: linear-gradient(90deg, #0e7490, #22d3ee);
        margin-top: 8px;
    }

    .score-text {
        color: #22d3ee;
        font-size: 0.75rem;
        font-weight: 700;
    }

    /* Meta info */
    .meta-info {
        color: #64748b;
        font-size: 0.78rem;
        margin-top: 6px;
    }

    .meta-info span {
        margin-right: 12px;
    }

    /* Abstract */
    .abstract-text {
        color: #94a3b8;
        font-size: 0.85rem;
        line-height: 1.6;
        margin-top: 8px;
    }

    /* Section headers */
    .section-header {
        background: linear-gradient(135deg, #0e7490 0%, #0891b2 100%);
        color: white;
        padding: 12px 20px;
        border-radius: 10px;
        margin-bottom: 20px;
        font-size: 1.2rem;
        font-weight: 700;
    }

    /* Stats cards */
    .stat-card {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 16px;
        text-align: center;
    }

    .stat-number {
        font-size: 2rem;
        font-weight: 800;
        color: #22d3ee;
    }

    .stat-label {
        font-size: 0.78rem;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* Image thumbnails */
    .result-image {
        width: 80px;
        height: 60px;
        object-fit: cover;
        border-radius: 6px;
        border: 1px solid #334155;
        float: right;
        margin-left: 12px;
    }

    /* Run progress */
    .run-status-running {
        color: #22d3ee;
        font-weight: 700;
        animation: pulse 1.5s infinite;
    }

    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }

    /* Expander customization */
    .streamlit-expanderHeader {
        background: #1e293b;
        border-radius: 8px;
    }

    /* Input field styling */
    .stTextInput input, .stTextArea textarea, .stSelectbox select {
        background: #1e293b;
        border-color: #334155;
        color: #f1f5f9;
    }

    /* DataFrame */
    .stDataFrame {
        border-radius: 8px;
        overflow: hidden;
    }

    /* Metric */
    [data-testid="stMetricValue"] {
        color: #22d3ee;
    }

    /* Alert/info boxes */
    .stAlert {
        border-radius: 8px;
    }

    /* Nav buttons in sidebar */
    .nav-button {
        width: 100%;
        text-align: left;
        padding: 10px 16px;
        margin: 2px 0;
        border-radius: 8px;
        border: none;
        cursor: pointer;
        font-size: 0.9rem;
        transition: all 0.15s ease;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        background: #1e293b;
        border-radius: 10px;
        padding: 4px;
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        color: #94a3b8;
    }

    .stTabs [aria-selected="true"] {
        background: #0e7490;
        color: white;
    }
</style>
""", unsafe_allow_html=True)


def check_password():
    """Returns True if the user had the correct password."""
    def password_entered():
        """Checks whether a password entered by the user is correct."""
        # Check environment variables first (works for .env local and Streamlit Secrets)
        # Fallback to 'admin123' if not set anywhere
        correct_password = os.getenv("APP_PASSWORD") or "admin123"
        
        if st.session_state["password"] == correct_password:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # don't store password
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True

    # Show login screen
    st.markdown("""
        <div style="text-align:center; padding: 50px 0;">
            <div style="font-size: 5rem;">🐠</div>
            <h1 style="color: #22d3ee;">Aquarium Science Monitor</h1>
            <p style="color: #94a3b8;">Internal science intelligence tool</p>
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.text_input("Please enter the access password", type="password", on_change=password_entered, key="password")
        if "password_correct" in st.session_state:
            st.error("😕 Password incorrect")
    return False


def main():
    """Main application router."""
    if not check_password():
        st.stop()  # Do not continue if password is not correct
        
    page = render_sidebar()

    if page == "Run Search":
        from src.ui.run_search import render_run_search
        render_run_search()
    elif page == "Results":
        from src.ui.results_table import render_results_table
        render_results_table()
    elif page == "Report View":
        from src.ui.report_view import render_report_view
        render_report_view()
    elif page == "Feed Builder":
        from src.ui.feed_builder import render_feed_builder
        render_feed_builder()
    elif page == "History":
        from src.ui.history import render_history
        render_history()
    elif page == "Settings":
        from src.ui.settings_view import render_settings_view
        render_settings_view()
    else:
        render_home()


def render_home():
    """Welcome/home page."""
    st.markdown("""
    <div style="text-align: center; padding: 40px 0 20px 0;">
        <div style="font-size: 4rem; margin-bottom: 8px;">🐠</div>
        <h1 style="color: #22d3ee; font-size: 2.2rem; font-weight: 800; margin: 0;">
            Aquarium Science Monitor
        </h1>
        <p style="color: #64748b; font-size: 1.05rem; margin-top: 8px;">
            Academic literature intelligence for aquarium science writers
        </p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown("""
        <div class="stat-card">
            <div style="font-size:2rem;">🔍</div>
            <div style="color:#22d3ee; font-weight:700; margin-top:4px;">Multi-Source</div>
            <div style="color:#64748b; font-size:0.8rem;">OpenAlex · Crossref · PubMed · EuropePMC · RSS</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown("""
        <div class="stat-card">
            <div style="font-size:2rem;">🧠</div>
            <div style="color:#22d3ee; font-weight:700; margin-top:4px;">Smart Scoring</div>
            <div style="color:#64748b; font-size:0.8rem;">Rule-based relevance engine with full explanations</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown("""
        <div class="stat-card">
            <div style="font-size:2rem;">📊</div>
            <div style="color:#22d3ee; font-weight:700; margin-top:4px;">Rich Exports</div>
            <div style="color:#64748b; font-size:0.8rem;">CSV · XLSX · DOCX · PDF report formats</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown("""
        <div class="stat-card">
            <div style="font-size:2rem;">🎯</div>
            <div style="color:#22d3ee; font-weight:700; margin-top:4px;">Curated</div>
            <div style="color:#64748b; font-size:0.8rem;">Deduplicated, filtered for aquarium relevance</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("""
        ### 🚀 Quick Start
        1. **Create a Profile** — Define your search query, date window, and source preferences
        2. **Run Search** — Hit "Run Search Now" to fetch and score results
        3. **Review Results** — Browse the curated report with relevance scores
        4. **Export** — Download as CSV, XLSX, DOCX, or PDF

        Use the **sidebar** to navigate between sections.
        """)

    with col_b:
        st.markdown("""
        ### 📡 Active Sources
        - **OpenAlex** — Broad academic literature index
        - **Crossref** — DOI metadata and journal content
        - **Europe PMC** — Biomedical and life science papers
        - **PubMed** — NCBI biomedical literature
        - **RSS Feeds** — Journals, news, institutional sources

        Configure which sources to enable in **Settings** or per-profile in **Profiles**.
        """)

    st.info("💡 **Tip:** Start by creating a Search Profile with your aquarium topic query, then head to **Run Search** to fetch results.")


if __name__ == "__main__":
    main()
