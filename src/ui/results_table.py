"""
Results table page — sortable, filterable, with row-level actions.
"""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from src.db.models import Result, SearchRun, Profile
from src.db.session import get_session
from src.services.export_service import export_csv, export_xlsx, export_docx, export_pdf


def render_results_table() -> None:
    st.markdown('<div class="section-header">📊 Results</div>', unsafe_allow_html=True)

    # Run selector
    run_id = _select_run()
    if not run_id:
        return

    # Load results
    with get_session() as session:
        results = (
            session.query(Result)
            .filter(Result.run_id == run_id, Result.is_irrelevant == False)
            .order_by(Result.relevance_score.desc())
            .all()
        )
        run = session.query(SearchRun).get(run_id)
        profile = session.query(Profile).get(run.profile_id) if run else None
        profile_name = profile.name if profile else "Unknown"

        # Detach: convert to dicts
        results_data = _results_to_dicts(results)

    if not results_data:
        st.info("No results for this run. Try running a search first.")
        return

    # Filters
    filtered_data = _render_filters(results_data)

    # Summary stats
    _render_stats(filtered_data, run)

    st.divider()

    # Export controls
    _render_export_controls(results, profile_name)

    st.divider()

    # Table
    _render_table(filtered_data, run_id)


def _select_run() -> int | None:
    """Dropdown to select a search run."""
    with get_session() as session:
        runs = (
            session.query(SearchRun, Profile)
            .join(Profile, SearchRun.profile_id == Profile.id)
            .filter(SearchRun.status == "done")
            .order_by(SearchRun.started_at.desc())
            .limit(20)
            .all()
        )
        run_options = {
            f"Run #{r.id} — {p.name} — {r.started_at.strftime('%Y-%m-%d %H:%M')} ({r.total_deduped_results} results)": r.id
            for r, p in runs
        }

    if not run_options:
        st.info("No completed search runs yet. Go to **Run Search** to get started.")
        return None

    # Pre-select last run if coming from run search
    default_idx = 0
    last_run_id = st.session_state.get("view_run_id")
    if last_run_id:
        for i, rid in enumerate(run_options.values()):
            if rid == last_run_id:
                default_idx = i
                break

    selected_label = st.selectbox("Select Search Run", list(run_options.keys()), index=default_idx)
    return run_options[selected_label]


def _render_filters(results_data: list[dict]) -> list[dict]:
    """Render filter controls and return filtered data."""
    with st.expander("🔎 Filters", expanded=True):
        col1, col2, col3 = st.columns(3)

        with col1:
            search_text = st.text_input("Search in title/abstract", key="filter_text")

        with col2:
            categories = sorted({r["Category"] for r in results_data if r["Category"]})
            selected_cats = st.multiselect("Category", options=["All"] + categories, default=["All"])

        with col3:
            sources = sorted({r["Source"] for r in results_data if r["Source"]})
            selected_sources = st.multiselect("Source", options=["All"] + sources, default=["All"])

        col4, col5 = st.columns(2)
        with col4:
            min_score = st.slider("Min Relevance Score", 0.0, 50.0, 0.0, 0.5)
        with col5:
            show_preprints = st.checkbox("Show Preprints", value=True)

    # Apply filters
    filtered = results_data
    if search_text:
        q = search_text.lower()
        filtered = [r for r in filtered if q in r["Title"].lower() or q in r["Abstract"].lower()]
    if selected_cats and "All" not in selected_cats:
        filtered = [r for r in filtered if r["Category"] in selected_cats]
    if selected_sources and "All" not in selected_sources:
        filtered = [r for r in filtered if r["Source"] in selected_sources]
    if min_score > 0:
        filtered = [r for r in filtered if r["Score"] >= min_score]
    if not show_preprints:
        filtered = [r for r in filtered if not r["Is Preprint"]]

    return filtered


def _render_stats(results_data: list[dict], run: SearchRun | None) -> None:
    """Render summary statistics."""
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Results Shown", len(results_data))
    with col2:
        avg_score = sum(r["Score"] for r in results_data) / len(results_data) if results_data else 0
        st.metric("Avg Score", f"{avg_score:.1f}")
    with col3:
        preprint_count = sum(1 for r in results_data if r["Is Preprint"])
        st.metric("Preprints", preprint_count)
    with col4:
        cats = len({r["Category"] for r in results_data if r["Category"]})
        st.metric("Categories", cats)


