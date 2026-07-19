"""Weighted-random least-used audio selector."""

from __future__ import annotations

import random
from datetime import datetime

from src.config.settings import SelectionConfig
from src.database.repository import AudioRepo
from src.models import AudioRecord
from src.services.base_selector import BaseSelector, NoCandidateError
from src.utils.logger import get_logger

log = get_logger(__name__)


class AudioSelector(BaseSelector[AudioRecord]):
    """Selects an audio file using weighted-random least-used strategy.

    Combines inverse ``usage_count`` and a recency penalty so:
      * least-used audios get higher weight
      * recently-used audios get a temporary penalty that decays over time
    """

    def __init__(
        self,
        audio_repo: AudioRepo,
        rng: random.Random | None = None,
        selection_cfg: SelectionConfig | None = None,
    ) -> None:
        super().__init__(rng=rng, selection_cfg=selection_cfg)
        self.audio_repo = audio_repo

    def _candidates(self, exclude_ids: set[str] | None = None) -> list[AudioRecord]:
        exclude_ids = exclude_ids or set()
        rows = self.audio_repo.list_all()
        return [a for a in rows if a.id not in exclude_ids]

    def _usage(self, candidate: AudioRecord) -> int:
        return candidate.usage_count

    def _last_used(self, candidate: AudioRecord) -> datetime | None:
        return candidate.last_used_at

    def select(self, exclude_ids: set[str] | None = None) -> AudioRecord:
        """Pick one audio record.

        ``exclude_ids`` lets the orchestrator avoid re-selecting an audio
        already used earlier in the same batch run.
        """
        candidates = self._candidates(exclude_ids=exclude_ids)
        if not candidates:
            raise NoCandidateError(
                "no audio candidates available (or all excluded)"
            )
        chosen = self._select_weighted(candidates)
        log.info(
            "AudioSelector picked audio id=%s usage=%d (pool=%d)",
            chosen.id, chosen.usage_count, len(candidates),
        )
        return chosen


__all__ = ["AudioSelector"]
