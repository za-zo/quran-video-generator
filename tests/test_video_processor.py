"""Unit tests for :class:`VideoProcessor` FFmpeg command construction.

These tests do NOT call real FFmpeg – they monkey-patch
:mod:`src.utils.ffmpeg_utils` to capture the command lines that would be
executed, then assert the correct flags / order are produced.

The pipeline re-encodes at every stage (mute, concat, trim) instead of
using ``-c copy``. Stream-copy was the root cause of frozen-frame and
black-flash artifacts at concat boundaries because it preserves each
source's original GOP/PTS layout and cuts only on keyframes. These tests
lock in the re-encode + closed-GOP behaviour so a regression is caught
immediately.
"""

from __future__ import annotations

import random
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.config.settings import Settings
from src.exceptions import FFmpegExecutionError
from src.models import AudioClip, AudioRecord, VideoSegment
from src.services import video_processor as vp_mod
from src.services.video_processor import VideoProcessor
from src.utils import ffmpeg_utils as ff


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _settings() -> Settings:
    return Settings(
        clip_duration=60,
        clips_per_audio=5,
        resolution="1080x1920",
        fps=30,
        video_codec="libx264",
        audio_codec="aac",
        output_dir="./output",
        temp_dir="./temp",
        mongodb_uri="mongodb://localhost/test",
        mongodb_db_name="qvg_test",
        cloudinary_cloud_name="test-cloud",
        cloudinary_api_key="test-key",
        cloudinary_api_secret="test-secret",
    )


def _audio() -> AudioRecord:
    return AudioRecord(
        id="audio-1",
        name="audio.mp3",
        source_url="https://example.com/audio.mp3",
        duration_seconds=300.0,
    )


def _clip() -> AudioClip:
    return AudioClip(audio_id="audio-1", index=0, start_seconds=10.0, end_seconds=70.0)


def _segments() -> list[VideoSegment]:
    return [
        VideoSegment(
            video_id="vid-1",
            name="v1.mp4",
            source_url="https://example.com/v1.mp4",
            duration_seconds=35.0,
        ),
        VideoSegment(
            video_id="vid-2",
            name="v2.mp4",
            source_url="https://example.com/v2.mp4",
            duration_seconds=35.0,
        ),
    ]


# ---------------------------------------------------------------------------
# Tests – mute (re-encode, not -c copy)
# ---------------------------------------------------------------------------

def test_mute_command_uses_reencode_with_closed_gop(monkeypatch, tmp_path):
    """``mute`` must re-encode with normalisation + closed-GOP flags.

    A ``-c:v copy`` here would preserve each source's original GOP and is
    the root cause of concat-boundary artifacts. We assert:
      * ``-an`` strips audio.
      * ``-c:v libx264`` (not ``copy``) re-encodes.
      * normalising ``-vf`` (scale + setsar + fps) is present.
      * closed-GOP flags (``-g``, ``-keyint_min``, ``-sc_threshold 0``,
        ``-flags +cgop``) are present.
    """
    captured: list[list[str]] = []
    monkeypatch.setattr(ff, "_run_subprocess", lambda cmd, **kw: captured.append(cmd) or MagicMock(returncode=0, stdout="", stderr=""))
    settings = _settings()
    processor = VideoProcessor(settings)
    src = tmp_path / "v.mp4"
    src.write_bytes(b"")
    processor.mute(src, tmp_path)
    assert captured, "no command executed"
    cmd = captured[0]
    assert cmd[0] == ff.FFMPEG_BIN
    assert "-an" in cmd
    assert "-y" in cmd
    assert str(src) in cmd
    # Re-encode, not stream-copy.
    assert "-c:v" in cmd and cmd[cmd.index("-c:v") + 1] == "libx264"
    assert "-copy" not in cmd
    # Normalising filter chain.
    assert "-vf" in cmd
    vf = cmd[cmd.index("-vf") + 1]
    assert "scale=1080:1920" in vf
    assert "setsar=1" in vf
    assert "fps=30" in vf
    # Pixel format.
    assert "-pix_fmt" in cmd and cmd[cmd.index("-pix_fmt") + 1] == "yuv420p"
    # Closed-GOP flags.
    assert "-g" in cmd and cmd[cmd.index("-g") + 1] == "30"
    assert "-keyint_min" in cmd and cmd[cmd.index("-keyint_min") + 1] == "30"
    assert "-sc_threshold" in cmd and cmd[cmd.index("-sc_threshold") + 1] == "0"
    assert "-flags" in cmd and cmd[cmd.index("-flags") + 1] == "+cgop"


