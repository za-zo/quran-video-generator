"""Generation orchestrator (Facade).

Coordinates the full pipeline end-to-end:

    for each audio in batch:
        select audio (weighted least-used)
        extract N non-overlapping clips
        for each clip:
            select category (weighted + cooldown)
            select videos until duration covered
            build final MP4 via VideoProcessor
            on success: update usage counts, mark job success
            on failure: mark job failed, log, continue

Single-clip failures never crash the batch (per spec §7). Usage counters are
bumped only after a successful export.

The orchestrator depends on ABSTRACTIONS only (repositories, selectors,
processor) – never on concrete FFmpeg/SQL details.
"""

from __future__ import annotations

import random
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from src.config.settings import Settings
from src.database.repository import AudioRepo, CategoryRepo, JobRepo, VideoRepo
from src.exceptions import AppBaseException, InsufficientAudioDurationError
from src.models import AudioClip, AudioRecord, GenerationJobResult
from src.services.audio_selector import AudioSelector
from src.services.category_selector import CategorySelector
from src.services.clip_extractor import ClipExtractor
from src.services.video_processor import VideoProcessor
from src.services.video_selector import VideoSelector
from src.utils.logger import get_logger

log = get_logger(__name__)


class GenerationOrchestrator:
    """Facade that wires the full generation pipeline together."""

    def __init__(
        self,
        session: Session,
        settings: Settings,
        *,
        audio_selector: AudioSelector | None = None,
        category_selector: CategorySelector | None = None,
        video_selector: VideoSelector | None = None,
        clip_extractor: ClipExtractor | None = None,
        video_processor: VideoProcessor | None = None,
        rng: random.Random | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.rng = rng or random.Random()

        self.audio_repo = AudioRepo(session)
        self.category_repo = CategoryRepo(session)
        self.video_repo = VideoRepo(session)
        self.job_repo = JobRepo(session)

        self.audio_selector = audio_selector or AudioSelector(
            self.audio_repo, rng=self.rng, selection_cfg=settings.selection,
        )
        self.category_selector = category_selector or CategorySelector(
            self.category_repo, self.job_repo, settings,
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
        """Generate clips for up to ``audio_count`` distinct audios.

        Each audio is processed in its own transaction so a failure on audio
        N doesn't roll back successful jobs from audios 1..N-1.
        """
        results: list[GenerationJobResult] = []
        used_audio_ids: set[int] = set()

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
        try:
            clips = self.clip_extractor.extract(audio)
        except InsufficientAudioDurationError as exc:
            log.warning("skipping audio id=%s: %s", audio.id, exc)
            return results
        except AppBaseException as exc:
            log.error("clip extraction failed for audio id=%s: %s", audio.id, exc)
            return results

        for clip in clips:
            result = self._process_clip(audio, clip)
            results.append(result)
        return results

    # --- Per-clip pipeline --------------------------------------------------

    def _process_clip(self, audio: AudioRecord, clip: AudioClip) -> GenerationJobResult:
        job = self.job_repo.create(
            audio_id=audio.id,
            clip_start=clip.start_seconds,
            clip_end=clip.end_seconds,
            status="pending",
        )
        self.session.commit()

        result = GenerationJobResult(
            job_id=job.id,
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

            # 3. Build the final MP4.
            output_path = self._build_output_path(audio, clip)
            self.video_processor.build_clip(audio, clip, segments, output_path)

            # 4. Persist usage updates (only after success).
            self._mark_used(audio.id, category.id, result.selected_video_ids)
            self.job_repo.mark_success(job.id, str(output_path))
            self.session.commit()

            result.output_path = output_path
            result.status = "success"
            log.info(
                "clip generated: job=%s audio=%s clip=%d -> %s",
                job.id, audio.id, clip.index, output_path,
            )
        except AppBaseException as exc:
            self.session.rollback()
            self._fail_job(job.id, exc)
            result.status = "failed"
            result.error_message = str(exc)
            log.error(
                "clip failed: job=%s audio=%s clip=%d: %s",
                job.id, audio.id, clip.index, exc,
            )
        except Exception as exc:  # pragma: no cover - safety net
            self.session.rollback()
            self._fail_job(job.id, exc)
            result.status = "failed"
            result.error_message = str(exc)
            log.exception(
                "unexpected error for job=%s audio=%s clip=%d",
                job.id, audio.id, clip.index,
            )
        return result

    # --- Helpers ------------------------------------------------------------

    def _mark_used(self, audio_id: int, category_id: int, video_ids: list[int]) -> None:
        self.audio_repo.mark_used(audio_id)
        self.category_repo.mark_used(category_id)
        self.video_repo.mark_used_many(video_ids)

    def _fail_job(self, job_id: int, exc: BaseException) -> None:
        try:
            # Fresh transaction for the failure update.
            self.job_repo.mark_failed(job_id, str(exc))
            self.session.commit()
        except Exception:
            self.session.rollback()
            log.exception("could not persist failure status for job=%s", job_id)

    def _build_output_path(self, audio: AudioRecord, clip: AudioClip) -> Path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = Path(self.settings.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir / f"{audio.id}_{clip.index}_{ts}.mp4"


__all__ = ["GenerationOrchestrator"]
