"""Abstract base selector – Strategy pattern.

All selectors (audio / category / video) implement :class:`BaseSelector` so
that the orchestrator can swap any selection algorithm without touching its
own code (Dependency Inversion + Open/Closed).
"""

from __future__ import annotations

import abc
import random
from datetime import datetime, timedelta, timezone
from typing import Generic, TypeVar

from src.config.settings import SelectionConfig
from src.exceptions import AppBaseException
from src.utils.logger import get_logger

log = get_logger(__name__)

T = TypeVar("T")


class NoCandidateError(AppBaseException):
    """Raised when a selector has zero candidates to choose from."""


class BaseSelector(abc.ABC, Generic[T]):
    """Common weighted-random selection machinery.

    Subclasses provide:
      * :meth:`_candidates` – list of candidate records (already loaded from DB)
      * :meth:`_usage`       – usage_count of a candidate
      * :meth:`_last_used`   – last_used_at of a candidate (may be ``None``)

    The base class then computes a weight per candidate combining inverse
    usage and recency, and picks one via :func:`random.choices`. Concrete
    selectors may further restrict candidates (e.g. cooldown filtering) before
    calling :meth:`_select_weighted`.
    """

    def __init__(
        self,
        rng: random.Random | None = None,
        selection_cfg: SelectionConfig | None = None,
    ) -> None:
        self.rng = rng or random.Random()
        self.cfg = selection_cfg or SelectionConfig()

    # --- API ----------------------------------------------------------------

    def select(self, *args, **kwargs) -> T:
        """Pick one candidate. Subclasses override to add arguments."""
        candidates = self._candidates(*args, **kwargs)
        if not candidates:
            raise NoCandidateError(f"{type(self).__name__} has no candidates")
        return self._select_weighted(candidates)

    # --- Hooks for subclasses ----------------------------------------------

    @abc.abstractmethod
    def _candidates(self, *args, **kwargs) -> list[T]:
        """Return the candidate pool."""

    def _usage(self, candidate: T) -> int:
        return 0

    def _last_used(self, candidate: T) -> datetime | None:
        return None

    # --- Weighted selection core -------------------------------------------

    def _select_weighted(self, candidates: list[T]) -> T:
        """Pick one candidate using weights = usage_score + recency_score."""
        weights = [self._weight(c) for c in candidates]
        # If all weights are zero (e.g. all candidates fresh + never used),
        # fall back to uniform sampling so we still make progress.
        if sum(weights) == 0:
            log.debug("all weights zero – falling back to uniform sampling")
            return self.rng.choice(candidates)
        return self.rng.choices(candidates, weights=weights, k=1)[0]

    def _weight(self, candidate: T) -> float:
        """Compute a non-negative weight for one candidate.

        Combines:
          * inverse usage_count (lower usage → higher weight)
          * recency penalty (older last_used_at → higher weight)

        Both components are normalised to the [0, 1] range based on the
        candidate pool, then combined with configurable weights.
        """
        usage = self._usage(candidate)
        last_used = self._last_used(candidate)

        # Inverse-usage component: 1 / (1 + usage_count)
        inv_usage = 1.0 / (1.0 + max(0, usage))

        # Recency component: 1.0 when never used or very old; decays to ~0
        # as last_used_at approaches now. Uses an exponential decay so the
        # penalty falls off smoothly rather than stepwise.
        if last_used is None:
            recency = 1.0
        else:
            now = datetime.now(timezone.utc)
            if last_used.tzinfo is None:
                last_used = last_used.replace(tzinfo=timezone.utc)
            age_minutes = max(0.0, (now - last_used).total_seconds() / 60.0)
            decay = float(self.cfg.recency_decay_minutes)
            recency = 1.0 - pow(0.5, age_minutes / decay) if decay > 0 else 1.0

        return max(0.0,
                   self.cfg.usage_weight * inv_usage
                   + self.cfg.recency_weight * recency)


__all__ = ["BaseSelector", "NoCandidateError"]
