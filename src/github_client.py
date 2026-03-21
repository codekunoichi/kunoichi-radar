import time
import logging
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)

GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"
MAX_RETRIES = 5
BASE_BACKOFF = 2


def build_search_url(query: str, page: int = 1) -> str:
    params = urlencode({
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": 100,
        "page": page,
    })
    return f"{GITHUB_SEARCH_URL}?{params}"


class GitHubClient:
    def __init__(self, token: str | None):
        if not token:
            raise ValueError("GITHUB_TOKEN is required")
        self.http = httpx.Client(
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30.0,
        )

    def _get(self, url: str) -> dict:
        for attempt in range(MAX_RETRIES):
            try:
                response = self.http.get(url)
            except httpx.RequestError as exc:
                logger.warning("Network error (attempt %d): %s", attempt + 1, exc)
                time.sleep(BASE_BACKOFF ** attempt)
                continue

            if response.status_code == 200:
                return response.json()

            if response.status_code in (403, 429):
                reset_ts = int(response.headers.get("X-RateLimit-Reset", 0))
                wait = max(reset_ts - int(time.time()), BASE_BACKOFF ** attempt)
                logger.warning("Rate limited. Waiting %ds (attempt %d).", wait, attempt + 1)
                time.sleep(wait)
                continue

            logger.error("Unexpected status %d for %s", response.status_code, url)
            response.raise_for_status()

        raise RuntimeError(f"Failed to fetch {url} after {MAX_RETRIES} retries")

    def _normalize(self, item: dict, category: str) -> dict:
        return {
            "repo_id": item["id"],
            "name": item["full_name"],
            "description": item.get("description") or "",
            "stars": item["stargazers_count"],
            "url": item["html_url"],
            "topics": ",".join(item.get("topics") or []),
            "category": category,
            "created_at": item.get("created_at"),
            "pushed_at": item.get("pushed_at"),
            "last_fetched": datetime.now(timezone.utc).isoformat(),
        }

    def search(self, query: str, category: str) -> list[dict]:
        results = []
        page = 1

        while True:
            url = build_search_url(query, page)
            logger.info("Fetching page %d for query: %s", page, query)
            data = self._get(url)
            items = data.get("items", [])

            if not items:
                break

            results.extend(self._normalize(item, category) for item in items)

            if len(results) >= data.get("total_count", 0) or len(items) < 100:
                break

            page += 1
            time.sleep(0.5)  # be kind to the API

        logger.info("Found %d repos for query: %s", len(results), query)
        return results

    def search_topic(self, topic: str, category: str) -> list[dict]:
        return self.search(f"topic:{topic} stars:>10", category)

    def close(self):
        self.http.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