# ---------------------------------------------------------------------------
# Tests – concat (demuxer first, filter_complex fallback; both re-encode)
# ---------------------------------------------------------------------------

def test_concat_tries_demuxer_first_with_reencode(monkeypatch, tmp_path):
    """Demuxer path must re-encode (NOT ``-c copy``) with closed GOP.

    The previous ``-f concat -c copy`` recipe appended encoded packets
    without rebuilding GOP or fixing PTS/DTS at the boundary, producing
    frozen last frames and black flashes.
    """
    captured: list[list[str]] = []
    monkeypatch.setattr(ff, "_run_subprocess", lambda cmd, **kw: captured.append(cmd) or MagicMock(returncode=0, stdout="", stderr=""))
    settings = _settings()
    processor = VideoProcessor(settings)
    clips = [tmp_path / "a.mp4", tmp_path / "b.mp4"]
    for c in clips:
        c.write_bytes(b"")
    dst = tmp_path / "out.mp4"
    processor.concat_clips(clips, dst)
    assert captured
    cmd = captured[0]
    assert "-f" in cmd and cmd[cmd.index("-f") + 1] == "concat"
    assert "-safe" in cmd and cmd[cmd.index("-safe") + 1] == "0"
    # Must re-encode, not stream-copy.
    assert "-c:v" in cmd and cmd[cmd.index("-c:v") + 1] == "libx264"
    assert "-c" not in cmd or cmd.index("-c:v") < cmd.index("-c") if "-c" in cmd else True
    # Normalising filter chain.
    assert "-vf" in cmd
    vf = cmd[cmd.index("-vf") + 1]
    assert "scale=1080:1920" in vf
    assert "fps=30" in vf
    # Closed-GOP flags.
    assert "-g" in cmd and cmd[cmd.index("-g") + 1] == "30"
    assert "-flags" in cmd and cmd[cmd.index("-flags") + 1] == "+cgop"
    # No audio in concat intermediate.
    assert "-an" in cmd


def test_concat_falls_back_to_filter_complex_on_failure(monkeypatch, tmp_path):
    """When demuxer fails, fallback uses ``filter_complex`` + scale + concat."""
    calls: list[list[str]] = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        # First call (demuxer) fails, second call (filter_complex) succeeds.
        if len(calls) == 1:
            raise FFmpegExecutionError("demuxer failed", cmd=cmd, stderr="Invalid data found")
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(ff, "_run_subprocess", fake_run)
    settings = _settings()
    processor = VideoProcessor(settings)
    clips = [tmp_path / "a.mp4", tmp_path / "b.mp4"]
    for c in clips:
        c.write_bytes(b"")
    dst = tmp_path / "out.mp4"
    processor.concat_clips(clips, dst)
    assert len(calls) == 2
    # Second command must use filter_complex + scale.
    assert "-filter_complex" in calls[1]
    fc = calls[1][calls[1].index("-filter_complex") + 1]
    assert "scale=1080:1920" in fc
    assert "concat=n=2" in fc
    assert "fps=30" in fc
    # Re-encode with closed GOP in fallback too.
    assert "-c:v" in calls[1] and calls[1][calls[1].index("-c:v") + 1] == "libx264"
    assert "-g" in calls[1] and calls[1][calls[1].index("-g") + 1] == "30"
    assert "-flags" in calls[1] and calls[1][calls[1].index("-flags") + 1] == "+cgop"


# ---------------------------------------------------------------------------
# Tests – trim (re-encode, not -c copy)
# ---------------------------------------------------------------------------

