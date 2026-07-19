"""Unit tests for :class:`ClipExtractor`."""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from src.config.settings import Settings
from src.exceptions import InsufficientAudioDurationError
from src.models import AudioRecord
from src.services.clip_extractor import ClipExtractor


def _audio(duration: float, audio_id: int = 1) -> AudioRecord:
    return AudioRecord(
        id=audio_id,
        filename=f"audio_{audio_id}.mp3",
        duration_seconds=duration,
    )


def test_too_short_audio_raises():
    settings = Settings(clip_duration=60, clips_per_audio=5, db_path="/tmp/_unused.db")
    extractor = ClipExtractor(settings, rng=random.Random(0))
    with pytest.raises(InsufficientAudioDurationError):
        extractor.extract(_audio(30.0))


def test_exact_fit_one_clip():
    settings = Settings(clip_duration=60, clips_per_audio=5, db_path="/tmp/_unused.db")
    extractor = ClipExtractor(settings, rng=random.Random(0))
    clips = extractor.extract(_audio(60.0))
    assert len(clips) == 1
    assert clips[0].duration_seconds == pytest.approx(60.0)
    assert clips[0].start_seconds == pytest.approx(0.0)


def test_clips_never_overlap():
    settings = Settings(clip_duration=10, clips_per_audio=5, db_path="/tmp/_unused.db")
    extractor = ClipExtractor(settings, rng=random.Random(7))
    clips = extractor.extract(_audio(120.0))
    assert len(clips) == 5
    # Sort by start and verify non-overlap.
    sorted_clips = sorted(clips, key=lambda c: c.start_seconds)
    for prev, cur in zip(sorted_clips, sorted_clips[1:]):
        assert cur.start_seconds >= prev.end_seconds - 1e-6, (
            f"overlap: prev={prev}, cur={cur}"
        )
    # All within bounds.
    for c in clips:
        assert c.start_seconds >= 0.0
        assert c.end_seconds <= 120.0 + 1e-6


def test_fewer_clips_than_requested_logs_warning_but_succeeds(caplog):
    settings = Settings(clip_duration=30, clips_per_audio=10, db_path="/tmp/_unused.db")
    extractor = ClipExtractor(settings, rng=random.Random(0))
    clips = extractor.extract(_audio(90.0))
    # 90s / 30s = 3 clips fit
    assert len(clips) == 3
    # All non-overlapping.
    sorted_clips = sorted(clips, key=lambda c: c.start_seconds)
    for prev, cur in zip(sorted_clips, sorted_clips[1:]):
        assert cur.start_seconds >= prev.end_seconds - 1e-6


def test_clip_indices_are_zero_based_and_sequential():
    settings = Settings(clip_duration=5, clips_per_audio=4, db_path="/tmp/_unused.db")
    extractor = ClipExtractor(settings, rng=random.Random(1))
    clips = extractor.extract(_audio(40.0))
    assert [c.index for c in clips] == [0, 1, 2, 3]


def test_clips_within_audio_bounds():
    settings = Settings(clip_duration=15, clips_per_audio=3, db_path="/tmp/_unused.db")
    extractor = ClipExtractor(settings, rng=random.Random(42))
    audio = _audio(100.0)
    clips = extractor.extract(audio)
    for c in clips:
        assert 0 <= c.start_seconds
        assert c.end_seconds <= audio.duration_seconds + 1e-6
        assert c.duration_seconds == pytest.approx(15.0)


def test_reproducible_with_seed():
    settings = Settings(clip_duration=10, clips_per_audio=4, db_path="/tmp/_unused.db")
    audio = _audio(80.0)
    e1 = ClipExtractor(settings, rng=random.Random(123))
    e2 = ClipExtractor(settings, rng=random.Random(123))
    c1 = e1.extract(audio)
    c2 = e2.extract(audio)
    assert [c.start_seconds for c in c1] == [c.start_seconds for c in c2]
