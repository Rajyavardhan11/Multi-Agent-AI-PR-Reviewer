import logging
from typing import Any

from agents.base import OllamaJSONAgent

logger = logging.getLogger(__name__)


class RefactorAgent(OllamaJSONAgent):
    async def review_diff(self, diff: str) -> dict[str, Any]:
        system_prompt = (
            "You are the Refactor Agent in a multi-agent pull request review system. "
            "Analyze ONLY code quality and maintainability issues in the supplied diff. "
            "Focus on dead code, duplicated logic, naming issues, missing error handling, "
            "performance problems, overly complex functions, brittle abstractions, and hard-to-test logic. "
            "Do not report security issues. Respond with valid JSON only using this schema: "
            '{"refactor_suggestions":[{"line":"str","problem":"str","suggestion":"str"}]}. '
            'Use "file:line" locations when possible. If there are no suggestions, return {"refactor_suggestions":[]}.'
        )
        user_prompt = f"Review this pull request diff for refactor opportunities only:\n\n{diff}"

        try:
            raw_output = await self._request_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            return self._normalize_output(raw_output)
        except Exception as exc:
            logger.exception("Refactor agent failed.")
            return {"refactor_suggestions": [], "error": str(exc)}

    @staticmethod
    def _normalize_output(raw_output: dict[str, Any]) -> dict[str, Any]:
        normalized_suggestions: list[dict[str, str]] = []
        for suggestion in raw_output.get("refactor_suggestions", []):
            if not isinstance(suggestion, dict):
                continue
            problem = str(suggestion.get("problem", "")).strip()
            if not problem:
                continue
            normalized_suggestions.append(
                {
                    "line": str(suggestion.get("line", "unknown")).strip() or "unknown",
                    "problem": problem,
                    "suggestion": (
                        str(suggestion.get("suggestion", "")).strip()
                        or "Simplify or restructure this logic."
                    ),
                }
            )
        return {"refactor_suggestions": normalized_suggestions}
