"""
Narration Agent — Phase 1 / Stage 4

Generates TTS audio from the English narration text, then optionally
generates subtitle files (SRT) for bilingual subtitles (Phase 2).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Optional

from src.config.settings import Config
from src.models.tts import TTSClient

logger = logging.getLogger(__name__)


class NarrationAgent:
    """Handles TTS audio generation and subtitle production."""

    def __init__(self, cfg: Config, tts: Optional[TTSClient] = None) -> None:
        self._cfg = cfg
        self._tts = tts or TTSClient(cfg)

    # ── public API ─────────────────────────────────────────────────────

    def generate_narration(
        self,
        scenes: list[dict[str, Any]],
        output_dir: str | Path,
    ) -> dict[str, Any]:
        """
        Generate a single full audio file from the concatenated English
        narration of all scenes.

        Returns
        -------
        dict with keys:
          audio_path  — path to the generated WAV/MP3 file
          duration_ms — approximate duration in milliseconds
        """
        # Concatenate all English narration
        full_text = "\n\n".join(
            s.get("en_narration", "") for s in scenes if s.get("en_narration")
        )
        if not full_text.strip():
            raise ValueError("No English narration text found in scenes.")

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        audio_path = output_dir / "narration.mp3"

        self._tts.generate(full_text, audio_path)

        # Rough duration estimate: ~15 chars/sec for English speech
        char_count = len(full_text)
        est_duration_ms = int((char_count / 15) * 1000)

        return {
            "audio_path": str(audio_path),
            "duration_ms": est_duration_ms,
            "char_count": char_count,
        }

    # ── subtitle generation (Phase 2) ──────────────────────────────────

    def generate_subtitles(
        self,
        scenes: list[dict[str, Any]],
        output_dir: str | Path,
    ) -> dict[str, str]:
        """
        Generate bilingual subtitle files (SRT format).

        Returns
        -------
        dict with keys ``srt_en`` and ``srt_zh`` (file paths).
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Build rough timing based on scene duration ratios
        # (In production, use Whisper for accurate word‑level timing)
        total_duration = sum(s.get("duration", 15) for s in scenes)
        running = 0.0

        en_entries: list[str] = []
        zh_entries: list[str] = []

        for i, scene in enumerate(scenes, start=1):
            dur = scene.get("duration", 15)
            start_sec = running
            end_sec = running + dur
            en_text = scene.get("en_narration", "").strip()
            zh_text = scene.get("zh_narration", "").strip()

            if en_text:
                en_entries.append(self._format_srt(i, start_sec, end_sec, en_text))
            if zh_text:
                zh_entries.append(self._format_srt(i, start_sec, end_sec, zh_text))
            running = end_sec

        en_path = output_dir / "subtitles_en.srt"
        zh_path = output_dir / "subtitles_zh.srt"

        en_path.write_text("\n\n".join(en_entries) + "\n", encoding="utf-8")
        zh_path.write_text("\n\n".join(zh_entries) + "\n", encoding="utf-8")

        logger.info("Subtitles generated: EN=%s ZH=%s", en_path.name, zh_path.name)
        return {"srt_en": str(en_path), "srt_zh": str(zh_path)}

    @staticmethod
    def _format_srt(index: int, start_sec: float, end_sec: float, text: str) -> str:
        """Format one SRT entry."""
        def _ts(sec: float) -> str:
            h = int(sec // 3600)
            m = int((sec % 3600) // 60)
            s = int(sec % 60)
            ms = int((sec - int(sec)) * 1000)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

        return f"{index}\n{_ts(start_sec)} --> {_ts(end_sec)}\n{text}"
