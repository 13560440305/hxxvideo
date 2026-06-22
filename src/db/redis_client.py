"""
Redis client wrapper.

Provides a connection pool to the local Redis instance, used for:
  • Task queue (Celery / RQ replacement for simple CLI mode)
  • Caching LLM responses
  • Rate limiting
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import redis

from src.config.settings import Config

logger = logging.getLogger(__name__)


class RedisClient:
    """Thin wrapper around ``redis.Redis`` with convenience helpers."""

    def __init__(self, cfg: Config) -> None:
        rd = cfg.redis
        self._client = redis.Redis(
            host=rd.host,
            port=rd.port,
            db=rd.db,
            password=rd.password or None,
            decode_responses=rd.decode_responses,
        )
        self._check_connection()

    def _check_connection(self) -> None:
        try:
            self._client.ping()
            logger.info("Redis connected at %s:%s/%d.", self._client.connection_pool.connection_kwargs.get("host"),
                        self._client.connection_pool.connection_kwargs.get("port"),
                        self._client.connection_pool.connection_kwargs.get("db", 0))
        except redis.ConnectionError as exc:
            logger.warning("Redis not available: %s — caching disabled.", exc)

    @property
    def client(self) -> redis.Redis:
        return self._client

    # ── generic JSON cache ─────────────────────────────────────────────

    def cache_get(self, key: str) -> Optional[Any]:
        try:
            raw = self._client.get(key)
            return json.loads(raw) if raw else None
        except Exception:
            return None

    def cache_set(self, key: str, value: Any, ttl: int = 3600) -> None:
        try:
            self._client.setex(key, ttl, json.dumps(value, ensure_ascii=False))
        except Exception as exc:
            logger.debug("Redis cache_set failed: %s", exc)

    def cache_delete(self, key: str) -> None:
        try:
            self._client.delete(key)
        except Exception:
            pass

    # ── task queue helpers (simple FIFO) ────────────────────────────────

    def enqueue(self, queue: str, payload: dict) -> None:
        self._client.rpush(queue, json.dumps(payload, ensure_ascii=False))

    def dequeue(self, queue: str, timeout: int = 0) -> Optional[dict]:
        result = self._client.blpop(queue, timeout=timeout)
        if result:
            _, data = result
            return json.loads(data)
        return None

    def queue_length(self, queue: str) -> int:
        return self._client.llen(queue)

    # ── lifecycle ───────────────────────────────────────────────────────

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Module‑level singleton
# ---------------------------------------------------------------------------
_redis_instance: Optional[RedisClient] = None


def get_redis(cfg: Optional[Config] = None) -> Optional[RedisClient]:
    """Return the singleton RedisClient (or None if unavailable)."""
    global _redis_instance
    if _redis_instance is None:
        try:
            _redis_instance = RedisClient(cfg or Config.get_instance())
        except Exception as exc:
            logger.warning("Failed to initialise Redis: %s", exc)
            return None
    return _redis_instance
