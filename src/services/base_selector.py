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

    Selection strategy (controlled by ``SelectionConfig.strict_least_used``):

    * **strict_least_used=True (default)** — *tiered* selection:
        1. Find the minimum ``usage_count`` among the candidates.
        2. Keep only candidates whose usage_count equals that minimum.
        3. Within this tied tier, apply the existing recency-weighted
           scoring (``_weight``) to break ties by recency, then pick
           one at random.
        This guarantees that the least-used elements are always
        exhausted before any higher-usage element is eligible — the
        "least-used first" promise.

    * **strict_least_used=False** — original weighted-random behaviour:
        compute a weight per candidate combining inverse usage and
        recency across the *entire* pool, then pick via
        :func:`random.choices`.

    Concrete selectors may further restrict candidates (e.g. cooldown
    filtering) before calling :meth:`_select_weighted`.
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
        """Pick one candidate.

        When ``self.cfg.strict_least_used`` is True (default), restricts
        the pool to the lowest-usage tier before applying the recency-
        weighted random selection. When False, applies the original
        weighted-random selection across the whole pool.
        """
        if getattr(self.cfg, "strict_least_used", True):
            return self._select_tiered(candidates)
        return self._select_legacy_weighted(candidates)

    def _select_tiered(self, candidates: list[T]) -> T:
        """Strict least-used-first selection with recency tie-break.

        1. Find min usage_count among candidates.
        2. Filter to only candidates at that minimum.
        3. Apply recency-weighted random selection within the tier.
        """
        if not candidates:
            raise NoCandidateError("tiered selection called with empty pool")
        if len(candidates) == 1:
            return candidates[0]

        usages = [self._usage(c) for c in candidates]
        min_usage = min(usages)
        tier = [c for c, u in zip(candidates, usages) if u == min_usage]

        if len(tier) == 1:
            chosen = tier[0]
        else:
            # Within the tied tier, apply recency-weighted random pick
            # for variety. The usage_score component is constant across
            # the tier (all equal to min_usage), so the recency_score
            # alone differentiates them.
            weights = [self._weight(c) for c in tier]
            if sum(weights) == 0:
                # All zero weights (e.g. all fresh + never used) —
                # uniform sampling for fairness.
                chosen = self.rng.choice(tier)
            else:
                chosen = self.rng.choices(tier, weights=weights, k=1)[0]

        log.debug(
            "tiered selection: pool=%d, tier_size=%d (min_usage=%d) -> picked",
            len(candidates), len(tier), min_usage,
        )
        return chosen

    def _select_legacy_weighted(self, candidates: list[T]) -> T:
        """Original weighted-random selection (pre-strict behaviour).

        Combines inverse usage_count and recency across the whole pool,
        then picks via random.choices. Kept for opt-in via
        ``strict_least_used=False``.
        """
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
