"""Unit tests for the three weighted selectors.

Run entirely in-process against a ``mongomock`` database – no MongoDB
Atlas cluster required. Verify BOTH functional correctness and statistical
properties of the weighted-random distribution.
"""

from __future__ import annotations

import random
from collections import Counter
from datetime import datetime, timezone

import mongomock
import pytest

from src.config.settings import SelectionConfig, Settings
from src.database.mongo_client import set_test_db
from src.database.repository import (
    AudioRepo,
    CategoryRepo,
    ExecutionRepo,
    VideoRepo,
    ensure_indexes,
)
from src.exceptions import InsufficientCategoryContentError, NoAvailableCategoryError
from src.services.audio_selector import AudioSelector
from src.services.category_selector import CategorySelector
from src.services.video_selector import VideoSelector
from src.utils.logger import reset_logging


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mongo_db(tmp_path, monkeypatch):
    """Spin up a fresh mongomock database for each test."""
    monkeypatch.setenv("MONGODB_URI", "mongodb://localhost/test")
    monkeypatch.setenv("MONGODB_DB_NAME", "qvg_test")
    monkeypatch.setenv("CLOUDINARY_CLOUD_NAME", "test-cloud")
    monkeypatch.setenv("CLOUDINARY_API_KEY", "test-key")
    monkeypatch.setenv("CLOUDINARY_API_SECRET", "test-secret")

    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        "mongodb_uri: mongodb://localhost/test\n"
        "mongodb_db_name: qvg_test\n"
        "cloudinary_cloud_name: test-cloud\n"
        "cloudinary_api_key: test-key\n"
        "cloudinary_api_secret: test-secret\n"
        "log_level: ERROR\n"
    )
    monkeypatch.setenv("QVG_CONFIG_FILE", str(cfg_path))

    from src.config.settings import reload_settings
    reload_settings(str(cfg_path))

    client = mongomock.MongoClient()
    db = client["qvg_test"]
    set_test_db(db)
    ensure_indexes(db)
    yield db
    set_test_db(None)
    reset_logging()


def _settings(cooldown: int = 2) -> Settings:
    return Settings(
        category_cooldown=cooldown,
        mongodb_uri="mongodb://localhost/test",
        mongodb_db_name="qvg_test",
        cloudinary_cloud_name="test-cloud",
        cloudinary_api_key="test-key",
        cloudinary_api_secret="test-secret",
    )


# --- AudioSelector ----------------------------------------------------------

def test_audio_selector_picks_from_pool(mongo_db):
    repo = AudioRepo(mongo_db)
    for i in range(5):
        repo.create(name=f"audio_{i}", source_url=f"https://example.com/{i}.mp3",
                    duration_seconds=300.0)
    sel = AudioSelector(repo, rng=random.Random(42))
    chosen = sel.select()
    assert chosen.name.startswith("audio_")
    assert chosen.duration_seconds == 300.0


def test_audio_selector_never_used_when_all_zero(mongo_db):
    repo = AudioRepo(mongo_db)
    for i in range(3):
        repo.create(name=f"a{i}", source_url=f"https://example.com/{i}.mp3",
                    duration_seconds=120.0)
    sel = AudioSelector(repo, rng=random.Random(0))
    for _ in range(20):
        assert sel.select() is not None


def test_audio_selector_weighted_distribution(mongo_db):
    """Low-usage audios should be picked more often than high-usage ones."""
    repo = AudioRepo(mongo_db)
    a0 = repo.create(name="low", source_url="https://example.com/low.mp3",
                     duration_seconds=100.0)
    a0_usage = repo.get(a0.id)
    assert a0_usage.usage_count == 0

    a1 = repo.create(name="high", source_url="https://example.com/high.mp3",
                     duration_seconds=100.0)
    # Bump usage_count to 50 directly so the recency penalty is also high.
    mongo_db["audios"].update_one(
        {"_id": _oid(a1.id)},
        {"$set": {"usage_count": 50, "last_used_at": datetime.now(timezone.utc)}},
    )

    sel = AudioSelector(repo, rng=random.Random(1234))
    counts = Counter(sel.select().name for _ in range(4000))
    assert counts["low"] > counts["high"] * 3


def test_audio_selector_excludes_ids(mongo_db):
    repo = AudioRepo(mongo_db)
    ids = []
    for i in range(4):
        a = repo.create(name=f"a{i}", source_url=f"https://example.com/{i}.mp3",
                        duration_seconds=100.0)
        ids.append(a.id)
    sel = AudioSelector(repo, rng=random.Random(0))
    # Exclude 3 of 4 -> only one remains.
    excluded = set(ids[1:])
    kept = ids[0]
    for _ in range(50):
        chosen = sel.select(exclude_ids=excluded)
        assert chosen.id == kept