def test_trim_command_uses_reencode_for_frame_accuracy(monkeypatch, tmp_path):
    """``trim`` must re-encode for frame-accurate cutting + fresh closed GOP.

    ``-c copy -t`` can only cut on the nearest keyframe and inherits the
    source's GOP layout, re-introducing concat-boundary artifacts.
    """
    captured: list[list[str]] = []
    monkeypatch.setattr(ff, "_run_subprocess", lambda cmd, **kw: captured.append(cmd) or MagicMock(returncode=0, stdout="", stderr=""))
    settings = _settings()
    processor = VideoProcessor(settings)
    src = tmp_path / "in.mp4"; src.write_bytes(b"")
    dst = tmp_path / "out.mp4"
    processor.trim_to_duration(src, dst, duration=42.5)
    cmd = captured[0]
    assert "-t" in cmd
    assert cmd[cmd.index("-t") + 1] == "42.500"
    # Re-encode, not stream-copy.
    assert "-c:v" in cmd and cmd[cmd.index("-c:v") + 1] == "libx264"
    assert "-copy" not in cmd
    # Normalising filter chain.
    assert "-vf" in cmd
    vf = cmd[cmd.index("-vf") + 1]
    assert "scale=1080:1920" in vf
    assert "fps=30" in vf
    # Closed-GOP flags so the trimmed output starts on a clean keyframe.
    assert "-g" in cmd and cmd[cmd.index("-g") + 1] == "30"
    assert "-flags" in cmd and cmd[cmd.index("-flags") + 1] == "+cgop"
    # PTS reset so the trimmed clip starts at zero.
    assert "-avoid_negative_ts" in cmd
    assert cmd[cmd.index("-avoid_negative_ts") + 1] == "make_zero"
    # No audio in trim intermediate (video is already muted upstream).
    assert "-an" in cmd


# ---------------------------------------------------------------------------
# Tests – extract_audio_clip
# ---------------------------------------------------------------------------

def test_extract_audio_clip_command(monkeypatch, tmp_path):
    captured: list[list[str]] = []
    monkeypatch.setattr(ff, "_run_subprocess", lambda cmd, **kw: captured.append(cmd) or MagicMock(returncode=0, stdout="", stderr=""))
    settings = _settings()
    processor = VideoProcessor(settings)
    audio = _audio()
    clip = _clip()
    # extract_audio_clip takes the local audio file path (already downloaded).
    audio_path = tmp_path / "audio.mp3"
    audio_path.write_bytes(b"")
    dst = tmp_path / "clip.m4a"
    processor.extract_audio_clip(audio_path, clip, dst)
    cmd = captured[0]
    assert "-ss" in cmd and cmd[cmd.index("-ss") + 1] == "10.000"
    assert "-t" in cmd and cmd[cmd.index("-t") + 1] == "60.000"
    # Must re-encode (NOT -c copy) because source mp3 -> m4a/aac container.
    assert "-c:a" in cmd and cmd[cmd.index("-c:a") + 1] == "aac"
    assert "-vn" in cmd
    assert "-c" not in cmd or cmd.index("-c:a") < cmd.index("-c") if "-c" in cmd else True


# ---------------------------------------------------------------------------
# Tests – merge_audio_video
# ---------------------------------------------------------------------------

def test_merge_command(monkeypatch, tmp_path):
    captured: list[list[str]] = []
    monkeypatch.setattr(ff, "_run_subprocess", lambda cmd, **kw: captured.append(cmd) or MagicMock(returncode=0, stdout="", stderr=""))
    settings = _settings()
    processor = VideoProcessor(settings)
    v = tmp_path / "v.mp4"; v.write_bytes(b"")
    a = tmp_path / "a.aac"; a.write_bytes(b"")
    dst = tmp_path / "out.mp4"
    processor.merge_audio_video(v, a, dst, duration=60.0)
    cmd = captured[0]
    assert "-map" in cmd and "0:v:0" in cmd
    assert "-map" in cmd and "1:a:0" in cmd
    assert "-c:v" in cmd and cmd[cmd.index("-c:v") + 1] == "libx264"
    assert "-c:a" in cmd and cmd[cmd.index("-c:a") + 1] == "aac"
    assert "-r" in cmd and cmd[cmd.index("-r") + 1] == "30"
    assert "-vf" in cmd and "scale=1080:1920" in cmd[cmd.index("-vf") + 1]
    assert "-shortest" in cmd
    assert "-t" in cmd and cmd[cmd.index("-t") + 1] == "60.000"
