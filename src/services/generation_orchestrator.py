"""Generation orchestrator (Facade).

Coordinates the full pipeline end-to-end:

    for each audio in batch:
        select audio (weighted least-used)
        download the source audio to a per-audio temp dir
        if duration is 0, probe it via ffprobe and update MongoDB
        extract N non-overlapping clips
        for each clip:
            create an execution document (status=pending)
            select category (weighted + cooldown)
            select videos until duration covered
            download the selected videos to a per-clip temp dir
            build final MP4 via VideoProcessor
            upload the MP4 to Cloudinary
            on success: update usage counts, mark execution success
                        with the Cloudinary URL/metadata
            on failure: mark execution failed, log, continue

Single-clip failures never crash the batch (per spec §7). Usage counters are
bumped only after a successful export + upload.

The orchestrator depends on ABSTRACTIONS only (repositories, selectors,
processor, uploader, downloader) – never on concrete FFmpeg/Mongo/HTTP
details.
"""

from __future__ import annotations

import random
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from pymongo.database import Database

from src.config.settings import Settings
from src.database.repository import (
    AudioRepo,
    CategoryRepo,
    ExecutionRepo,
    VideoRepo,
    ensure_indexes,
)
from src.exceptions import AppBaseException, InsufficientAudioDurationError
from src.models import AudioClip, AudioRecord, GenerationJobResult
from src.services.audio_selector import AudioSelector
from src.services.category_selector import CategorySelector
from src.services.clip_extractor import ClipExtractor
from src.services.video_processor import VideoProcessor
from src.services.video_selector import VideoSelector
from src.utils import media_downloader
from src.utils import ffmpeg_utils as ff
from src.utils.cloudinary_uploader import (
    CloudinaryUploadError,
    upload_video,
)
from src.utils.file_utils import temp_workdir
from src.utils.logger import get_logger

log = get_logger(__name__)


