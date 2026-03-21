import pytest
import httpx
from unittest.mock import patch, MagicMock
from src.github_client import GitHubClient, build_search_url


SAMPLE_REPO = {
    "id": 123456,
    "full_name": "test-org/test-repo",
    "description": "A test repository",
    "stargazers_count": 150,
    "html_url": "https://github.com/test-org/test-repo",
    "topics": ["ai", "llm"],
    "created_at": "2023-01-01T00:00:00Z",
    "pushed_at": "2024-01-01T00:00:00Z",
}

SAMPLE_SEARCH_RESPONSE = {
    "total_count": 1,
    "incomplete_results": False,
    "items": [SAMPLE_REPO],
}


def test_build_search_url_query():
    url = build_search_url("llm agents stars:>10", page=1)
    assert "q=llm+agents+stars%3A%3E10" in url or "llm" in url
    assert "per_page=100" in url


def test_build_search_url_topic():
    url = build_search_url("topic:mlops stars:>10", page=1)
    assert "mlops" in url


def test_github_client_requires_token():
    with pytest.raises(ValueError, match="GITHUB_TOKEN"):
        GitHubClient(token=None)


def test_fetch_repos_returns_normalized_list():
    client = GitHubClient(token="fake-token")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = SAMPLE_SEARCH_RESPONSE
    mock_response.headers = {}

    with patch.object(client.http, "get", return_value=mock_response):
        results = client.search("llm agents stars:>10", category="AI Engineering")

    assert len(results) == 1
    repo = results[0]
    assert repo["repo_id"] == 123456
    assert repo["name"] == "test-org/test-repo"
    assert repo["stars"] == 150
    assert repo["category"] == "AI Engineering"


def test_deduplication():
    client = GitHubClient(token="fake-token")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = SAMPLE_SEARCH_RESPONSE
    mock_response.headers = {}

    with patch.object(client.http, "get", return_value=mock_response):
        results1 = client.search("llm agents stars:>10", category="AI Engineering")
        results2 = client.search("agentic AI stars:>10", category="AI Engineering")

    ids = [r["repo_id"] for r in results1 + results2]
    assert ids.count(123456) == 2  # dedup happens at DB layer, client returns all


def test_rate_limit_retry(monkeypatch):
    client = GitHubClient(token="fake-token")

    rate_limited = MagicMock()
    rate_limited.status_code = 403
    rate_limited.headers = {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "0"}
    rate_limited.json.return_value = {"message": "API rate limit exceeded"}

    ok_response = MagicMock()
    ok_response.status_code = 200
    ok_response.json.return_value = SAMPLE_SEARCH_RESPONSE
    ok_response.headers = {}

    call_count = 0

    def fake_get(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return rate_limited
        return ok_response

    monkeypatch.setattr(client.http, "get", fake_get)
    monkeypatch.setattr("src.github_client.time.sleep", lambda _: None)

    results = client.search("llm agents stars:>10", category="AI Engineering")
    assert len(results) == 1
    assert call_count == 2
