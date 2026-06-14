from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

# Voice-mode profile (Phase 3 + identity grounding). Keeps GARVIS concise AND
# grounded as a real local assistant. Without explicit grounding, llama3.1 free-
# associates on the name "GARVIS"/"JARVIS" and roleplays a sci-fi AI (spaceships,
# missions, survival). This prompt establishes who the user is, what JARVIS is, and
# forbids the fictional setting. Applied ONLY when the command source is "voice";
# text/api callers keep the original open-ended behaviour.
VOICE_SYSTEM_PROMPT = (
    "You are JARVIS, Stas's local AI assistant running on his personal Predator "
    "computer. You are talking with Stas by voice. "
    "If asked who you are, answer exactly: I am JARVIS, your local AI assistant. "
    "Be direct, useful, calm, and practical - a real personal assistant, not a "
    "character. "
    "Reply in the SAME language Stas used: Hebrew if he speaks Hebrew, English if "
    "he speaks English. Match his language every time. "
    "Keep answers to 1-3 short, natural spoken sentences. No markdown, no lists, no "
    "essays. "
    "You are NOT on a spaceship, a mission, a game, or a survival scenario. Do not "
    "invent missions, crews, sectors, ships, the UNSC, the Normandy, or any "
    "fictional setting. Never call yourself GARVIS or any other name. Do not "
    "roleplay a sci-fi AI. Only roleplay if Stas explicitly asks you to. "
    "If you do not know something, say so plainly. "
    "If Stas explicitly asks for detail, you may give a longer answer."
)


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


class AgentExecutor:
    def __init__(self) -> None:
        self.ollama_host = os.getenv("OLLAMA_HOST", "http://garvis-ollama:11434").rstrip("/")
        self.model = os.getenv("OLLAMA_DEFAULT_MODEL", "llama3.1")
        # Safe, tunable performance knobs (all optional; sane defaults).
        self.keep_alive = os.getenv("OLLAMA_KEEP_ALIVE", "30m")          # avoid cold reloads
        self.voice_num_predict = _int_env("VOICE_NUM_PREDICT", 96)        # cap voice reply length
        self.num_ctx = _int_env("OLLAMA_NUM_CTX", 0)                      # 0 = leave model default

    async def health_check(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self.ollama_host}/api/tags", timeout=5) as response:
                return response.status == 200
        except Exception:
            return False

    def _build_payload(self, text: str, context: dict[str, Any] | None) -> dict[str, Any]:
        ctx = context or {}
        is_voice = str(ctx.get("source", "")) == "voice" or bool(ctx.get("voice"))

        options: dict[str, Any] = {}
        if self.num_ctx:
            options["num_ctx"] = self.num_ctx

        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": text,
            "stream": False,
            "keep_alive": self.keep_alive,   # Phase 2: prevent ~5s cold reloads
        }

        if is_voice:
            payload["system"] = VOICE_SYSTEM_PROMPT          # Phase 3: brevity
            options["num_predict"] = self.voice_num_predict  # Phase 2: bound reply length

        if options:
            payload["options"] = options
        return payload

    async def execute(self, text: str, context: dict[str, Any] | None = None) -> str:
        payload = self._build_payload(text, context)
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
