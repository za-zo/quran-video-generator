"""Weighted-random least-used category selector with cooldown."""

from __future__ import annotations

import random
from datetime import datetime

from src.config.settings import SelectionConfig, Settings
from src.database.repository import CategoryRepo, ExecutionRepo
from src.exceptions import NoAvailableCategoryError
from src.models import CategoryRecord
from src.services.base_selector import BaseSelector
from src.utils.logger import get_logger

log = get_logger(__name__)


class CategorySelector(BaseSelector[CategoryRecord]):
    """Selects a scenery category.

    Selection rules:
      1. Exclude any category whose id appears among the last K successful
         jobs (configurable via ``category_cooldown``).
      2. From the remaining pool, apply weighted-random least-used selection
         (same scoring function as :class:`AudioSelector`).
      3. Raise :class:`NoAvailableCategoryError` if the pool is empty after
         cooldown filtering (rather than picking the same category again).
    """

    def __init__(
        self,
        category_repo: CategoryRepo,
        execution_repo: ExecutionRepo,
        settings: Settings,
        rng: random.Random | None = None,
        selection_cfg: SelectionConfig | None = None,
    ) -> None:
        super().__init__(rng=rng, selection_cfg=selection_cfg)
        self.category_repo = category_repo
        self.execution_repo = execution_repo
        self.cooldown = settings.category_cooldown

    def _candidates(self) -> list[CategoryRecord]:
        return self.category_repo.list_all()

    def _usage(self, candidate: CategoryRecord) -> int:
        return candidate.usage_count

    def _last_used(self, candidate: CategoryRecord) -> datetime | None:
        return candidate.last_used_at

    def select(self) -> CategoryRecord:
        """Pick a category respecting the cooldown window."""
        candidates = self._candidates()
        if not candidates:
            raise NoAvailableCategoryError("no categories registered in DB")

        # Safeguard: If the total number of categories is less than or equal
        # to the cooldown K, applying the cooldown would block everything.
        # We bypass it to keep the pipeline running.
        if self.cooldown > 0 and len(candidates) > self.cooldown:
            recent_ids = set(self.execution_repo.recent_category_ids(self.cooldown))
            if recent_ids:
                log.debug("cooldown excludes category ids: %s", recent_ids)
            filtered = [c for c in candidates if c.id not in recent_ids]
            if not filtered:
                raise NoAvailableCategoryError(
                    f"all {len(candidates)} categories are on cooldown "
                    f"(K={self.cooldown})"
                )
            candidates = filtered
        elif self.cooldown > 0 and len(candidates) <= self.cooldown:
            log.warning(
                "Total categories (%d) <= cooldown K (%d). Ignoring cooldown to avoid empty pool.",
                len(candidates), self.cooldown
            )

        chosen = self._select_weighted(candidates)
        log.info(
            "CategorySelector picked category id=%s name=%r usage=%d (pool=%d)",
            chosen.id, chosen.name, chosen.usage_count, len(candidates),
        )
        return chosen


__all__ = ["CategorySelector"]
