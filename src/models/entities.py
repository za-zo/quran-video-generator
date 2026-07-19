"""Domain entities (lightweight dataclasses).

These are the data structures that flow between selectors, the clip
extractor, the video processor, and the orchestrator. They are deliberately
decoupled from the storage layer so we can change the persistence backend
(SQLAlchemy → MongoDB → anything) without touching the orchestration logic.

ID convention
-------------
All ``id`` fields are ``str`` (MongoDB ``ObjectId`` stringified at the
repository boundary). This keeps the rest of the codebase storage-agnostic
and lets the webapp pass IDs around as plain URL segments.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class AudioRecord:
    """Audio file as known to the selection layer.

    ``source_url`` is a remote URL the pipeline downloads at runtime –
    the file is NOT stored locally.
    """

    id: str
    name: str
    source_url: str
    duration_seconds: float
    usage_count: int = 0
    last_used_at: datetime | None = None


@dataclass(frozen=True)
class CategoryRecord:
    id: str
    name: str
    usage_count: int = 0
    last_used_at: datetime | None = None


@dataclass(frozen=True)
class VideoRecord:
    id: str
    category_id: str
    name: str
    source_url: str
    duration_seconds: float
    usage_count: int = 0
    last_used_at: datetime | None = None


@dataclass(frozen=True)
class AudioClip:
    """A non-overlapping slice of a longer audio file."""

    audio_id: str
    index: int        # 0-based index among clips generated from this audio
    start_seconds: float
    end_seconds: float

    @property
    def duration_seconds(self) -> float:
        return self.end_seconds - self.start_seconds


@dataclass(frozen=True)
class VideoSegment:
    """A single background-video file chosen for a clip.

    ``local_path`` is set by the orchestrator after the segment's
    ``source_url`` has been downloaded to a temp directory; the FFmpeg
    layer consumes only that local path.
    """

    video_id: str
    name: str
    source_url: str
    duration_seconds: float
    local_path: Path | None = None


@dataclass
class GenerationJobResult:
    """Outcome of one clip-generation job."""

    job_id: str
    audio_id: str
    clip_index: int
    clip_start: float
    clip_end: float
    output_path: Path | None = None
    cloudinary_url: str | None = None
    cloudinary_public_id: str | None = None
    status: str = "pending"
    error_message: str | None = None
    selected_category_id: str | None = None
    selected_video_ids: list[str] = field(default_factory=list)


__all__ = [
    "AudioRecord",
    "CategoryRecord",
    "VideoRecord",
    "AudioClip",
    "VideoSegment",
    "GenerationJobResult",
]
