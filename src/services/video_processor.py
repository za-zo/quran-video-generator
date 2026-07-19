"""FFmpeg-backed video processor.

Owns every FFmpeg operation required by the pipeline:
  * Mute background videos (``-an -c:v copy``).
  * Concatenate muted videos (demuxer-first, re-encode fallback).
  * Trim the concatenated video to exactly the audio clip duration.
  * Extract the Quran audio clip from the source audio.
  * Merge the muted/trimmed video with the Quran audio clip and export.

All technical parameters (resolution, fps, codecs, temp dir) come from
:class:`Settings` – nothing is hardcoded.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from src.config.settings import Settings
from src.exceptions import CorruptedMediaError, FFmpegExecutionError
from src.models import AudioClip, AudioRecord, VideoSegment
from src.utils import ffmpeg_utils as ff
from src.utils.file_utils import cleanup_path, ensure_dir, temp_workdir
from src.utils.logger import get_logger

log = get_logger(__name__)


class VideoProcessor:
    """Single entry point for all FFmpeg operations.

    The processor never touches the database – it only knows about
    :class:`AudioRecord`, :class:`AudioClip`, :class:`VideoSegment`, and
    :class:`Settings`. This keeps the SRP boundary clean.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.temp_root = ensure_dir(settings.temp_dir)

    # --- Public pipeline primitives ----------------------------------------

    def mute(self, src: Path, dst_dir: Path) -> Path:
        """Strip audio from ``src`` -> ``dst_dir / src.name`` (lossless copy)."""
        dst = dst_dir / f"muted_{src.name}"
        ff.mute_video(src, dst)
        return dst

    def concat_clips(self, clips: list[Path], dst: Path) -> Path:
        """Concatenate ``clips`` into ``dst``.

        First tries the fast ``-c copy`` demuxer path. If that fails (e.g.
        mismatched codecs/resolutions), falls back to re-encoding with the
        configured target resolution/fps.
        """
        if not clips:
            raise FFmpegExecutionError("concat_clips called with empty list")

        try:
            return ff.concat_demuxer(clips, dst)
        except FFmpegExecutionError as exc:
            log.warning(
                "concat demuxer failed (%s); falling back to re-encode path",
                exc.message,
            )
            # Clean partial output before retry.
            cleanup_path(dst)
            return ff.concat_with_reencode(
                clips, dst,
                width=self.settings.resolution_width,
                height=self.settings.resolution_height,
                fps=self.settings.fps,
                video_codec=self.settings.video_codec,
                audio_codec=self.settings.audio_codec,
            )

    def trim_to_duration(self, src: Path, dst: Path, duration: float) -> Path:
        """Trim ``src`` to exactly ``duration`` seconds."""
        if duration <= 0:
            raise FFmpegExecutionError(
                f"trim_to_duration called with non-positive duration {duration!r}"
            )
        return ff.trim_video(src, dst, duration=duration)

    def extract_audio_clip(self, audio: AudioRecord, clip: AudioClip, dst: Path) -> Path:
        """Slice the source audio file according to ``clip``."""
        if not audio.path.is_file():
            raise CorruptedMediaError(f"audio source missing: {audio.path}")
        return ff.extract_audio_clip(
            audio.path, dst,
            start=clip.start_seconds,
            duration=clip.duration_seconds,
            audio_codec=self.settings.audio_codec,
        )

    def merge_audio_video(
        self,
        video: Path,
        audio: Path,
        dst: Path,
        *,
        duration: float,
    ) -> Path:
        """Merge a muted video with an audio clip, producing the final MP4."""
        return ff.merge_audio_video(
            video, audio, dst,
            video_codec=self.settings.video_codec,
            audio_codec=self.settings.audio_codec,
            fps=self.settings.fps,
            width=self.settings.resolution_width,
            height=self.settings.resolution_height,
            duration=duration,
        )

    # --- High-level orchestration primitive --------------------------------

    def build_clip(
        self,
        audio: AudioRecord,
        clip: AudioClip,
        segments: list[VideoSegment],
        output_path: Path,
    ) -> Path:
        """Run the full FFmpeg pipeline for a single clip.

        Steps (all inside a temp dir which is cleaned up at the end):
          1. Validate every input file with ffprobe.
          2. Mute each background video.
          3. Concatenate muted videos.
          4. Trim to clip.duration_seconds.
          5. Extract the Quran audio clip.
          6. Merge trimmed video + Quran audio -> ``output_path``.
        """
        if not segments:
            raise FFmpegExecutionError(
                "build_clip requires at least one video segment"
            )

        # Validate inputs first – fail fast on corrupted media.
        ff.validate_media(audio.path, expect_audio=True)
        for seg in segments:
            ff.validate_media(seg.path, expect_video=True)

        ensure_dir(output_path.parent)

        with temp_workdir(prefix=f"clip_{clip.audio_id}_{clip.index}_", base_dir=self.temp_root) as tmp:
            try:
                # 1. Mute all background videos.
                muted: list[Path] = []
                for i, seg in enumerate(segments):
                    muted.append(self.mute(seg.path, tmp))

                # 2. Concatenate.
                concat_dst = tmp / "concat.mp4"
                self.concat_clips(muted, concat_dst)

                # 3. Trim to the audio clip duration.
                trimmed = tmp / "trimmed.mp4"
                self.trim_to_duration(concat_dst, trimmed, clip.duration_seconds)

                # 4. Extract the Quran audio clip.
                audio_clip = tmp / f"audio_{clip.audio_id}_{clip.index}.m4a"
                self.extract_audio_clip(audio, clip, audio_clip)

                # 5. Merge to final output.
                self.merge_audio_video(
                    video=trimmed,
                    audio=audio_clip,
                    dst=output_path,
                    duration=clip.duration_seconds,
                )
            except Exception:
                # Make sure a partial output file doesn't linger.
                cleanup_path(output_path)
                raise

        log.info("VideoProcessor produced %s", output_path)
        return output_path


__all__ = ["VideoProcessor"]
