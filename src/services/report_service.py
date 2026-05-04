"""
Report generation service — generates HTML cards for the report view.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from src.db.models import Result


def generate_report_html(results: list[Result], run_info: dict[str, Any] | None = None) -> str:
    """Generate full HTML report for a list of results."""
    items_html = "\n".join(_result_card_html(r) for r in results)

    header = ""
    if run_info:
        date_str = run_info.get("date", datetime.utcnow().strftime("%Y-%m-%d"))
        profile_name = run_info.get("profile", "Unknown Profile")
        total = run_info.get("total", len(results))
        header = f"""
        <div class="report-header">
            <h1>🐠 Aquarium Science Monitor</h1>
            <div class="report-meta">
                Profile: <strong>{profile_name}</strong> &nbsp;|&nbsp;
                Date: <strong>{date_str}</strong> &nbsp;|&nbsp;
                Results: <strong>{total}</strong>
            </div>
        </div>
        """

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>Aquarium Science Monitor Report</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #0f172a; color: #f1f5f9; margin: 0; padding: 24px; }}
  .report-header {{ background: linear-gradient(135deg, #0e7490, #0891b2);
                    border-radius: 12px; padding: 24px; margin-bottom: 28px; }}
  .report-header h1 {{ margin: 0 0 8px 0; font-size: 1.8rem; color: white; }}
  .report-meta {{ color: rgba(255,255,255,0.8); font-size: 0.9rem; }}
  .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 12px;
           padding: 20px; margin-bottom: 16px; }}
  .card-title {{ font-size: 1.05rem; font-weight: 700; margin: 0 0 10px 0; }}
  .card-title a {{ color: #22d3ee; text-decoration: none; }}
  .card-title a:hover {{ text-decoration: underline; }}
  .badge {{ display: inline-block; padding: 2px 10px; border-radius: 999px;
            font-size: 0.7rem; font-weight: 700; margin: 0 4px 4px 0; }}
  .badge-cat {{ background: rgba(14,116,144,0.3); color: #22d3ee; }}
  .badge-preprint {{ background: rgba(139,92,246,0.3); color: #c4b5fd; }}
  .badge-article {{ background: rgba(16,185,129,0.2); color: #6ee7b7; }}
  .badge-news {{ background: rgba(245,158,11,0.2); color: #fcd34d; }}
  .badge-taxon {{ background: rgba(52,211,153,0.15); color: #6ee7b7;
                  border: 1px solid rgba(110,231,183,0.25); font-size: 0.68rem; }}
  .abstract {{ color: #94a3b8; font-size: 0.85rem; line-height: 1.6; margin: 10px 0; }}
  .meta {{ color: #64748b; font-size: 0.78rem; margin-top: 8px; }}
  .score {{ color: #22d3ee; font-size: 0.75rem; font-weight: 700; float: right; }}
  img.thumb {{ width: 80px; height: 60px; object-fit: cover; border-radius: 6px;
               float: right; margin-left: 12px; border: 1px solid #334155; }}
</style>
</head>
<body>
{header}
<div class="results">
{items_html}
</div>
</body>
</html>
"""


def _result_card_html(r: Result) -> str:
    title_html = r.title
    if r.url:
        title_html = f'<a href="{r.url}" target="_blank">{r.title}</a>'

    # Badges
    badges = ""
    if r.category:
        badges += f'<span class="badge badge-cat">{r.category}</span>'
    if r.subcategory:
        badges += f'<span class="badge badge-cat">{r.subcategory}</span>'
    if r.is_preprint:
        badges += '<span class="badge badge-preprint">PREPRINT</span>'
    elif r.content_type == "news" or r.content_type == "rss":
        badges += f'<span class="badge badge-news">{(r.content_type or "").upper()}</span>'
    else:
        badges += '<span class="badge badge-article">ARTICLE</span>'

    # Taxa chips
    taxa_html = ""
    for taxon in r.get_taxa()[:6]:
        taxa_html += f'<span class="badge badge-taxon">{taxon}</span>'

    # Abstract
    abstract_html = ""
    if r.abstract_or_summary:
        text = r.abstract_or_summary[:400]
        if len(r.abstract_or_summary) > 400:
            text += "..."
        abstract_html = f'<p class="abstract">{text}</p>'

    # Image
    img_html = ""
    if r.image_url:
        img_html = f'<img class="thumb" src="{r.image_url}" alt="thumbnail" loading="lazy"/>'

    # Meta
    date_str = r.published_at.strftime("%Y-%m-%d") if r.published_at else "Unknown date"
    journal = r.journal_or_outlet or r.source_name or r.source_connector
    meta_html = f'<div class="meta">{journal} &nbsp;·&nbsp; {date_str}</div>'

    score_html = f'<span class="score">Score: {r.relevance_score:.1f}</span>'

    return f"""
<div class="card">
  {img_html}
  {score_html}
  <h3 class="card-title">{title_html}</h3>
  <div>{badges}{taxa_html}</div>
  {abstract_html}
  {meta_html}
</div>
"""
