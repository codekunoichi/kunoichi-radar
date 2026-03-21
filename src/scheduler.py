import logging
from pathlib import Path

import yaml

from src.github_client import GitHubClient
from src.database import get_engine, get_session, upsert_repos

logger = logging.getLogger(__name__)


def load_categories(config_path: str = "config/categories.yaml") -> list[dict]:
    with open(config_path) as f:
        return yaml.safe_load(f)["categories"]


def run_fetch(token: str, db_path: str = "data/radar.db", config_path: str = "config/categories.yaml") -> dict:
    categories = load_categories(config_path)
    engine = get_engine(db_path)

    total_upserted = 0
    summary = {}

    with GitHubClient(token=token) as client:
        for category in categories:
            cat_name = category["name"]
            all_repos = []
            seen_ids: set[int] = set()

            for query in category.get("queries", []):
                repos = client.search(query, category=cat_name)
                for repo in repos:
                    if repo["repo_id"] not in seen_ids:
                        seen_ids.add(repo["repo_id"])
                        all_repos.append(repo)

            for topic in category.get("topics", []):
                repos = client.search_topic(topic, category=cat_name)
                for repo in repos:
                    if repo["repo_id"] not in seen_ids:
                        seen_ids.add(repo["repo_id"])
                        all_repos.append(repo)

            with get_session(engine) as session:
                count = upsert_repos(session, all_repos)

            summary[cat_name] = count
            total_upserted += count
            logger.info("Category '%s': %d unique repos upserted", cat_name, count)

    logger.info("Fetch complete. Total upserted: %d", total_upserted)
    return summary
