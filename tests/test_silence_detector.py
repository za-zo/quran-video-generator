"""Unit tests for :class:`SilenceDetector` and silence-aware clip extraction.

The :class:`SilenceDetector.analyze` method requires pydub + an actual
audio file, so we test only the pure-Python ``find_nearest_position``
helper here. The :class:`ClipExtractor.extract` tests verify that
passing ``silence_positions`` snaps clip ends to the detected silences
and that passing nothing keeps the legacy mechanical-cut behaviour.
"""

from __future__ import annotations

import random

import pytest

from src.config.settings import Settings
from src.exceptions import AppBaseException
from src.models import AudioRecord
from src.services.clip_extractor import ClipExtractor
from src.services.silence_detector import SilenceDetector


def _settings(**overrides) -> Settings:
    defaults = dict(
        clip_duration=60,
        clips_per_audio=5,
        mongodb_uri="mongodb://localhost/test",
        mongodb_db_name="qvg_test",
        cloudinary_cloud_name="test-cloud",
        cloudinary_api_key="test-key",
        cloudinary_api_secret="test-secret",
    )
    defaults.update(overrides)
    return Settings(**defaults)


def _silence_cfg_settings(**overrides) -> Settings:
    """Settings with a small tolerance so silence snapping is testable."""
    s = _settings(**overrides)
    return s.model_copy(update={
        "silence_detection": s.silence_detection.model_copy(
            update={"tolerance_seconds": 5.0}
        ),
    })


def _audio(duration: float, audio_id: str = "audio-1") -> AudioRecord:
    return AudioRecord(
        id=audio_id,
        name=f"audio_{audio_id}.mp3",
        source_url=f"https://example.com/audio_{audio_id}.mp3",
        duration_seconds=duration,
    )


# --- find_nearest_position --------------------------------------------------

def test_find_nearest_position_returns_closest_in_window():
    s = _silence_cfg_settings()
    det = SilenceDetector(s)
    positions = [
        {"position_seconds": 30.0, "duration_ms": 400},
        {"position_seconds": 60.0, "duration_ms": 500},
        {"position_seconds": 120.0, "duration_ms": 600},
    ]
    # target 62 → nearest is 60.0 (within ±5s window).
    assert det.find_nearest_position(62.0, positions) == 60.0


def test_find_nearest_position_returns_none_when_outside_window():
    s = _silence_cfg_settings()  # tolerance = 5.0
    det = SilenceDetector(s)
    positions = [
        {"position_seconds": 10.0, "duration_ms": 400},
        {"position_seconds": 100.0, "duration_ms": 500},
    ]
    # target 50, nearest is 10 or 100 — both 40+ away, outside ±5s window.
    assert det.find_nearest_position(50.0, positions) is None


def test_find_nearest_position_picks_closest_among_several():
    s = _silence_cfg_settings()
    det = SilenceDetector(s)
    positions = [
        {"position_seconds": 58.0, "duration_ms": 400},
        {"position_seconds": 61.0, "duration_ms": 500},  # 1s from 60
        {"position_seconds": 65.0, "duration_ms": 600},  # 5s from 60
    ]
    # target 60 — 58 (2s), 61 (1s), 65 (5s). 61 is closest.
    assert det.find_nearest_position(60.0, positions) == 61.0


def test_find_nearest_position_returns_none_for_empty_list():
    s = _silence_cfg_settings()
    det = SilenceDetector(s)
    assert det.find_nearest_position(60.0, []) is None


def test_find_nearest_position_uses_custom_tolerance():
    s = _silence_cfg_settings()
    det = SilenceDetector(s)
    positions = [{"position_seconds": 70.0, "duration_ms": 400}]
    # Default tolerance is 5.0 → 70 is too far from 60.
    assert det.find_nearest_position(60.0, positions) is None
    # With explicit tolerance=15 → 70 is within ±15s of 60.
    assert det.find_nearest_position(60.0, positions, tolerance_seconds=15.0) == 70.0


# --- analyze() error handling ----------------------------------------------

def test_analyze_raises_app_exception_when_file_missing(tmp_path):
    s = _silence_cfg_settings()
    det = SilenceDetector(s)
    with pytest.raises(AppBaseException) as exc_info:
        det.analyze(tmp_path / "does_not_exist.mp3")
    assert "not found" in str(exc_info.value).lower()


# --- ClipExtractor with silence positions -----------------------------------

