import hashlib
import hmac
import json
import logging
import os
from typing import Any

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from graph.review_graph import review_graph
from services.github import GitHubService

load_dotenv()

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/webhook")
async def github_webhook(request: Request) -> JSONResponse:
    raw_body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")
    event_type = request.headers.get("X-GitHub-Event", "")

    try:
        _verify_signature(raw_body, signature)
        payload = json.loads(raw_body.decode("utf-8"))
    except HTTPException:
        raise
    except json.JSONDecodeError as exc:
        logger.exception("Failed to decode webhook payload.")
        raise HTTPException(status_code=400, detail="Invalid JSON payload.") from exc

    if event_type != "pull_request":
        return JSONResponse({"status": "ignored", "reason": "Unsupported event type."})

    action = payload.get("action")
    if action not in {"opened", "synchronize"}:
        return JSONResponse({"status": "ignored", "reason": f"Unhandled action: {action}"})

    repo_info = payload.get("repository", {})
    pull_request = payload.get("pull_request", {})
    owner = repo_info.get("owner", {}).get("login")
    repo = repo_info.get("name")
    pr_number = payload.get("number") or pull_request.get("number")

    if not owner or not repo or not pr_number:
        logger.error("Webhook payload missing repository context.")
        raise HTTPException(status_code=400, detail="Webhook payload missing repository details.")

    github_service = GitHubService()

    try:
        diff = await github_service.get_pr_diff(owner, repo, int(pr_number))
        if len(diff) > 50000:
            await github_service.post_pr_comment(
                owner,
                repo,
                int(pr_number),
                "PR too large for automated review",
            )
            return JSONResponse({"status": "processed", "detail": "Large PR skipped."})

        review_state = await review_graph.ainvoke({"diff": diff})
        final_review = review_state.get("final_review", {})
        comment_body = format_github_comment(
            final_review=final_review,
            security_output=review_state.get("security_output"),
            refactor_output=review_state.get("refactor_output"),
        )
        await github_service.post_pr_comment(owner, repo, int(pr_number), comment_body)
        return JSONResponse({"status": "processed"})
    except Exception:
        logger.exception("Webhook processing failed.")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "detail": "Webhook processing failed."},
        )


def _verify_signature(raw_body: bytes, signature: str | None) -> None:
    secret = os.getenv("GITHUB_WEBHOOK_SECRET")
    if not secret:
        logger.error("GITHUB_WEBHOOK_SECRET is not configured.")
        raise HTTPException(status_code=500, detail="Webhook secret is not configured.")

    if not signature:
        raise HTTPException(status_code=401, detail="Missing webhook signature.")

    expected = "sha256=" + hmac.new(
        secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature.")


def format_github_comment(
    *,
    final_review: dict[str, Any] | None,
    security_output: dict[str, Any] | None,
    refactor_output: dict[str, Any] | None,
) -> str:
    final_review = final_review or {}
    security_output = security_output or {}
    refactor_output = refactor_output or {}

    severity_label = _severity_label(str(final_review.get("overall_severity", "low")))
    summary = str(final_review.get("summary", "No summary was generated.")).strip()

    lines = [
        "## 🤖 Multi-Agent AI Code Review",
        "",
        f"**Overall Severity:** {severity_label}",
        "",
        f"**Summary:** {summary}",
        "",
        "---",
        "",
    ]

    included_sections = 0

    if not security_output.get("error"):
        included_sections += 1
        lines.extend(_render_security_section(final_review.get("security_issues", [])))

    if not refactor_output.get("error"):
        included_sections += 1
        if included_sections > 1:
            lines.append("")
        lines.extend(_render_refactor_section(final_review.get("refactor_suggestions", [])))

    if included_sections == 0:
        lines.extend(
            [
                "No review sections could be generated because the upstream agents failed.",
                "",
            ]
        )

    lines.extend(
        [
            "",
            "---",
            "*Reviewed by Multi-Agent AI — Security Agent + Refactor Agent + Summary Agent*",
        ]
    )
    return "\n".join(lines).strip()


def _render_security_section(security_issues: list[dict[str, Any]]) -> list[str]:
    section = ["### 🔐 Security Issues"]
    if not security_issues:
        section.extend(["_No security issues found._"])
        return section

    section.extend(
        [
            "| Severity | Location | Issue | Fix |",
            "|----------|----------|-------|-----|",
        ]
    )
    for issue in security_issues:
        section.append(
            "| {severity} | {line} | {issue_text} | {fix} |".format(
                severity=_escape_cell(str(issue.get("severity", "low")).title()),
                line=_escape_cell(str(issue.get("line", "unknown"))),
                issue_text=_escape_cell(str(issue.get("issue", ""))),
                fix=_escape_cell(str(issue.get("fix", ""))),
            )
        )
    return section


def _render_refactor_section(refactor_suggestions: list[dict[str, Any]]) -> list[str]:
    section = ["### ♻️ Refactor Suggestions"]
    if not refactor_suggestions:
        section.extend(["_No refactor suggestions found._"])
        return section

    section.extend(
        [
            "| Location | Problem | Suggestion |",
            "|----------|---------|------------|",
        ]
    )
    for suggestion in refactor_suggestions:
        section.append(
            "| {line} | {problem} | {suggestion_text} |".format(
                line=_escape_cell(str(suggestion.get("line", "unknown"))),
                problem=_escape_cell(str(suggestion.get("problem", ""))),
                suggestion_text=_escape_cell(str(suggestion.get("suggestion", ""))),
            )
        )
    return section


def _severity_label(severity: str) -> str:
    normalized = severity.lower().strip()
    mapping = {
        "critical": "🔴 Critical",
        "high": "🟠 High",
        "medium": "🟡 Medium",
        "low": "🟢 Low",
    }
    return mapping.get(normalized, "🟢 Low")


def _escape_cell(value: str) -> str:
    return value.replace("\n", " ").replace("|", "\\|").strip()
