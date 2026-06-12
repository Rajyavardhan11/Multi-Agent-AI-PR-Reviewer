import os

import pytest
from httpx import ASGITransport, AsyncClient

from main import app
from tests.conftest import build_signature


@pytest.mark.asyncio
async def test_webhook_rejects_invalid_signature(sample_diff: str) -> None:
    os.environ["GITHUB_WEBHOOK_SECRET"] = "topsecret"
    payload = {
        "action": "opened",
        "number": 7,
        "repository": {"name": "demo", "owner": {"login": "octocat"}},
        "pull_request": {"number": 7},
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/webhook",
            json=payload,
            headers={
                "X-GitHub-Event": "pull_request",
                "X-Hub-Signature-256": "sha256=invalid",
            },
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_webhook_posts_large_pr_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    os.environ["GITHUB_WEBHOOK_SECRET"] = "topsecret"
    os.environ["GITHUB_TOKEN"] = "github-token"

    payload = {
        "action": "opened",
        "number": 11,
        "repository": {"name": "demo", "owner": {"login": "octocat"}},
        "pull_request": {"number": 11},
    }
    body, signature = build_signature("topsecret", payload)
    posted_comments: list[str] = []

    async def fake_get_pr_diff(self, owner: str, repo: str, pr_number: int) -> str:
        return "x" * 50001

    async def fake_post_pr_comment(self, owner: str, repo: str, pr_number: int, body: str) -> None:
        posted_comments.append(body)

    monkeypatch.setattr("routes.webhook.GitHubService.get_pr_diff", fake_get_pr_diff)
    monkeypatch.setattr("routes.webhook.GitHubService.post_pr_comment", fake_post_pr_comment)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "pull_request",
                "X-Hub-Signature-256": signature,
            },
        )

    assert response.status_code == 200
    assert posted_comments == ["PR too large for automated review"]


@pytest.mark.asyncio
async def test_webhook_runs_graph_and_posts_comment(
    monkeypatch: pytest.MonkeyPatch,
    sample_diff: str,
) -> None:
    os.environ["GITHUB_WEBHOOK_SECRET"] = "topsecret"
    os.environ["GITHUB_TOKEN"] = "github-token"

    payload = {
        "action": "synchronize",
        "number": 5,
        "repository": {"name": "demo", "owner": {"login": "octocat"}},
        "pull_request": {"number": 5},
    }
    body, signature = build_signature("topsecret", payload)
    posted_comments: list[str] = []

    class FakeGraph:
        async def ainvoke(self, state):
            assert state == {"diff": sample_diff}
            return {
                "security_output": {
                    "security_issues": [
                        {
                            "severity": "high",
                            "line": "app.py:5",
                            "issue": "SQL injection risk.",
                            "fix": "Use parameters.",
                        }
                    ]
                },
                "refactor_output": {
                    "refactor_suggestions": [
                        {
                            "line": "app.py:3",
                            "problem": "Function is doing too much.",
                            "suggestion": "Extract query generation into a helper.",
                        }
                    ]
                },
                "final_review": {
                    "overall_severity": "high",
                    "summary": "The PR adds a high-risk security issue and a moderate maintainability concern.",
                    "security_issues": [
                        {
                            "severity": "high",
                            "line": "app.py:5",
                            "issue": "SQL injection risk.",
                            "fix": "Use parameters.",
                        }
                    ],
                    "refactor_suggestions": [
                        {
                            "line": "app.py:3",
                            "problem": "Function is doing too much.",
                            "suggestion": "Extract query generation into a helper.",
                        }
                    ],
                },
            }

    async def fake_get_pr_diff(self, owner: str, repo: str, pr_number: int) -> str:
        return sample_diff

    async def fake_post_pr_comment(self, owner: str, repo: str, pr_number: int, body: str) -> None:
        posted_comments.append(body)

    monkeypatch.setattr("routes.webhook.review_graph", FakeGraph())
    monkeypatch.setattr("routes.webhook.GitHubService.get_pr_diff", fake_get_pr_diff)
    monkeypatch.setattr("routes.webhook.GitHubService.post_pr_comment", fake_post_pr_comment)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "pull_request",
                "X-Hub-Signature-256": signature,
            },
        )

    assert response.status_code == 200
    assert len(posted_comments) == 1
    assert "## 🤖 Multi-Agent AI Code Review" in posted_comments[0]
    assert "🔐 Security Issues" in posted_comments[0]
    assert "♻️ Refactor Suggestions" in posted_comments[0]
