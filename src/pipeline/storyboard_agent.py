"""
Storyboard Agent — Phase 1 / Stage 2

Takes the script from Stage 1 and enriches each scene with detailed visual
prompts, camera directions, and shot types suitable for video generation APIs.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from src.config.settings import Config
from src.models.llm import LLMClient

logger = logging.getLogger(__name__)

STORYBOARD_SYSTEM_PROMPT = """You are a professional film storyboard artist and director of photography. Given a video script, your job is to expand each scene with rich visual descriptions optimised for AI video generation models (such as Wan2.2, CogVideoX, or Midjourney).

For each scene you must provide:
- An expanded, highly detailed English visual prompt (cinematic, with lighting, camera movement, composition)
- Shot type (wide / medium / close / aerial / POV / tracking)
- Camera movement (static / pan / tilt / dolly / crane / handheld)
- Lighting mood (e.g. "golden hour warm", "neon cyberpunk", "soft diffused")
- Key visual elements to include

Respond in valid JSON only."""

STORYBOARD_USER_TEMPLATE = """Given the following video script, create a detailed storyboard.

Script Title: {title}
Script Description: {description}

Scenes:
{scenes_text}

For each scene (keep the same id), add:
1. ``expanded_visual_prompt`` — a detailed 1-2 sentence prompt optimised for AI video generation
2. ``camera_movement`` — camera motion direction
3. ``lighting`` — lighting description
4. ``key_elements`` — list of key visual elements to include
5. Keep the original ``duration``, ``zh_narration``, ``en_narration``, ``shot_type``

Output as a JSON object with a key "scenes" containing the array:
{{
  "scenes": [
    {{
      "id": 1,
      "duration": 15,
      "zh_narration": "...",
      "en_narration": "...",
      "shot_type": "wide",
      "expanded_visual_prompt": "...",
      "camera_movement": "...",
      "lighting": "...",
      "key_elements": ["..."]
    }}
  ]
}}

Respond with ONLY the JSON object, no other text."""


class StoryboardAgent:
    """Enriches a script with detailed visual storyboard data."""

    def __init__(self, cfg: Config, llm: Optional[LLMClient] = None) -> None:
        self._cfg = cfg
        self._llm = llm or LLMClient(cfg)

    def generate(self, script: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Take a script dict (from ScriptAgent) and produce a storyboard
        (list of enriched scene dicts).
        """
        scenes = script.get("scenes", [])
        scenes_text = json.dumps(scenes, ensure_ascii=False, indent=2)

        user_prompt = STORYBOARD_USER_TEMPLATE.format(
            title=script.get("title", ""),
            description=script.get("description", ""),
            scenes_text=scenes_text,
        )

        logger.info("StoryboardAgent: generating storyboard for %d scenes …", len(scenes))

        # Use chat_json for safe JSON parsing (handles markdown wrapping etc.)
        response = self._llm.chat_json(
            STORYBOARD_SYSTEM_PROMPT,
            user_prompt,
            model=self._cfg.openrouter.storyboard_model,
        )

        # Normalise: the response may be a list, or a dict with a "scenes"/"storyboard" key
        storyboard: list[dict[str, Any]]
        if isinstance(response, list):
            storyboard = response
        elif isinstance(response, dict):
            storyboard = (
                response.get("scenes")
                or response.get("storyboard")
                or [response]  # single scene wrapped in an object
            )
        else:
            storyboard = []

        # Filter out any non‑dict entries
        storyboard = [s for s in storyboard if isinstance(s, dict)]

        logger.info("StoryboardAgent: storyboard complete — %d scenes enriched.", len(storyboard))
        return storyboard
