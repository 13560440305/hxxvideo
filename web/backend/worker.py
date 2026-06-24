"""
Background pipeline runner.

Runs ``PipelineOrchestrator.run()`` in a daemon thread so the HTTP response
can return immediately while the pipeline processes in the background.
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

from src.config.settings import Config
from src.db.postgres import DatabaseManager
from src.pipeline.orchestrator import PipelineOrchestrator

logger = logging.getLogger(__name__)

# Track running tasks: project_id -> Thread
_active_tasks: dict[int, threading.Thread] = {}


def run_pipeline(
    project_id: int,
    topic: str,
    niche: str = "general",
    duration: int = 180,
    fmt: str = "youtube",
    bg_music: Optional[str] = None,
    skip_video: bool = False,
    regenerate: bool = False,
) -> None:
    """
    Start pipeline in a background thread.

    If ``regenerate=True``, loads the existing script from DB and resumes
    from storyboard stage (keeping the edited script).
    """

    def _run() -> None:
        try:
            cfg = Config.get_instance()
            db = DatabaseManager(cfg)
            db.connect()
            orch = PipelineOrchestrator(cfg, db)

            if regenerate:
                project = db.get_project(project_id)
                if not project:
                    logger.error("Regenerate failed: project %d not found", project_id)
                    return
                script = project.get("script_json")
                if not script:
                    logger.error("Regenerate failed: no script_json for project %d", project_id)
                    db.update_project_status(project_id, "failed",
                                             error_message="No script to regenerate from")
                    return

                storyboard = orch.storyboard_agent.generate(script)
                db.update_project_status(project_id, "storyboarding",
                                         storyboard_json=storyboard)
                # Save scenes
                for i, scene in enumerate(storyboard):
                    db.save_scene(
                        project_id=project_id,
                        scene_index=i + 1,
                        duration_sec=scene.get("duration", 15),
                        zh_narration=scene.get("zh_narration", ""),
                        en_narration=scene.get("en_narration", ""),
                        visual_prompt=scene.get("expanded_visual_prompt",
                                                  scene.get("visual_prompt", "")),
                        shot_type=scene.get("shot_type", "medium"),
                    )

                # Continue with remaining stages (asset, narration, compose)
                # We manually call the stages after storyboard
                project_dir = None  # will be resolved from output_path
                _continue_pipeline(orch, db, project_id, storyboard, project)
            else:
                result = orch.run(
                    topic=topic,
                    niche=niche,
                    duration=duration,
                    fmt=fmt,
                    bg_music=bg_music,
                    skip_video=skip_video,
                )
                logger.info("Pipeline completed for project %d: %s",
                            project_id, result.get("status"))

        except Exception as exc:
            logger.exception("Background pipeline failed for project %d", project_id)
            try:
                db = DatabaseManager(Config.get_instance())
                db.connect()
                db.update_project_status(project_id, "failed", error_message=str(exc))
            except Exception:
                logger.error("Failed to update error status for project %d", project_id)
        finally:
            _active_tasks.pop(project_id, None)

    thread = threading.Thread(
        target=_run,
        daemon=True,
        name=f"pipeline-{project_id}",
    )
    _active_tasks[project_id] = thread
    thread.start()


def _continue_pipeline(
    orch: PipelineOrchestrator,
    db: DatabaseManager,
    project_id: int,
    storyboard: list[dict],
    project: dict,
) -> None:
    """Continue pipeline from storyboard stage (for regenerate)."""
    from pathlib import Path

    cfg = Config.get_instance()
    output_path = project.get("output_path") or ""
    project_dir = Path(output_path).parent if output_path else Path(cfg.paths.output_dir)

    try:
        # Stage 3: Narration & subtitles
        db.update_project_status(project_id, "generating")
        audio_result = orch.narration_agent.generate_narration(
            storyboard, str(project_dir / "audio")
        )
        sub_result = orch.narration_agent.generate_subtitles(
            storyboard, str(project_dir / "subtitles")
        )

        # Stage 4: Video composition
        db.update_project_status(project_id, "composing")
        clips = orch.asset_agent.generate_clips(
            storyboard, output_dir=str(project_dir / "clips")
        )
        clips = [c for c in clips if c]
        if not clips:
            clips = PipelineOrchestrator._generate_placeholder_clips(
                Path(project_dir), storyboard
            )

        output_video = orch.composer.compose(
            video_clips=clips,
            audio_path=audio_result.get("audio_path", ""),
            output_path=str(project_dir / "final.mp4"),
            subtitle_en=sub_result.get("srt_en"),
            subtitle_zh=sub_result.get("srt_zh"),
            bg_music_path=None,
        )

        # Quality check
        orch.composer.check_quality(str(output_video))

        # Cover image
        try:
            title = project.get("script_json", {}).get("title", project.get("topic", ""))
            cover_path = orch.asset_agent.generate_cover(title, project.get("niche", "general"))
        except Exception as exc:
            logger.warning("Cover generation skipped: %s", exc)

        db.update_project_status(project_id, "done", output_path=str(output_video))

    except Exception as exc:
        logger.exception("Pipeline continuation failed for project %d", project_id)
        db.update_project_status(project_id, "failed", error_message=str(exc))


def get_active_task_count() -> int:
    """Return number of currently running pipeline tasks."""
    return len(_active_tasks)


def reap_stale_tasks() -> None:
    """On server startup, mark any 'running' tasks as failed."""
    try:
        db = DatabaseManager(Config.get_instance())
        db.connect()
        projects = db.list_projects(limit=100)
        for p in projects:
            if p["status"] in ("scripting", "storyboarding", "generating", "composing"):
                db.update_project_status(
                    p["id"], "failed",
                    error_message="Server restarted while task was running",
                )
                logger.info("Reaped stale task for project %d (%s)", p["id"], p["status"])
    except Exception as exc:
        logger.warning("Failed to reap stale tasks: %s", exc)
