"""SQLAlchemy ORM models for the Quran Video Generator.

Tables
------
audios           – one row per Quran audio file (full surah).
categories       – one row per scenery category (sea, forest, …).
videos           – one row per background video file, FK to categories.
generation_jobs  – one row per generated clip, FK to audios.

Selection state (``usage_count`` / ``last_used_at``) is updated only after a
job succeeds – never on failure.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Declarative base class shared by all ORM models."""


class Audio(Base):
    __tablename__ = "audios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    jobs: Mapped[list["GenerationJob"]] = relationship(back_populates="audio")

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Audio id={self.id} filename={self.filename!r} "
            f"usage={self.usage_count} dur={self.duration_seconds:.1f}>"
        )


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    videos: Mapped[list["Video"]] = relationship(back_populates="category", cascade="all, delete-orphan")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Category id={self.id} name={self.name!r} usage={self.usage_count}>"


class Video(Base):
    __tablename__ = "videos"
    __table_args__ = (UniqueConstraint("category_id", "filename", name="uq_category_filename"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"), nullable=False)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    category: Mapped[Category] = relationship(back_populates="videos")

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Video id={self.id} cat={self.category_id} filename={self.filename!r} "
            f"usage={self.usage_count} dur={self.duration_seconds:.1f}>"
        )


class GenerationJob(Base):
    __tablename__ = "generation_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    audio_id: Mapped[int] = mapped_column(ForeignKey("audios.id", ondelete="CASCADE"), nullable=False)
    clip_start: Mapped[float] = mapped_column(Float, nullable=False)
    clip_end: Mapped[float] = mapped_column(Float, nullable=False)
    output_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    audio: Mapped[Audio] = relationship(back_populates="jobs")

    # Status constants
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<GenerationJob id={self.id} audio={self.audio_id} "
            f"start={self.clip_start:.1f} end={self.clip_end:.1f} status={self.status!r}>"
        )


__all__ = ["Base", "Audio", "Category", "Video", "GenerationJob"]
