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
            probe videos in category if duration is 0 and update MongoDB
            select videos until duration covered
            download the selected videos to a per-clip temp dir
            build final MP4 via VideoProcessor
            upload the MP4 to Cloudinary
            on success: update usage counts, mark execution success
                        with the Cloudinary URL/metadata
            on failure: mark execution failed, log, continue

Single-clip failures never crash the batch (per spec §7). Usage counters are
bumped only after a successful export + upload.
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
        
        with temp_workdir(prefix=f"audio_{audio.id}_", base_dir=self.settings.temp_dir) as audio_tmp:
            try:
                audio_local = media_downloader.download_to_temp(
                    audio.source_url, audio_tmp,
                    expected_extension=".mp3",
                    filename_hint=f"audio_{audio.id}",
                    expect_audio=True,
                )

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

                for clip in clips:
                    result = self._process_clip(audio, audio_local, clip)
                    results.append(result)
                    
            except AppBaseException as exc:
                log.error("audio processing failed for audio id=%s: %s", audio.id, exc)
                return results
                
        return results

    # --- Per-clip pipeline --------------------------------------------------

    def _process_clip(self, audio: AudioRecord, audio_local_path: Path, clip: AudioClip) -> GenerationJobResult:
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

            # 1.5. Probe videos with unknown durations so the selector works correctly.
            self._ensure_video_durations(category.id)

            # 2. Select videos until duration covered.
            segments = self.video_selector.select_segments_for_duration(
                category_id=category.id,
                target_duration=clip.duration_seconds,
            )
            result.selected_video_ids = [s.video_id for s in segments]

            self.execution_repo.mark_selection(
                execution_id, category.id, result.selected_video_ids
            )

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
        except Exception as exc:
            self._fail_execution(execution_id, exc)
            result.status = "failed"
            result.error_message = str(exc)
            log.exception(
                "unexpected error for exec=%s audio=%s clip=%d",
                execution_id, audio.id, clip.index,
            )
        return result

    # --- Helpers ------------------------------------------------------------

    def _ensure_video_durations(self, category_id: str) -> None:
        """Probe and update duration for any video in the category marked as 0.0s."""
        videos = self.video_repo.list_for_category(category_id)
        unprobed = [v for v in videos if v.duration_seconds <= 0]
        if not unprobed:
            return

        log.info("Found %d video(s) with unknown duration in category %s. Probing...", len(unprobed), category_id)
        with temp_workdir(prefix=f"probe_{category_id}_", base_dir=self.settings.temp_dir) as tmp:
            for v in unprobed:
                try:
                    local = media_downloader.download_to_temp(
                        v.source_url, tmp,
                        expected_extension=".mp4",
                        filename_hint=f"probe_{v.id}",
                        expect_video=True,
                    )
                    probe = ff.validate_media(local, expect_video=True)
                    self.video_repo.update_duration(v.id, probe.duration_seconds)
                    log.info("Video id=%s probed duration=%.2fs", v.id, probe.duration_seconds)
                except Exception as exc:
                    log.error("Failed to probe video id=%s: %s", v.id, exc)

    def _mark_used(self, audio_id: str, category_id: str, video_ids: list[str]) -> None:
        try:
            self.audio_repo.mark_used(audio_id)
            self.category_repo.mark_used(category_id)
            self.video_repo.mark_used_many(video_ids)
        except Exception:
            log.exception("failed to bump usage counters (non-fatal)")

    def _fail_execution(self, execution_id: str, exc: BaseException) -> None:
        try:
            self.execution_repo.mark_failed(execution_id, str(exc))
        except Exception:
            log.exception("could not persist failure status for exec=%s", execution_id)

    def _build_output_path(
        self, audio: AudioRecord, clip: AudioClip, execution_id: str
    ) -> Path:
        out_dir = Path(self.settings.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        short_id = execution_id[-8:] if len(execution_id) >= 8 else execution_id
        return out_dir / f"{audio.id}_{clip.index}_{short_id}.mp4"


__all__ = ["GenerationOrchestrator"]
