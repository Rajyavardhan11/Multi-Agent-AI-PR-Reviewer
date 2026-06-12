import pytest
import httpx

from agents.base import OllamaJSONAgent
from agents.refactor_agent import RefactorAgent
from agents.security_agent import SecurityAgent
from agents.summary_agent import SummaryAgent


@pytest.mark.asyncio
async def test_ollama_agent_posts_chat_request(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_request: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured_request["url"] = str(request.url)
        captured_request["payload"] = request.read()
        return httpx.Response(
            200,
            json={"message": {"content": '{"security_issues": []}'}},
        )

    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient

    class FakeAsyncClient:
        def __init__(self, *, timeout: float):
            self.timeout = timeout
            self.client = real_async_client(transport=transport)

        async def __aenter__(self):
            return self.client

        async def __aexit__(self, exc_type, exc, tb):
            await self.client.aclose()

    monkeypatch.setenv("OLLAMA_MODEL", "phi3:latest")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    result = await OllamaJSONAgent()._request_json(
        system_prompt="Return JSON only.",
        user_prompt="Review this diff.",
    )

    assert result == {"security_issues": []}
    assert captured_request["url"] == "http://localhost:11434/api/chat"
    assert b'"model":"phi3:latest"' in captured_request["payload"]
    assert b'"format":"json"' in captured_request["payload"]


@pytest.mark.asyncio
async def test_security_agent_returns_normalized_issues(monkeypatch: pytest.MonkeyPatch, sample_diff: str) -> None:
    async def fake_request_json(self, *, system_prompt: str, user_prompt: str):
        assert "security" in system_prompt.lower()
        assert sample_diff in user_prompt
        return {
            "security_issues": [
                {
                    "severity": "HIGH",
                    "line": "app.py:5",
                    "issue": "SQL query built from unsanitized input.",
                    "fix": "Use a parameterized query.",
                }
            ]
        }

    monkeypatch.setattr(SecurityAgent, "_request_json", fake_request_json)

    result = await SecurityAgent().review_diff(sample_diff)

    assert result == {
        "security_issues": [
            {
                "severity": "high",
                "line": "app.py:5",
                "issue": "SQL query built from unsanitized input.",
                "fix": "Use a parameterized query.",
            }
        ]
    }


@pytest.mark.asyncio
async def test_refactor_agent_returns_normalized_suggestions(
    monkeypatch: pytest.MonkeyPatch,
    sample_diff: str,
) -> None:
    async def fake_request_json(self, *, system_prompt: str, user_prompt: str):
        assert "maintainability" in system_prompt.lower()
        assert sample_diff in user_prompt
        return {
            "refactor_suggestions": [
                {
                    "line": "app.py:3",
                    "problem": "Database logic is embedded inside request handling.",
                    "suggestion": "Move query construction into a repository function.",
                }
            ]
        }

    monkeypatch.setattr(RefactorAgent, "_request_json", fake_request_json)

    result = await RefactorAgent().review_diff(sample_diff)

    assert result == {
        "refactor_suggestions": [
            {
                "line": "app.py:3",
                "problem": "Database logic is embedded inside request handling.",
                "suggestion": "Move query construction into a repository function.",
            }
        ]
    }


@pytest.mark.asyncio
async def test_summary_agent_falls_back_when_model_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_request_json(self, *, system_prompt: str, user_prompt: str):
        raise RuntimeError("Ollama unavailable")

    monkeypatch.setattr(SummaryAgent, "_request_json", fake_request_json)

    security_output = {
        "security_issues": [
            {
                "severity": "critical",
                "line": "app.py:8",
                "issue": "Leaked API key.",
                "fix": "Move the key to environment configuration.",
            }
        ]
    }
    refactor_output = {
        "refactor_suggestions": [
            {
                "line": "app.py:3",
                "problem": "Mixed concerns in one function.",
                "suggestion": "Extract the persistence layer into its own module.",
            }
        ]
    }

    result = await SummaryAgent().summarize_reviews(security_output, refactor_output)

    assert result["overall_severity"] == "critical"
    assert "1 security issue" in result["summary"]
    assert result["security_issues"] == security_output["security_issues"]
    assert result["refactor_suggestions"] == refactor_output["refactor_suggestions"]
