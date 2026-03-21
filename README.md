# ⚡ Kunoichi Radar

Discover trending GitHub repositories at the intersection of AI and industry verticals — AI Engineering, Dental AI, and Healthcare AI.

## Features

- Fetches and ranks repos from GitHub Search API across configurable categories
- Deduplicates repos that appear across multiple search queries
- SQLite-backed cache with upsert on refresh
- Rich CLI for fetching, listing, and exporting results
- FastAPI web dashboard with tabbed categories, sortable tables, and live filters
- Daily auto-refresh via GitHub Actions

---

## Setup

### 1. Clone and create a virtual environment

```bash
git clone https://github.com/codekunoichi/kunoichi-radar.git
cd kunoichi-radar
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and set your GITHUB_TOKEN
```

Generate a token at https://github.com/settings/tokens — no special scopes needed (public repo access only).

### 3. Fetch data

```bash
python main.py fetch
```

---

## CLI Usage

```bash
# Fetch all categories from GitHub API
python main.py fetch

# List repos (all categories, default sorting)
python main.py list

# Filter by category and minimum stars
python main.py list --category "AI Engineering" --min-stars 100

# Export to CSV
python main.py export --format csv --output results.csv

# Export to JSON
python main.py export --format json
```

---

## Web Dashboard

```bash
uvicorn src.web:app --reload --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 — tabbed categories, sortable tables, min-star slider, date-range filter, and a "Refresh Now" button that triggers a live background fetch.

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | HTML dashboard (`?min_stars=`, `?pushed_after=`, `?pushed_before=`) |
| `/refresh` | POST | Trigger a background fetch; returns `{"status": "started"}` |
| `/status` | GET | Returns `{"fetch_in_progress": true/false}` |
| `/api/repos` | GET | JSON list of repos (`?category=`, `?min_stars=`) |

---

## Configuration

Edit `config/categories.yaml` to add, remove, or modify search categories:

```yaml
categories:
  - name: "My Category"
    queries:
      - "my topic stars:>50"
    topics:
      - my-github-topic
```

---

## Project Structure

```
kunoichi-radar/
├── README.md
├── requirements.txt
├── .env.example
├── config/
│   └── categories.yaml       # Search categories (editable)
├── src/
│   ├── github_client.py      # GitHub API calls, rate limiting, pagination
│   ├── database.py           # SQLAlchemy models and queries
│   ├── scheduler.py          # Fetch orchestration
│   └── web.py                # FastAPI app
├── templates/
│   └── dashboard.html        # Jinja2 web dashboard
├── main.py                   # CLI entry point
├── data/                     # SQLite DB (auto-created)
└── tests/
    └── test_github_client.py
```

---

## GitHub Actions

The workflow at `.github/workflows/refresh.yml` runs `python main.py fetch` daily at 6am UTC and commits the updated `data/radar.db` back to the repo. Make sure `GITHUB_TOKEN` is available in your repo secrets (it is by default for Actions).

---

## Running Tests

```bash
source venv/bin/activate
pytest tests/ -v
```
