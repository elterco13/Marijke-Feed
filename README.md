# 🐠 Aquarium Science Monitor

An internal Streamlit web application for an aquarium science writer to manually run configurable searches across academic APIs and RSS sources, aggregate results, score relevance, and produce curated HTML reports with export options.

---

## Quick Start

### 1. Prerequisites

- Python 3.11+
- pip

### 2. Install Dependencies

```bash
cd aquarium_science_monitor
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

```env
OPENALEX_EMAIL=your_email@example.com
CONTACT_EMAIL=your_email@example.com
```

This is required for OpenAlex polite-pool access (no API key needed — just your email).

### 4. Run

```bash
streamlit run app.py
```

The app will auto-create the database (`data/app.db`) and seed default connectors and RSS feeds on first run.

Open: http://localhost:8501

---

## First Steps

1. **Create a Profile** → Go to **Profiles** → New Profile
   - Enter a search query (e.g. `ornamental fish new species taxonomy`)
   - Set date window and result limit
   - Choose which connectors to enable

2. **Run a Search** → Go to **Run Search**
   - Select your profile
   - Toggle connectors
   - Click **🚀 Run Search Now**

3. **Review Results** → Go to **Results** or **Report View**
   - Filter by category, source, score
   - Save or mark irrelevant
   - Download as CSV / XLSX / DOCX / PDF

---

## Project Structure

```
aquarium_science_monitor/
├── app.py                        # Streamlit entry point
├── requirements.txt
├── .env.example
├── README.md
├── data/
│   ├── app.db                    # SQLite database (auto-created)
│   ├── seed_sources.json         # Default RSS feeds
│   ├── taxon_keywords.json       # Aquarium taxa + common names
│   ├── include_keywords.json     # Positive topic keywords
│   ├── exclude_keywords.json     # Exclusion keywords
│   ├── category_rules.json       # Category → keyword mapping
│   └── source_boosts.json        # Journal/source score boosts
├── exports/                      # Downloaded export files stored here
├── src/
│   ├── config/
│   │   └── settings.py           # Pydantic settings (env-driven)
│   ├── db/
│   │   ├── base.py               # SQLAlchemy declarative base
│   │   ├── models.py             # ORM models
│   │   ├── session.py            # Engine + session factory
│   │   └── init_db.py            # DB init + seeding
│   ├── schemas/
│   │   ├── source_record.py      # NormalizedSourceRecord schema
│   │   ├── profile.py            # Profile schema
│   │   └── run.py                # Run schema
│   ├── connectors/
│   │   ├── base.py               # BaseConnector ABC
│   │   ├── openalex.py           # OpenAlex connector
│   │   ├── crossref.py           # Crossref connector
│   │   ├── europepmc.py          # Europe PMC connector
│   │   ├── pubmed.py             # PubMed connector
│   │   ├── rss.py                # Generic RSS connector
│   │   └── news_stub.py          # News/comms stub
│   ├── services/
│   │   ├── source_registry.py    # Connector registry
│   │   ├── search_service.py     # Search orchestration
│   │   ├── normalization_service.py
│   │   ├── dedupe_service.py     # Multi-strategy deduplication
│   │   ├── scoring_service.py    # Rule-based relevance engine
│   │   ├── taxonomy_service.py   # Taxa extraction
│   │   ├── export_service.py     # CSV/XLSX/DOCX/PDF
│   │   └── report_service.py     # HTML report generation
│   ├── ui/
│   │   ├── sidebar.py
│   │   ├── profiles.py
│   │   ├── run_search.py
│   │   ├── results_table.py
│   │   ├── report_view.py
│   │   ├── history.py
│   │   └── settings_view.py
│   └── utils/
│       ├── logging.py
│       ├── dates.py
│       ├── text.py
│       ├── urls.py
│       └── hashing.py
└── tests/
```

---

## Configuring Sources

### RSS Feeds

Manage RSS feeds in **Settings → RSS Feeds** or edit `data/seed_sources.json` before first run.

Default feeds include:
- ZooKeys (taxonomy)
- Frontiers in Marine Science
- Journal of Fish Biology
- Diseases of Aquatic Organisms
- Coral Reefs
- Taxonomy (MDPI)
- ScienceDaily (fish + marine biology)

### Keyword Tuning

Edit JSON files in `data/`:
- `include_keywords.json` — add/remove positive keywords and weights
- `exclude_keywords.json` — add hard excludes or soft penalties
- `source_boosts.json` — increase/decrease journal-level boosts
- `category_rules.json` — add new category rules
- `taxon_keywords.json` — add genera, species, common names

Changes take effect immediately (files are loaded fresh each run).

---

## Data Sources

| Source | API | Auth Required | Notes |
|--------|-----|---------------|-------|
| OpenAlex | REST | Email only (polite pool) | Best for broad academic coverage |
| Crossref | REST | Email only (mailto) | Good for DOI/abstract data |
| Europe PMC | REST | None | Strong for biomedical, preprints |
| PubMed | E-utilities XML | Optional API key | Good for fish diseases/microbiology |
| RSS | feedparser | None | Configurable per-journal |

---

## Relevance Scoring

Scoring is fully transparent and rule-based. Each result includes a `relevance_explanation` JSON with:
- `positive_title_hits` — keywords found in title (2× weight)
- `positive_abstract_hits` — keywords found in abstract
- `taxon_hits` — taxa/species found in text (5 pts each)
- `negative_hits` — penalizing keywords found
- `journal_boost` — journal-level boost applied
- `doi_bonus`, `abstract_bonus` — metadata completeness signals
- `component_scores` — per-component score breakdown

Scores range from 0 (irrelevant) to ~100+ (highly relevant). The engine hard-excludes records matching any `hard_exclude: true` keyword.

---

## Deduplication

Records are deduplicated in priority order:
1. **Exact DOI match** — same DOI = duplicate
2. **Normalized URL match** — same URL (stripped query/fragment) = duplicate
3. **Exact normalized title** — same title (lowercased, stripped) = duplicate
4. **Fuzzy title + date proximity** — ≥88% similarity + within 90 days = duplicate

The best representative is kept (prefers: has DOI > has abstract > not preprint > most recent).

---

## Adding New Connectors

1. Create `src/connectors/my_connector.py` extending `BaseConnector`
2. Implement `run(profile) -> list[NormalizedSourceRecord]`
3. Register in `src/services/source_registry.py`
4. Add a seeded row in `_seed_connectors()` in `init_db.py`
5. Optionally add a toggle in `.env.example`

---

## Architecture Notes: Future Expansion

### Scheduled Runs
`SearchService.run_search()` is completely decoupled from the Streamlit UI.
To add scheduling:
```python
from apscheduler.schedulers.background import BackgroundScheduler
scheduler = BackgroundScheduler()
scheduler.add_job(func=run_scheduled_search, trigger="interval", hours=24)
scheduler.start()
```
The `SearchRun` table already tracks all metadata for run history and scheduling state.

### Email Delivery
Add `src/services/email_service.py`:
```python
def send_run_report(run_id: int, recipient: str):
    results = load_results(run_id)
    html = generate_report_html(results)
    send_email(recipient, html)  # via smtplib or Mailgun API
