"""
FastAPI dependency injection — shared resources.
"""

from __future__ import annotations

from typing import Optional

from fastapi import HTTPException

from src.config.settings import Config, load_config
from src.db.postgres import DatabaseManager


def get_cfg() -> Config:
    """Return the singleton Config."""
    return Config.get_instance()


_db: Optional[DatabaseManager] = None


def get_db() -> DatabaseManager:
    """Return the singleton DatabaseManager (lazy init)."""
    global _db
    if _db is None:
        _db = DatabaseManager(get_cfg())
        _db.connect()
    return _db


def get_project_or_404(project_id: int) -> dict:
    """Helper: fetch project by ID or raise 404."""
    db = get_db()
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project #{project_id} not found")
    return project