# --- CategorySelector -------------------------------------------------------

def test_category_selector_cooldown_blocks_recent(mongo_db):
    """When K=2 categories are on cooldown and only those exist, raise."""
    cr = CategoryRepo(mongo_db)
    er = ExecutionRepo(mongo_db)
    for i in range(2):
        c = cr.create(name=f"cat_{i}")
        # Mark the category as recently used by bumping last_used_at.
        mongo_db["categories"].update_one(
            {"_id": _oid(c.id)},
            {"$set": {"last_used_at": datetime.now(timezone.utc)}},
        )
    sel = CategorySelector(cr, er, _settings(cooldown=2), rng=random.Random(0))
    with pytest.raises(NoAvailableCategoryError):
        sel.select()


def test_category_selector_skips_cooldown_when_alternatives_exist(mongo_db):
    cr = CategoryRepo(mongo_db)
    er = ExecutionRepo(mongo_db)
    hot = cr.create(name="hot")
    mongo_db["categories"].update_one(
        {"_id": _oid(hot.id)},
        {"$set": {"last_used_at": datetime.now(timezone.utc)}},
    )
    cold = cr.create(name="cold")  # never used
    sel = CategorySelector(cr, er, _settings(cooldown=2), rng=random.Random(0))
    for _ in range(20):
        assert sel.select().name == "cold"


def test_category_selector_weighted_distribution(mongo_db):
    cr = CategoryRepo(mongo_db)
    er = ExecutionRepo(mongo_db)
    low = cr.create(name="low")
    high = cr.create(name="high")
    mongo_db["categories"].update_one(
        {"_id": _oid(high.id)},
        {"$set": {
            "usage_count": 50,
            "last_used_at": datetime.now(timezone.utc),
        }},
    )
    sel = CategorySelector(cr, er, _settings(cooldown=0), rng=random.Random(99))
    counts = Counter(sel.select().name for _ in range(3000))
    assert counts["low"] > counts["high"] * 3


# --- VideoSelector ----------------------------------------------------------

def test_video_selector_covers_duration(mongo_db):
    cr = CategoryRepo(mongo_db)
    vr = VideoRepo(mongo_db)
    cat = cr.create(name="sea")
    for i in range(3):
        vr.create(
            category_id=cat.id, name=f"sea_{i}",
            source_url=f"https://example.com/sea_{i}.mp4",
            duration_seconds=25.0,
        )
    sel = VideoSelector(vr, _settings(cooldown=0), rng=random.Random(0))
    segments = sel.select_segments_for_duration(cat.id, target_duration=60.0)
    assert sum(seg.duration_seconds for seg in segments) >= 60.0
    ids = [seg.video_id for seg in segments]
    assert len(ids) == len(set(ids))


def test_video_selector_reuse_when_pool_exhausted(mongo_db):
    cr = CategoryRepo(mongo_db)
    vr = VideoRepo(mongo_db)
    cat = cr.create(name="forest")
    vr.create(category_id=cat.id, name="forest_0",
              source_url="https://example.com/f0.mp4", duration_seconds=15.0)
    vr.create(category_id=cat.id, name="forest_1",
              source_url="https://example.com/f1.mp4", duration_seconds=15.0)
    settings = Settings(
        allow_video_reuse_within_job=True,
        mongodb_uri="mongodb://localhost/test",
        mongodb_db_name="qvg_test",
        cloudinary_cloud_name="test-cloud",
        cloudinary_api_key="test-key",
        cloudinary_api_secret="test-secret",
    )
    sel = VideoSelector(vr, settings, rng=random.Random(0))
    segments = sel.select_segments_for_duration(cat.id, target_duration=60.0)
    assert sum(seg.duration_seconds for seg in segments) >= 60.0


def test_video_selector_strict_raises(mongo_db):
    cr = CategoryRepo(mongo_db)
    vr = VideoRepo(mongo_db)
    cat = cr.create(name="desert")
    vr.create(category_id=cat.id, name="desert_0",
              source_url="https://example.com/d0.mp4", duration_seconds=10.0)
    settings = Settings(
        allow_video_reuse_within_job=False,
        mongodb_uri="mongodb://localhost/test",
        mongodb_db_name="qvg_test",
        cloudinary_cloud_name="test-cloud",
        cloudinary_api_key="test-key",
        cloudinary_api_secret="test-secret",
    )
    sel = VideoSelector(vr, settings, rng=random.Random(0))
    with pytest.raises(InsufficientCategoryContentError):
        sel.select_segments_for_duration(cat.id, target_duration=120.0)


