"""
Profiles page — create, edit, duplicate, activate, delete search profiles.
"""

from __future__ import annotations

import json
from datetime import datetime

import streamlit as st

from src.db.models import Profile
from src.db.session import get_session
from src.services.source_registry import get_all_connector_keys, get_connector_display_names


def render_profiles() -> None:
    st.markdown('<div class="section-header">🗂️ Search Profiles</div>', unsafe_allow_html=True)

    tab_list, tab_new = st.tabs(["📋 All Profiles", "➕ New Profile"])

    with tab_list:
        _render_profile_list()

    with tab_new:
        _render_profile_form(profile=None)


def _render_profile_list() -> None:
    with get_session() as session:
        profiles = session.query(Profile).order_by(Profile.updated_at.desc()).all()
        # detach from session
        profiles_data = [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "is_active": p.is_active,
                "query_text": p.query_text,
                "date_window_days": p.date_window_days,
                "result_limit": p.result_limit,
                "include_preprints": p.include_preprints,
                "enabled_connectors_json": p.enabled_connectors_json,
                "include_keywords_json": p.include_keywords_json,
                "exclude_keywords_json": p.exclude_keywords_json,
                "created_at": p.created_at,
                "updated_at": p.updated_at,
            }
            for p in profiles
        ]

    if not profiles_data:
        st.info("No profiles yet. Create your first profile in the 'New Profile' tab.")
        return

    for p in profiles_data:
        with st.container():
            cols = st.columns([0.05, 0.55, 0.15, 0.25])

            with cols[0]:
                status_icon = "🟢" if p["is_active"] else "⭕"
                st.markdown(f"<div style='padding-top:8px;font-size:1.2rem;'>{status_icon}</div>", unsafe_allow_html=True)

            with cols[1]:
                st.markdown(f"""
                <div style='padding-top:4px;'>
                    <strong style='color:#f1f5f9;'>{p['name']}</strong>
                    <div style='color:#64748b; font-size:0.8rem;'>{p.get('description') or ''}</div>
                    <div style='color:#475569; font-size:0.75rem; margin-top:2px;'>
                        Query: <em>{p['query_text'][:60]}{'...' if len(p['query_text'])>60 else ''}</em>
                        &nbsp;·&nbsp; {p['date_window_days']}d window &nbsp;·&nbsp; limit {p['result_limit']}
                    </div>
                </div>
                """, unsafe_allow_html=True)

            with cols[2]:
                st.markdown(f"<div style='color:#64748b; font-size:0.75rem; padding-top:10px;'>Updated: {p['updated_at'].strftime('%Y-%m-%d') if p['updated_at'] else 'N/A'}</div>", unsafe_allow_html=True)

            with cols[3]:
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    if st.button("✏️", key=f"edit_{p['id']}", help="Edit"):
                        st.session_state[f"edit_profile_id"] = p["id"]
                with c2:
                    if st.button("📋", key=f"dup_{p['id']}", help="Duplicate"):
                        _duplicate_profile(p["id"])
                        st.rerun()
                with c3:
                    toggle_label = "🔴" if p["is_active"] else "🟢"
                    toggle_help = "Deactivate" if p["is_active"] else "Activate"
                    if st.button(toggle_label, key=f"toggle_{p['id']}", help=toggle_help):
                        _toggle_profile(p["id"], not p["is_active"])
                        st.rerun()
                with c4:
                    if st.button("🗑️", key=f"del_{p['id']}", help="Delete"):
                        st.session_state[f"confirm_delete_{p['id']}"] = True

            # Confirm delete
            if st.session_state.get(f"confirm_delete_{p['id']}"):
                st.warning(f"⚠️ Delete profile **{p['name']}**? This cannot be undone.")
                cc1, cc2 = st.columns(2)
                with cc1:
                    if st.button("Yes, delete", key=f"confirm_yes_{p['id']}", type="primary"):
                        _delete_profile(p["id"])
                        st.session_state.pop(f"confirm_delete_{p['id']}", None)
                        st.rerun()
                with cc2:
                    if st.button("Cancel", key=f"confirm_no_{p['id']}"):
                        st.session_state.pop(f"confirm_delete_{p['id']}", None)
                        st.rerun()

            # Edit form inline
            if st.session_state.get("edit_profile_id") == p["id"]:
                with st.expander("✏️ Edit Profile", expanded=True):
                    with get_session() as session2:
                        profile_obj = session2.query(Profile).get(p["id"])
                        if profile_obj:
                            _render_profile_form(profile=profile_obj)

            st.divider()


