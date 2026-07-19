"""FFmpeg-backed video processor.

Owns every FFmpeg operation required by the pipeline:
  * Mute background videos (re-encoded to a normalised, closed-GOP layout
    so subsequent concat is seamless).
  * Concatenate muted videos (demuxer-first, filter-complex fallback –
    both paths re-encode with a fixed closed GOP).
  * Trim the concatenated video to exactly the audio clip duration
    (re-encoded for frame-accurate cutting).
  * Extract the Quran audio clip from the source audio.
  * Merge the muted/trimmed video with the Quran audio clip and export.

All technical parameters (resolution, fps, codecs, temp dir) come from
:class:`Settings` – nothing is hardcoded.

Local-path contract
-------------------
The pipeline no longer reads media from the filesystem directly. The caller
(``GenerationOrchestrator``) downloads each needed file via
:mod:`src.utils.media_downloader` into a per-clip temp directory and then
hands the local paths to ``build_clip``:

  * ``audio_local_path`` – the downloaded source audio file.
  * each ``VideoSegment.local_path`` – the downloaded background video.

If either is missing, ``build_clip`` fails fast with a clear error.
"""

from __future__ import annotations

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

    The processor never touches the database or the network – it only knows
    about :class:`AudioRecord`, :class:`AudioClip`, :class:`VideoSegment`,
    and :class:`Settings`. This keeps the SRP boundary clean.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.temp_root = ensure_dir(settings.temp_dir)

    # --- Public pipeline primitives ----------------------------------------

    def mute(self, src: Path, dst_dir: Path) -> Path:
        """Strip audio from ``src`` -> ``dst_dir / muted_<name>``.

        Re-encodes to the configured target resolution/fps/codec with a
        closed fixed GOP. Stream-copy (``-c:v copy``) would preserve each
        source's original GOP/PTS layout and break concat boundaries.
        """
        dst = dst_dir / f"muted_{src.name}"
        ff.mute_video(
            src, dst,
            width=self.settings.resolution_width,
            height=self.settings.resolution_height,
            fps=self.settings.fps,
            video_codec=self.settings.video_codec,
        )
        return dst

    def concat_clips(self, clips: list[Path], dst: Path) -> Path:
        """Concatenate ``clips`` into ``dst``.

        First tries the concat demuxer (now re-encoding, not stream-copy).
        If that fails (e.g. mismatched codecs the demuxer cannot decode),
        falls back to the ``filter_complex`` concat path which normalises
        every input via scale+fps+setsar before concatenating.

        Both paths emit a closed, fixed-GOP stream so boundaries between
        clips are seamless (no frozen last frame, no black flash).
        """
        if not clips:
            raise FFmpegExecutionError("concat_clips called with empty list")

        try:
            return ff.concat_demuxer(
                clips, dst,
                width=self.settings.resolution_width,
                height=self.settings.resolution_height,
                fps=self.settings.fps,
                video_codec=self.settings.video_codec,
            )
        except FFmpegExecutionError as exc:
            log.warning(
                "concat demuxer failed (%s); falling back to filter_complex path",
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
        """Trim ``src`` to exactly ``duration`` seconds (frame-accurate).

        Re-encodes rather than using ``-c copy -t`` so the cut is
        frame-accurate and the output starts on a clean keyframe with a
        fresh closed GOP — preventing concat/merge artifacts downstream.
        """
        if duration <= 0:
            raise FFmpegExecutionError(
                f"trim_to_duration called with non-positive duration {duration!r}"
            )
        return ff.trim_video(
            src, dst, duration=duration,
            width=self.settings.resolution_width,
            height=self.settings.resolution_height,
            fps=self.settings.fps,
            video_codec=self.settings.video_codec,
        )

    def extract_audio_clip(self, audio_path: Path, clip: AudioClip, dst: Path) -> Path:
        """Slice the source audio file according to ``clip``."""
        if not audio_path.is_file():
            raise CorruptedMediaError(f"audio source missing: {audio_path}")
        return ff.extract_audio_clip(
            audio_path, dst,
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
        audio_local_path: Path,
        clip: AudioClip,
        segments: list[VideoSegment],
        output_path: Path,
    ) -> Path:
        """Run the full FFmpeg pipeline for a single clip.

        Parameters
        ----------
        audio
            The audio record (used only for metadata; the actual bytes are
            at ``audio_local_path``).
        audio_local_path
            Local filesystem path to the downloaded source audio.
        clip
            Slice info (start/end within ``audio_local_path``).
        segments
            Background videos with their ``local_path`` already populated
            by the orchestrator's download step.
        output_path
            Where to write the final MP4.
        """
        if not segments:
            raise FFmpegExecutionError(
                "build_clip requires at least one video segment"
            )
        if not audio_local_path.is_file():
            raise CorruptedMediaError(
                f"audio local file missing: {audio_local_path}"
            )
        for seg in segments:
            if seg.local_path is None or not seg.local_path.is_file():
                raise CorruptedMediaError(
                    f"video segment {seg.video_id} local file missing: {seg.local_path}"
                )

        # Validate inputs first – fail fast on corrupted media.
        ff.validate_media(audio_local_path, expect_audio=True)
        for seg in segments:
            ff.validate_media(seg.local_path, expect_video=True)

        ensure_dir(output_path.parent)

        with temp_workdir(prefix=f"clip_{clip.audio_id}_{clip.index}_", base_dir=self.temp_root) as tmp:
            try:
                # 1. Mute all background videos (using their local paths).
                muted: list[Path] = []
                for i, seg in enumerate(segments):
                    muted.append(self.mute(seg.local_path, tmp))

                # 2. Concatenate.
                concat_dst = tmp / "concat.mp4"
                self.concat_clips(muted, concat_dst)

                # 3. Trim to the audio clip duration.
                trimmed = tmp / "trimmed.mp4"
                self.trim_to_duration(concat_dst, trimmed, clip.duration_seconds)

                # 4. Extract the Quran audio clip.
                audio_clip = tmp / f"audio_{clip.audio_id}_{clip.index}.m4a"
                self.extract_audio_clip(audio_local_path, clip, audio_clip)

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
