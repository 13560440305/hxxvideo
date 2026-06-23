"""
StarVoyage CLI — argparse entry point for the video pipeline.

Usage
-----
  python -m src run --topic "..." --niche china_food --duration 180
  python -m src draft --topic "..." --niche china_city
  python -m src init-db
  python -m src list-projects
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Optional

from src.config.settings import Config, load_config, parse_resolution
from src.db.postgres import DatabaseManager
from src.db.redis_client import RedisClient
from src.pipeline.orchestrator import PipelineOrchestrator

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="starvoyage",
        description="StarVoyage AI Video Engine — AI‑driven video production pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python -m src run --topic \"成都火锅的百年历史\" --niche china_food --duration 180\n"
            "  python -m src draft --topic \"上海外滩的清晨\" --niche china_city\n"
            "  python -m src init-db\n"
        ),
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to config.yaml (default: config/config.yaml next to settings.py)",
    )
    parser.add_argument(
        "--log-level",
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Override log level from config",
    )
    parser.add_argument(
        "--no-db",
        action="store_true",
        help="Skip database connection (offline mode)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # ── run ────────────────────────────────────────────────────────────
    run_p = sub.add_parser("run", help="Run the full video generation pipeline")
    run_p.add_argument("--topic", required=True, help="Video topic (Chinese)")
    run_p.add_argument("--niche", default="general", help="Content niche template name")
    run_p.add_argument("--duration", type=int, default=180, help="Target video duration in seconds")
    run_p.add_argument("--format", default="youtube", choices=["youtube", "shorts"], help="Video format (影响分辨率和比例)")
    run_p.add_argument("--resolution", default=None,
                       help="画面分辨率: 预设名(720p/1080p/short/square) 或 WxH(1920x1080). "
                            "默认 720p(16:9), --format shorts 自动切为 9:16")
    run_p.add_argument("--output-dir", default=None, help="Custom output directory")
    run_p.add_argument("--bg-music", default=None, help="Path to background music file")
    run_p.add_argument("--skip-video", action="store_true", help="Skip final video composition (draft mode)")

    # ── draft ──────────────────────────────────────────────────────────
    draft_p = sub.add_parser("draft", help="Generate script + storyboard only (no video)")
    draft_p.add_argument("--topic", required=True, help="Video topic (Chinese)")
    draft_p.add_argument("--niche", default="general", help="Content niche template name")
    draft_p.add_argument("--duration", type=int, default=180, help="Target video duration in seconds")

    # ── init-db ────────────────────────────────────────────────────────
    sub.add_parser("init-db", help="Initialise database schema and exit")

    # ── list-projects ──────────────────────────────────────────────────
    list_p = sub.add_parser("list-projects", help="List recent projects from database")
    list_p.add_argument("--limit", type=int, default=10)
    list_p.add_argument("--json", action="store_true", help="Output as JSON")

    # ── project-info ───────────────────────────────────────────────────
    info_p = sub.add_parser("project-info", help="Show details for a project")
    info_p.add_argument("project_id", type=int, help="Project ID")
    info_p.add_argument("--json", action="store_true", help="Output as JSON")

    # ── check-quality ──────────────────────────────────────────────────
    qual_p = sub.add_parser("check-quality", help="Run quality check on a video file")
    qual_p.add_argument("video_path", help="Path to MP4 video file")

    # ── list-niches ────────────────────────────────────────────────────
    sub.add_parser("list-niches", help="List available niche templates")

    return parser


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def cmd_run(args: argparse.Namespace, cfg: Config, orch: PipelineOrchestrator) -> dict:
    """Execute the full pipeline."""
    # 处理分辨率
    if args.resolution:
        w, h = parse_resolution(args.resolution)
    elif args.format == "shorts":
        w, h = 1080, 1920  # 9:16 竖屏
    else:
        w, h = cfg.resolution.width, cfg.resolution.height

    cfg.resolution.width = w
    cfg.resolution.height = h

    return orch.run(
        topic=args.topic,
        niche=args.niche,
        duration=args.duration,
        fmt=args.format,
        output_dir=args.output_dir,
        bg_music=args.bg_music,
        skip_video=args.skip_video,
    )


def cmd_draft(args: argparse.Namespace, cfg: Config, orch: PipelineOrchestrator) -> dict:
    """Generate script + storyboard only."""
    return orch.draft(
        topic=args.topic,
        niche=args.niche,
        duration=args.duration,
    )


def cmd_init_db(args: argparse.Namespace, cfg: Config) -> dict:
    """Initialise / verify the database schema."""
    db = DatabaseManager(cfg)
    db.connect()
    db.close()
    return {"status": "ok", "message": "Database schema initialised."}


def cmd_list_projects(args: argparse.Namespace, cfg: Config) -> dict:
    """List recent projects."""
    db = DatabaseManager(cfg)
    db.connect()
    projects = db.list_projects(limit=args.limit)
    db.close()
    return {"projects": projects}


def cmd_project_info(args: argparse.Namespace, cfg: Config) -> dict:
    """Show a single project's details."""
    db = DatabaseManager(cfg)
    db.connect()
    project = db.get_project(args.project_id)
    db.close()
    if not project:
        return {"error": f"Project #{args.project_id} not found."}
    return {"project": project}


def cmd_check_quality(args: argparse.Namespace, cfg: Config) -> dict:
    """Run quality check on a video."""
    from src.pipeline.composer import Composer
    composer = Composer(cfg)
    return composer.check_quality(args.video_path)


