"""Unit tests for :class:`VideoProcessor` FFmpeg command construction.

These tests do NOT call real FFmpeg – they monkey-patch
:mod:`src.utils.ffmpeg_utils` to capture the command lines that would be
executed, then assert the correct flags / order are produced.
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
        db_path="/tmp/_unused.db",
    )


def _audio() -> AudioRecord:
    return AudioRecord(id=1, filename="/tmp/audio.mp3", duration_seconds=300.0)


def _clip() -> AudioClip:
    return AudioClip(audio_id=1, index=0, start_seconds=10.0, end_seconds=70.0)


def _segments() -> list[VideoSegment]:
    return [
        VideoSegment(video_id=1, filename="/tmp/v1.mp4", duration_seconds=35.0),
        VideoSegment(video_id=2, filename="/tmp/v2.mp4", duration_seconds=35.0),
    ]


# ---------------------------------------------------------------------------
# Tests – mute
# ---------------------------------------------------------------------------

def test_mute_command_uses_an_and_copy(monkeypatch, tmp_path):
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
    assert "-c:v" in cmd and cmd[cmd.index("-c:v") + 1] == "copy"
    assert "-y" in cmd
    assert str(src) in cmd


# ---------------------------------------------------------------------------
# Tests – concat (demuxer first, re-encode fallback)
# ---------------------------------------------------------------------------

def test_concat_tries_demuxer_first(monkeypatch, tmp_path):
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
    assert "-c" in cmd and cmd[cmd.index("-c") + 1] == "copy"


def test_concat_falls_back_to_reencode_on_failure(monkeypatch, tmp_path):
    calls: list[list[str]] = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        # First call (demuxer) fails, second call (re-encode) succeeds.
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


# ---------------------------------------------------------------------------
# Tests – trim
# ---------------------------------------------------------------------------

def test_trim_command(monkeypatch, tmp_path):
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
    assert "-c" in cmd and cmd[cmd.index("-c") + 1] == "copy"


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
    Path(audio.filename).write_bytes(b"")
    dst = tmp_path / "clip.m4a"
    processor.extract_audio_clip(audio, clip, dst)
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
