"""Generation orchestrator (Facade).

Coordinates the full pipeline: select audio → download → analyse silences
→ extract clips → select category → select videos → download videos →
encode with FFmpeg → upload to Cloudinary → update Mongo.

High-level progress is reported via :data:`pipeline_log` (user-facing
step-by-step narrative). Technical DEBUG spam goes through the regular
``log.debug(...)`` calls.
"""

from __future__ import annotations

import random
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from pymongo.database import Database

from src.config.settings import Settings
from src.database.repository import (
    AudioRepo, CategoryRepo, ExecutionRunRepo, ExecutionSliceRepo,
    VideoRepo, ensure_indexes,
)
from src.exceptions import AppBaseException, InsufficientAudioDurationError
from src.models import AudioClip, AudioRecord, GenerationJobResult
from src.services.audio_selector import AudioSelector
from src.services.category_selector import CategorySelector
from src.services.clip_extractor import ClipExtractor
from src.services.silence_detector import SilenceDetector
from src.services.video_processor import VideoProcessor
from src.services.video_selector import VideoSelector
from src.utils import media_downloader
from src.utils import ffmpeg_utils as ff
from src.utils.cloudinary_uploader import upload_video
from src.utils.file_utils import temp_workdir
from src.utils.logger import get_logger, pipeline_log

log = get_logger(__name__)

