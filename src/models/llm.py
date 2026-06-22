"""
LLM unified interface — OpenRouter.

All LLM calls go through here.  The client is OpenAI‑compatible so it works
with any OpenRouter model or a local vLLM / Ollama endpoint.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

import requests

from src.config.settings import Config

logger = logging.getLogger(__name__)


class LLMClient:
    """Lightweight OpenRouter client (no OpenAI SDK dependency)."""

    def __init__(self, cfg: Config) -> None:
        oc = cfg.openrouter
        self.api_key = oc.api_key
        self.base_url = oc.base_url.rstrip("/")
        self.script_model = oc.script_model
        self.storyboard_model = oc.storyboard_model
        self.max_tokens = oc.max_tokens
        self.temperature = oc.temperature
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
        )

    # ── public API ─────────────────────────────────────────────────────

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: Optional[dict] = None,
    ) -> str:
        """
        Send a chat completion request and return the content string.

        If *response_format* is ``{"type": "json_object"}`` the model is
        forced to emit valid JSON.
        """
        payload: dict[str, Any] = {
            "model": model or self.script_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format

        logger.debug("LLM request — model=%s | system=%d chars | user=%d chars",
                     payload["model"], len(system_prompt), len(user_prompt))

        resp = self._session.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            timeout=120,
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"OpenRouter API error {resp.status_code}: {resp.text}"
            )

        content: str = resp.json()["choices"][0]["message"]["content"]
        logger.debug("LLM response — %d chars received.", len(content))
        return content

    def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> dict:
        """Convenience: parse the response as JSON, with robust fallback."""
        raw = self.chat(
            system_prompt,
            user_prompt,
            model=model,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        return self._parse_json_safe(raw)

    @staticmethod
    def _parse_json_safe(text: str) -> dict:
        """
        Parse JSON from LLM response, handling common wrapping patterns:
          - Markdown code blocks: ```json ... ```
          - Leading/trailing whitespace
          - `json` prefix
        """
        cleaned = text.strip()

        # Try direct parse first
        if cleaned:
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                pass

            # Try extracting from ```json ... ``` block
            m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", cleaned, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(1).strip())
                except json.JSONDecodeError:
                    pass

            # Try extracting from `json ... ` inline code
            m = re.search(r"`(?:json)?\s*(.*?)\s*`", cleaned, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(1).strip())
                except json.JSONDecodeError:
                    pass

            # Last resort: find first { ... } block
            brace_start = cleaned.find("{")
            brace_end = cleaned.rfind("}")
            if brace_start != -1 and brace_end > brace_start:
                try:
                    return json.loads(cleaned[brace_start : brace_end + 1])
                except json.JSONDecodeError:
                    pass

        logger.error("chat_json: failed to parse LLM response as JSON.\nRaw response:\n%s", text[:2000])
        raise ValueError(
            "LLM did not return valid JSON. "
            "Try a different model or check the raw response above. "
            f"Raw preview: {text[:200]}"
        )


# ---------------------------------------------------------------------------
# Module‑level singleton
# ---------------------------------------------------------------------------
_llm_instance: Optional[LLMClient] = None


def get_llm(cfg: Optional[Config] = None) -> LLMClient:
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = LLMClient(cfg or Config.get_instance())
    return _llm_instance
