import asyncio
import time

import pytest

from agents.refactor_agent import RefactorAgent
from agents.security_agent import SecurityAgent
from agents.summary_agent import SummaryAgent
from graph.review_graph import review_graph


@pytest.mark.asyncio
async def test_review_graph_runs_end_to_end_in_parallel(
    monkeypatch: pytest.MonkeyPatch,
    sample_diff: str,
) -> None:
    async def fake_security_review(self, diff: str):
        await asyncio.sleep(0.2)
        return {
            "security_issues": [
                {
                    "severity": "high",
                    "line": "app.py:5",
                    "issue": "Unsanitized SQL input.",
                    "fix": "Use bound parameters.",
                }
            ]
        }

    async def fake_refactor_review(self, diff: str):
        await asyncio.sleep(0.2)
        return {
            "refactor_suggestions": [
                {
                    "line": "app.py:3",
                    "problem": "Function mixes querying and transport concerns.",
                    "suggestion": "Split data access from request logic.",
                }
            ]
        }

    async def fake_summary(self, security_output, refactor_output):
        return {
            "overall_severity": "high",
            "summary": "The PR adds one high-risk security issue and one refactor concern.",
            "security_issues": security_output["security_issues"],
            "refactor_suggestions": refactor_output["refactor_suggestions"],
        }

    monkeypatch.setattr(SecurityAgent, "review_diff", fake_security_review)
    monkeypatch.setattr(RefactorAgent, "review_diff", fake_refactor_review)
    monkeypatch.setattr(SummaryAgent, "summarize_reviews", fake_summary)

    start = time.perf_counter()
    result = await review_graph.ainvoke({"diff": sample_diff})
    elapsed = time.perf_counter() - start

    assert elapsed < 0.35
    assert result["final_review"]["overall_severity"] == "high"
    assert len(result["security_output"]["security_issues"]) == 1
    assert len(result["refactor_output"]["refactor_suggestions"]) == 1
