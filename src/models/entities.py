"""Domain entities (lightweight dataclasses).

These are the data structures that flow between selectors, the clip
extractor, the video processor, and the orchestrator. They are deliberately
decoupled from the ORM models so we can change the storage layer without
touching the orchestration logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class AudioRecord:
    """Audio file as known to the selection layer."""

    id: int
    filename: str
    duration_seconds: float
    usage_count: int = 0
    last_used_at: datetime | None = None

    @property
    def path(self) -> Path:
        return Path(self.filename)


@dataclass(frozen=True)
class CategoryRecord:
    id: int
    name: str
    usage_count: int = 0
    last_used_at: datetime | None = None


@dataclass(frozen=True)
class VideoRecord:
    id: int
    category_id: int
    filename: str
    duration_seconds: float
    usage_count: int = 0
    last_used_at: datetime | None = None

    @property
    def path(self) -> Path:
        return Path(self.filename)


@dataclass(frozen=True)
class AudioClip:
    """A non-overlapping slice of a longer audio file."""

    audio_id: int
    index: int        # 0-based index among clips generated from this audio
    start_seconds: float
    end_seconds: float

    @property
    def duration_seconds(self) -> float:
        return self.end_seconds - self.start_seconds


@dataclass(frozen=True)
class VideoSegment:
    """A single background-video file chosen for a clip."""

    video_id: int
    filename: str
    duration_seconds: float

    @property
    def path(self) -> Path:
        return Path(self.filename)


@dataclass
class GenerationJobResult:
    """Outcome of one clip-generation job."""

    job_id: int
    audio_id: int
    clip_index: int
    clip_start: float
    clip_end: float
    output_path: Path | None = None
    status: str = "pending"
    error_message: str | None = None
    selected_category_id: int | None = None
    selected_video_ids: list[int] = field(default_factory=list)


__all__ = [
    "AudioRecord",
    "CategoryRecord",
    "VideoRecord",
    "AudioClip",
    "VideoSegment",
    "GenerationJobResult",
]
