"""
Feed Builder page — create, edit, duplicate, activate, delete search profiles using ontology packs.
"""

from __future__ import annotations

import json
from datetime import datetime

import streamlit as st

from src.db.models import Profile
from src.db.session import get_session
from src.services.source_registry import get_all_connector_keys, get_connector_display_names
from src.services.query_builder import (
    get_all_categories,
    get_all_subcategories,
    get_all_taxon_packs,
    get_all_exclusion_packs,
    build_query
)

def render_feed_builder() -> None:
    st.markdown('<div class="section-header">🗂️ Feed Builder</div>', unsafe_allow_html=True)

    tab_list, tab_new = st.tabs(["📋 All Feeds", "➕ New Feed"])

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
                "created_at": p.created_at,
                "updated_at": p.updated_at,
            }
            for p in profiles
        ]

    if not profiles_data:
        st.info("No feeds yet. Create your first feed in the 'New Feed' tab.")
        return

    for p in profiles_data:
        with st.container():
            cols = st.columns([0.05, 0.55, 0.15, 0.25])

            with cols[0]:
                status_icon = "🟢" if p["is_active"] else "⭕"
                st.markdown(f"<div style='padding-top:8px;font-size:1.2rem;'>{status_icon}</div>", unsafe_allow_html=True)

            with cols[1]:
                desc = p.get('description') or ''
                st.markdown(f"""
                <div style='padding-top:4px;'>
                    <strong style='color:#f1f5f9;'>{p['name']}</strong>
                    <div style='color:#64748b; font-size:0.8rem;'>{desc}</div>
                    <div style='color:#475569; font-size:0.75rem; margin-top:2px;'>
                        {p['date_window_days']}d window &nbsp;·&nbsp; limit {p['result_limit']}
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
                st.warning(f"⚠️ Delete feed **{p['name']}**? This cannot be undone.")
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
                with st.expander("✏️ Edit Feed", expanded=True):
                    with get_session() as session2:
                        profile_obj = session2.query(Profile).get(p["id"])
                        if profile_obj:
                            _render_profile_form(profile=profile_obj)

            st.divider()


def _render_profile_form(profile: Profile | None) -> None:
    """Render create/edit form for a profile using the pack-based feed builder."""
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
        "selected_categories": json.loads(profile.selected_categories_json) if profile and profile.selected_categories_json else [],
        "selected_subcategories": json.loads(profile.selected_subcategories_json) if profile and profile.selected_subcategories_json else [],
        "selected_taxon_packs": json.loads(profile.selected_taxon_packs_json) if profile and profile.selected_taxon_packs_json else [],
        "selected_exclusions": json.loads(profile.selected_exclusions_json) if profile and profile.selected_exclusions_json else [],
        "manual_categories": profile.get_manual_categories() if profile else [],
        "manual_taxa": profile.get_manual_taxa() if profile else [],
        "manual_exclusions": profile.get_exclude_keywords() if profile else [],
    }

    form_id = profile.id if profile else 'new'
    
    # Session state for manual lists to handle the "+" button interactions
    for key in ["manual_categories", "manual_taxa", "manual_exclusions"]:
        ss_key = f"{key}_{form_id}"
        if ss_key not in st.session_state:
            st.session_state[ss_key] = defaults[key]

    # --- 1. Basic Info ---
    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Feed Name *", value=defaults["name"], key=f"name_{form_id}")
    with col2:
        is_active = st.checkbox("Active", value=defaults["is_active"], key=f"active_{form_id}")

    description = st.text_area("Description", value=defaults["description"], height=60, key=f"desc_{form_id}")
    st.divider()

    # --- 2. Feed Ontology Selections ---
    st.markdown("### 🧩 Feed Ontology Selections")
    st.info("Select packs to automatically build your query. The final query matches: `(Taxa) AND (Categories OR Subcategories) NOT (Exclusions)`")
    
    c1, c2, c3, c4 = st.columns(4)
    
    selected_cats = []
    with c1:
        st.markdown("#### Categories")
        for cat in get_all_categories():
            if st.checkbox(cat["name"], value=cat["id"] in defaults["selected_categories"], key=f"cat_{cat['id']}_{form_id}", help=cat["description"]):
                selected_cats.append(cat["id"])
                
    selected_subcats = []
    with c2:
        st.markdown("#### Subcategories")
        for sub in get_all_subcategories():
            if st.checkbox(sub["name"], value=sub["id"] in defaults["selected_subcategories"], key=f"sub_{sub['id']}_{form_id}", help=sub["description"]):
                selected_subcats.append(sub["id"])
                
    selected_taxa = []
    with c3:
        st.markdown("#### Taxon Packs")
        for tax in get_all_taxon_packs():
            if st.checkbox(tax["name"], value=tax["id"] in defaults["selected_taxon_packs"], key=f"tax_{tax['id']}_{form_id}", help=tax["description"]):
                selected_taxa.append(tax["id"])
                
    selected_exc = []
    with c4:
        st.markdown("#### Exclusions")
        for exc in get_all_exclusion_packs():
            if st.checkbox(exc["name"], value=exc["id"] in defaults["selected_exclusions"], key=f"exc_{exc['id']}_{form_id}", help=exc["description"]):
                selected_exc.append(exc["id"])

    st.divider()

    # --- 3. Manual Overrides ---
    st.markdown("### ✍️ Manual Overrides")
    st.caption("Add specific terms not covered by the packs above. Use the '+' button to add.")
    
    col_m1, col_m2, col_m3 = st.columns(3)
    
    with col_m1:
        st.markdown("**Manual Categories**")
        _render_manual_list_editor("manual_categories", form_id)
        
    with col_m2:
        st.markdown("**Manual Taxa**")
        _render_manual_list_editor("manual_taxa", form_id)
        
    with col_m3:
        st.markdown("**Manual Exclusions**")
        _render_manual_list_editor("manual_exclusions", form_id)

    st.divider()

    # --- 4. Settings & More Overrides ---
    st.markdown("### ⚙️ Settings & More Overrides")
    query_text = st.text_area("Manual Query Extension (Optional)", value=defaults["query_text"], height=80,
                               help="Appended to the automatic query using AND. Useful for narrow, specific terms.",
                               key=f"qtext_{form_id}")

    col3, col4 = st.columns(2)
    with col3:
        date_window = st.slider("Date Window (days)", 7, 365, defaults["date_window_days"],
                                help="How far back to search.", key=f"window_{form_id}")
    with col4:
        result_limit = st.slider("Max Results per Source", 10, 200, defaults["result_limit"], key=f"limit_{form_id}")

    include_preprints = st.checkbox("Include Preprints", value=defaults["include_preprints"], key=f"pre_{form_id}")

    st.markdown("**Enabled Connectors**")
    enabled_connectors = []
    cols_conn = st.columns(3)
    for idx, key in enumerate(all_keys):
        display = connector_display.get(key, key)
        checked = key in defaults["enabled_connectors"]
        if cols_conn[idx % 3].checkbox(display, value=checked, key=f"conn_{key}_{form_id}"):
            enabled_connectors.append(key)

    st.markdown("<br>", unsafe_allow_html=True)
    submit_label = "💾 Save Feed" if profile else "➕ Create Feed"
    if st.button(submit_label, type="primary", use_container_width=True, key=f"save_btn_{form_id}"):
        if not name.strip():
            st.error("Feed name is required.")
        else:
            _save_profile(
                profile_id=profile.id if profile else None,
                name=name.strip(),
                description=description.strip(),
                is_active=is_active,
                query_text=query_text.strip() if query_text else None,
                date_window_days=date_window,
                result_limit=result_limit,
                include_preprints=include_preprints,
                enabled_connectors=enabled_connectors,
                selected_cats=selected_cats,
                selected_subcats=selected_subcats,
                selected_taxa=selected_taxa,
                selected_exc=selected_exc,
                manual_cats=st.session_state.get(f"manual_categories_{form_id}", []),
                manual_taxa=st.session_state.get(f"manual_taxa_{form_id}", []),
                manual_exc=st.session_state.get(f"manual_exclusions_{form_id}", [])
            )
            st.success("✅ Feed saved!")
            # Clear session state for this form
            for key in ["manual_categories", "manual_taxa", "manual_exclusions"]:
                st.session_state.pop(f"{key}_{form_id}", None)
            st.session_state.pop("edit_profile_id", None)
            st.rerun()

    # Query preview outside form (only works for existing profiles right now in Streamlit without fragments)
    if profile:
        st.markdown("#### 🔍 Active Query Preview")
        preview_query = build_query(profile)
        st.code(preview_query or "No ontology packs selected. Empty query.", language="sql")


def _save_profile(
    profile_id: int | None,
    name: str,
    description: str,
    is_active: bool,
    query_text: str | None,
    date_window_days: int,
    result_limit: int,
    include_preprints: bool,
    enabled_connectors: list[str],
    selected_cats: list[str],
    selected_subcats: list[str],
    selected_taxa: list[str],
    selected_exc: list[str],
    manual_cats: list[str],
    manual_taxa: list[str],
    manual_exc: list[str]
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
        
        p.selected_categories_json = json.dumps(selected_cats)
        p.selected_subcategories_json = json.dumps(selected_subcats)
        p.selected_taxon_packs_json = json.dumps(selected_taxa)
        p.selected_exclusions_json = json.dumps(selected_exc)
        
        p.include_keywords_json = json.dumps(manual_cats)
        p.taxon_allowlist_json = json.dumps(manual_taxa)
        p.exclude_keywords_json = json.dumps(manual_exc)
        
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
            
            selected_categories_json=original.selected_categories_json,
            selected_subcategories_json=original.selected_subcategories_json,
            selected_taxon_packs_json=original.selected_taxon_packs_json,
            selected_exclusions_json=original.selected_exclusions_json,
            
            include_keywords_json=original.include_keywords_json,
            exclude_keywords_json=original.exclude_keywords_json,
            taxon_allowlist_json=original.taxon_allowlist_json,
            taxon_blocklist_json=original.taxon_blocklist_json,
            journals_allowlist_json=original.journals_allowlist_json,
            journals_blocklist_json=original.journals_blocklist_json,
        )
        session.add(clone)
        session.commit()
    st.success("Feed duplicated!")


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
    st.success("Feed deleted.")


def _render_manual_list_editor(key: str, form_id: str | int) -> None:
    """Helper to render a text input + add button and a list of tags."""
    ss_key = f"{key}_{form_id}"
    current_list = st.session_state.get(ss_key, [])
    
    # Input row
    c_in, c_btn = st.columns([0.8, 0.2])
    with c_in:
        new_val = st.text_input(f"Add to {key}", key=f"input_{ss_key}", label_visibility="collapsed")
    with c_btn:
        if st.button("➕", key=f"btn_{ss_key}"):
            if new_val and new_val.strip() and new_val.strip() not in current_list:
                current_list.append(new_val.strip())
                st.session_state[ss_key] = current_list
                st.rerun()

    # Display list
    if current_list:
        st.markdown('<div style="display: flex; flex-wrap: wrap; gap: 4px; margin-top: 8px;">', unsafe_allow_html=True)
        for i, item in enumerate(current_list):
            cols = st.columns([0.85, 0.15])
            with cols[0]:
                st.markdown(f"""<div style="background: #334155; color: #f1f5f9; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem;">{item}</div>""", unsafe_allow_html=True)
            with cols[1]:
                if st.button("x", key=f"del_{ss_key}_{i}", help=f"Remove {item}"):
                    current_list.pop(i)
                    st.session_state[ss_key] = current_list
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.caption("No manual terms added.")