def _render_profile_form(profile: Profile | None) -> None:
    """Render create/edit form for a profile."""
    connector_display = get_connector_display_names()
    all_keys = get_all_connector_keys()

    # Defaults
    defaults = {
        "name": profile.name if profile else "",
        "description": profile.description if profile else "",
        "is_active": profile.is_active if profile else True,
        "query_text": profile.query_text if profile else "",
        "date_window_days": profile.date_window_days if profile else 30,
        "result_limit": profile.result_limit if profile else 50,
        "include_preprints": profile.include_preprints if profile else True,
        "enabled_connectors": json.loads(profile.enabled_connectors_json) if profile and profile.enabled_connectors_json else all_keys,
        "include_keywords": ", ".join(json.loads(profile.include_keywords_json)) if profile and profile.include_keywords_json else "",
        "exclude_keywords": ", ".join(json.loads(profile.exclude_keywords_json)) if profile and profile.exclude_keywords_json else "",
    }

    with st.form(key=f"profile_form_{profile.id if profile else 'new'}"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Profile Name *", value=defaults["name"])
        with col2:
            is_active = st.checkbox("Active", value=defaults["is_active"])

        description = st.text_area("Description", value=defaults["description"], height=60)
        query_text = st.text_area("Search Query *", value=defaults["query_text"], height=80,
                                   help="Main search query to send to all enabled sources.")

        col3, col4 = st.columns(2)
        with col3:
            date_window = st.slider("Date Window (days)", 7, 365, defaults["date_window_days"],
                                    help="How far back to search.")
        with col4:
            result_limit = st.slider("Max Results per Source", 10, 200, defaults["result_limit"])

        include_preprints = st.checkbox("Include Preprints", value=defaults["include_preprints"])

        st.markdown("**Enabled Connectors**")
        enabled_connectors = []
        cols_conn = st.columns(3)
        for idx, key in enumerate(all_keys):
            display = connector_display.get(key, key)
            checked = key in defaults["enabled_connectors"]
            if cols_conn[idx % 3].checkbox(display, value=checked, key=f"conn_{key}_{profile.id if profile else 'new'}"):
                enabled_connectors.append(key)

        include_kws = st.text_area(
            "Additional Include Keywords (comma-separated)",
            value=defaults["include_keywords"],
            height=60,
            help="Extra terms to boost relevance score. Merged with global keyword config.",
        )
        exclude_kws = st.text_area(
            "Additional Exclude Keywords (comma-separated)",
            value=defaults["exclude_keywords"],
            height=60,
            help="Terms that should penalize relevance score.",
        )

        submit_label = "💾 Save Changes" if profile else "➕ Create Profile"
        submitted = st.form_submit_button(submit_label, type="primary", use_container_width=True)

        if submitted:
            if not name.strip():
                st.error("Profile name is required.")
                return
            if not query_text.strip():
                st.error("Search query is required.")
                return

            _save_profile(
                profile_id=profile.id if profile else None,
                name=name.strip(),
                description=description.strip(),
                is_active=is_active,
                query_text=query_text.strip(),
                date_window_days=date_window,
                result_limit=result_limit,
                include_preprints=include_preprints,
                enabled_connectors=enabled_connectors,
                include_keywords=[k.strip() for k in include_kws.split(",") if k.strip()],
                exclude_keywords=[k.strip() for k in exclude_kws.split(",") if k.strip()],
            )
            st.success("✅ Profile saved!")
            st.session_state.pop("edit_profile_id", None)
            st.rerun()


def _save_profile(
    profile_id: int | None,
    name: str,
    description: str,
    is_active: bool,
    query_text: str,
    date_window_days: int,
    result_limit: int,
    include_preprints: bool,
    enabled_connectors: list[str],
    include_keywords: list[str],
    exclude_keywords: list[str],
) -> None:
    with get_session() as session:
        if profile_id:
            p = session.query(Profile).get(profile_id)
        else:
            p = Profile()
            session.add(p)

        p.name = name
        p.description = description
        p.is_active = is_active
        p.query_text = query_text
        p.date_window_days = date_window_days
        p.result_limit = result_limit
        p.include_preprints = include_preprints
        p.enabled_connectors_json = json.dumps(enabled_connectors)
        p.include_keywords_json = json.dumps(include_keywords)
        p.exclude_keywords_json = json.dumps(exclude_keywords)
        p.updated_at = datetime.utcnow()

        session.commit()


def _duplicate_profile(profile_id: int) -> None:
    with get_session() as session:
        original = session.query(Profile).get(profile_id)
        if not original:
            return
        clone = Profile(
            name=f"{original.name} (copy)",
            description=original.description,
            is_active=False,
            query_text=original.query_text,
            date_window_days=original.date_window_days,
            result_limit=original.result_limit,
            include_preprints=original.include_preprints,
            source_types_json=original.source_types_json,
            enabled_connectors_json=original.enabled_connectors_json,
            include_keywords_json=original.include_keywords_json,
            exclude_keywords_json=original.exclude_keywords_json,
            taxon_allowlist_json=original.taxon_allowlist_json,
            taxon_blocklist_json=original.taxon_blocklist_json,
            journals_allowlist_json=original.journals_allowlist_json,
            journals_blocklist_json=original.journals_blocklist_json,
        )
        session.add(clone)
        session.commit()
    st.success("Profile duplicated!")


def _toggle_profile(profile_id: int, active: bool) -> None:
    with get_session() as session:
        p = session.query(Profile).get(profile_id)
        if p:
            p.is_active = active
            p.updated_at = datetime.utcnow()
            session.commit()


def _delete_profile(profile_id: int) -> None:
    with get_session() as session:
        p = session.query(Profile).get(profile_id)
        if p:
            session.delete(p)
            session.commit()
    st.success("Profile deleted.")
