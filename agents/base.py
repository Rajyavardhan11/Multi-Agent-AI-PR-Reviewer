import json
import os
import re
from typing import Any

import httpx


class OllamaJSONAgent:
    """Shared Ollama helper that requests JSON-only responses."""

    def __init__(
        self,
        *,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.model = model or os.getenv("OLLAMA_MODEL", "phi3:latest")
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        self.timeout = timeout

    async def _request_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()

        response_body = response.json()
        raw_text = response_body.get("message", {}).get("content", "")
        return self._extract_json(raw_text)

    @staticmethod
    def _extract_json(raw_text: str) -> dict[str, Any]:
        candidate = raw_text.strip()
        fenced_match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", candidate, re.DOTALL)
        if fenced_match:
            candidate = fenced_match.group(1).strip()

        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            start = candidate.find("{")
            end = candidate.rfind("}")
            if start == -1 or end == -1 or end < start:
                raise ValueError(f"Ollama response did not contain JSON: {raw_text}") from None
            return json.loads(candidate[start : end + 1])
