"""
Settings page — RSS feeds, exclusion rules, and app configuration.
"""

from __future__ import annotations

import json

import streamlit as st

from src.db.models import SavedSource, NegativeFeedbackRule, Connector
from src.db.session import get_session


def render_settings_view() -> None:
    st.markdown('<div class="section-header">⚙️ Settings</div>', unsafe_allow_html=True)

    tab_rss, tab_connectors, tab_rules, tab_about = st.tabs([
        "📡 RSS Feeds",
        "🔌 Connectors",
        "🚫 Exclusion Rules",
        "ℹ️ About",
    ])

    with tab_rss:
        _render_rss_feeds()

    with tab_connectors:
        _render_connectors()

    with tab_rules:
        _render_exclusion_rules()

    with tab_about:
        _render_about()


def _render_rss_feeds() -> None:
    st.markdown("#### 📡 RSS Feed Sources")
    st.caption("Manage the RSS feeds used by the RSS connector.")

    with get_session() as session:
        feeds = session.query(SavedSource).filter_by(source_type="rss").order_by(SavedSource.name).all()
        feed_data = [
            {"id": f.id, "name": f.name, "url": f.url, "is_enabled": f.is_enabled, "notes": f.notes}
            for f in feeds
        ]

    for feed in feed_data:
        with st.container():
            cols = st.columns([0.05, 0.4, 0.4, 0.15])
            with cols[0]:
                icon = "🟢" if feed["is_enabled"] else "⭕"
                st.markdown(f"<div style='padding-top:8px;'>{icon}</div>", unsafe_allow_html=True)
            with cols[1]:
                st.markdown(f"<div style='padding-top:4px;'><strong>{feed['name']}</strong></div>", unsafe_allow_html=True)
            with cols[2]:
                st.markdown(f"<div style='color:#64748b; font-size:0.8rem; padding-top:8px; overflow:hidden; text-overflow:ellipsis;'>{feed['url'][:60]}...</div>", unsafe_allow_html=True)
            with cols[3]:
                tc1, tc2 = st.columns(2)
                with tc1:
                    toggle = "🔴" if feed["is_enabled"] else "🟢"
                    if st.button(toggle, key=f"feed_toggle_{feed['id']}", help="Toggle"):
                        _toggle_feed(feed["id"], not feed["is_enabled"])
                        st.rerun()
                with tc2:
                    if st.button("🗑️", key=f"feed_del_{feed['id']}", help="Delete"):
                        _delete_feed(feed["id"])
                        st.rerun()
        st.divider()

    # Add new feed
    st.markdown("#### ➕ Add RSS Feed")
    with st.form("add_feed_form"):
        col1, col2 = st.columns(2)
        with col1:
            feed_name = st.text_input("Feed Name *")
        with col2:
            feed_url = st.text_input("Feed URL *", placeholder="https://...")
        feed_notes = st.text_input("Notes (optional)")
        if st.form_submit_button("Add Feed", type="primary"):
            if feed_name and feed_url:
                _add_feed(feed_name, feed_url, feed_notes)
                st.success(f"✅ Added: {feed_name}")
                st.rerun()
            else:
                st.error("Name and URL are required.")


def _render_connectors() -> None:
    st.markdown("#### 🔌 Connector Status")
    st.caption("View connector configurations. Enable/disable globally via .env file.")

    with get_session() as session:
        connectors = session.query(Connector).order_by(Connector.name).all()
        conn_data = [
            {
                "id": c.id,
                "name": c.name,
                "connector_key": c.connector_key,
                "source_family": c.source_family,
                "enabled_by_default": c.enabled_by_default,
                "config": c.get_config(),
            }
            for c in connectors
        ]

    family_colors = {
        "academic": "#0e7490",
        "rss": "#f59e0b",
        "news": "#8b5cf6",
        "preprint": "#8b5cf6",
    }

    for c in conn_data:
        color = family_colors.get(c["source_family"], "#64748b")
        with st.container():
            cols = st.columns([0.5, 0.2, 0.3])
            with cols[0]:
                st.markdown(f"""
                <div>
                    <strong style='color:#f1f5f9;'>{c['name']}</strong>
                    <span style='background:{color}33; color:{color}; font-size:0.7rem; padding:1px 8px; border-radius:999px; margin-left:8px;'>{c['source_family']}</span>
                </div>
                <div style='color:#64748b; font-size:0.78rem;'>{c['connector_key']}</div>
                """, unsafe_allow_html=True)
            with cols[1]:
                status = "✅ Default ON" if c["enabled_by_default"] else "⭕ Default OFF"
                st.markdown(f"<div style='padding-top:4px; color:#94a3b8; font-size:0.8rem;'>{status}</div>", unsafe_allow_html=True)
            with cols[2]:
                if c["config"]:
                    with st.expander("Config"):
                        st.json(c["config"])
        st.divider()

    st.info("💡 Enable/disable connectors globally in your `.env` file using `ENABLE_CONNECTOR_*` variables, or per-feed in the Feed Builder page.")


