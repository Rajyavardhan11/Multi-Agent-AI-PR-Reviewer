import logging
from typing import Any

from agents.base import OllamaJSONAgent

logger = logging.getLogger(__name__)


class SummaryAgent(OllamaJSONAgent):
    async def summarize_reviews(
        self,
        security_output: dict[str, Any] | None,
        refactor_output: dict[str, Any] | None,
    ) -> dict[str, Any]:
        security_output = security_output or {"security_issues": []}
        refactor_output = refactor_output or {"refactor_suggestions": []}
        security_issues = security_output.get("security_issues", [])
        refactor_suggestions = refactor_output.get("refactor_suggestions", [])

        system_prompt = (
            "You are the Summary Agent in a multi-agent pull request review system. "
            "Synthesize the provided agent outputs into a concise executive summary. "
            "Do not invent findings. Use only the supplied security issues and refactor suggestions. "
            "Respond with valid JSON only using this schema: "
            '{"overall_severity":"low|medium|high|critical","summary":"str","security_issues":[],"refactor_suggestions":[]}. '
            "The summary must be 2-3 sentences."
        )
        user_prompt = (
            "Summarize these agent outputs into one final review.\n\n"
            f"Security agent output:\n{security_output}\n\n"
            f"Refactor agent output:\n{refactor_output}\n\n"
            "Remember: if an agent output includes an error, reflect that the review is partial."
        )

        try:
            raw_output = await self._request_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            summary_text = str(raw_output.get("summary", "")).strip()
            if not summary_text:
                raise ValueError("Summary agent returned an empty summary.")

            return {
                "overall_severity": self._normalize_severity(
                    raw_output.get("overall_severity"),
                    security_issues,
                    refactor_suggestions,
                ),
                "summary": summary_text,
                "security_issues": security_issues,
                "refactor_suggestions": refactor_suggestions,
            }
        except Exception:
            logger.exception("Summary agent failed. Falling back to deterministic summary.")
            return self._fallback_summary(security_output, refactor_output)

    def _fallback_summary(
        self,
        security_output: dict[str, Any],
        refactor_output: dict[str, Any],
    ) -> dict[str, Any]:
        security_issues = security_output.get("security_issues", [])
        refactor_suggestions = refactor_output.get("refactor_suggestions", [])
        issues_count = len(security_issues)
        suggestions_count = len(refactor_suggestions)
        skipped_sections: list[str] = []

        if security_output.get("error"):
            skipped_sections.append("security")
        if refactor_output.get("error"):
            skipped_sections.append("refactor")

        summary_parts = [
            f"The automated review found {issues_count} security issue(s) and {suggestions_count} refactor suggestion(s)."
        ]
        if skipped_sections:
            skipped = " and ".join(skipped_sections)
            summary_parts.append(
                f"The {skipped} section could not be generated, so this is a partial review."
            )
        else:
            summary_parts.append("The overall severity is based on the most serious security finding.")

        return {
            "overall_severity": self._derive_overall_severity(
                security_issues,
                refactor_suggestions,
            ),
            "summary": " ".join(summary_parts),
            "security_issues": security_issues,
            "refactor_suggestions": refactor_suggestions,
        }

    def _normalize_severity(
        self,
        candidate: Any,
        security_issues: list[dict[str, Any]],
        refactor_suggestions: list[dict[str, Any]],
    ) -> str:
        normalized = str(candidate or "").lower().strip()
        if normalized in {"low", "medium", "high", "critical"}:
            return normalized
        return self._derive_overall_severity(security_issues, refactor_suggestions)

    @staticmethod
    def _derive_overall_severity(
        security_issues: list[dict[str, Any]],
        refactor_suggestions: list[dict[str, Any]],
    ) -> str:
        severities = {str(issue.get("severity", "")).lower() for issue in security_issues}
        if "critical" in severities:
            return "critical"
        if "high" in severities:
            return "high"
        if "medium" in severities:
            return "medium"
        if security_issues or len(refactor_suggestions) >= 5:
            return "low" if not refactor_suggestions else "medium"
        if refactor_suggestions:
            return "low"
        return "low"