class GenerationOrchestrator:
    def __init__(self, db: Database, settings: Settings, *, audio_selector=None, category_selector=None, video_selector=None, clip_extractor=None, video_processor=None, rng=None) -> None:
        self.db = db
        self.settings = settings
        self.rng = rng or random.Random()

        self.audio_repo = AudioRepo(db)
        self.category_repo = CategoryRepo(db)
        self.video_repo = VideoRepo(db)
        self.run_repo = ExecutionRunRepo(db)
        self.slice_repo = ExecutionSliceRepo(db)

        self.audio_selector = audio_selector or AudioSelector(self.audio_repo, rng=self.rng, selection_cfg=settings.selection)
        self.category_selector = category_selector or CategorySelector(self.category_repo, self.slice_repo, settings, rng=self.rng, selection_cfg=settings.selection)
        self.video_selector = video_selector or VideoSelector(self.video_repo, settings, rng=self.rng, selection_cfg=settings.selection)
        self.silence_detector = SilenceDetector(settings)
        self.clip_extractor = clip_extractor or ClipExtractor(
            settings, rng=self.rng, silence_detector=self.silence_detector,
        )
        self.video_processor = video_processor or VideoProcessor(settings)

    def run_batch(self, audio_count: int) -> list[GenerationJobResult]:
        ensure_indexes(self.db)

        run_doc = self.run_repo.create(self.settings.github_run_id)
        execution_id = str(run_doc["_id"])
        log.info("Created execution run id=%s", execution_id)

        pipeline_log.batch_start(
            audio_count=audio_count,
            clips_per_audio=self.settings.clips_per_audio,
            clip_duration=self.settings.clip_duration,
        )
        batch_start = time.time()

        results: list[GenerationJobResult] = []
        used_audio_ids: set[str] = set()

        for i in range(audio_count):
            try:
                audio = self.audio_selector.select(exclude_ids=used_audio_ids)
            except AppBaseException as exc:
                log.error("could not select audio #%d: %s", i + 1, exc)
                pipeline_log.clip_failed(index=i + 1, total=audio_count, error=str(exc))
                break

            used_audio_ids.add(audio.id)
            pipeline_log.audio_selected(
                index=i + 1,
                total=audio_count,
                name=audio.name,
                usage_count=audio.usage_count,
                duration_s=audio.duration_seconds,
            )
            audio_results = self._process_audio(execution_id, audio)
            results.extend(audio_results)

        succeeded = sum(1 for r in results if r.status == "success")
        failed = sum(1 for r in results if r.status == "failed")

        run_status = "success" if failed == 0 else ("failed" if succeeded == 0 else "partial")
        self.run_repo.mark_completed(execution_id, run_status)

        total_elapsed = time.time() - batch_start
        pipeline_log.batch_summary(
            succeeded=succeeded, failed=failed, total_elapsed_s=total_elapsed,
        )
        log.info("batch finished: %d jobs (%d success, %d failed)", len(results), succeeded, failed)
        return results

    def _process_audio(self, execution_id: str, audio: AudioRecord) -> list[GenerationJobResult]:
        results: list[GenerationJobResult] = []
        with temp_workdir(prefix=f"audio_{audio.id}_", base_dir=self.settings.temp_dir) as audio_tmp:
            try:
                audio_local = media_downloader.download_to_temp(audio.source_url, audio_tmp, expected_extension=".mp3", filename_hint=f"audio_{audio.id}", expect_audio=True)

                if audio.duration_seconds <= 0:
                    try:
                        probe = ff.validate_media(audio_local, expect_audio=True)
                        audio = replace(audio, duration_seconds=probe.duration_seconds)
                        self.audio_repo.update_duration(audio.id, probe.duration_seconds)
                    except Exception as exc:
                        log.error("failed to probe duration for audio id=%s: %s", audio.id, exc)
                        return results

                # --- Silence analysis (run once per audio, cached) -------
                if not audio.silence_analyzed:
                    try:
                        positions = self.silence_detector.analyze(audio_local)
                        self.audio_repo.save_silence_positions(audio.id, positions)
                        audio = replace(
                            audio,
                            silence_analyzed=True,
                            silence_positions=positions,
                        )
                        pipeline_log.silence_analyzed(audio.name, len(positions))
                    except AppBaseException as exc:
                        log.warning(
                            "silence analysis failed for %s: %s — using mechanical cuts",
                            audio.name, exc,
                        )

                try:
                    clips = self.clip_extractor.extract(
                        audio,
                        silence_positions=audio.silence_positions,
                    )
                except InsufficientAudioDurationError as exc:
                    log.warning("skipping audio id=%s: %s", audio.id, exc)
                    return results

                for clip in clips:
                    result = self._process_clip(execution_id, audio, audio_local, clip)
                    results.append(result)
            except AppBaseException as exc:
                log.error("audio processing failed for audio id=%s: %s", audio.id, exc)
        return results

    def _process_clip(self, execution_id: str, audio: AudioRecord, audio_local_path: Path, clip: AudioClip) -> GenerationJobResult:
        slice_doc = self.slice_repo.create(
            execution_id=execution_id,
            audio_id=audio.id,
            slice_index=clip.index,
            clip_start=clip.start_seconds,
            clip_end=clip.end_seconds,
            clip_duration=clip.duration_seconds,
            github_run_id=self.settings.github_run_id,
        )
        slice_id = str(slice_doc["_id"])

        result = GenerationJobResult(job_id=slice_id, audio_id=audio.id, clip_index=clip.index, clip_start=clip.start_seconds, clip_end=clip.end_seconds, status="pending")

        total_clips = self.settings.clips_per_audio
        pipeline_log.clip_start(
            index=clip.index + 1,
            total=total_clips,
            start_s=clip.start_seconds,
            end_s=clip.end_seconds,
        )

        try:
            category = self.category_selector.select()
            result.selected_category_id = category.id
            pipeline_log.category_selected(name=category.name, usage_count=category.usage_count)

            self._ensure_video_durations(category.id)

            segments = self.video_selector.select_segments_for_duration(category_id=category.id, target_duration=clip.duration_seconds)
            result.selected_video_ids = [s.video_id for s in segments]
            pipeline_log.videos_selected(
                count=len(segments),
                total_duration_s=sum(s.duration_seconds for s in segments),
            )

            self.slice_repo.mark_selection(slice_id, category.id, result.selected_video_ids)

            with temp_workdir(prefix=f"clip_{clip.audio_id}_{clip.index}_", base_dir=self.settings.temp_dir) as tmp:
                downloaded_segments = []
                for seg in segments:
                    local_path = media_downloader.download_to_temp(seg.source_url, tmp, expected_extension=".mp4", filename_hint=f"video_{seg.video_id}", expect_video=True)
                    downloaded_segments.append(replace(seg, local_path=local_path))
                segments = downloaded_segments

                output_path = self._build_output_path(audio, clip, slice_id)
                self.video_processor.build_clip(audio, audio_local_path, clip, segments, output_path)

                upload = upload_video(output_path, slice_id, self.settings)

                self.slice_repo.mark_success(slice_id, cloudinary_url=upload.secure_url, cloudinary_public_id=upload.public_id, duration_seconds=upload.duration_seconds, width=upload.width, height=upload.height)
                self.run_repo.increment_counters(execution_id, success=True)

                result.cloudinary_url = upload.secure_url
                result.cloudinary_public_id = upload.public_id
                result.output_path = output_path
                result.status = "success"

                pipeline_log.clip_success(index=clip.index + 1, total=total_clips)

                self._mark_used(audio.id, category.id, result.selected_video_ids)

        except AppBaseException as exc:
            self.slice_repo.mark_failed(slice_id, str(exc))
            self.run_repo.increment_counters(execution_id, success=False)
            result.status = "failed"
            result.error_message = str(exc)
            pipeline_log.clip_failed(index=clip.index + 1, total=total_clips, error=str(exc))
        except Exception as exc:
            self.slice_repo.mark_failed(slice_id, str(exc))
            self.run_repo.increment_counters(execution_id, success=False)
            result.status = "failed"
            result.error_message = str(exc)
            pipeline_log.clip_failed(index=clip.index + 1, total=total_clips, error=str(exc))
        return result

    def _ensure_video_durations(self, category_id: str) -> None:
        videos = self.video_repo.list_for_category(category_id)
        unprobed = [v for v in videos if v.duration_seconds <= 0]
        if not unprobed: return
        with temp_workdir(prefix=f"probe_{category_id}_", base_dir=self.settings.temp_dir) as tmp:
            for v in unprobed:
                try:
                    local = media_downloader.download_to_temp(v.source_url, tmp, expected_extension=".mp4", filename_hint=f"probe_{v.id}", expect_video=True)
                    probe = ff.validate_media(local, expect_video=True)
                    self.video_repo.update_duration(v.id, probe.duration_seconds)
                except Exception as exc:
                    log.error("Failed to probe video id=%s: %s", v.id, exc)

    def _mark_used(self, audio_id: str, category_id: str, video_ids: list[str]) -> None:
        try:
            self.audio_repo.mark_used(audio_id)
            self.category_repo.mark_used(category_id)
            self.video_repo.mark_used_many(video_ids)
        except Exception:
            log.exception("failed to bump usage counters (non-fatal)")

    def _build_output_path(self, audio: AudioRecord, clip: AudioClip, slice_id: str) -> Path:
        out_dir = Path(self.settings.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        short_id = slice_id[-8:] if len(slice_id) >= 8 else slice_id
        return out_dir / f"{audio.id}_{clip.index}_{short_id}.mp4"


__all__ = ["GenerationOrchestrator"]
