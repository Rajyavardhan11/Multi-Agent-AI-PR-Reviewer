import os

import httpx


class GitHubService:
    def __init__(
        self,
        *,
        token: str | None = None,
        base_url: str = "https://api.github.com",
        api_version: str = "2026-03-10",
        timeout: float = 30.0,
    ) -> None:
        self.token = token or os.getenv("GITHUB_TOKEN")
        if not self.token:
            raise ValueError("GITHUB_TOKEN is not set.")
        self.base_url = base_url.rstrip("/")
        self.api_version = api_version
        self.timeout = timeout

    def _headers(self, accept: str = "application/vnd.github+json") -> dict[str, str]:
        return {
            "Accept": accept,
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": self.api_version,
        }

    async def get_pr_diff(self, owner: str, repo: str, pr_number: int) -> str:
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                url,
                headers=self._headers("application/vnd.github.diff"),
            )
            response.raise_for_status()
            return response.text

    async def post_pr_comment(self, owner: str, repo: str, pr_number: int, body: str) -> None:
        url = f"{self.base_url}/repos/{owner}/{repo}/issues/{pr_number}/comments"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                url,
                headers=self._headers(),
                json={"body": body},
            )
            response.raise_for_status()