def _render_export_controls(results: list[Result], profile_name: str) -> None:
    """Export download buttons."""
    st.markdown("**📥 Export Results**")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        csv_data = export_csv(results)
        st.download_button("⬇️ CSV", data=csv_data, file_name="results.csv", mime="text/csv")

    with col2:
        xlsx_data = export_xlsx(results)
        st.download_button("⬇️ XLSX", data=xlsx_data, file_name="results.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    with col3:
        docx_data = export_docx(results, profile_name)
        st.download_button("⬇️ DOCX", data=docx_data, file_name="results.docx",
                           mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    with col4:
        try:
            pdf_data = export_pdf(results, profile_name)
            st.download_button("⬇️ PDF", data=pdf_data, file_name="results.pdf", mime="application/pdf")
        except Exception as e:
            st.button("⬇️ PDF (unavailable)", disabled=True, help=str(e))


def _render_table(results_data: list[dict], run_id: int) -> None:
    """Render the results table with row actions."""
    if not results_data:
        st.info("No results match your filters.")
        return

    # Truncate abstract for display
    display_data = []
    for r in results_data:
        display_data.append({
            "Title": r["Title"][:80] + ("..." if len(r["Title"]) > 80 else ""),
            "Category": r["Category"],
            "Subcategory": r["Subcategory"],
            "Species": r["Species"][:40] if r["Species"] else "",
            "Source": r["Source"],
            "Date": r["Published"],
            "Score": r["Score"],
            "Type": r["Content Type"],
            "Preprint": "✓" if r["Is Preprint"] else "",
            "_id": r["ID"],
        })

    df = pd.DataFrame(display_data)
    df_display = df.drop(columns=["_id"])

    st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Score": st.column_config.NumberColumn(format="%.1f"),
        },
    )

    # Row actions
    st.markdown("**Row Actions**")
    col_sel, col_act = st.columns([0.4, 0.6])
    with col_sel:
        selected_title = st.selectbox(
            "Select result",
            options=[r["Title"] for r in results_data],
            key="row_action_select",
        )
    with col_act:
        selected_result = next((r for r in results_data if r["Title"] == selected_title), None)
        if selected_result:
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("🔗 Open", key="open_link"):
                    if selected_result.get("URL"):
                        st.markdown(f"[Open in browser]({selected_result['URL']})")
                    else:
                        st.warning("No URL available.")
            with c2:
                if st.button("⭐ Save", key="save_result"):
                    _update_result_flag(selected_result["ID"], "is_saved", True)
                    st.success("Saved!")
            with c3:
                if st.button("🚫 Irrelevant", key="mark_irrelevant"):
                    _update_result_flag(selected_result["ID"], "is_irrelevant", True)
                    st.success("Marked irrelevant.")
                    st.rerun()

    # Show detail for selected
    if selected_result:
        with st.expander("📄 Result Detail", expanded=False):
            st.markdown(f"### {selected_result['Title']}")
            meta = []
            if selected_result.get("Journal"):
                meta.append(f"**Journal:** {selected_result['Journal']}")
            if selected_result.get("Published"):
                meta.append(f"**Published:** {selected_result['Published']}")
            if selected_result.get("DOI"):
                meta.append(f"**DOI:** `{selected_result['DOI']}`")
            meta.append(f"**Score:** {selected_result['Score']:.1f}")
            if selected_result.get("Category"):
                meta.append(f"**Category:** {selected_result['Category']}")
            st.markdown(" · ".join(meta))

            if selected_result.get("Authors"):
                st.markdown(f"*Authors: {selected_result['Authors'][:100]}*")
            if selected_result.get("Species"):
                st.markdown(f"🦠 **Taxa:** {selected_result['Species']}")
            if selected_result.get("Abstract"):
                st.markdown("**Abstract:**")
                st.markdown(selected_result["Abstract"][:1000])
            if selected_result.get("URL"):
                st.markdown(f"🔗 [{selected_result['URL']}]({selected_result['URL']})")


def _results_to_dicts(results: list[Result]) -> list[dict]:
    return [
        {
            "ID": r.id,
            "Title": r.title,
            "Category": r.category or "",
            "Subcategory": r.subcategory or "",
            "Species": "; ".join(r.get_species()),
            "Taxa": "; ".join(r.get_taxa()),
            "Source": r.source_name or r.source_connector,
            "Journal": r.journal_or_outlet or "",
            "Authors": "; ".join(r.get_authors()),
            "Published": r.published_at.strftime("%Y-%m-%d") if r.published_at else "",
            "DOI": r.doi or "",
            "URL": r.url or "",
            "Abstract": r.abstract_or_summary or "",
            "Score": r.relevance_score,
            "Content Type": r.content_type or "",
            "Is Preprint": r.is_preprint,
            "Is Saved": r.is_saved,
        }
        for r in results
    ]


def _update_result_flag(result_id: int, field: str, value: bool) -> None:
    with get_session() as session:
        r = session.query(Result).get(result_id)
        if r:
            setattr(r, field, value)
            session.commit()
