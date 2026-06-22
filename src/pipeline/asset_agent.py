"""
Asset Agent — Phase 1/2 视频素材生成

调用 SiliconFlow API 为每个分镜场景生成真实视频片段。
支持并行提交 + 轮询，自动下载到本地。

=== 缓存机制 ===
基于 visual_prompt 的 MD5 哈希做缓存，同 prompt 不会重复调用 SiliconFlow。
缓存文件: output/._clip_cache.json
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import time
from pathlib import Path
from typing import Any, Optional

import requests

from src.config.settings import Config
from src.models.video import VideoClient

logger = logging.getLogger(__name__)

CACHE_FILE = "._clip_cache.json"


class AssetAgent:
    """使用 SiliconFlow 为每个分镜场景生成视频片段（带缓存）。"""

    def __init__(self, cfg: Config) -> None:
        self._cfg = cfg
        self._video_client = VideoClient(cfg)
        self._cache: dict[str, dict] = {}  # prompt_hash → {path, prompt}
        self._cache_path = Path(cfg.paths.output_dir) / CACHE_FILE
        self._load_cache()

    # ── 缓存管理 ───────────────────────────────────────────────────────────

    def _load_cache(self) -> None:
        if self._cache_path.exists():
            try:
                raw = self._cache_path.read_text(encoding="utf-8")
                self._cache = json.loads(raw)
                # 清理失效条目（文件已被删除的）
                stale = [k for k, v in self._cache.items() if not Path(v["path"]).exists()]
                for k in stale:
                    del self._cache[k]
                if stale:
                    logger.info("Clip cache: %d stale entries removed.", len(stale))
                logger.info(
                    "Clip cache loaded: %d entries (%s)",
                    len(self._cache),
                    self._cache_path,
                )
            except Exception as exc:
                logger.warning("Failed to load clip cache: %s", exc)
                self._cache = {}
        else:
            logger.debug("No clip cache found at %s", self._cache_path)

    def _save_cache(self) -> None:
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._cache_path.write_text(
                json.dumps(self._cache, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("Failed to save clip cache: %s", exc)

    def _cache_key(self, prompt: str) -> str:
        return hashlib.md5(prompt.encode("utf-8")).hexdigest()

    def _cache_get(self, prompt: str) -> Optional[str]:
        """Return cached clip path for *prompt*, or None."""
        key = self._cache_key(prompt)
        entry = self._cache.get(key)
        if entry and Path(entry["path"]).exists():
            return entry["path"]
        return None

    def _cache_put(self, prompt: str, clip_path: str) -> None:
        key = self._cache_key(prompt)
        self._cache[key] = {"path": clip_path, "prompt": prompt[:200]}
        self._save_cache()

    # ── 主接口 ─────────────────────────────────────────────────────────────

    def generate_clips(
        self,
        storyboard: list[dict[str, Any]],
        output_dir: str | Path = "output/clips",
    ) -> list[str]:
        """
        为分镜中的每个场景生成视频片段。

        优先从缓存复用，缓存缺失才调 SiliconFlow 花钱生成。

        Parameters
        ----------
        storyboard : list[dict]
            分镜列表，每个 scene 需包含 ``expanded_visual_prompt``（或 ``visual_prompt``）。
        output_dir : str | Path
            视频片段下载到本地的目录。

        Returns
        -------
        list[str]
            本地视频文件路径列表，与 storyboard 一一对应。
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        clip_paths: list[str] = []
        tasks: list[dict] = []

        # ── Step 1: 检查缓存 + 提交无缓存的任务 ─────────────────────────
        logger.info("AssetAgent: checking %d scenes (cache at %s) …",
                     len(storyboard), self._cache_path)

        for i, scene in enumerate(storyboard):
            prompt = (
                scene.get("expanded_visual_prompt")
                or scene.get("visual_prompt")
                or ""
            )
            if not prompt:
                logger.warning("  Scene %d: no visual prompt, skipping.", i + 1)
                clip_paths.append("")
                continue

            # 查缓存
            cached = self._cache_get(prompt)
            if cached:
                # 复制到当前输出目录
                dest = output_dir / f"scene_{i + 1:02d}.mp4"
                shutil.copy2(cached, dest)
                clip_paths.append(str(dest))
                logger.info("  Scene %d: CACHED ✅ (prompt hash %s) → %s",
                             i + 1, self._cache_key(prompt)[:12], dest.name)
                continue

            # 缓存缺失 → 提交 SiliconFlow
            try:
                req_id = self._video_client.submit_video(prompt)
                if req_id:
                    tasks.append({
                        "index": i,
                        "prompt": prompt,
                        "request_id": req_id,
                        "file_url": None,
                    })
                    clip_paths.append("")  # 占位，下载后填充
                    logger.info("  Scene %d: CACHE MISS → submitting (requestId=%s)",
                                 i + 1, req_id)
                else:
                    logger.warning("  Scene %d submit failed (empty requestId).", i + 1)
                    clip_paths.append("")
            except Exception as exc:
                logger.error("  Scene %d submit failed: %s", i + 1, exc)
                clip_paths.append("")

        if not tasks:
            # 所有场景都命中缓存
            done = sum(1 for p in clip_paths if p)
            logger.info("AssetAgent: all %d scenes served from cache.", done)
            return clip_paths

        # ── Step 2: 轮询所有任务直到完成 ───────────────────────────────
        logger.info("AssetAgent: polling %d new tasks …", len(tasks))
        pending = list(tasks)
        deadline = time.time() + 1800

        while pending and time.time() < deadline:
            for task in list(pending):
                try:
                    result = self._video_client.query_video(task["request_id"])
                    status = result.get("status", "")

                    if status == "Succeed":
                        videos = result.get("results", {}).get("videos", [])
                        file_url = videos[0].get("url", "") if videos else ""
                        if not file_url:
                            file_url = result.get("results", {}).get("video_url", "") or result.get("file_url", "")
                        if file_url:
                            task["file_url"] = file_url
                            pending.remove(task)
                            logger.info("  Scene %d done ✅", task["index"] + 1)
                        else:
                            logger.warning("  Scene %d succeeded but no URL.", task["index"] + 1)
                            pending.remove(task)

                    elif status in ("Failed", "Cancelled"):
                        reason = result.get("reason", "unknown")
                        logger.error("  Scene %d %s: %s", task["index"] + 1, status, reason)
                        pending.remove(task)

                except Exception as exc:
                    logger.warning("  Scene %d poll error: %s", task["index"] + 1, exc)

            if pending:
                time.sleep(5)

        if pending:
            logger.warning("AssetAgent: %d tasks still pending after deadline.", len(pending))

        # ── Step 3: 下载 + 写入缓存 ─────────────────────────────────────
        logger.info("AssetAgent: downloading %d clips …", len(tasks))
        for task in tasks:
            if not task["file_url"]:
                clip_paths.append("")
                continue

            ext = ".mp4"
            out_path = output_dir / f"scene_{task['index'] + 1:02d}{ext}"

            try:
                self._download(task["file_url"], out_path)
                clip_paths.append(str(out_path))
                # 写入缓存
                self._cache_put(task["prompt"], str(out_path.resolve()))
                logger.info("  Scene %d → %s (cached)", task["index"] + 1, out_path.name)
            except Exception as exc:
                logger.error("  Scene %d download failed: %s", task["index"] + 1, exc)
                clip_paths.append("")

        done = sum(1 for p in clip_paths if p)
        logger.info("AssetAgent: %d/%d clips ready.", done, len(storyboard))
        return clip_paths

    def generate_cover(self, title: str, niche: str = "general") -> str:
        """调用 SiliconFlow Flux 生成封面图。"""
        prompt_map = {
            "china_food": "Cinematic food photography, steaming hot pot, warm lighting, appetite appeal, top view",
            "china_city": "Aerial cityscape photography, modern city skyline at golden hour, misty morning",
            "china_tech": "Futuristic technology lab, blue neon lighting, clean lines, innovation concept",
            "travel": "Breathtaking natural landscape, misty mountains at sunrise, cinematic wide shot",
        }
        style = prompt_map.get(niche, "Cinematic travel photography, vibrant colors, professional lighting")
        full_prompt = f"{style}, title: {title}, clean composition, text overlay space"

        # 封面也走缓存
        cached = self._cache_get(full_prompt)
        if cached:
            logger.info("Cover image: CACHED ✅ → %s", cached)
            return cached

        logger.info("Generating cover image: niche=%s", niche)
        image_url = self._video_client.generate_image(full_prompt)

        out = Path(self._cfg.paths.output_dir) / "cover.jpg"
        self._download(image_url, out)
        self._cache_put(full_prompt, str(out.resolve()))
        logger.info("Cover image → %s (cached)", out)
        return str(out)

    # ── 内部工具 ────────────────────────────────────────────────────────

    @staticmethod
    def _download(url: str, dest: Path) -> None:
        """从 URL 下载文件到本地路径。"""
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(resp.content)
