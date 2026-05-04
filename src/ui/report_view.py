"""
Report View page — HTML card-style display with export options.
"""

from __future__ import annotations

import streamlit as st

from src.db.models import Result, SearchRun, Profile
from src.db.session import get_session
from src.services.report_service import generate_report_html
from src.services.export_service import export_csv, export_xlsx, export_docx, export_pdf


def render_report_view() -> None:
    st.markdown('<div class="section-header">📄 Report View</div>', unsafe_allow_html=True)

    # Run selector
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
            f"Run #{r.id} — {p.name} — {r.started_at.strftime('%Y-%m-%d %H:%M')}": (r.id, p.name)
            for r, p in runs
        }

    if not run_options:
        st.info("No completed search runs yet.")
        return

    selected_label = st.selectbox(
        "Select Run",
        list(run_options.keys()),
        index=0,
        key="report_run_select",
    )
    run_id, profile_name = run_options[selected_label]

    # Filter controls
    col1, col2, col3 = st.columns(3)
    with col1:
        min_score = st.slider("Min Score", 0.0, 50.0, 5.0, 0.5, key="report_min_score")
    with col2:
        show_preprints = st.checkbox("Show Preprints", value=True, key="report_show_preprints")
    with col3:
        max_results = st.slider("Max Results to Show", 10, 200, 50, 5, key="report_max_results")

    # Load results
    with get_session() as session:
        query = (
            session.query(Result)
            .filter(
                Result.run_id == run_id,
                Result.is_irrelevant == False,
                Result.relevance_score >= min_score,
            )
            .order_by(Result.relevance_score.desc())
            .limit(max_results)
        )
        if not show_preprints:
            query = query.filter(Result.is_preprint == False)
        results = query.all()
        profile = session.query(Profile).get(
            session.query(SearchRun).get(run_id).profile_id
        )
        profile_name_actual = profile.name if profile else profile_name

    if not results:
        st.info("No results match your filters.")
        return

    # Export bar
    st.markdown(f"**Showing {len(results)} results** (score ≥ {min_score})")
    
    exp_cols = st.columns(4)
    with exp_cols[0]:
        st.download_button("⬇️ CSV", data=export_csv(results), file_name="report.csv", mime="text/csv", key="rep_csv")
    with exp_cols[1]:
        st.download_button("⬇️ XLSX", data=export_xlsx(results), file_name="report.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="rep_xlsx")
    with exp_cols[2]:
        st.download_button("⬇️ DOCX", data=export_docx(results, profile_name_actual), file_name="report.docx",
                           mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", key="rep_docx")
    with exp_cols[3]:
        try:
            pdf_data = export_pdf(results, profile_name_actual)
            st.download_button("⬇️ PDF", data=pdf_data, file_name="report.pdf", mime="application/pdf", key="rep_pdf")
        except Exception as e:
            st.button("⬇️ PDF", disabled=True, help=str(e), key="rep_pdf_disabled")

    st.divider()

    # Category grouping
    group_by_cat = st.checkbox("Group by Category", value=True, key="report_group_cat")

    if group_by_cat:
        cats: dict[str, list[Result]] = {}
        for r in results:
            cat = r.category or "Uncategorized"
            cats.setdefault(cat, []).append(r)

        for cat, cat_results in sorted(cats.items()):
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #0e7490 0%, #0891b2 100%);
                        color: white; padding: 8px 16px; border-radius: 8px; 
                        margin: 16px 0 12px 0; font-weight: 700; font-size: 0.95rem;">
                📂 {cat} &nbsp;<span style="font-weight:400;opacity:0.8;">({len(cat_results)})</span>
            </div>
            """, unsafe_allow_html=True)
            for r in cat_results:
                _render_result_card(r)
    else:
        for r in results:
            _render_result_card(r)


def _render_result_card(r: Result) -> None:
    """Render a single result card using Streamlit components."""
    with st.container():
        # Badges
        badge_html = ""
        if r.category:
            badge_html += f'<span class="badge badge-category">{r.category}</span>'
        if r.subcategory:
            badge_html += f'<span class="badge badge-subcategory">{r.subcategory}</span>'
        if r.is_preprint:
            badge_html += '<span class="badge badge-preprint">PREPRINT</span>'
        elif r.content_type in ("news", "rss"):
            badge_html += f'<span class="badge badge-{r.content_type}">{(r.content_type or "").upper()}</span>'
        else:
            badge_html += '<span class="badge badge-article">ARTICLE</span>'

        # Taxa chips
        taxa_html = ""
        for taxon in r.get_taxa()[:6]:
            taxa_html += f'<span class="badge badge-taxon">{taxon}</span>'

        # Image
        img_html = ""
        if r.image_url:
            img_html = f'<img class="result-image" src="{r.image_url}" alt="thumbnail" loading="lazy"/>'

        # Title link
        title_html = r.title
        if r.url:
            title_html = f'<a href="{r.url}" target="_blank">{r.title}</a>'

        # Abstract
        abstract = ""
        if r.abstract_or_summary:
            abstract = r.abstract_or_summary[:400]
            if len(r.abstract_or_summary) > 400:
                abstract += "..."

        # Meta
        date_str = r.published_at.strftime("%Y-%m-%d") if r.published_at else "Unknown date"
        journal = r.journal_or_outlet or r.source_name or r.source_connector
        authors = r.get_authors()
        author_str = ", ".join(authors[:3])
        if len(authors) > 3:
            author_str += f" +{len(authors)-3} more"

        score_bar_width = min(100, r.relevance_score * 2)

        st.markdown(f"""
        <div class="report-card">
            {img_html}
            <h3>{title_html}</h3>
            <div style="margin: 6px 0;">{badge_html}{taxa_html}</div>
            {"<p class='abstract-text'>" + abstract + "</p>" if abstract else ""}
            <div class="meta-info">
                <span>📰 {journal}</span>
                <span>📅 {date_str}</span>
                {"<span>👤 " + author_str + "</span>" if author_str else ""}
                {"<span>DOI: <code>" + r.doi + "</code></span>" if r.doi else ""}
            </div>
            <div style="margin-top: 8px; display: flex; align-items: center; gap: 12px;">
                <span class="score-text">Score: {r.relevance_score:.1f}</span>
                <div style="flex:1; height:4px; background:#1e3a4a; border-radius:2px;">
                    <div style="width:{score_bar_width}%; height:100%; background:linear-gradient(90deg,#0e7490,#22d3ee); border-radius:2px;"></div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Row actions
        c1, c2, c3 = st.columns([0.12, 0.12, 0.76])
        with c1:
            if st.button("⭐", key=f"save_{r.id}", help="Save"):
                _update_flag(r.id, "is_saved", True)
                st.toast("Saved!")
        with c2:
            if st.button("🚫", key=f"irrel_{r.id}", help="Mark irrelevant"):
                _update_flag(r.id, "is_irrelevant", True)
                st.rerun()


def _update_flag(result_id: int, field: str, value: bool) -> None:
    with get_session() as session:
        r = session.query(Result).get(result_id)
        if r:
            setattr(r, field, value)
            session.commit()
