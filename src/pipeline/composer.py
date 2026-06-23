"""
Composer — Phase 1 / Stage 5

Uses FFmpeg to assemble the final video:
  1. Concatenate video clips
  2. Scale / normalise to consistent resolution and frame rate
  3. Add audio (narration + optional background music)
  4. Burn bilingual subtitles
  5. Output final MP4
"""

from __future__ import annotations

import json
import logging
import subprocess as sp
from pathlib import Path
from typing import Any, Optional

from src.config.settings import Config

logger = logging.getLogger(__name__)

TARGET_WIDTH = 1280
TARGET_HEIGHT = 720
TARGET_FPS = 24


class Composer:
    """FFmpeg‑based video composer."""

    def __init__(self, cfg: Config) -> None:
        self._cfg = cfg
        # Use configured ffmpeg path, fall back to PATH
        self._ffmpeg = cfg.paths.ffmpeg_path or "ffmpeg"
        self._ffprobe = cfg.paths.ffmpeg_path.replace("ffmpeg.exe", "ffprobe.exe") \
            if "ffmpeg.exe" in cfg.paths.ffmpeg_path else "ffprobe"
        self._target_w = cfg.resolution.width
        self._target_h = cfg.resolution.height
        self._target_fps = cfg.resolution.fps

    # ── public API ─────────────────────────────────────────────────────

    def compose(
        self,
        video_clips: list[str],
        audio_path: str,
        output_path: str | Path,
        subtitle_en: Optional[str] = None,
        subtitle_zh: Optional[str] = None,
        bg_music_path: Optional[str] = None,
        bg_music_volume: float = 0.15,
    ) -> Path:
        """
        Assemble the final video.

        Works in stages to avoid complex single‑filter‑graph crashes:
          1. Concatenate clips (concat demuxer)
          2. Scale & normalise resolution / fps
          3. Add audio (narration ± bg music)
          4. Burn subtitles
          5. Final encode
        """
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        # ── Step 1: concatenate ─────────────────────────────────────────
        concat_path = output.parent / "._concat.mp4"
        self._concat_clips(video_clips, concat_path)

        # ── Step 2: normalise resolution & fps ──────────────────────────
        scaled_path = output.parent / "._scaled.mp4"
        self._normalise(concat_path, scaled_path)
        concat_path.unlink(missing_ok=True)

        # ── Step 3: add audio (narration ± bg music) ───────────────────
        with_audio_path = output.parent / "._with_audio.mp4"
        self._add_audio(scaled_path, audio_path, with_audio_path, bg_music_path, bg_music_volume)
        scaled_path.unlink(missing_ok=True)

        # ── Step 4: burn subtitles & final encode ──────────────────────
        self._burn_subtitles(with_audio_path, output, subtitle_en, subtitle_zh)
        with_audio_path.unlink(missing_ok=True)

        logger.info("Composer: final video → %s", output)
        return output

    # ── internal stages ─────────────────────────────────────────────────

    def _concat_clips(self, clips: list[str], output: Path) -> None:
        """Concatenate video clips via the concat demuxer."""
        if not clips:
            raise ValueError("No video clips to concatenate.")

        # Use absolute paths so concat demuxer resolves correctly
        list_path = output.parent / f"._concat_list_{output.stem}.txt"
        with open(list_path, "w", encoding="utf-8") as fh:
            for clip in clips:
                abs_path = Path(clip).resolve()
                fh.write(f"file '{abs_path}'\n")

        self._run([
            self._ffmpeg, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_path),
            "-c", "copy",
            str(output),
        ])
        list_path.unlink(missing_ok=True)

    def _normalise(self, input_path: Path, output_path: Path) -> None:
        """Scale + crop to fill target resolution (cover mode, no black bars)."""
        vf = (
            f"scale={self._target_w}:{self._target_h}:"
            f"force_original_aspect_ratio=increase,"
            f"crop={self._target_w}:{self._target_h}"
        )
        self._run([
            self._ffmpeg, "-y",
            "-i", str(input_path),
            "-vf", vf,
            "-r", str(self._target_fps),
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-an",  # drop audio from concat (we'll add narration separately)
            str(output_path),
        ])

    def _add_audio(
        self,
        video_path: Path,
        audio_path: str,
        output_path: Path,
        bg_music_path: Optional[str] = None,
        bg_music_volume: float = 0.15,
    ) -> None:
        """Mix narration audio (± background music) with video."""
        has_bg = bg_music_path and Path(bg_music_path).exists()

        if has_bg:
            # Shorten narration to match video duration if needed
            self._run([
                self._ffmpeg, "-y",
                "-i", str(video_path),
                "-i", audio_path,
                "-i", str(bg_music_path),
                "-filter_complex",
                f"[1:a]adelay=1s[a1];[2:a]volume={bg_music_volume}[bg];"
                f"[a1][bg]amix=inputs=2:duration=first:dropout_transition=2[aout]",
                "-map", "0:v:0",
                "-map", "[aout]",
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "192k",
                "-shortest",
                str(output_path),
            ])
        else:
            self._run([
                self._ffmpeg, "-y",
                "-i", str(video_path),
                "-i", audio_path,
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "192k",
                "-shortest",
                str(output_path),
            ])

    def _burn_subtitles(
        self,
        input_path: Path,
        output_path: Path,
        subtitle_en: Optional[str] = None,
        subtitle_zh: Optional[str] = None,
    ) -> None:
        """Burn bilingual subtitles into video and output final file."""
        has_en = subtitle_en and Path(subtitle_en).exists()
        has_zh = subtitle_zh and Path(subtitle_zh).exists()

        if not has_en and not has_zh:
            # Just copy
            self._run([
                self._ffmpeg, "-y",
                "-i", str(input_path),
                "-c", "copy",
                str(output_path),
            ])
            return

        # Build subtitle filter graph
        # Merge both SRTs into one temp file at a simple path (avoid Windows
        # drive-letter colon issues in the subtitles filter).
        temp_srt = Path("._starvoyage_temp_subs.srt")
        if has_en and has_zh:
            en_text = Path(subtitle_en).read_text(encoding="utf-8")
            zh_text = Path(subtitle_zh).read_text(encoding="utf-8")
            en_lines = [l for l in en_text.strip().split("\n\n") if l.strip()]
            zh_lines = [l for l in zh_text.strip().split("\n\n") if l.strip()]
            merged = []
            for i, (en_block, zh_block) in enumerate(zip(en_lines, zh_lines), start=1):
                en_parts = en_block.split("\n", 2)
                zh_parts = zh_block.split("\n", 2)
                if len(en_parts) == 3 and len(zh_parts) == 3:
                    merged.append(f"{2*i-1}\n{en_parts[1]}\n{en_parts[2]}")
                    merged.append(f"{2*i}\n{zh_parts[1]}\n{zh_parts[2]}")
            temp_srt.write_text("\n\n".join(merged), encoding="utf-8")
        elif has_en:
            temp_srt.write_text(Path(subtitle_en).read_text(encoding="utf-8"), encoding="utf-8")
        else:
            temp_srt.write_text(Path(subtitle_zh).read_text(encoding="utf-8"), encoding="utf-8")

        vf = f"subtitles={temp_srt.name}:charenc=utf-8"
        self._run([
            self._ffmpeg, "-y",
            "-i", str(input_path),
            "-vf", vf,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "copy",
            "-pix_fmt", "yuv420p",
            str(output_path),
        ])
        temp_srt.unlink(missing_ok=True)

    # ── quality check ──────────────────────────────────────────────────

    def check_quality(self, video_path: str | Path) -> dict[str, Any]:
        """Run ffprobe to check basic quality metrics."""
        cmd = [
            self._ffprobe,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(video_path),
        ]
        result = sp.run(cmd, capture_output=True, text=False)
        if result.returncode != 0:
            return {"error": result.stderr.decode("utf-8", errors="replace")[:500]}

        data = json.loads(result.stdout.decode("utf-8", errors="replace"))
        video_stream = next(
            (s for s in data.get("streams", []) if s.get("codec_type") == "video"),
            {},
        )
        audio_stream = next(
            (s for s in data.get("streams", []) if s.get("codec_type") == "audio"),
            {},
        )

        info = {
            "width": video_stream.get("width"),
            "height": video_stream.get("height"),
            "fps": eval(video_stream.get("r_frame_rate", "0/1")) if video_stream.get("r_frame_rate") else 0,
            "video_codec": video_stream.get("codec_name"),
            "audio_codec": audio_stream.get("codec_name"),
            "duration_s": float(data.get("format", {}).get("duration", 0)),
            "bit_rate": int(data.get("format", {}).get("bit_rate", 0)),
            "file_size_bytes": int(data.get("format", {}).get("size", 0)),
        }
        logger.info("Quality check: %d×%d @ %.2f fps, %.1fs",
                     info["width"], info["height"], info["fps"], info["duration_s"])
        return info

    # ── helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _run(cmd: list[str]) -> None:
        """Run a subprocess and raise on failure."""
        logger.debug("FFmpeg command: %s", " ".join(cmd))
        result = sp.run(cmd, capture_output=True, text=False)
        if result.returncode != 0:
            stderr = (result.stderr.decode("utf-8", errors="replace") if result.stderr else "")
            # FFmpeg version banner is huge — show last 1500 chars where the real error is
            tail = stderr[-1500:] if len(stderr) > 1500 else stderr
            logger.debug("FFmpeg stderr (tail): %s", tail)
            raise RuntimeError(f"FFmpeg failed (code {result.returncode}):\n{tail}")

    @staticmethod
    def _esc(path: str) -> str:
        """Escape a path for FFmpeg filter arguments (escape ``\\`` and ``:``)."""
        return path.replace("\\", "\\\\").replace(":", "\\:")
