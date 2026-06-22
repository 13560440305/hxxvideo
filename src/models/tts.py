"""
TTS unified interface.

Primary:  Microsoft Edge TTS (free, high quality)
Fallback: ShortGPT's TTS engine (if available)

The design doc specifies edge‑tts as the default.  We import and use
the ``edge_tts`` package directly.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

from src.config.settings import Config

logger = logging.getLogger(__name__)


class TTSClient:
    """Text‑to‑speech wrapper with Edge TTS as the primary engine."""

    def __init__(self, cfg: Config) -> None:
        et = cfg.edge_tts
        self.voice = et.voice
        self.rate = et.rate
        self.volume = et.volume

    # ── public API ─────────────────────────────────────────────────────

    def generate(self, text: str, output_path: str | Path) -> Path:
        """
        Generate an audio file from *text* and save to *output_path*.

        Returns the resolved output path.
        """
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        logger.info("TTS: generating %s → %s (voice=%s)", text[:60], output.name, self.voice)

        # edge‑tts is async; we run it synchronously here.
        asyncio.run(self._run_edge_tts(text, str(output)))

        if not output.exists():
            raise RuntimeError(f"TTS generation failed — output not found: {output}")
        logger.info("TTS complete — %s (%.1f KB)", output.name, output.stat().st_size / 1024)
        return output

    async def _run_edge_tts(self, text: str, output_path: str) -> None:
        """Internal coroutine that calls the edge_tts library."""
        # pylint: disable=import-outside-toplevel
        import edge_tts  # type: ignore[import-untyped]

        communicate = edge_tts.Communicate(
            text=text,
            voice=self.voice,
            rate=self.rate,
            volume=self.volume,
        )
        await communicate.save(output_path)


# ---------------------------------------------------------------------------
# Module‑level singleton
# ---------------------------------------------------------------------------
_tts_instance: Optional[TTSClient] = None


def get_tts(cfg: Optional[Config] = None) -> TTSClient:
    global _tts_instance
    if _tts_instance is None:
        _tts_instance = TTSClient(cfg or Config.get_instance())
    return _tts_instance
