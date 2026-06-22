"""
Pipeline Orchestrator — coordinates the full video generation process.

Phase 1 & 2 flow:
  User Input → ScriptAgent → StoryboardAgent → AssetAgent → NarrationAgent → Composer

AssetAgent calls SiliconFlow (Wan2.2) to generate real video clips.
Falls back to coloured placeholders if SiliconFlow is unavailable.
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from src.config.settings import Config
from src.db.postgres import DatabaseManager, get_db
from src.pipeline.script_agent import ScriptAgent
from src.pipeline.storyboard_agent import StoryboardAgent
from src.pipeline.asset_agent import AssetAgent
from src.pipeline.narration_agent import NarrationAgent
from src.pipeline.composer import Composer

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """Top‑level coordinator for the AI video pipeline."""

    def __init__(
        self,
        cfg: Optional[Config] = None,
        db: Optional[DatabaseManager] = None,
    ) -> None:
        self._cfg = cfg or Config.get_instance()
        self._db = db  # optional — we connect to DB lazily

        # Sub‑agents (created on demand)
        self._script_agent: Optional[ScriptAgent] = None
        self._storyboard_agent: Optional[StoryboardAgent] = None
        self._asset_agent: Optional[AssetAgent] = None
        self._narration_agent: Optional[NarrationAgent] = None
        self._composer: Optional[Composer] = None

    # ── properties (lazy init) ─────────────────────────────────────────

    @property
    def script_agent(self) -> ScriptAgent:
        if self._script_agent is None:
            self._script_agent = ScriptAgent(self._cfg)
        return self._script_agent

    @property
    def storyboard_agent(self) -> StoryboardAgent:
        if self._storyboard_agent is None:
            self._storyboard_agent = StoryboardAgent(self._cfg)
        return self._storyboard_agent

    @property
    def asset_agent(self) -> AssetAgent:
        if self._asset_agent is None:
            self._asset_agent = AssetAgent(self._cfg)
        return self._asset_agent

    @property
    def narration_agent(self) -> NarrationAgent:
        if self._narration_agent is None:
            self._narration_agent = NarrationAgent(self._cfg)
        return self._narration_agent

    @property
    def composer(self) -> Composer:
        if self._composer is None:
            self._composer = Composer(self._cfg)
        return self._composer

    # ── pipeline stages ────────────────────────────────────────────────

    def run(
        self,
        topic: str,
        niche: str = "general",
        duration: int = 180,
        fmt: str = "youtube",
        output_dir: Optional[str] = None,
        video_clips: Optional[list[str]] = None,
        bg_music: Optional[str] = None,
        skip_video: bool = False,
    ) -> dict[str, Any]:
        """
        Execute the full pipeline (or as much as possible).

        Returns a result dict with all intermediate artefact paths.
        """
        # Resolve output directory
        out = Path(output_dir or self._cfg.paths.output_dir)
        project_dir = out / f"{datetime.now():%Y%m%d_%H%M%S}_{_slugify(topic)[:40]}"
        project_dir.mkdir(parents=True, exist_ok=True)

        result: dict[str, Any] = {
            "topic": topic,
            "niche": niche,
            "duration": duration,
            "format": fmt,
            "output_dir": str(project_dir),
            "status": "started",
        }

        # ── DB record ──────────────────────────────────────────────────
        project_id: Optional[int] = None
        try:
            db = self._db or get_db(self._cfg)
            project_id = db.create_project(topic, niche, duration, fmt)
            result["project_id"] = project_id
            logger.info("Pipeline started — project #%d: %s", project_id, topic)
        except Exception as exc:
            logger.warning("DB unavailable, continuing without persistence: %s", exc)

        # ── Stage 1: Script ────────────────────────────────────────────
        try:
            logger.info("── Stage 1: Script generation ──")
            script = self.script_agent.generate(topic, niche, duration)
            result["script"] = script

            # Save script JSON
            (project_dir / "script.json").write_text(
                json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8"
            )

            if project_id:
                db.update_project_status(project_id, "scripting", script_json=script)
        except Exception as exc:
            logger.error("Script generation failed: %s", exc)
            result["status"] = "failed"
            result["error"] = f"Script generation failed: {exc}"
            if project_id:
                db.update_project_status(project_id, "failed", error_message=str(exc))
            return result

        # ── Stage 2: Storyboard ────────────────────────────────────────
        try:
            logger.info("── Stage 2: Storyboard generation ──")
            storyboard = self.storyboard_agent.generate(script)
            result["storyboard"] = storyboard

            (project_dir / "storyboard.json").write_text(
                json.dumps(storyboard, ensure_ascii=False, indent=2), encoding="utf-8"
            )

            if project_id:
                db.update_project_status(project_id, "storyboarding", storyboard_json=storyboard)
                # Save individual scenes to DB
                for i, scene in enumerate(storyboard):
                    db.save_scene(
                        project_id=project_id,
                        scene_index=i + 1,
                        duration_sec=scene.get("duration", 15),
                        zh_narration=scene.get("zh_narration", ""),
                        en_narration=scene.get("en_narration", ""),
                        visual_prompt=scene.get("expanded_visual_prompt", scene.get("visual_prompt", "")),
                        shot_type=scene.get("shot_type", "medium"),
                    )
        except Exception as exc:
            logger.error("Storyboard generation failed: %s", exc)
            result["status"] = "failed"
            result["error"] = f"Storyboard generation failed: {exc}"
            if project_id:
                db.update_project_status(project_id, "failed", error_message=str(exc))
            return result

        # ── Stage 3: Audio (narration + subtitles) ─────────────────────
        try:
            logger.info("── Stage 3: Narration & subtitles ──")
            audio_result = self.narration_agent.generate_narration(
                storyboard, str(project_dir / "audio")
            )
            result["audio"] = audio_result

            sub_result = self.narration_agent.generate_subtitles(
                storyboard, str(project_dir / "subtitles")
            )
            result["subtitles"] = sub_result

            if project_id:
                db.update_project_status(project_id, "generating")
        except Exception as exc:
            logger.warning("Narration/subtitle generation failed (non‑fatal): %s", exc)
            result["warning"] = f"Narration generation failed: {exc}"

        # ── Stage 4: Video composition ─────────────────────────────────
        if not skip_video:
            try:
                logger.info("── Stage 4: Video composition ──")
                clips: list[str] = []
                if video_clips:
                    clips = video_clips
                else:
                    # 先尝试 SiliconFlow 生成真实视频片段
                    clips = self.asset_agent.generate_clips(
                        storyboard,
                        output_dir=str(project_dir / "clips"),
                    )
                    # 过滤失败的（空字符串）
                    clips = [c for c in clips if c]

                if not clips:
                    logger.warning("SiliconFlow clips unavailable — generating coloured placeholders.")
                    clips = self._generate_placeholder_clips(project_dir, storyboard)

                output_video = self.composer.compose(
                    video_clips=clips,
                    audio_path=result.get("audio", {}).get("audio_path", ""),
                    output_path=str(project_dir / "final.mp4"),
                    subtitle_en=result.get("subtitles", {}).get("srt_en"),
                    subtitle_zh=result.get("subtitles", {}).get("srt_zh"),
                    bg_music_path=bg_music,
                )
                result["video_path"] = str(output_video)

                # Quality check (Phase 2)
                quality = self.composer.check_quality(str(output_video))
                result["quality"] = quality

                if project_id:
                    db.update_project_status(project_id, "done", output_path=str(output_video))
            except Exception as exc:
                logger.error("Video composition failed: %s", exc)
                result["status"] = "failed"
                result["error"] = f"Video composition failed: {exc}"
                if project_id:
                    db.update_project_status(project_id, "failed", error_message=str(exc))
                return result
        else:
            logger.info("── Skip video (draft mode) ──")
            result["status"] = "draft_ready"
            if project_id:
                db.update_project_status(project_id, "done")

        result["status"] = "completed"
        logger.info("Pipeline complete — results in %s", project_dir)
        return result

    # ── draft mode (script + storyboard only) ─────────────────────────

    def draft(
        self,
        topic: str,
        niche: str = "general",
        duration: int = 180,
    ) -> dict[str, Any]:
        """Generate script + storyboard only (no video, no audio)."""
        out = Path(self._cfg.paths.output_dir)
        project_dir = out / f"draft_{datetime.now():%Y%m%d_%H%M%S}_{_slugify(topic)[:40]}"
        project_dir.mkdir(parents=True, exist_ok=True)

        script = self.script_agent.generate(topic, niche, duration)
        (project_dir / "script.json").write_text(
            json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        storyboard = self.storyboard_agent.generate(script)
        (project_dir / "storyboard.json").write_text(
            json.dumps(storyboard, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        return {
            "status": "draft_ready",
            "output_dir": str(project_dir),
            "script": script,
            "storyboard": storyboard,
        }

    # ── placeholder clips ───────────────────────────────────────────────

    SCENE_COLORS = [
        "#2C3E50", "#E74C3C", "#27AE60", "#F39C12",
        "#8E44AD", "#3498DB", "#E67E22", "#1ABC9C",
        "#C0392B", "#2980B9", "#D35400", "#16A085",
    ]

    @staticmethod
    def _generate_placeholder_clips(project_dir: Path, storyboard: list[dict]) -> list[str]:
        """
        Generate one coloured placeholder clip per scene, matching each
        scene's duration.  Colours vary so scene boundaries are visible.
        """
        import subprocess as sp

        clips_dir = project_dir / "clips"
        clips_dir.mkdir(parents=True, exist_ok=True)
        clip_paths: list[str] = []
        colors = PipelineOrchestrator.SCENE_COLORS

        for i, scene in enumerate(storyboard):
            duration = scene.get("duration", 5)
            if duration < 1:
                duration = 5
            color = colors[i % len(colors)]
            out = clips_dir / f"scene_{i + 1:02d}.mp4"

            # Use coloured background without drawtext (font issues on Windows)
            cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi",
                "-i", f"color=c={color}:s=1280x720:d={duration}:r=24",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-pix_fmt", "yuv420p",
                str(out),
            ]
            # capture_output as bytes to avoid GBK decode errors on Windows
            sp.run(cmd, capture_output=True, text=False)

            if out.exists():
                clip_paths.append(str(out))
                logger.debug("  Placeholder clip %02d: %ds %s", i + 1, duration, color)

        if not clip_paths:
            logger.warning("Failed to generate any placeholder clips.")
        return clip_paths


# ── helpers ───────────────────────────────────────────────────────────────

def _slugify(text: str) -> str:
    """A very simple slugify: lowercase, spaces→underscores, strip non‑alnum."""
    import re
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9一-鿿\s-]", "", text)
    text = re.sub(r"[\s-]+", "_", text)
    return text.strip("_")