class GenerationOrchestrator:
    """Facade that wires the full generation pipeline together."""

    def __init__(
        self,
        db: Database,
        settings: Settings,
        *,
        audio_selector: AudioSelector | None = None,
        category_selector: CategorySelector | None = None,
        video_selector: VideoSelector | None = None,
        clip_extractor: ClipExtractor | None = None,
        video_processor: VideoProcessor | None = None,
        rng: random.Random | None = None,
    ) -> None:
        self.db = db
        self.settings = settings
        self.rng = rng or random.Random()

        self.audio_repo = AudioRepo(db)
        self.category_repo = CategoryRepo(db)
        self.video_repo = VideoRepo(db)
        self.execution_repo = ExecutionRepo(db)

        self.audio_selector = audio_selector or AudioSelector(
            self.audio_repo, rng=self.rng, selection_cfg=settings.selection,
        )
        self.category_selector = category_selector or CategorySelector(
            self.category_repo, self.execution_repo, settings,
            rng=self.rng, selection_cfg=settings.selection,
        )
        self.video_selector = video_selector or VideoSelector(
            self.video_repo, settings,
            rng=self.rng, selection_cfg=settings.selection,
        )
        self.clip_extractor = clip_extractor or ClipExtractor(settings, rng=self.rng)
        self.video_processor = video_processor or VideoProcessor(settings)

    # --- Batch entry point -------------------------------------------------

    def run_batch(self, audio_count: int) -> list[GenerationJobResult]:
        """Generate clips for up to ``audio_count`` distinct audios."""
        # Ensure indexes exist (idempotent) so a fresh cluster behaves
        # the same as a long-running one.
        ensure_indexes(self.db)

        results: list[GenerationJobResult] = []
        used_audio_ids: set[str] = set()

        for i in range(audio_count):
            try:
                audio = self.audio_selector.select(exclude_ids=used_audio_ids)
            except AppBaseException as exc:
                log.error("could not select audio #%d: %s", i + 1, exc)
                break

            used_audio_ids.add(audio.id)
            audio_results = self._process_audio(audio)
            results.extend(audio_results)

        # Summary
        succeeded = sum(1 for r in results if r.status == "success")
        failed = sum(1 for r in results if r.status == "failed")
        log.info(
            "batch finished: %d jobs (%d success, %d failed)",
            len(results), succeeded, failed,
        )
        return results

    # --- Per-audio pipeline -------------------------------------------------

    def _process_audio(self, audio: AudioRecord) -> list[GenerationJobResult]:
        results: list[GenerationJobResult] = []
        
        # We download the audio once per audio, rather than once per clip,
        # to save bandwidth and time.
        with temp_workdir(prefix=f"audio_{audio.id}_", base_dir=self.settings.temp_dir) as audio_tmp:
            try:
                audio_local = media_downloader.download_to_temp(
                    audio.source_url, audio_tmp,
                    expected_extension=".mp3",
                    filename_hint=f"audio_{audio.id}",
                    expect_audio=True,
                )

                # If duration is unknown (0), probe it from the downloaded file and update DB.
                if audio.duration_seconds <= 0:
                    try:
                        probe = ff.validate_media(audio_local, expect_audio=True)
                        audio = replace(audio, duration_seconds=probe.duration_seconds)
                        self.audio_repo.update_duration(audio.id, probe.duration_seconds)
                        log.info("Audio id=%s probed duration=%.2fs", audio.id, probe.duration_seconds)
                    except Exception as exc:
                        log.error("failed to probe duration for audio id=%s: %s", audio.id, exc)
                        return results

                try:
                    clips = self.clip_extractor.extract(audio)
                except InsufficientAudioDurationError as exc:
                    log.warning("skipping audio id=%s: %s", audio.id, exc)
                    return results
                except AppBaseException as exc:
                    log.error("clip extraction failed for audio id=%s: %s", audio.id, exc)
                    return results

                # Each clip gets its own temp dir so a failure on clip N doesn't
                # leave half-downloaded files for clip N+1.
                for clip in clips:
                    result = self._process_clip(audio, audio_local, clip)
                    results.append(result)
                    
            except AppBaseException as exc:
                log.error("audio processing failed for audio id=%s: %s", audio.id, exc)
                return results
                
        return results

    # --- Per-clip pipeline --------------------------------------------------

    def _process_clip(self, audio: AudioRecord, audio_local_path: Path, clip: AudioClip) -> GenerationJobResult:
        # Create the execution document up front so even a failed download
        # leaves a traceable record.
        exec_doc = self.execution_repo.create(
            audio_id=audio.id,
            slice_index=clip.index,
            clip_start=clip.start_seconds,
            clip_end=clip.end_seconds,
            clip_duration=clip.duration_seconds,
            github_run_id=self.settings.github_run_id,
            status="pending",
        )
        execution_id = str(exec_doc["_id"])

        result = GenerationJobResult(
            job_id=execution_id,
            audio_id=audio.id,
            clip_index=clip.index,
            clip_start=clip.start_seconds,
            clip_end=clip.end_seconds,
            status="pending",
        )

        try:
            # 1. Select category.
            category = self.category_selector.select()
            result.selected_category_id = category.id

            # 2. Select videos until duration covered.
            segments = self.video_selector.select_segments_for_duration(
                category_id=category.id,
                target_duration=clip.duration_seconds,
            )
            result.selected_video_ids = [s.video_id for s in segments]

            # Persist the selection so the webapp can show what was chosen
            # even if the next steps fail.
            self.execution_repo.mark_selection(
                execution_id, category.id, result.selected_video_ids
            )

            # 3. Download all media needed for this clip into a temp dir,
            #    then run FFmpeg, then upload to Cloudinary. Everything
            #    inside one temp_workdir so cleanup is automatic.
            with temp_workdir(
                prefix=f"clip_{clip.audio_id}_{clip.index}_",
                base_dir=self.settings.temp_dir,
            ) as tmp:
                # 3a. Download each selected video.
                for seg in segments:
                    seg.local_path = media_downloader.download_to_temp(
                        seg.source_url, tmp,
                        expected_extension=".mp4",
                        filename_hint=f"video_{seg.video_id}",
                        expect_video=True,
                    )

                # 3b. Build the final MP4 locally.
                output_path = self._build_output_path(audio, clip, execution_id)
                self.video_processor.build_clip(
                    audio, audio_local_path, clip, segments, output_path,
                )

                # 3c. Upload to Cloudinary.
                upload = upload_video(output_path, execution_id, self.settings)

                # 3d. Persist success + Cloudinary metadata.
                self.execution_repo.mark_success(
                    execution_id,
                    cloudinary_url=upload.secure_url,
                    cloudinary_public_id=upload.public_id,
                    duration_seconds=upload.duration_seconds,
                    width=upload.width,
                    height=upload.height,
                )

                result.cloudinary_url = upload.secure_url
                result.cloudinary_public_id = upload.public_id
                result.output_path = output_path
                result.status = "success"
                log.info(
                    "clip generated: exec=%s audio=%s clip=%d -> %s",
                    execution_id, audio.id, clip.index, upload.secure_url,
                )

            # 4. Persist usage updates (only after success).
            self._mark_used(audio.id, category.id, result.selected_video_ids)

        except AppBaseException as exc:
            self._fail_execution(execution_id, exc)
            result.status = "failed"
            result.error_message = str(exc)
            log.error(
                "clip failed: exec=%s audio=%s clip=%d: %s",
                execution_id, audio.id, clip.index, exc,
            )
        except Exception as exc:  # pragma: no cover - safety net
            self._fail_execution(execution_id, exc)
            result.status = "failed"
            result.error_message = str(exc)
            log.exception(
                "unexpected error for exec=%s audio=%s clip=%d",
                execution_id, audio.id, clip.index,
            )
        return result

    # --- Helpers ------------------------------------------------------------

    def _mark_used(self, audio_id: str, category_id: str, video_ids: list[str]) -> None:
        """Bump usage counters after a successful clip.

        Issued as sequential writes without an explicit transaction; see
        the module docstring in :mod:`src.database.repository` for the
        consistency tradeoff.
        """
        try:
            self.audio_repo.mark_used(audio_id)
            self.category_repo.mark_used(category_id)
            self.video_repo.mark_used_many(video_ids)
        except Exception:
            # Don't crash the clip just because a counter didn't bump.
            log.exception("failed to bump usage counters (non-fatal)")

    def _fail_execution(self, execution_id: str, exc: BaseException) -> None:
        try:
            self.execution_repo.mark_failed(execution_id, str(exc))
        except Exception:
            log.exception("could not persist failure status for exec=%s", execution_id)

    def _build_output_path(
        self, audio: AudioRecord, clip: AudioClip, execution_id: str
    ) -> Path:
        """Build the local output path for the final MP4.

        Uses the execution_id (short suffix) so the file is traceable to
        its MongoDB document even after the temp dir is gone.
        """
        out_dir = Path(self.settings.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        short_id = execution_id[-8:] if len(execution_id) >= 8 else execution_id
        return out_dir / f"{audio.id}_{clip.index}_{short_id}.mp4"


__all__ = ["GenerationOrchestrator"]
