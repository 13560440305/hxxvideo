"""
StarVoyage Web API — FastAPI application entry point.

Usage:
    uvicorn web.backend.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from web.backend.routes.projects import router as projects_router
from web.backend.worker import reap_stale_tasks

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: reap stale tasks. Shutdown: cleanup."""
    logger.info("StarVoyage API starting …")
    try:
        reap_stale_tasks()
    except Exception as exc:
        logger.warning("Startup task reap skipped: %s", exc)
    yield
    logger.info("StarVoyage API shutting down …")


app = FastAPI(
    title="StarVoyage Video Engine API",
    version="0.3.0",
    lifespan=lifespan,
)

# CORS for Next.js dev server (localhost:3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects_router, prefix="/api")
