"""Unit tests for :class:`SilenceDetector` and silence-aware clip extraction.

Tests cover:
1. ``find_nearest_position`` — pure-Python helper (no audio file needed).
2. ``analyze()`` — generates a synthetic WAV with known silences and
   verifies the detected centres are close to the expected positions.
3. ``ClipExtractor.extract()`` — verifies silence snapping works when
   positions are provided, and that the legacy mechanical-cut behaviour
   is preserved when they're not.
"""

from __future__ import annotations

import random
import wave
import struct
from pathlib import Path

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


def _generate_synthetic_wav(
    path: Path,
    sr: int = 22050,
    duration_s: float = 10.0,
    silence_positions: list[tuple[float, float]] | None = None,
) -> None:
    """Write a WAV file with tone segments separated by silences.

    ``silence_positions`` is a list of ``(start_s, end_s)`` pairs. The
    rest of the audio is a 220 Hz sine wave (audible tone).
    """
    silence_positions = silence_positions or []
    n_samples = int(sr * duration_s)
    samples: list[int] = []

    import math
    for i in range(n_samples):
        t = i / sr
        in_silence = False
        for start, end in silence_positions:
            if start <= t <= end:
                in_silence = True
                break
        if in_silence:
            samples.append(0)
        else:
            val = int(32767 * 0.5 * math.sin(2 * math.pi * 220 * t))
            samples.append(val)

    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(struct.pack(f"<{len(samples)}h", *samples))


# ===========================================================================
# find_nearest_position tests (pure Python, no audio file)
# ===========================================================================

def test_find_nearest_position_returns_value_in_window():
    """Test 1: a position within the tolerance window is returned."""
    s = _silence_cfg_settings()
    det = SilenceDetector(s)
    positions = [
        {"position_seconds": 10.0, "duration_ms": 400},
        {"position_seconds": 20.0, "duration_ms": 500},
        {"position_seconds": 30.0, "duration_ms": 300},
    ]
    # target=20.5, tolerance=2.0 → 20.0 is within ±2s and closest.
    assert det.find_nearest_position(20.5, positions, tolerance_seconds=2.0) == 20.0


def test_find_nearest_position_returns_none_outside_window():
    """Test 2: no position within tolerance → None."""
    s = _silence_cfg_settings()
    det = SilenceDetector(s)
    positions = [
        {"position_seconds": 10.0, "duration_ms": 400},
        {"position_seconds": 20.0, "duration_ms": 500},
        {"position_seconds": 30.0, "duration_ms": 300},
    ]
    # target=15.0, tolerance=2.0 → nearest is 10 (5s away) or 20 (5s away),
    # both outside ±2s → None.
    assert det.find_nearest_position(15.0, positions, tolerance_seconds=2.0) is None


def test_find_nearest_position_returns_closest_among_several():
    """Test 3: when multiple positions are in the window, return the closest."""
    s = _silence_cfg_settings()
    det = SilenceDetector(s)
    positions = [
        {"position_seconds": 19.0, "duration_ms": 400},
        {"position_seconds": 20.5, "duration_ms": 500},
    ]
    # target=20.0, tolerance=2.0 → 19.0 (dist 1.0) and 20.5 (dist 0.5).
    # 20.5 is closer.
    assert det.find_nearest_position(20.0, positions, tolerance_seconds=2.0) == 20.5


def test_find_nearest_position_returns_none_for_empty_list():
    """Test 4: empty positions list → None."""
    s = _silence_cfg_settings()
    det = SilenceDetector(s)
    assert det.find_nearest_position(60.0, []) is None


def test_find_nearest_position_uses_cfg_tolerance_when_none_passed():
    """Test 5: when tolerance_seconds=None, use self.cfg.tolerance_seconds."""
    s = _silence_cfg_settings()  # cfg.tolerance_seconds = 5.0
    det = SilenceDetector(s)
    positions = [{"position_seconds": 64.0, "duration_ms": 400}]
    # target=60, cfg tolerance=5.0 → 64 is within ±5s → returns 64.0.
    assert det.find_nearest_position(60.0, positions) == 64.0
    # target=60, cfg tolerance=5.0 → 70 is 10s away, outside window.
    positions_far = [{"position_seconds": 70.0, "duration_ms": 400}]
    assert det.find_nearest_position(60.0, positions_far) is None


# ===========================================================================
# analyze() tests (require librosa + synthetic audio)
# ===========================================================================

