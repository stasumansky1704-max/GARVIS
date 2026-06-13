from __future__ import annotations

import json
import os
import urllib.request
from typing import Any


class AgentExecutor:
    def __init__(self) -> None:
        self.ollama_host = os.getenv("OLLAMA_HOST", "http://garvis-ollama:11434").rstrip("/")
        self.model = os.getenv("OLLAMA_DEFAULT_MODEL", "llama3.1")

    async def health_check(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self.ollama_host}/api/tags", timeout=5) as response:
                return response.status == 200
        except Exception:
            return False

    async def execute(self, text: str, context: dict[str, Any] | None = None) -> str:
        payload = {
            "model": self.model,
            "prompt": text,
            "stream": False,
        }

        data = json.dumps(payload).encode("utf-8")

        request = urllib.request.Request(
            f"{self.ollama_host}/api/generate",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=120) as response:
            raw = response.read().decode("utf-8")
            parsed = json.loads(raw)
            return parsed.get("response", "")
