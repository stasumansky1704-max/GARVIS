"""Ollama runtime client for GARVIS inference layer.

Provides async HTTP communication with a local Ollama instance,
with retry logic, health checks, and proper connection management.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


class OllamaClient:
    """Async client for Ollama local inference API.

    Wraps Ollama's HTTP endpoints with aiohttp, providing:
    - Text generation via ``/api/generate``
    - Model listing via ``/api/tags``
    - Health checking via ``/api/tags``
    - Automatic retry with exponential backoff
    - Proper session lifecycle management
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        default_model: str = "llama3.1",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Lazy-initialize and return the aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=120),
            )
        return self._session

    async def generate(
        self,
        prompt: str,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> str:
        """Generate text via Ollama.

        POSTs to ``/api/generate`` with the prompt and options.
        Retries up to 3 times with exponential backoff on failure.

        Args:
            prompt: The text prompt to send.
            model: Model name override (defaults to ``default_model``).
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to predict (``num_predict``).
            **kwargs: Additional options forwarded to Ollama.

        Returns:
            The generated response text from Ollama's ``response`` field.

        Raises:
            ConnectionError: If Ollama is unreachable after all retries.
            TimeoutError: If the request times out repeatedly.
            RuntimeError: For HTTP errors or unexpected responses.
        """
        model_name = model or self.default_model
        url = f"{self.base_url}/api/generate"
        payload: dict[str, Any] = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                **kwargs,
            },
        }

        max_retries = 3
        last_exception: Exception | None = None

        for attempt in range(1, max_retries + 1):
            try:
                session = await self._get_session()
                async with session.post(url, json=payload) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        logger.warning(
                            "Ollama HTTP %s on attempt %s/%s: %s",
                            resp.status,
                            attempt,
                            max_retries,
                            body[:200],
                        )
                        if attempt == max_retries:
                            raise RuntimeError(
                                f"Ollama returned HTTP {resp.status} after "
                                f"{max_retries} retries: {body[:500]}"
                            )
                        await asyncio.sleep(2 ** attempt)
                        continue

                    data = await resp.json()
                    response_text = data.get("response", "").strip()
                    logger.debug(
                        "Ollama generate success (attempt %s/%s)",
                        attempt,
                        max_retries,
                    )
                    return response_text

            except aiohttp.ClientConnectionError as exc:
                last_exception = exc
                logger.warning(
                    "Ollama connection error attempt %s/%s: %s",
                    attempt,
                    max_retries,
                    exc,
                )
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)
            except asyncio.TimeoutError as exc:
                last_exception = exc
                logger.warning(
                    "Ollama timeout attempt %s/%s",
                    attempt,
                    max_retries,
                )
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)
            except Exception as exc:
                logger.error(
                    "Unexpected error calling Ollama: %s", exc, exc_info=True
                )
                raise

        # All retries exhausted
        if last_exception is not None:
            if isinstance(last_exception, aiohttp.ClientConnectionError):
                raise ConnectionError(
                    f"Ollama at {self.base_url} is unreachable after "
                    f"{max_retries} retries: {last_exception}"
                ) from last_exception
            if isinstance(last_exception, asyncio.TimeoutError):
                raise TimeoutError(
                    f"Ollama request timed out after {max_retries} retries"
                ) from last_exception

        raise RuntimeError(
            f"Ollama generation failed after {max_retries} retries"
        )

    async def list_models(self) -> list[str]:
        """List available models from Ollama.

        Returns:
            List of model names installed locally.

        Raises:
            ConnectionError: If Ollama is unreachable.
        """
        url = f"{self.base_url}/api/tags"
        try:
            session = await self._get_session()
            async with session.get(url) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise RuntimeError(
                        f"Ollama returned HTTP {resp.status}: {body[:500]}"
                    )
                data = await resp.json()
                models = data.get("models", [])
                return [m.get("name", "") for m in models if m.get("name")]
        except aiohttp.ClientConnectionError as exc:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.base_url}: {exc}"
            ) from exc

    async def health_check(self) -> bool:
        """Check if Ollama is reachable and responsive.

        Returns:
            True if Ollama responds with HTTP 200, False otherwise.
        """
        url = f"{self.base_url}/api/tags"
        try:
            session = await self._get_session()
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                return resp.status == 200
        except Exception:
            return False

    async def close(self) -> None:
        """Close the aiohttp session and release connections."""
        if self._session is not None and not self._session.closed:
            await self._session.close()
            self._session = None
            logger.debug("OllamaClient session closed")

    async def __aenter__(self) -> OllamaClient:
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit — ensures session cleanup."""
        await self.close()
