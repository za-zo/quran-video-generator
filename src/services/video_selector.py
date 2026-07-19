"""Weighted-random video selector within a single category.

Selects videos one at a time until their cumulative duration covers the
target clip duration. If the category runs out of videos before reaching the
target, behaviour is controlled by ``allow_video_reuse_within_job``:

  * True  – cycle through already-picked videos to make up the difference
            (a warning is logged).
  * False – raise :class:`InsufficientCategoryContentError`.
"""

from __future__ import annotations

import random
from datetime import datetime

from src.config.settings import SelectionConfig, Settings
from src.database.repository import VideoRepo
from src.exceptions import InsufficientCategoryContentError
from src.models import VideoRecord, VideoSegment
from src.services.base_selector import BaseSelector, NoCandidateError
from src.utils.logger import get_logger

log = get_logger(__name__)


class VideoSelector(BaseSelector[VideoRecord]):
    """Selects individual videos from one category, weighted by usage."""

    def __init__(
        self,
        video_repo: VideoRepo,
        settings: Settings,
        rng: random.Random | None = None,
        selection_cfg: SelectionConfig | None = None,
    ) -> None:
        super().__init__(rng=rng, selection_cfg=selection_cfg)
        self.video_repo = video_repo
        self.allow_reuse = settings.allow_video_reuse_within_job

    def _candidates(self, category_id: str, exclude_ids: set[str] | None = None) -> list[VideoRecord]:
        exclude_ids = exclude_ids or set()
        rows = self.video_repo.list_for_category(category_id)
        return [v for v in rows if v.id not in exclude_ids]

    def _usage(self, candidate: VideoRecord) -> int:
        return candidate.usage_count

    def _last_used(self, candidate: VideoRecord) -> datetime | None:
        return candidate.last_used_at

    # --- Public API ---------------------------------------------------------

    def select_segments_for_duration(self, category_id: str, target_duration: float) -> list[VideoSegment]:
        """Return a list of :class:`VideoSegment` whose total duration >= ``target_duration``.

        The same video is never selected twice in the same call unless reuse
        is explicitly allowed and the pool is exhausted.
        """
        if target_duration <= 0:
            return []

        available = self._candidates(category_id)
        if not available:
            raise NoCandidateError(
                f"category id={category_id} has no videos registered"
            )

        chosen: list[VideoSegment] = []
        chosen_ids: set[str] = set()
        pool = list(available)

        while _sum_duration(chosen) < target_duration:
            remaining = [v for v in pool if v.id not in chosen_ids]
            if not remaining:
                # Pool exhausted before reaching target.
                if not chosen:
                    raise NoCandidateError(
                        f"category id={category_id} pool empty before any pick"
                    )
                if self.allow_reuse:
                    log.warning(
                        "category id=%s exhausted at %.2fs/%.2fs – allowing reuse",
                        category_id, _sum_duration(chosen), target_duration,
                    )
                    # Cycle through already-chosen videos in order.
                    nxt = chosen[len(chosen) % len(chosen)]
                    chosen.append(VideoSegment(
                        video_id=nxt.video_id,
                        name=nxt.name,
                        source_url=nxt.source_url,
                        duration_seconds=nxt.duration_seconds,
                    ))
                    continue
                raise InsufficientCategoryContentError(
                    f"category id={category_id} cannot cover target duration "
                    f"{target_duration:.2f}s (got {_sum_duration(chosen):.2f}s "
                    f"with {len(chosen)} videos, reuse disabled)"
                )

            picked = self._select_weighted(remaining)
            chosen_ids.add(picked.id)
            chosen.append(
                VideoSegment(
                    video_id=picked.id,
                    name=picked.name,
                    source_url=picked.source_url,
                    duration_seconds=picked.duration_seconds,
                )
            )

        log.info(
            "VideoSelector chose %d videos totalling %.2fs for category id=%s (target=%.2fs)",
            len(chosen), _sum_duration(chosen), category_id, target_duration,
        )
        return chosen


def _sum_duration(segments: list[VideoSegment]) -> float:
    return sum(s.duration_seconds for s in segments)


__all__ = ["VideoSelector"]
