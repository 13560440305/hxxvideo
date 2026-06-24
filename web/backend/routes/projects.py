"""
Project CRUD routes.
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from src.config.settings import parse_resolution
from src.pipeline.orchestrator import PipelineOrchestrator

from web.backend.deps import get_cfg, get_db, get_project_or_404
from web.backend.schemas.project import (
    CreateProjectRequest,
    NicheItem,
    ProjectResponse,
    ScriptUpdateRequest,
    StatusResponse,
)
from web.backend.worker import reap_stale_tasks, run_pipeline

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


# ── Projects ────────────────────────────────────────────────────────────────


@router.get("/projects")
def list_projects(limit: int = 20, offset: int = 0, status: Optional[str] = None):
    cfg = get_cfg()
    db = get_db()
    projects = db.list_projects(limit=limit, offset=offset)
    if status:
        projects = [p for p in projects if p["status"] == status]
    # Format datetimes to string
    for p in projects:
        for key in ("created_at", "updated_at"):
            if p.get(key):
                p[key] = str(p[key])
    return {"projects": projects, "total": len(projects)}


@router.post("/projects", status_code=201)
def create_project(body: CreateProjectRequest):
    cfg = get_cfg()
    db = get_db()

    # Handle resolution override
    if body.resolution:
        w, h = parse_resolution(body.resolution)
        cfg.resolution.width = w
        cfg.resolution.height = h
    elif body.fmt == "shorts":
        cfg.resolution.width = 1080
        cfg.resolution.height = 1920

    # Create DB record
    project_id = db.create_project(
        topic=body.topic,
        niche=body.niche,
        duration=body.duration,
        fmt=body.fmt,
    )

    # Start background pipeline
    run_pipeline(
        project_id=project_id,
        topic=body.topic,
        niche=body.niche,
        duration=body.duration,
        fmt=body.fmt,
        bg_music=body.bg_music,
        skip_video=body.skip_video,
    )

    return {"project_id": project_id, "status": "draft"}


@router.get("/projects/{project_id}")
def get_project(project_id: int):
    db = get_db()
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Cast datetime to string
    for key in ("created_at", "updated_at"):
        if project.get(key):
            project[key] = str(project[key])

    # Fetch scenes
    scenes = db.get_project_scenes(project_id)
    project["scenes"] = scenes

    # Parse JSON fields
    for key in ("script_json", "storyboard_json"):
        if project.get(key) and isinstance(project[key], str):
            try:
                project[key] = json.loads(project[key])
            except (json.JSONDecodeError, TypeError):
                pass

    return project


@router.get("/projects/{project_id}/status")
def get_project_status(project_id: int):
    db = get_db()
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return {
        "id": project["id"],
        "status": project["status"],
        "updated_at": str(project["updated_at"]) if project.get("updated_at") else "",
    }


@router.delete("/projects/{project_id}")
def delete_project(project_id: int):
    db = get_db()
    project = get_project_or_404(project_id)

    # Delete output files
    if project.get("output_path"):
        out_dir = Path(project["output_path"]).parent
        if out_dir.exists():
            shutil.rmtree(out_dir, ignore_errors=True)

    db.delete_project_cascaded(project_id)
    return {"ok": True}


# ── Script ──────────────────────────────────────────────────────────────────


@router.get("/projects/{project_id}/script")
def get_script(project_id: int):
    project = get_project_or_404(project_id)
    raw = project.get("script_json")
    if isinstance(raw, str):
        return json.loads(raw)
    return raw or {}


@router.put("/projects/{project_id}/script")
def update_script(project_id: int, body: ScriptUpdateRequest):
    db = get_db()
    project = get_project_or_404(project_id)

    # Build updated script JSON preserving title/description
    script = project.get("script_json") or {}
    if isinstance(script, str):
        script = json.loads(script)
    script["scenes"] = body.scenes

    db.update_project_status(project_id, project["status"], script_json=script)
    return {"ok": True}


@router.post("/projects/{project_id}/regenerate")
def regenerate(project_id: int):
    project = get_project_or_404(project_id)
    # 先把状态改成 regenerating，前端才能开始轮询
    db = get_db()
    db.update_project_status(project_id, "storyboarding",
                             storyboard_json=project.get("storyboard_json"))
    run_pipeline(
        project_id=project_id,
        topic=project["topic"],
        niche=project["niche"],
        duration=project["duration"],
        fmt=project["format"],
        regenerate=True,
    )
    return {"project_id": project_id, "status": "regenerating"}


# ── File serving ────────────────────────────────────────────────────────────


@router.get("/projects/{project_id}/video")
def get_video(project_id: int):
    project = get_project_or_404(project_id)
    path = project.get("output_path")
    if not path or not Path(path).exists():
        raise HTTPException(status_code=404, detail="Video not found or not yet generated")
    return FileResponse(path, media_type="video/mp4", filename="final.mp4")


@router.get("/projects/{project_id}/cover")
def get_cover(project_id: int):
    project = get_project_or_404(project_id)
    # Cover is stored at output parent dir
    out_dir = Path(project["output_path"]).parent if project.get("output_path") else None
    if out_dir:
        cover = out_dir / "cover.jpg"
        if cover.exists():
            return FileResponse(str(cover), media_type="image/jpeg", filename="cover.jpg")
    # Fallback: try output root
    cfg = get_cfg()
    default_cover = Path(cfg.paths.output_dir) / "cover.jpg"
    if default_cover.exists():
        return FileResponse(str(default_cover), media_type="image/jpeg", filename="cover.jpg")
    raise HTTPException(status_code=404, detail="Cover image not found")


# ── Niches ──────────────────────────────────────────────────────────────────


@router.get("/niches")
def list_niches():
    cfg = get_cfg()
    niche_dir = Path(cfg.paths.template_dir) / "niches"
    if not niche_dir.exists():
        return {"niches": []}

    import yaml

    niches = []
    for f in sorted(niche_dir.glob("*.yaml")):
        with open(f, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        niches.append({
            "name": data.get("name", f.stem),
            "description": data.get("description", ""),
            "file": f.name,
        })
    return {"niches": niches}
