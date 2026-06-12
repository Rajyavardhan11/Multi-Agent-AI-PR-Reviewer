import logging
from typing import Any

from agents.base import OllamaJSONAgent

logger = logging.getLogger(__name__)


class SecurityAgent(OllamaJSONAgent):
    async def review_diff(self, diff: str) -> dict[str, Any]:
        system_prompt = (
            "You are the Security Agent in a multi-agent pull request review system. "
            "Analyze ONLY security issues in the supplied diff. Limit findings to "
            "hardcoded secrets, SQL injection, XSS, insecure dependencies, exposed API keys, "
            "unsafe deserialization, auth bypasses, insecure crypto, or dangerous file/system access. "
            "Do not comment on style, readability, architecture, or generic code quality. "
            "Respond with valid JSON only using this schema: "
            '{"security_issues":[{"severity":"low|medium|high|critical","line":"str","issue":"str","fix":"str"}]}. '
            'Use "file:line" locations when possible. If there are no issues, return {"security_issues":[]}.'
        )
        user_prompt = f"Review this pull request diff for security issues only:\n\n{diff}"

        try:
            raw_output = await self._request_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            return self._normalize_output(raw_output)
        except Exception as exc:
            logger.exception("Security agent failed.")
            return {"security_issues": [], "error": str(exc)}

    @staticmethod
    def _normalize_output(raw_output: dict[str, Any]) -> dict[str, Any]:
        normalized_issues: list[dict[str, str]] = []
        for issue in raw_output.get("security_issues", []):
            if not isinstance(issue, dict):
                continue
            description = str(issue.get("issue", "")).strip()
            if not description:
                continue
            severity = str(issue.get("severity", "low")).lower()
            if severity not in {"low", "medium", "high", "critical"}:
                severity = "low"
            normalized_issues.append(
                {
                    "severity": severity,
                    "line": str(issue.get("line", "unknown")).strip() or "unknown",
                    "issue": description,
                    "fix": str(issue.get("fix", "")).strip() or "Review and harden this code path.",
                }
            )
        return {"security_issues": normalized_issues}
