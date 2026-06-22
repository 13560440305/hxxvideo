"""
Video / Image generation unified interface — SiliconFlow.

Handles both text‑to‑video and text‑to‑image submissions via the
SiliconFlow asynchronous API (submit → query until ready).
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import requests

from src.config.settings import Config

logger = logging.getLogger(__name__)

# Default polling interval (seconds)
POLL_INTERVAL = 3.0
MAX_POLL_TIME = 300.0  # 5 minutes


class VideoClient:
    """SiliconFlow async API client for video & image generation."""

    def __init__(self, cfg: Config) -> None:
        sc = cfg.siliconflow
        self.api_key = sc.api_key
        self.base_url = sc.base_url.rstrip("/")
        self.video_model = sc.video_model
        self.image_model = sc.image_model
        self.image_size = sc.image_size
        self.num_frames = sc.num_frames
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
        )

    # ── video generation ───────────────────────────────────────────────

    def submit_video(self, prompt: str, negative_prompt: str = "") -> str:
        """
        Submit a text‑to‑video generation task.

        Returns a *request_id* that can be polled with ``query_video()``,
        or empty string on failure (insufficient balance, etc.).
        """
        url = f"{self.base_url}/video/submit"
        payload = {
            "model": self.video_model,
            "prompt": prompt,
            "negative_prompt": negative_prompt or "low quality, blurry, watermark",
            "num_frames": self.num_frames,
            "resolution": self.image_size,
        }
        logger.info("Submitting video: model=%s prompt=%.60s…", self.video_model, prompt)
        resp = self._session.post(url, json=payload, timeout=60)
        if resp.status_code != 200:
            err = f"SiliconFlow submit error {resp.status_code}: {resp.text[:200]}"
            if resp.status_code == 403:
                logger.warning("%s — insufficient balance, will use placeholder clips.", err)
            else:
                logger.error(err)
            return ""
        data = resp.json()
        request_id: str = data.get("requestId", "")
        if not request_id:
            logger.warning("SiliconFlow submit returned no requestId: %s", data)
            return ""
        logger.info("Video task submitted — requestId=%s", request_id)
        return request_id

    def query_video(self, request_id: str) -> dict:
        """
        Poll for completion via ``POST /v1/video/status``.

        Returns the result dict with keys:
          ``status`` (Succeed/InQueue/InProgress/Failed),
          ``results.videos[].url`` (when done),
          ``reason`` (if failed).
        """
        url = f"{self.base_url}/video/status"
        resp = self._session.post(url, json={"requestId": request_id}, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(f"SiliconFlow video query error {resp.status_code}: {resp.text}")
        return resp.json()

    def generate_video(
        self, prompt: str, negative_prompt: str = "", poll: bool = True
    ) -> str:
        """
        Submit a video task and optionally poll until done.

        Returns the file URL of the generated video clip.
        """
        req_id = self.submit_video(prompt, negative_prompt)
        if not req_id:
            return ""  # submit failed, caller should fall back
        if not poll:
            return req_id  # caller will poll later

        deadline = time.time() + MAX_POLL_TIME
        while time.time() < deadline:
            result = self.query_video(req_id)
            status = result.get("status", "")
            logger.debug("Video task %s — status=%s", req_id, status)
            if status == "Succeed":
                videos = result.get("results", {}).get("videos", [])
                file_url = videos[0].get("url", "") if videos else ""
                if not file_url:
                    # fallback to flat result format
                    file_url = result.get("results", {}).get("video_url", "") or result.get("file_url", "")
                if not file_url:
                    raise RuntimeError(f"Video task succeeded but no file_url: {result}")
                logger.info("Video generation complete — %s", file_url)
                return file_url
            if status in ("Failed", "Cancelled"):
                raise RuntimeError(f"Video task {status}: {result.get('reason', 'unknown')}")
            if status in ("Submitted", "InQueue", "InProgress", "Processing"):
                time.sleep(POLL_INTERVAL)
            else:
                logger.warning("Unknown status %s — retrying …", status)
                time.sleep(POLL_INTERVAL)

        raise TimeoutError(f"Video task {req_id} did not complete within {MAX_POLL_TIME}s")

    # ── image generation ───────────────────────────────────────────────

    def generate_image(self, prompt: str, negative_prompt: str = "") -> str:
        """
        Generate a single image via SiliconFlow (synchronous API).

        Returns the image URL.
        """
        url = f"{self.base_url}/images/generations"
        payload = {
            "model": self.image_model,
            "prompt": prompt,
            "negative_prompt": negative_prompt or "low quality, blurry, watermark, text",
            "size": self.image_size,
            "n": 1,
        }
        logger.info("Generating image: prompt=%.60s…", prompt)
        resp = self._session.post(url, json=payload, timeout=120)
        if resp.status_code != 200:
            raise RuntimeError(f"SiliconFlow image error {resp.status_code}: {resp.text}")
        data = resp.json()
        image_url: str = data["data"][0]["url"]
        logger.info("Image generated — %s", image_url)
        return image_url


# ---------------------------------------------------------------------------
# Module‑level singleton
# ---------------------------------------------------------------------------
_video_instance: Optional[VideoClient] = None


def get_video_client(cfg: Optional[Config] = None) -> VideoClient:
    global _video_instance
    if _video_instance is None:
        _video_instance = VideoClient(cfg or Config.get_instance())
    return _video_instance
