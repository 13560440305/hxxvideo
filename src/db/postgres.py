"""
PostgreSQL + pgvector database layer.

Provides a connection‑pooled DatabaseManager that auto‑creates the schema
(including the pgvector extension) on first connect.
"""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Generator, Optional

import psycopg2
import psycopg2.extras
import psycopg2.pool
from psycopg2.extensions import connection as PgConnection

from src.config.settings import Config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema DDL (run once on init)
# ---------------------------------------------------------------------------
SCHEMA_SQL = """
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Projects table
CREATE TABLE IF NOT EXISTS projects (
    id              SERIAL PRIMARY KEY,
    topic           TEXT NOT NULL,
    niche           TEXT NOT NULL DEFAULT 'general',
    duration        INT NOT NULL DEFAULT 180,
    format          TEXT NOT NULL DEFAULT 'youtube',
    status          TEXT NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft','scripting','storyboarding',
                                          'generating','composing','done','failed')),
    script_json     JSONB,
    storyboard_json JSONB,
    output_path     TEXT,
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Scenes (storyboard detail, stored separately for vector search)
CREATE TABLE IF NOT EXISTS scenes (
    id              SERIAL PRIMARY KEY,
    project_id      INT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    scene_index     INT NOT NULL,
    duration_sec    INT NOT NULL DEFAULT 15,
    zh_narration    TEXT,
    en_narration    TEXT,
    visual_prompt   TEXT,
    shot_type       TEXT,
    embedding       vector(1536),          -- pgvector col for similarity search
    asset_path      TEXT,                  -- path to generated video clip
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for vector similarity search
CREATE INDEX IF NOT EXISTS idx_scenes_embedding ON scenes
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Task log (for Celery / background task tracking)
CREATE TABLE IF NOT EXISTS tasks (
    id              SERIAL PRIMARY KEY,
    project_id      INT REFERENCES projects(id) ON DELETE SET NULL,
    task_type       TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','running','done','failed')),
    result          JSONB,
    error_message   TEXT,
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to projects
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'set_projects_updated_at'
    ) THEN
        CREATE TRIGGER set_projects_updated_at
            BEFORE UPDATE ON projects
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
END;
$$;
"""


# ---------------------------------------------------------------------------
# Database Manager
# ---------------------------------------------------------------------------
class DatabaseManager:
    """Simple thread‑safe connection pool wrapping psycopg2 + pgvector."""

    def __init__(self, cfg: Config) -> None:
        self._cfg = cfg
        self._pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None

    # ── connection lifecycle ───────────────────────────────────────────

    def connect(self) -> None:
        """Initialise the pool, create schema if needed."""
        if self._pool is not None:
            return

        pg = self._cfg.postgres
        logger.info(
            "Connecting to PostgreSQL at %s:%s/%s …",
            pg.host, pg.port, pg.database,
        )
        self._pool = psycopg2.pool.ThreadedConnectionPool(
            pg.min_conn,
            pg.max_conn,
            dsn=pg.dsn,
        )
        self._init_schema()
        logger.info("PostgreSQL pool ready (min=%d, max=%d).", pg.min_conn, pg.max_conn)

    def close(self) -> None:
        if self._pool is not None:
            self._pool.closeall()
            self._pool = None
            logger.info("PostgreSQL pool closed.")

    def _init_schema(self) -> None:
        """Run schema DDL in a separate connection."""
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(SCHEMA_SQL)
            conn.commit()
            logger.debug("Database schema initialised.")
        finally:
            self._pool.putconn(conn)

    # ── context manager for one conn per thread ────────────────────────

    @contextmanager
    def get_conn(self) -> Generator[PgConnection, None, None]:
        if self._pool is None:
            raise RuntimeError("DatabaseManager not connected. Call connect() first.")
        conn = self._pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.putconn(conn)

    # ── CRUD helpers ───────────────────────────────────────────────────

    def create_project(
        self,
        topic: str,
        niche: str = "general",
        duration: int = 180,
        fmt: str = "youtube",
    ) -> int:
        """Insert a new project row, return its id."""
        with self.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO projects (topic, niche, duration, format, status)
                       VALUES (%s, %s, %s, %s, 'draft')
                       RETURNING id""",
                    (topic, niche, duration, fmt),
                )
                return cur.fetchone()[0]

    def update_project_status(self, project_id: int, status: str, **extra) -> None:
        """Update project status and optional fields."""
        sets = ["status = %s"]
        params: list[Any] = [status]
        for col, val in extra.items():
            if col in ("script_json", "storyboard_json"):
                sets.append(f"{col} = %s::jsonb")
                params.append(json.dumps(val))
            else:
                sets.append(f"{col} = %s")
                params.append(val)
        params.append(project_id)
        with self.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE projects SET {', '.join(sets)} WHERE id = %s",
                    params,
                )

    def get_project(self, project_id: int) -> Optional[dict]:
        with self.get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM projects WHERE id = %s", (project_id,))
                row = cur.fetchone()
                return dict(row) if row else None

    def list_projects(self, limit: int = 20, offset: int = 0) -> list[dict]:
        with self.get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM projects ORDER BY created_at DESC LIMIT %s OFFSET %s",
                    (limit, offset),
                )
                return [dict(r) for r in cur.fetchall()]

    def save_scene(
        self,
        project_id: int,
        scene_index: int,
        duration_sec: int,
        zh_narration: str,
        en_narration: str,
        visual_prompt: str,
        shot_type: str,
        embedding: Optional[list[float]] = None,
    ) -> int:
        with self.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO scenes
                       (project_id, scene_index, duration_sec, zh_narration,
                        en_narration, visual_prompt, shot_type, embedding)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s::vector)
                       RETURNING id""",
                    (
                        project_id, scene_index, duration_sec,
                        zh_narration, en_narration, visual_prompt, shot_type,
                        embedding,
                    ),
                )
                return cur.fetchone()[0]

    def search_similar_scenes(
        self, embedding: list[float], top_k: int = 5
    ) -> list[dict]:
        with self.get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """SELECT s.*, p.topic, p.niche
                       FROM scenes s
                       JOIN projects p ON p.id = s.project_id
                       ORDER BY s.embedding <=> %s::vector
                       LIMIT %s""",
                    (embedding, top_k),
                )
                return [dict(r) for r in cur.fetchall()]

    # ── Phase 3: Web UI helpers ──────────────────────────────────────────

    def get_project_scenes(self, project_id: int) -> list[dict]:
        """Return all scenes for a project, ordered by scene_index."""
        with self.get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM scenes WHERE project_id = %s ORDER BY scene_index",
                    (project_id,),
                )
                return [dict(r) for r in cur.fetchall()]

    def delete_project_cascaded(self, project_id: int) -> None:
        """Delete a project and its cascaded scenes."""
        with self.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM projects WHERE id = %s", (project_id,))


# ---------------------------------------------------------------------------
# Module‑level singleton
# ---------------------------------------------------------------------------
_db_instance: Optional[DatabaseManager] = None


def get_db(cfg: Optional[Config] = None) -> DatabaseManager:
    """Return the singleton DatabaseManager, creating it if necessary."""
    global _db_instance
    if _db_instance is None:
        _db_instance = DatabaseManager(cfg or Config.get_instance())
        _db_instance.connect()
    return _db_instance
