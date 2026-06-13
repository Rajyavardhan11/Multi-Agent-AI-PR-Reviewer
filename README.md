# Multi-Agent AI Code Review Agent

A production ready GitHub pull request review service that orchestrates multiple specialized AI agents with LangGraph:

- `Security Agent` reviews diffs only for security issues.
- `Refactor Agent` reviews diffs only for code quality and maintainability issues.
- `Summary Agent` combines the findings into one final GitHub PR comment.

The app exposes a FastAPI webhook that listens for GitHub `pull_request` events, fetches the PR diff, runs the review graph through a local Ollama model, and posts the final comment back to the PR.

## Architecture

```text
GitHub Pull Request Webhook
            |
            v
     FastAPI /webhook
            |
            v
      GitHubService
     (fetch PR diff)
            |
            v
         LangGraph
        +--------+
START ->|        |-> Security Agent -----+
        |        |                       |
        |        |-> Refactor Agent -----+--> Summary Agent --> GitHub comment
        +--------+
```

## Project Structure

```text
ai-code-review-agent/
├── agents/
│   ├── base.py
│   ├── refactor_agent.py
│   ├── security_agent.py
│   └── summary_agent.py
├── graph/
│   └── review_graph.py
├── routes/
│   └── webhook.py
├── services/
│   └── github.py
├── tests/
│   ├── conftest.py
│   ├── test_agents.py
│   ├── test_review_graph.py
│   └── test_webhook.py
├── .env.example
├── Dockerfile
├── main.py
├── pytest.ini
├── README.md
└── requirements.txt
```

## What Each Agent Does

### Security Agent

- Accepts the PR diff as input
- Looks only for security vulnerabilities
- Returns:

```json
{
  "security_issues": [
    {
      "severity": "high",
      "line": "app.py:42",
      "issue": "Unsanitized input reaches a SQL query.",
      "fix": "Use parameterized queries or an ORM binding API."
    }
  ]
}
```

### Refactor Agent

- Accepts the PR diff as input
- Looks only for maintainability and quality issues
- Returns:

```json
{
  "refactor_suggestions": [
    {
      "line": "service.py:18",
      "problem": "Duplicated request retry logic appears in multiple branches.",
      "suggestion": "Extract a shared retry helper with a clear error policy."
    }
  ]
}
```

### Summary Agent

- Accepts the outputs from the Security Agent and Refactor Agent
- Produces an overall severity and concise executive summary
- Returns:

```json
{
  "overall_severity": "medium",
  "summary": "The PR introduces one medium-severity security risk and two maintainability concerns. Address the SQL handling first, then simplify the duplicated error paths.",
  "security_issues": [],
  "refactor_suggestions": []
}
```

## Setup

1. Create and activate a Python 3.11 virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create your environment file:

```bash
cp .env.example .env
```

4. Make sure Ollama is installed and the local server is running:

```bash
ollama serve
```

5. Pull the local model:

```bash
ollama pull phi3:latest
```

6. Fill in:

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=phi3:latest
GITHUB_TOKEN=your_github_token
GITHUB_WEBHOOK_SECRET=your_webhook_secret
LOG_LEVEL=INFO
```

7. Run the server:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Registering the GitHub Webhook

1. Open your GitHub repository.
2. Go to `Settings` → `Webhooks` → `Add webhook`.
3. Set the payload URL to your deployed `/webhook` endpoint.
4. Set `Content type` to `application/json`.
5. Set the secret to the same value as `GITHUB_WEBHOOK_SECRET`.
6. Subscribe to `Pull requests` events.
7. Save the webhook.

The service responds to these actions:

- `pull_request.opened`
- `pull_request.synchronize`

## Comment Output

The bot posts a single GitHub timeline comment in this format:

```markdown
## 🤖 Multi-Agent AI Code Review

**Overall Severity:** 🔴 Critical / 🟠 High / 🟡 Medium / 🟢 Low

**Summary:** {summary}

---

### 🔐 Security Issues
| Severity | Location | Issue | Fix |
|----------|----------|-------|-----|
| ...      | ...      | ...   | ... |

### ♻️ Refactor Suggestions
| Location | Problem | Suggestion |
|----------|---------|------------|
| ...      | ...     | ...        |

---
*Reviewed by Multi-Agent AI — Security Agent + Refactor Agent + Summary Agent*
```

## Error Handling

- If the PR diff exceeds 50,000 characters, the bot posts `PR too large for automated review`.
- If one agent fails, the failed section is skipped and the remaining review is still posted.
- All errors are logged and the FastAPI server keeps running.

## Running Tests

```bash
pytest
```

The test suite covers:

- each agent independently
- the full LangGraph flow end to end
- the webhook route and signature validation
- mocked Ollama and GitHub API interactions

## Docker

Build:

```bash
docker build -t ai-code-review-agent .
```

Run:

```bash
docker run --rm -p 8000:8000 --env-file .env ai-code-review-agent
```

If the app runs in Docker and Ollama runs on your Mac host, set:

```env
OLLAMA_BASE_URL=http://host.docker.internal:11434
```
