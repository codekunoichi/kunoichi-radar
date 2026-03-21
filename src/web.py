import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from src.database import get_engine, get_session, get_repos, get_categories, get_last_fetched
from src.scheduler import run_fetch

load_dotenv()
logger = logging.getLogger(__name__)

DB_PATH = os.getenv("DB_PATH", "data/radar.db")
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

app = FastAPI(title="Kunoichi Radar")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

_fetch_in_progress = False


def _engine():
    return get_engine(DB_PATH)


@app.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    min_stars: int = 0,
    pushed_after: str = "",
    pushed_before: str = "",
):
    engine = _engine()
    with get_session(engine) as session:
        categories = get_categories(session)
        last_fetched = get_last_fetched(session)

        repos_by_category = {}
        for cat in categories:
            repos_by_category[cat] = get_repos(
                session,
                category=cat,
                min_stars=min_stars,
                pushed_after=pushed_after or None,
                pushed_before=pushed_before or None,
            )

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "repos_by_category": repos_by_category,
            "categories": categories,
            "last_fetched": last_fetched,
            "min_stars": min_stars,
            "pushed_after": pushed_after,
            "pushed_before": pushed_before,
            "fetch_in_progress": _fetch_in_progress,
        },
    )


@app.post("/refresh")
async def refresh(background_tasks: BackgroundTasks):
    global _fetch_in_progress
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return JSONResponse({"error": "GITHUB_TOKEN not configured"}, status_code=500)

    if _fetch_in_progress:
        return JSONResponse({"status": "already running"})

    def do_fetch():
        global _fetch_in_progress
        _fetch_in_progress = True
        try:
            summary = run_fetch(token=token, db_path=DB_PATH)
            logger.info("Background fetch complete: %s", summary)
        except Exception as exc:
            logger.error("Fetch failed: %s", exc)
        finally:
            _fetch_in_progress = False

    background_tasks.add_task(do_fetch)
    return JSONResponse({"status": "started"})


@app.get("/status")
async def status():
    return JSONResponse({"fetch_in_progress": _fetch_in_progress})


@app.get("/api/repos")
async def api_repos(
    category: str = "",
    min_stars: int = 0,
):
    engine = _engine()
    with get_session(engine) as session:
        repos = get_repos(session, category=category or None, min_stars=min_stars)
    return repos
