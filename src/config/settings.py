"""
StarVoyage AI Video Engine — Configuration Module
==================================================
Loads settings from config.yaml (or env var STARVOYAGE_CONFIG).
Supports environment variable overrides for sensitive fields.
"""

from __future__ import annotations

import os
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Default config path resolution
# ---------------------------------------------------------------------------
def _default_config_path() -> Path:
    """
    Resolve config.yaml by walking up from the current file.
    Look order:
      1. Project root (two levels up from src/config/settings.py)
      2. Current directory
    """
    here = Path(__file__).resolve().parent  # src/config/
    # project root = src/config/../../
    project_root = here.parent.parent
    candidates = [
        project_root / "config.yaml",
        Path.cwd() / "config.yaml",
        here / "config.yaml",
    ]
    for c in candidates:
        if c.exists():
            return c
    # Fallback — caller will raise if it doesn't exist
    return project_root / "config.yaml"


# ---------------------------------------------------------------------------
# Dataclass‑based config model
# ---------------------------------------------------------------------------
@dataclass
class PostgresConfig:
    host: str = "127.0.0.1"
    port: int = 5432
    database: str = "starvoyage"
    user: str = "postgres"
    password: str = "ABC123###"
    min_conn: int = 2
    max_conn: int = 10

    @property
    def dsn(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

    @property
    def dsn_async(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


@dataclass
class RedisConfig:
    host: str = "127.0.0.1"
    port: int = 6379
    db: int = 0
    password: str = "ABC123###"
    decode_responses: bool = True

    @property
    def dsn(self) -> str:
        return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"


@dataclass
class OpenRouterConfig:
    api_key: str = ""
    base_url: str = "https://openrouter.ai/api/v1"
    script_model: str = "deepseek/deepseek-chat-v3-0324"
    storyboard_model: str = "deepseek/deepseek-chat-v3-0324"
    max_tokens: int = 8192
    temperature: float = 0.7


@dataclass
class SiliconFlowConfig:
    api_key: str = ""
    base_url: str = "https://api.siliconflow.cn/v1"
    video_model: str = "Wan-AI/Wan2.2-T2V-A14B"
    image_model: str = "black-forest-labs/FLUX.1-dev"
    image_size: str = "1280x720"
    num_frames: int = 120  # 5s @ 24fps


@dataclass
class EdgeTTSConfig:
    voice: str = "en-US-AndrewNeural"
    rate: str = "-5%"
    volume: str = "+10%"


@dataclass
class PathsConfig:
    output_dir: str = "output"
    music_dir: str = "assets/music"
    fonts_dir: str = "assets/fonts"
    watermark_dir: str = "assets/watermark"
    template_dir: str = ""
    ffmpeg_path: str = ""  # custom path to ffmpeg.exe (Windows)


# ── 分辨率预设 ────────────────────────────────────────────────────────────
RESOLUTION_PRESETS = {
    "1080p": (1920, 1080),
    "720p":  (1280, 720),
    "480p":  (854, 480),
    "360p":  (640, 360),
    "short": (1080, 1920),   # 9:16 竖屏
    "square": (1080, 1080),  # 1:1 方形
}


def parse_resolution(value: str) -> tuple[int, int]:
    """解析分辨率，支持预设名或 WxH 格式。"""
    if value in RESOLUTION_PRESETS:
        return RESOLUTION_PRESETS[value]
    if "x" in value.lower():
        parts = value.lower().split("x")
        return int(parts[0]), int(parts[1])
    raise ValueError(
        f"Unknown resolution: {value}. "
        f"Use preset {list(RESOLUTION_PRESETS.keys())} or WxH."
    )


@dataclass
class ResolutionConfig:
    width: int = 1280
    height: int = 720
    fps: int = 24

    @property
    def preset(self) -> str:
        """返回最近的预设名，方便传给 SiliconFlow 等外部 API。"""
        for name, (w, h) in RESOLUTION_PRESETS.items():
            if (w, h) == (self.width, self.height):
                return name
        return f"{self.width}x{self.height}"


@dataclass
class Config:
    postgres: PostgresConfig = field(default_factory=PostgresConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    openrouter: OpenRouterConfig = field(default_factory=OpenRouterConfig)
    siliconflow: SiliconFlowConfig = field(default_factory=SiliconFlowConfig)
    edge_tts: EdgeTTSConfig = field(default_factory=EdgeTTSConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    resolution: ResolutionConfig = field(default_factory=ResolutionConfig)
    log_level: str = "INFO"
    max_scenes: int = 12
    default_scene_duration: int = 15

    # ── built‑in singleton ───────────────────────────────────────────
    _instance: Optional["Config"] = None

    @classmethod
    def get_instance(cls) -> "Config":
        if cls._instance is None:
            cls._instance = load_config()
        return cls._instance


# ---------------------------------------------------------------------------
# Load / reload logic
# ---------------------------------------------------------------------------
def load_config(config_path: Optional[str] = None) -> Config:
    """
    Load configuration from a YAML file.

    Resolution order:
      1. Explicit *config_path* argument
      2. ``STARVOYAGE_CONFIG`` environment variable
      3. ``config.yaml`` next to this file
    """

    resolved: Path
    if config_path:
        resolved = Path(config_path)
    elif env_path := os.environ.get("STARVOYAGE_CONFIG"):
        resolved = Path(env_path)
    else:
        resolved = _default_config_path()

    if not resolved.exists():
        raise FileNotFoundError(
            f"Configuration file not found at {resolved}. "
            "Create config.yaml or set STARVOYAGE_CONFIG env var."
        )

    with open(resolved, "r", encoding="utf-8") as fh:
        raw: dict = yaml.safe_load(fh) or {}

    cfg = Config()

    # ── postgres ──────────────────────────────────────────────────────
    pg = raw.get("postgres", {})
    cfg.postgres.host = pg.get("host", cfg.postgres.host)
    cfg.postgres.port = pg.get("port", cfg.postgres.port)
    cfg.postgres.database = pg.get("database", cfg.postgres.database)
    cfg.postgres.user = pg.get("user", cfg.postgres.user)
    cfg.postgres.password = pg.get("password", cfg.postgres.password)
    cfg.postgres.min_conn = pg.get("min_conn", cfg.postgres.min_conn)
    cfg.postgres.max_conn = pg.get("max_conn", cfg.postgres.max_conn)

    # ── redis ─────────────────────────────────────────────────────────
    rd = raw.get("redis", {})
    cfg.redis.host = rd.get("host", cfg.redis.host)
    cfg.redis.port = rd.get("port", cfg.redis.port)
    cfg.redis.db = rd.get("db", cfg.redis.db)
    cfg.redis.password = rd.get("password", cfg.redis.password)

    # ── openrouter ────────────────────────────────────────────────────
    or_ = raw.get("openrouter", {})
    cfg.openrouter.api_key = or_.get("api_key", "") or os.environ.get("OPENROUTER_API_KEY", "")
    cfg.openrouter.base_url = or_.get("base_url", cfg.openrouter.base_url)
    cfg.openrouter.script_model = or_.get("script_model", cfg.openrouter.script_model)
    cfg.openrouter.storyboard_model = or_.get("storyboard_model", cfg.openrouter.storyboard_model)
    cfg.openrouter.max_tokens = or_.get("max_tokens", cfg.openrouter.max_tokens)
    cfg.openrouter.temperature = or_.get("temperature", cfg.openrouter.temperature)

    # ── siliconflow ───────────────────────────────────────────────────
    sf = raw.get("siliconflow", {})
    cfg.siliconflow.api_key = sf.get("api_key", "") or os.environ.get("SILICONFLOW_API_KEY", "")
    cfg.siliconflow.base_url = sf.get("base_url", cfg.siliconflow.base_url)
    cfg.siliconflow.video_model = sf.get("video_model", cfg.siliconflow.video_model)
    cfg.siliconflow.image_model = sf.get("image_model", cfg.siliconflow.image_model)
    cfg.siliconflow.image_size = sf.get("image_size", cfg.siliconflow.image_size)
    cfg.siliconflow.num_frames = sf.get("num_frames", cfg.siliconflow.num_frames)

    # ── edge_tts ──────────────────────────────────────────────────────
    et = raw.get("edge_tts", {})
    cfg.edge_tts.voice = et.get("voice", cfg.edge_tts.voice)
    cfg.edge_tts.rate = et.get("rate", cfg.edge_tts.rate)
    cfg.edge_tts.volume = et.get("volume", cfg.edge_tts.volume)

    # ── paths ─────────────────────────────────────────────────────────
    pt = raw.get("paths", {})
    base = resolved.parent.resolve()
    cfg.paths.output_dir = str(base / pt.get("output_dir", cfg.paths.output_dir))
    cfg.paths.music_dir = str(base / pt.get("music_dir", cfg.paths.music_dir))
    cfg.paths.fonts_dir = str(base / pt.get("fonts_dir", cfg.paths.fonts_dir))
    cfg.paths.watermark_dir = str(base / pt.get("watermark_dir", cfg.paths.watermark_dir))
    cfg.paths.template_dir = str(base / pt.get("template_dir", "templates"))
    cfg.paths.ffmpeg_path = pt.get("ffmpeg_path", "")  # absolute path, not relative to base

    # ── resolution ─────────────────────────────────────────────────────
    res = raw.get("resolution", {})
    cfg.resolution.width = res.get("width", cfg.resolution.width)
    cfg.resolution.height = res.get("height", cfg.resolution.height)
    cfg.resolution.fps = res.get("fps", cfg.resolution.fps)

    # 兼容旧版 image_size 覆盖
    if "image_size" in raw.get("siliconflow", {}):
        si = raw["siliconflow"]["image_size"]
        if si and "x" in si:
            w, h = si.split("x")
            cfg.resolution.width = int(w)
            cfg.resolution.height = int(h)

    # ── misc ──────────────────────────────────────────────────────────
    cfg.log_level = raw.get("log_level", cfg.log_level)
    cfg.max_scenes = raw.get("max_scenes", cfg.max_scenes)
    cfg.default_scene_duration = raw.get("default_scene_duration", cfg.default_scene_duration)

    # Ensure output dir exists
    os.makedirs(cfg.paths.output_dir, exist_ok=True)

    return cfg