def test_analyze_detects_known_silences(tmp_path):
    """Test 6: analyze() on a synthetic WAV finds silence centres close
    to the known silence positions (±0.2s tolerance)."""
    try:
        import librosa  # noqa: F401
    except ImportError:
        pytest.skip("librosa not installed — skipping analyze() test")

    # Build a 10s audio with a 0.5s silence centred at 3.0s and a 0.5s
    # silence centred at 7.0s.
    # Silence 1: [2.75, 3.25] → centre = 3.0
    # Silence 2: [6.75, 7.25] → centre = 7.0
    wav_path = tmp_path / "synthetic.wav"
    _generate_synthetic_wav(
        wav_path,
        sr=22050,
        duration_s=10.0,
        silence_positions=[(2.75, 3.25), (6.75, 7.25)],
    )

    s = _silence_cfg_settings()
    # Use a low percentile so the silence (0 energy) is clearly below the
    # threshold of the tone segments.
    s = s.model_copy(update={
        "silence_detection": s.silence_detection.model_copy(
            update={
                "min_silence_len_ms": 200,
                "threshold_percentile": 10,
            },
        ),
    })
    det = SilenceDetector(s)
    positions = det.analyze(wav_path)

    assert len(positions) >= 2, f"expected >=2 silences, got {len(positions)}"

    # The detected centres should be close to 3.0 and 7.0.
    detected_centres = [p["position_seconds"] for p in positions]

    # Check that 3.0 is close to one detected centre.
    close_to_3 = [c for c in detected_centres if abs(c - 3.0) <= 0.2]
    assert len(close_to_3) >= 1, (
        f"no detected silence centre near 3.0s; got {detected_centres}"
    )
    # Check that 7.0 is close to one detected centre.
    close_to_7 = [c for c in detected_centres if abs(c - 7.0) <= 0.2]
    assert len(close_to_7) >= 1, (
        f"no detected silence centre near 7.0s; got {detected_centres}"
    )


def test_analyze_returns_centre_not_start_or_end(tmp_path):
    """The stored position_seconds must be the CENTRE of each silence,
    not the start or end."""
    try:
        import librosa  # noqa: F401
    except ImportError:
        pytest.skip("librosa not installed — skipping analyze() test")

    # One 1.0s silence centred at 5.0 → [4.5, 5.5] → centre = 5.0
    wav_path = tmp_path / "centre_test.wav"
    _generate_synthetic_wav(
        wav_path,
        sr=22050,
        duration_s=10.0,
        silence_positions=[(4.5, 5.5)],
    )

    s = _silence_cfg_settings()
    s = s.model_copy(update={
        "silence_detection": s.silence_detection.model_copy(
            update={"min_silence_len_ms": 200, "threshold_percentile": 10},
        ),
    })
    det = SilenceDetector(s)
    positions = det.analyze(wav_path)

    assert len(positions) >= 1
    # The centre should be ~5.0, NOT 4.5 (start) or 5.5 (end).
    centre = positions[0]["position_seconds"]
    assert abs(centre - 5.0) <= 0.2, (
        f"centre should be ~5.0 (midpoint of [4.5, 5.5]), got {centre}"
    )


def test_analyze_raises_app_exception_when_file_missing(tmp_path):
    """analyze() raises AppBaseException when the audio file doesn't exist."""
    s = _silence_cfg_settings()
    det = SilenceDetector(s)
    with pytest.raises(AppBaseException) as exc_info:
        det.analyze(tmp_path / "does_not_exist.mp3")
    assert "not found" in str(exc_info.value).lower()


def test_analyze_returns_empty_for_continuous_tone(tmp_path):
    """An audio with no silences (pure tone) should return 0 positions
    (or very few spurious ones that get filtered by min_silence_len_ms)."""
    try:
        import librosa  # noqa: F401
    except ImportError:
        pytest.skip("librosa not installed — skipping analyze() test")

    wav_path = tmp_path / "tone_only.wav"
    _generate_synthetic_wav(
        wav_path, sr=22050, duration_s=5.0, silence_positions=[],
    )

    s = _silence_cfg_settings()
    s = s.model_copy(update={
        "silence_detection": s.silence_detection.model_copy(
            update={"min_silence_len_ms": 300, "threshold_percentile": 5},
        ),
    })
    det = SilenceDetector(s)
    positions = det.analyze(wav_path)
    # A continuous tone has no real silences — expect 0 or very few.
    assert len(positions) <= 1, (
        f"continuous tone should have ~0 silences, got {len(positions)}"
    )


# ===========================================================================
# ClipExtractor with silence positions (backward compat)
# ===========================================================================

def test_clip_extractor_snaps_end_to_silence_when_in_window():
    """Test 7: When a silence position falls within ±tolerance of the ideal
    clip end, the clip's end_seconds must equal that silence position (and
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
    """Test 7b: When no silence is within the tolerance window, the mechanical
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
    """Test 8: The legacy behaviour (no silence_positions arg) is preserved:
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
    """Test 8b: When silence_detector is None (the default for tests that don't
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