def cmd_list_niches(args: argparse.Namespace, cfg: Config) -> dict:
    """List available niche templates."""
    niche_dir = Path(cfg.paths.template_dir) / "niches"
    if not niche_dir.exists():
        return {"niches": []}
    niches = []
    for f in sorted(niche_dir.glob("*.yaml")):
        import yaml
        with open(f, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        niches.append({
            "name": data.get("name", f.stem),
            "description": data.get("description", ""),
            "file": f.name,
        })
    return {"niches": niches}


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

def main(argv: Optional[list[str]] = None) -> int:
    # Force UTF-8 for stdout on Windows (emoji / CJK support)
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass

    parser = build_parser()
    args = parser.parse_args(argv)

    # ── Load config ────────────────────────────────────────────────────
    try:
        cfg = load_config(args.config)
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    # Override log level from CLI
    log_level = args.log_level or cfg.log_level
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # ── Dispatch ───────────────────────────────────────────────────────
    try:
        if args.command in ("init-db", "list-projects", "project-info"):
            result = COMMAND_MAP[args.command](args, cfg)
        elif args.command in ("check-quality", "list-niches"):
            result = COMMAND_MAP[args.command](args, cfg)
        elif args.command in ("run", "draft"):
            orch = PipelineOrchestrator(cfg, db=None if args.no_db else None)
            result = COMMAND_MAP[args.command](args, cfg, orch)
        else:
            result = {"error": f"Unknown command: {args.command}"}
    except Exception as exc:
        logger.exception("Command failed")
        result = {"error": str(exc)}

    # ── Output ─────────────────────────────────────────────────────────
    if args.command == "list-projects" and getattr(args, "json", False):
        _print_json(result)
    elif args.command == "project-info" and getattr(args, "json", False):
        _print_json(result)
    else:
        _print_human(result)

    if "error" in result:
        return 1
    return 0


COMMAND_MAP = {
    "run": cmd_run,
    "draft": cmd_draft,
    "init-db": cmd_init_db,
    "list-projects": cmd_list_projects,
    "project-info": cmd_project_info,
    "check-quality": cmd_check_quality,
    "list-niches": cmd_list_niches,
}


# ---------------------------------------------------------------------------
# Output formatting helpers
# ---------------------------------------------------------------------------

def _print_json(data: dict) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def _print_human(data: dict) -> None:
    if "error" in data:
        print(f"\n  ❌ {data['error']}\n")
        return

    status = data.get("status", "")
    if status == "completed":
        print(f"\n  ✅ Pipeline completed!")
        print(f"  📁 Output: {data.get('output_dir', '?')}")
        if "video_path" in data:
            print(f"  🎬 Video:  {data['video_path']}")
        if "audio" in data:
            print(f"  🔊 Audio:  {data['audio'].get('audio_path', '?')}")
        if "quality" in data:
            q = data["quality"]
            print(f"  📐 Quality: {q.get('width', '?')}×{q.get('height', '?')} "
                  f"@{q.get('fps', '?'):.1f}fps, {q.get('duration_s', 0):.1f}s")
        if "script" in data:
            scenes = data["script"].get("scenes", [])
            print(f"  📝 Script: \"{data['script'].get('title', '?')}\" ({len(scenes)} scenes)")
        print()

    elif status == "draft_ready":
        print(f"\n  📝 Draft ready!")
        print(f"  📁 Output: {data.get('output_dir', '?')}")
        if "script" in data:
            scenes = data["script"].get("scenes", [])
            print(f"  📝 Script: \"{data['script'].get('title', '?')}\" ({len(scenes)} scenes)")
            print(f"     → {data['output_dir']}/script.json")
            print(f"     → {data['output_dir']}/storyboard.json")
        print()

    elif status == "ok":
        print(f"\n  ✅ {data.get('message', 'OK')}\n")

    elif "projects" in data:
        projects = data["projects"]
        if not projects:
            print("\n  📭 No projects found.\n")
        else:
            print(f"\n  📋 Recent projects ({len(projects)}):\n")
            print(f"  {'ID':>4}  {'Status':<14}  {'Topic':<40}  {'Created':<20}")
            print(f"  {'─'*4}  {'─'*14}  {'─'*40}  {'─'*20}")
            for p in projects:
                print(f"  {p['id']:>4}  {p['status']:<14}  {p['topic']:<40}  {str(p['created_at'])[:19]}")
        print()

    elif "project" in data:
        p = data["project"]
        print(f"\n  Project #{p['id']}")
        print(f"  Topic:    {p['topic']}")
        print(f"  Niche:    {p['niche']}")
        print(f"  Duration: {p['duration']}s")
        print(f"  Format:   {p['format']}")
        print(f"  Status:   {p['status']}")
        print(f"  Created:  {p['created_at']}")
        if p.get("output_path"):
            print(f"  Output:   {p['output_path']}")
        if p.get("error_message"):
            print(f"  Error:    {p['error_message']}")
        print()

    elif "niches" in data:
        niches = data["niches"]
        if not niches:
            print("\n  📭 No niche templates found.\n")
        else:
            print(f"\n  Available niches ({len(niches)}):\n")
            for n in niches:
                print(f"  • {n['name']:<20} — {n['description']}")
        print()

    elif "width" in data:
        print(f"\n  📐 Quality Report:")
        print(f"  Resolution: {data.get('width', '?')}×{data.get('height', '?')}")
        print(f"  FPS:        {data.get('fps', 0):.2f}")
        print(f"  Duration:   {data.get('duration_s', 0):.1f}s")
        print(f"  Video:      {data.get('video_codec', '?')}")
        print(f"  Audio:      {data.get('audio_codec', '?')}")
        print(f"  Bitrate:    {data.get('bit_rate', 0):,} bps")
        print(f"  File size:  {data.get('file_size_bytes', 0):,} bytes")
        print()

    else:
        # Fallback: print as JSON
        _print_json(data)