```

### Feedback Learning
The `is_saved` and `is_irrelevant` flags on `Result` rows are in place.
The `NegativeFeedbackRule` table holds explicit user exclusion rules.
A future `feedback_service.py` could:
- Aggregate saved/irrelevant signals per keyword/source
- Auto-adjust scoring weights in `scoring_service.py`
- Build a lightweight classifier from labeled data

### Multi-user Support
Add a `users` table, attach `profile_id` and `run_id` to user sessions.
Use `streamlit-authenticator` for session auth.
The schema is already keyed for per-user isolation.

---

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENALEX_EMAIL` | — | Email for OpenAlex polite pool (required) |
| `CONTACT_EMAIL` | — | Contact email for API User-Agent headers |
| `DATABASE_URL` | `sqlite:///./data/app.db` | SQLAlchemy database URL |
| `REQUEST_TIMEOUT` | `30` | HTTP request timeout in seconds |
| `DEFAULT_RESULT_LIMIT` | `50` | Default max results per source |
| `DEFAULT_DATE_WINDOW_DAYS` | `30` | Default search date window |
| `ENABLE_CONNECTOR_OPENALEX` | `true` | Enable/disable OpenAlex connector |
| `ENABLE_CONNECTOR_CROSSREF` | `true` | Enable/disable Crossref connector |
| `ENABLE_CONNECTOR_EUROPEPMC` | `true` | Enable/disable Europe PMC connector |
| `ENABLE_CONNECTOR_PUBMED` | `true` | Enable/disable PubMed connector |
| `ENABLE_CONNECTOR_RSS` | `true` | Enable/disable RSS connector |
| `PUBMED_API_KEY` | — | Optional PubMed API key (increases rate limit) |
| `LOG_LEVEL` | `INFO` | Logging level |

---

## License

Internal use only.