# --- Helper -----------------------------------------------------------------

def _oid(id_str: str):
    from bson import ObjectId
    return ObjectId(id_str)


# --- Strict least-used-first (Task 1) --------------------------------------

def _selection_cfg(strict: bool) -> SelectionConfig:
    return SelectionConfig(strict_least_used=strict)


def test_strict_least_used_picks_zero_usage_first(mongo_db):
    """With 3 audios at usage=0 and 2 at usage=5, the usage=0 pool must
    be selected >= 95% of the time over 500 selections (without ever
    calling mark_used, so usage counts never change)."""
    repo = AudioRepo(mongo_db)
    zero_audios = [
        repo.create(name=f"zero_{i}", source_url=f"https://e.com/z{i}.mp3",
                    duration_seconds=200.0)
        for i in range(3)
    ]
    high_audios = [
        repo.create(name=f"high_{i}", source_url=f"https://e.com/h{i}.mp3",
                    duration_seconds=200.0)
        for i in range(2)
    ]
    # Bump the high_* audios to usage_count=5 directly.
    for a in high_audios:
        mongo_db["audios"].update_one(
            {"_id": _oid(a.id)},
            {"$set": {"usage_count": 5, "last_used_at": datetime.now(timezone.utc)}},
        )

    sel = AudioSelector(
        repo,
        rng=random.Random(2024),
        selection_cfg=_selection_cfg(strict=True),
    )

    counts = Counter(sel.select().name for _ in range(500))
    zero_total = sum(counts[a.name] for a in zero_audios)
    high_total = sum(counts[a.name] for a in high_audios)
    assert zero_total >= 475, (
        f"strict mode should pick zero-usage >=95% of the time, "
        f"got zero={zero_total}/500"
    )
    assert high_total <= 25


def test_strict_least_used_uniform_when_all_zero(mongo_db):
    """When every audio has usage=0, no single audio should dominate
    (>60% of 300 selections). Verifies variety within a tied tier."""
    repo = AudioRepo(mongo_db)
    names = [f"u_{i}" for i in range(5)]
    for n in names:
        repo.create(name=n, source_url=f"https://e.com/{n}.mp3",
                    duration_seconds=150.0)

    sel = AudioSelector(
        repo,
        rng=random.Random(7),
        selection_cfg=_selection_cfg(strict=True),
    )
    counts = Counter(sel.select().name for _ in range(300))
    for n in names:
        assert counts[n] <= 180, (
            f"audio {n!r} picked {counts[n]}/300 — exceeds 60% uniformity"
            f" threshold"
        )


def test_legacy_weighted_when_strict_disabled(mongo_db):
    """With strict_least_used=False, the old weighted-random behaviour
    is used: high-usage audios CAN be picked (just less often). We
    verify the high-usage pool is picked at least once in 500 tries
    (it would be ~0% under strict mode)."""
    repo = AudioRepo(mongo_db)
    zero_audios = [
        repo.create(name=f"z_{i}", source_url=f"https://e.com/z{i}.mp3",
                    duration_seconds=200.0)
        for i in range(3)
    ]
    high_audios = [
        repo.create(name=f"h_{i}", source_url=f"https://e.com/h{i}.mp3",
                    duration_seconds=200.0)
        for i in range(2)
    ]
    for a in high_audios:
        mongo_db["audios"].update_one(
            {"_id": _oid(a.id)},
            {"$set": {"usage_count": 5, "last_used_at": datetime.now(timezone.utc)}},
        )

    sel = AudioSelector(
        repo,
        rng=random.Random(99),
        selection_cfg=_selection_cfg(strict=False),
    )
    counts = Counter(sel.select().name for _ in range(500))
    high_total = sum(counts[a.name] for a in high_audios)
    # Under legacy weighted, the high-usage pool is disadvantaged but
    # not excluded. We expect it to be picked at least a handful of
    # times (non-zero), proving strict tiering is OFF.
    assert high_total > 0, (
        "legacy mode should still occasionally pick high-usage audios, "
        "but got 0/500"
    )


def test_strict_mode_default_is_on(mongo_db):
    """SelectionConfig() with no args must default strict_least_used=True."""
    cfg = SelectionConfig()
    assert cfg.strict_least_used is True

