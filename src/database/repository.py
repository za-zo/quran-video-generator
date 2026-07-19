"""Repository pattern – thin data-access layer on top of SQLAlchemy.

Each repository owns one table and exposes only the operations the rest of
the application needs. Selectors and the orchestrator depend on these
abstractions, never on raw SQL or ORM objects leaking outside this module.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.models import Audio, Category, GenerationJob, Video
from src.exceptions import DatabaseIntegrityError
from src.utils.logger import get_logger

log = get_logger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- AudioRepo --------------------------------------------------------------

class AudioRepo:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_or_create(self, filename: str, duration_seconds: float) -> Audio:
        existing = self.session.execute(
            select(Audio).where(Audio.filename == filename)
        ).scalar_one_or_none()
        if existing is not None:
            # Refresh duration in case the file was re-encoded.
            if existing.duration_seconds != duration_seconds:
                existing.duration_seconds = duration_seconds
                self.session.flush()
            return existing
        audio = Audio(filename=filename, duration_seconds=duration_seconds)
        self.session.add(audio)
        self.session.flush()
        return audio

    def get(self, audio_id: int) -> Audio | None:
        return self.session.get(Audio, audio_id)

    def list_all(self) -> list[Audio]:
        return list(self.session.execute(select(Audio).order_by(Audio.id)).scalars())

    def mark_used(self, audio_id: int) -> None:
        audio = self.get(audio_id)
        if audio is None:
            raise DatabaseIntegrityError(f"Audio id={audio_id} not found")
        audio.usage_count += 1
        audio.last_used_at = _utcnow()
        self.session.flush()

    def stats(self) -> list[tuple[str, int, datetime | None]]:
        rows = self.list_all()
        return [(a.filename, a.usage_count, a.last_used_at) for a in rows]


# --- CategoryRepo -----------------------------------------------------------

class CategoryRepo:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_or_create(self, name: str) -> Category:
        existing = self.session.execute(
            select(Category).where(Category.name == name)
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        cat = Category(name=name)
        self.session.add(cat)
        self.session.flush()
        return cat

    def list_all(self) -> list[Category]:
        return list(self.session.execute(select(Category).order_by(Category.id)).scalars())

    def mark_used(self, category_id: int) -> None:
        cat = self.session.get(Category, category_id)
        if cat is None:
            raise DatabaseIntegrityError(f"Category id={category_id} not found")
        cat.usage_count += 1
        cat.last_used_at = _utcnow()
        self.session.flush()


# --- VideoRepo --------------------------------------------------------------

class VideoRepo:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_or_create(self, category_id: int, filename: str, duration_seconds: float) -> Video:
        existing = self.session.execute(
            select(Video).where(
                Video.category_id == category_id,
                Video.filename == filename,
            )
        ).scalar_one_or_none()
        if existing is not None:
            if existing.duration_seconds != duration_seconds:
                existing.duration_seconds = duration_seconds
                self.session.flush()
            return existing
        v = Video(
            category_id=category_id,
            filename=filename,
            duration_seconds=duration_seconds,
        )
        self.session.add(v)
        self.session.flush()
        return v

    def list_for_category(self, category_id: int) -> list[Video]:
        return list(
            self.session.execute(
                select(Video).where(Video.category_id == category_id).order_by(Video.id)
            ).scalars()
        )

    def mark_used(self, video_id: int) -> None:
        v = self.session.get(Video, video_id)
        if v is None:
            raise DatabaseIntegrityError(f"Video id={video_id} not found")
        v.usage_count += 1
        v.last_used_at = _utcnow()
        self.session.flush()

    def mark_used_many(self, video_ids: Iterable[int]) -> None:
        for vid in video_ids:
            self.mark_used(vid)


# --- JobRepo ----------------------------------------------------------------

class JobRepo:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        audio_id: int,
        clip_start: float,
        clip_end: float,
        status: str = GenerationJob.PENDING,
    ) -> GenerationJob:
        job = GenerationJob(
            audio_id=audio_id,
            clip_start=clip_start,
            clip_end=clip_end,
            status=status,
        )
        self.session.add(job)
        self.session.flush()
        return job

    def mark_success(self, job_id: int, output_path: str) -> None:
        job = self.session.get(GenerationJob, job_id)
        if job is None:
            raise DatabaseIntegrityError(f"Job id={job_id} not found")
        job.status = GenerationJob.SUCCESS
        job.output_path = output_path
        job.completed_at = _utcnow()
        self.session.flush()

    def mark_failed(self, job_id: int, error_message: str) -> None:
        job = self.session.get(GenerationJob, job_id)
        if job is None:
            raise DatabaseIntegrityError(f"Job id={job_id} not found")
        job.status = GenerationJob.FAILED
        job.error_message = error_message[:4000]
        job.completed_at = _utcnow()
        self.session.flush()

    def recent_category_ids(self, k: int) -> list[int]:
        """Return category_ids used by the last K *successful* jobs.

        Used by :class:`CategorySelector` to apply the cooldown window.
        Returns at most K entries (most-recent first).
        """
        if k <= 0:
            return []
        # We didn't store category_id on jobs by design (a job may use many
        # videos across categories). Instead we infer from the most recently
        # used categories via their last_used_at timestamps.
        cats = self.session.execute(
            select(Category).where(Category.last_used_at.is_not(None))
            .order_by(Category.last_used_at.desc()).limit(k)
        ).scalars().all()
        return [c.id for c in cats]

    def list_recent(self, limit: int = 20) -> list[GenerationJob]:
        return list(
            self.session.execute(
                select(GenerationJob).order_by(GenerationJob.id.desc()).limit(limit)
            ).scalars()
        )

    def count_by_status(self) -> dict[str, int]:
        jobs = self.session.execute(select(GenerationJob)).scalars().all()
        out: dict[str, int] = {}
        for j in jobs:
            out[j.status] = out.get(j.status, 0) + 1
        return out


__all__ = ["AudioRepo", "CategoryRepo", "VideoRepo", "JobRepo"]
