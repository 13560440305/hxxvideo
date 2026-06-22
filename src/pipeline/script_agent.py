"""
Script Agent — Phase 1 / Stage 1

Uses an LLM (via OpenRouter) to generate a structured video script from a
user topic.  Supports niche templates (Phase 2) for tone & structure control.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

import yaml

from src.config.settings import Config
from src.models.llm import LLMClient

logger = logging.getLogger(__name__)

# Default system prompt (used when no niche template is loaded)
DEFAULT_SYSTEM_PROMPT = """You are a professional documentary script writer, specializing in showcasing Chinese culture to a global audience.

You must respond in valid JSON only, following the exact output schema requested."""

SCRIPT_USER_TEMPLATE = """Create a {duration}-second video script about the topic: 「{topic}」

Requirements:
- Divide into approximately {scene_count} scenes, each about {scene_duration} seconds
- Style: {tone}
- Each scene must include: Chinese narration, English narration, visual description keywords
- The first scene MUST have a strong visual hook
- Target audience: {audience}
{extra_instructions}

Output JSON structure:
{{
  "title": "Video title (English, catchy)",
  "description": "Channel description (English, under 150 chars)",
  "scenes": [
    {{
      "id": 1,
      "duration": 15,
      "zh_narration": "Chinese narration text",
      "en_narration": "English narration text",
      "visual_prompt": "cinematic shot description in English",
      "shot_type": "wide|medium|close|aerial"
    }}
  ]
}}

Respond with ONLY the JSON object, no other text."""


class ScriptAgent:
    """Generates structured video scripts via LLM."""

    def __init__(self, cfg: Config, llm: Optional[LLMClient] = None) -> None:
        self._cfg = cfg
        self._llm = llm or LLMClient(cfg)

    # ── public API ─────────────────────────────────────────────────────

    def generate(
        self,
        topic: str,
        niche: Optional[str] = None,
        duration: int = 180,
        audience: str = "global",
        extra_instructions: str = "",
    ) -> dict[str, Any]:
        """
        Generate a full script for the given *topic*.

        Returns the parsed JSON script dict.
        """
        # Load niche config if provided (Phase 2)
        tone = "warm, authentic, curious"
        extra = extra_instructions

        if niche:
            niche_cfg = self._load_niche(niche)
            if niche_cfg:
                tone = niche_cfg.get("script", {}).get("tone", tone)
                forbidden = niche_cfg.get("script", {}).get("forbidden_words", [])
                preferred = niche_cfg.get("script", {}).get("preferred_words", [])
                if forbidden:
                    extra += f"\n- Forbidden words: {', '.join(forbidden)}"
                if preferred:
                    extra += f"\n- Preferred words: {', '.join(preferred)}"

        scene_count = min(
            max(1, duration // self._cfg.default_scene_duration),
            self._cfg.max_scenes,
        )
        scene_duration = duration // scene_count

        system_prompt = self._build_system_prompt(niche)
        user_prompt = SCRIPT_USER_TEMPLATE.format(
            topic=topic,
            duration=duration,
            scene_count=scene_count,
            scene_duration=scene_duration,
            tone=tone,
            audience=audience,
            extra_instructions=extra,
        )

        logger.info("ScriptAgent: generating script for topic='%s' (%ds, %d scenes)",
                     topic, duration, scene_count)
        result = self._llm.chat_json(system_prompt, user_prompt)
        logger.info("ScriptAgent: script generated — title='%s' (%d scenes)",
                     result.get("title", "?"), len(result.get("scenes", [])))
        return result

    # ── internals ──────────────────────────────────────────────────────

    def _build_system_prompt(self, niche: Optional[str] = None) -> str:
        """Build the system prompt, optionally incorporating niche rules."""
        prompts_dir = Path(self._cfg.paths.template_dir) / "prompts"
        prompt_file = prompts_dir / "script_zh.txt"

        if prompt_file.exists():
            base = prompt_file.read_text(encoding="utf-8")
        else:
            base = DEFAULT_SYSTEM_PROMPT

        # If we had per‑niche system instructions we could append them here.
        return base

    def _load_niche(self, name: str) -> Optional[dict]:
        """Load a niche YAML config (Phase 2)."""
        niche_path = Path(self._cfg.paths.template_dir) / "niches" / f"{name}.yaml"
        if not niche_path.exists():
            logger.warning("Niche config not found: %s (falling back to defaults)", niche_path)
            return None
        with open(niche_path, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh)
