"""Unit tests for the three weighted selectors.

These tests run entirely in-process against a temporary SQLite database and
verify BOTH functional correctness and statistical properties of the
weighted-random distribution (spec §10).
"""

from __future__ import annotations

import random
import statistics
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.config.settings import SelectionConfig, Settings
from src.database.models import Base
from src.database.repository import AudioRepo, CategoryRepo, JobRepo, VideoRepo
from src.database.session import get_engine, reset_engine
from src.exceptions import InsufficientCategoryContentError, NoAvailableCategoryError
from src.models import AudioRecord
from src.services.audio_selector import AudioSelector
from src.services.category_selector import CategorySelector
from src.services.video_selector import VideoSelector
from src.utils.logger import reset_logging


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """Point the app at a fresh SQLite file inside ``tmp_path``."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("QVG_DB_PATH", str(db_path))
    # Also override the config file so settings.db_path is correct.
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(f"db_path: {db_path}\nlog_level: ERROR\n")
    monkeypatch.setenv("QVG_CONFIG_FILE", str(cfg_path))

    from src.config.settings import reload_settings
    reload_settings(str(cfg_path))
    reset_engine()
    Base.metadata.create_all(get_engine())
    yield db_path
    reset_engine()
    reset_logging()


@pytest.fixture()
def session_factory(tmp_db):
    from src.database.session import get_session_factory
    return get_session_factory()


# --- AudioSelector ----------------------------------------------------------

def test_audio_selector_picks_from_pool(tmp_db, session_factory):
    with session_factory() as s:
        repo = AudioRepo(s)
        for i in range(5):
            repo.get_or_create(f"audio_{i}.mp3", duration_seconds=300.0)
        s.commit()

        sel = AudioSelector(repo, rng=random.Random(42))
        chosen = sel.select()
        assert chosen.filename.startswith("audio_")
        assert chosen.duration_seconds == 300.0


def test_audio_selector_never_used_when_all_zero(tmp_db, session_factory):
    """All-zero usage should still return a valid record (uniform fallback)."""
    with session_factory() as s:
        repo = AudioRepo(s)
        for i in range(3):
            repo.get_or_create(f"a{i}.mp3", duration_seconds=120.0)
        s.commit()

        sel = AudioSelector(repo, rng=random.Random(0))
        for _ in range(20):
            assert sel.select() is not None


def test_audio_selector_weighted_distribution(tmp_db, session_factory):
    """Low-usage audios should be picked more often than high-usage ones."""
    with session_factory() as s:
        repo = AudioRepo(s)
        # 1 audio with usage_count=0, 1 with usage_count=50
        a0 = repo.get_or_create("low.mp3", 100.0)
        a0.usage_count = 0
        a0.last_used_at = None
        a1 = repo.get_or_create("high.mp3", 100.0)
        a1.usage_count = 50
        a1.last_used_at = datetime.now(timezone.utc)
        s.commit()

        sel = AudioSelector(repo, rng=random.Random(1234))
        counts = Counter(sel.select().filename for _ in range(4000))
        # The low-usage audio should be picked significantly more often.
        assert counts["low.mp3"] > counts["high.mp3"] * 3


def test_audio_selector_excludes_ids(tmp_db, session_factory):
    with session_factory() as s:
        repo = AudioRepo(s)
        for i in range(4):
            repo.get_or_create(f"a{i}.mp3", 100.0)
        s.commit()
        sel = AudioSelector(repo, rng=random.Random(0))
        # IDs are auto-increment starting at 1, so exclude {2,3,4} -> only id=1 remains.
        for _ in range(50):
            chosen = sel.select(exclude_ids={2, 3, 4})
            assert chosen.id == 1


# --- CategorySelector -------------------------------------------------------

def _make_settings(cooldown: int = 2) -> Settings:
    return Settings(category_cooldown=cooldown, db_path="/tmp/_unused.db")


def test_category_selector_cooldown_blocks_recent(tmp_db, session_factory):
    """When K=2 categories are on cooldown and only those exist, raise."""
    with session_factory() as s:
        cr = CategoryRepo(s)
        jr = JobRepo(s)
        for i in range(2):
            c = cr.get_or_create(f"cat_{i}")
            c.last_used_at = datetime.now(timezone.utc)  # just used -> cooldown
        s.commit()
        sel = CategorySelector(cr, jr, _make_settings(cooldown=2), rng=random.Random(0))
        with pytest.raises(NoAvailableCategoryError):
            sel.select()


def test_category_selector_skips_cooldown_when_alternatives_exist(tmp_db, session_factory):
    with session_factory() as s:
        cr = CategoryRepo(s)
        jr = JobRepo(s)
        hot = cr.get_or_create("hot")
        hot.last_used_at = datetime.now(timezone.utc)
        cold = cr.get_or_create("cold")  # never used
        s.commit()
        sel = CategorySelector(cr, jr, _make_settings(cooldown=2), rng=random.Random(0))
        for _ in range(20):
            assert sel.select().name == "cold"


def test_category_selector_weighted_distribution(tmp_db, session_factory):
    with session_factory() as s:
        cr = CategoryRepo(s)
        jr = JobRepo(s)
        low = cr.get_or_create("low"); low.usage_count = 0
        high = cr.get_or_create("high"); high.usage_count = 50
        high.last_used_at = datetime.now(timezone.utc)
        s.commit()
        sel = CategorySelector(cr, jr, _make_settings(cooldown=0), rng=random.Random(99))
        counts = Counter(sel.select().name for _ in range(3000))
        assert counts["low"] > counts["high"] * 3


# --- VideoSelector ----------------------------------------------------------

def test_video_selector_covers_duration(tmp_db, session_factory):
    with session_factory() as s:
        cr = CategoryRepo(s)
        vr = VideoRepo(s)
        cat = cr.get_or_create("sea")
        # Three 25s videos -> need 60s, so 3 will cover.
        for i in range(3):
            vr.get_or_create(cat.id, f"sea_{i}.mp4", 25.0)
        s.commit()
        sel = VideoSelector(vr, _make_settings(cooldown=0), rng=random.Random(0))
        segments = sel.select_segments_for_duration(cat.id, target_duration=60.0)
        assert sum(seg.duration_seconds for seg in segments) >= 60.0
        # No duplicates when pool was big enough.
        ids = [seg.video_id for seg in segments]
        assert len(ids) == len(set(ids))


def test_video_selector_reuse_when_pool_exhausted(tmp_db, session_factory):
    with session_factory() as s:
        cr = CategoryRepo(s)
        vr = VideoRepo(s)
        cat = cr.get_or_create("forest")
        vr.get_or_create(cat.id, "forest_0.mp4", 15.0)
        vr.get_or_create(cat.id, "forest_1.mp4", 15.0)
        s.commit()
        settings = Settings(allow_video_reuse_within_job=True, db_path="/tmp/_unused.db")
        sel = VideoSelector(vr, settings, rng=random.Random(0))
        segments = sel.select_segments_for_duration(cat.id, target_duration=60.0)
        assert sum(seg.duration_seconds for seg in segments) >= 60.0


def test_video_selector_strict_raises(tmp_db, session_factory):
    with session_factory() as s:
        cr = CategoryRepo(s)
        vr = VideoRepo(s)
        cat = cr.get_or_create("desert")
        vr.get_or_create(cat.id, "desert_0.mp4", 10.0)
        s.commit()
        settings = Settings(allow_video_reuse_within_job=False, db_path="/tmp/_unused.db")
        sel = VideoSelector(vr, settings, rng=random.Random(0))
        with pytest.raises(InsufficientCategoryContentError):
            sel.select_segments_for_duration(cat.id, target_duration=120.0)