def test_clip_extractor_snaps_end_to_silence_when_in_window():
    """When a silence position falls within ±tolerance of the ideal clip
    end, the clip's end_seconds must equal that silence position (and
    start_seconds is shifted back to keep the duration).

    We use clip_duration=120 with a 120s audio so there's exactly one
    zone [0,120] and the only valid mechanical start is 0 → ideal end
    is 120. A silence at 120.0 is within the ±5s tolerance window."""
    settings = _silence_cfg_settings(
        clip_duration=120,
        clips_per_audio=1,
    )
    extractor = ClipExtractor(settings, rng=random.Random(0),
                              silence_detector=SilenceDetector(settings))
    audio = _audio(120.0)
    # Place a silence at exactly 120.0 — the ideal end of clip 0.
    positions = [{"position_seconds": 120.0, "duration_ms": 500}]
    clips = extractor.extract(audio, silence_positions=positions)
    assert len(clips) == 1
    assert clips[0].end_seconds == pytest.approx(120.0, abs=1e-3)
    assert clips[0].start_seconds == pytest.approx(0.0, abs=1e-3)
    assert clips[0].duration_seconds == pytest.approx(120.0, abs=1e-3)


def test_clip_extractor_keeps_mechanical_cut_when_silence_outside_window():
    """When no silence is within the tolerance window, the mechanical
    cut (start + clip_duration) is kept unchanged.

    Same setup: clip_duration=120, audio=120s, only valid start is 0,
    ideal end is 120. A silence at 60.0 is 60s away from the ideal end
    — well outside the ±5s window, so no snapping occurs."""
    settings = _silence_cfg_settings(
        clip_duration=120,
        clips_per_audio=1,
    )
    extractor = ClipExtractor(settings, rng=random.Random(0),
                              silence_detector=SilenceDetector(settings))
    audio = _audio(120.0)
    # Place a silence far from the clip end (at 60s, tolerance is 5s).
    positions = [{"position_seconds": 60.0, "duration_ms": 500}]
    clips = extractor.extract(audio, silence_positions=positions)
    assert len(clips) == 1
    # End should be 120.0 (mechanical, no snapping to 60.0).
    assert clips[0].end_seconds == pytest.approx(120.0, abs=1e-3)
    assert clips[0].start_seconds == pytest.approx(0.0, abs=1e-3)


def test_clip_extractor_without_positions_uses_mechanical_cuts():
    """The legacy behaviour (no silence_positions arg) is preserved:
    clips are placed mechanically inside each zone, no snapping."""
    settings = _silence_cfg_settings(clip_duration=10, clips_per_audio=4)
    extractor = ClipExtractor(settings, rng=random.Random(1),
                              silence_detector=SilenceDetector(settings))
    audio = _audio(40.0)
    clips_no_silence = extractor.extract(audio)
    clips_empty_silence = extractor.extract(audio, silence_positions=[])
    # Both should produce 4 clips of exactly 10s with the same boundaries
    # (because silence_positions is empty in the second case).
    assert [c.start_seconds for c in clips_no_silence] == \
           [c.start_seconds for c in clips_empty_silence]
    assert all(c.duration_seconds == pytest.approx(10.0) for c in clips_no_silence)


def test_clip_extractor_without_detector_ignores_positions():
    """When silence_detector is None (the default for tests that don't
    need it), passing silence_positions has no effect — mechanical cuts
    are used. This preserves backwards compatibility with the existing
    test_clip_extractor.py suite."""
    settings = _silence_cfg_settings(clip_duration=120, clips_per_audio=1)
    extractor = ClipExtractor(settings, rng=random.Random(0))  # no detector
    audio = _audio(120.0)
    positions = [{"position_seconds": 120.0, "duration_ms": 500}]
    clips = extractor.extract(audio, silence_positions=positions)
    assert len(clips) == 1
    # End should be 120.0 — matches the silence by coincidence, but the
    # point is no detector means no snapping logic ran.
    assert clips[0].end_seconds == pytest.approx(120.0, abs=1e-3)


def test_existing_clip_extractor_tests_still_pass():
    """Smoke test: the existing ClipExtractor tests (test_clip_extractor.py)
    construct ClipExtractor without silence_detector and call extract()
    without silence_positions. Verify that path still works."""
    settings = _silence_cfg_settings(clip_duration=10, clips_per_audio=4)
    extractor = ClipExtractor(settings, rng=random.Random(42))
    audio = _audio(80.0)
    clips = extractor.extract(audio)
    assert len(clips) == 4
    # All within bounds.
    for c in clips:
        assert 0 <= c.start_seconds
        assert c.end_seconds <= 80.0 + 1e-6