def _render_exclusion_rules() -> None:
    st.markdown("#### 🚫 Exclusion Rules")
    st.caption("Rules that penalize or hard-exclude results from the relevance scorer.")

    with get_session() as session:
        rules = session.query(NegativeFeedbackRule).filter_by(is_active=True).order_by(NegativeFeedbackRule.created_at.desc()).all()
        rule_data = [
            {"id": r.id, "type": r.rule_type, "value": r.rule_value, "reason": r.reason}
            for r in rules
        ]

    if not rule_data:
        st.info("No active exclusion rules. Add rules below.")
    else:
        for rule in rule_data:
            cols = st.columns([0.15, 0.35, 0.4, 0.1])
            with cols[0]:
                st.markdown(f"`{rule['type']}`")
            with cols[1]:
                st.markdown(f"**{rule['value']}**")
            with cols[2]:
                st.markdown(f"<span style='color:#64748b;'>{rule['reason'] or ''}</span>", unsafe_allow_html=True)
            with cols[3]:
                if st.button("🗑️", key=f"rule_del_{rule['id']}"):
                    _delete_rule(rule["id"])
                    st.rerun()
        st.divider()

    st.markdown("#### ➕ Add Exclusion Rule")
    with st.form("add_rule_form"):
        col1, col2 = st.columns(2)
        with col1:
            rule_type = st.selectbox("Type", ["keyword", "journal", "taxon", "source", "pattern"])
        with col2:
            rule_value = st.text_input("Value *", placeholder="e.g. salmon farming")
        rule_reason = st.text_input("Reason (optional)")
        if st.form_submit_button("Add Rule", type="primary"):
            if rule_value:
                _add_rule(rule_type, rule_value, rule_reason)
                st.success(f"✅ Rule added: [{rule_type}] {rule_value}")
                st.rerun()
            else:
                st.error("Rule value is required.")


def _render_about() -> None:
    st.markdown("""
    ### 🐠 Aquarium Science Monitor

    **Version:** 1.0.0-MVP  
    **Purpose:** Internal science intelligence tool for aquarium-focused science writing.

    #### Architecture Notes

    **Future: Scheduled Runs**
    The `SearchService` class is fully decoupled from the UI.
    To add scheduling, wrap `search_service.run_search()` in an APScheduler or Celery task.
    The `SearchRun` table already tracks all metadata needed for run history.

    **Future: Email Delivery**
    Add an `email_service.py` that takes a `run_id`, queries the results, calls `report_service.generate_report_html()`,
    and sends via SMTP (smtplib) or an API like Mailgun/SendGrid.

    **Future: Feedback Learning**
    The `NegativeFeedbackRule` table and `is_saved`/`is_irrelevant` flags on `Result` are in place.
    A `feedback_service.py` could aggregate these signals to adjust scoring weights in `scoring_service.py`.

    **Future: Multi-user**
    Add a `users` table and attach all `Profile`, `SearchRun`, and `Result` records to user IDs.
    Add lightweight session authentication via `streamlit-authenticator`.

    **Adding New Connectors**
    1. Create `src/connectors/my_connector.py` extending `BaseConnector`
    2. Register it in `src/services/source_registry.py`
    3. Add a row to the `connectors` DB table
    4. Add a toggle in `.env.example`

    ---

    **Data Sources:**
    - [OpenAlex](https://openalex.org) — Open academic graph
    - [Crossref](https://crossref.org) — DOI metadata
    - [Europe PMC](https://europepmc.org) — Biomedical literature
    - [PubMed](https://pubmed.ncbi.nlm.nih.gov) — NCBI biomedical
    - RSS — Configurable journal/news feeds
    """)


def _toggle_feed(feed_id: int, enabled: bool) -> None:
    with get_session() as session:
        f = session.query(SavedSource).get(feed_id)
        if f:
            f.is_enabled = enabled
            session.commit()


def _delete_feed(feed_id: int) -> None:
    with get_session() as session:
        f = session.query(SavedSource).get(feed_id)
        if f:
            session.delete(f)
            session.commit()


def _add_feed(name: str, url: str, notes: str) -> None:
    with get_session() as session:
        session.add(SavedSource(name=name, url=url, source_type="rss", source_family="rss",
                                is_enabled=True, notes=notes or None))
        session.commit()


def _add_rule(rule_type: str, rule_value: str, reason: str) -> None:
    with get_session() as session:
        session.add(NegativeFeedbackRule(rule_type=rule_type, rule_value=rule_value,
                                         reason=reason or None, is_active=True))
        session.commit()


def _delete_rule(rule_id: int) -> None:
    with get_session() as session:
        r = session.query(NegativeFeedbackRule).get(rule_id)
        if r:
            session.delete(r)
            session.commit()
