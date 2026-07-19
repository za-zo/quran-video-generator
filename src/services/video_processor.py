"""FFmpeg-backed video processor.

Owns every FFmpeg operation required by the pipeline.
All technical parameters (resolution, fps, codecs, temp dir) come from
:class:`Settings` – nothing is hardcoded.
"""

from __future__ import annotations

from pathlib import Path

from src.config.settings import Settings
from src.exceptions import CorruptedMediaError, FFmpegExecutionError
from src.models import AudioClip, AudioRecord, VideoSegment
from src.utils import ffmpeg_utils as ff
from src.utils.file_utils import cleanup_path, ensure_dir
from src.utils.logger import get_logger

log = get_logger(__name__)


class VideoProcessor:
    """Single entry point for all FFmpeg operations."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.temp_root = ensure_dir(settings.temp_dir)

    def build_clip(
        self,
        audio: AudioRecord,
        audio_local_path: Path,
        clip: AudioClip,
        segments: list[VideoSegment],
        output_path: Path,
    ) -> Path:
        """Run the full FFmpeg pipeline for a single clip in one pass."""
        if not segments:
            raise FFmpegExecutionError("build_clip requires at least one video segment")
        if not audio_local_path.is_file():
            raise CorruptedMediaError(f"audio local file missing: {audio_local_path}")
        
        for seg in segments:
            if seg.local_path is None or not seg.local_path.is_file():
                raise CorruptedMediaError(f"video segment {seg.video_id} local file missing: {seg.local_path}")

        # Validate inputs first – fail fast on corrupted media.
        ff.validate_media(audio_local_path, expect_audio=True)
        for seg in segments:
            ff.validate_media(seg.local_path, expect_video=True)

        ensure_dir(output_path.parent)

        try:
            ff.build_clip_one_pass(
                video_paths=[seg.local_path for seg in segments],
                audio_path=audio_local_path,
                dst=output_path,
                audio_start=clip.start_seconds,
                duration=clip.duration_seconds,
                width=self.settings.resolution_width,
                height=self.settings.resolution_height,
                fps=self.settings.fps,
                video_codec=self.settings.video_codec,
                video_preset=self.settings.video_preset,
                audio_codec=self.settings.audio_codec,
            )
        except Exception:
            cleanup_path(output_path)
            raise

        log.info("VideoProcessor produced %s", output_path)
        return output_path


__all__ = ["VideoProcessor"]
