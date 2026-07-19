"""Thin subprocess wrappers around ffmpeg / ffprobe.

Goals
-----
* Build explicit, debuggable FFmpeg command lines (no ffmpeg-python magic).
* Capture stderr and translate well-known failure signatures into the
  matching custom exceptions (see :mod:`src.exceptions`).
* Wrap every FFmpeg call with one retry on transient failure.
* Provide reusable primitives: probe duration, validate media, mute, concat
  (demuxer or filter_complex), trim, merge audio+video.

This module deliberately stays free of any application logic – it is purely a
controlled wrapper over the FFmpeg binary.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from src.exceptions import (
    CorruptedMediaError,
    FFmpegExecutionError,
    UnsupportedCodecError,
)
from src.utils.logger import get_logger

log = get_logger(__name__)

# Failure-signature regexes -> exception type. Order matters: more specific
# patterns first.
_FAILURE_SIGNATURES: list[tuple[re.Pattern[str], type[Exception]]] = [
    (re.compile(r"Invalid data found when processing input", re.I), CorruptedMediaError),
    (re.compile(r"moov atom not found", re.I), CorruptedMediaError),
    (re.compile(r"End of file|premature EOF", re.I), CorruptedMediaError),
    (re.compile(r"Not enough memory", re.I), FFmpegExecutionError),
    (re.compile(r"Unknown codec|Decoder .* not found|could not find tag", re.I),
     UnsupportedCodecError),
    (re.compile(r"No such file or directory", re.I), CorruptedMediaError),
    (re.compile(r"Permission denied", re.I), CorruptedMediaError),
]


@dataclass(frozen=True)
class MediaProbe:
    """Result of probing a media file with ffprobe."""

    path: Path
    duration_seconds: float
    has_audio: bool
    has_video: bool
    video_codec: str | None
    audio_codec: str | None
    width: int | None
    height: int | None
    fps: float | None

    @property
    def exists_and_valid(self) -> bool:
        return self.duration_seconds > 0


def _resolve_binary(name: str) -> str:
    """Return the absolute path to ``name`` or the name itself if on PATH."""
    path = shutil.which(name)
    if path is None:
        # Fall back to the bare name; subprocess will raise FileNotFoundError,
        # which we translate into a friendly error message.
        return name
    return path


FFMPEG_BIN = _resolve_binary("ffmpeg")
FFPROBE_BIN = _resolve_binary("ffprobe")


# --- subprocess execution ---------------------------------------------------

def _run_subprocess(
    cmd: list[str],
    *,
    retries: int = 1,
) -> subprocess.CompletedProcess[str]:
    """Run ``cmd`` capturing stdout/stderr.

    Retries once on any non-zero exit, after a short sleep. Translates the
    second failure into the appropriate custom exception based on stderr
    pattern matching.
    """
    log.debug("exec: %s", " ".join(cmd))
    attempt = 0
    last_exc: Exception | None = None
    while attempt <= retries:
        try:
            result = subprocess.run(
                cmd,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except FileNotFoundError as exc:
            # ffmpeg/ffprobe binary missing – not transient.
            raise FFmpegExecutionError(
                f"required binary not found: {cmd[0]!r}",
                cmd=cmd,
                stderr="",
                returncode=None,
                cause=exc,
            ) from exc
        except OSError as exc:
            last_exc = exc
            attempt += 1
            if attempt <= retries:
                log.warning("transient OS error running %s: %s – retrying", cmd[0], exc)
                time.sleep(0.5)
                continue
            raise FFmpegExecutionError(
                f"OS error running {cmd[0]}: {exc}",
                cmd=cmd,
                stderr="",
                returncode=None,
                cause=exc,
            ) from exc

        if result.returncode == 0:
            return result

        last_exc = None
        stderr = result.stderr or ""
        if attempt < retries:
            attempt += 1
            log.warning(
                "ffmpeg command failed (rc=%s), retrying: %s",
                result.returncode, cmd[0],
            )
            time.sleep(0.5)
            continue

        # Final failure: classify & raise.
        for pattern, exc_type in _FAILURE_SIGNATURES:
            if pattern.search(stderr):
                raise exc_type(
                    f"{cmd[0]} failed: {pattern.pattern!r} matched",
                    cause=FFmpegExecutionError(
                        f"{cmd[0]} exited with code {result.returncode}",
                        cmd=cmd,
                        stderr=stderr,
                        returncode=result.returncode,
                    ),
                )
        raise FFmpegExecutionError(
            f"{cmd[0]} exited with code {result.returncode}",
            cmd=cmd,
            stderr=stderr,
            returncode=result.returncode,
        )

    # Unreachable, but keep mypy happy.
    raise FFmpegExecutionError(  # pragma: no cover
        "unreachable: subprocess retry loop exited without return",
        cmd=cmd,
    )


# --- ffprobe ----------------------------------------------------------------

def probe_media(path: str | os.PathLike) -> MediaProbe:
    """Probe a media file and return structured info.

    Raises :class:`CorruptedMediaError` if the file does not exist or has no
    decodable streams / zero duration.
    """
    p = Path(path)
    if not p.is_file():
        raise CorruptedMediaError(f"file does not exist: {p}")
    if os.access(p, os.R_OK) is False:
        raise CorruptedMediaError(f"file is not readable: {p}")

    cmd = [
        FFPROBE_BIN,
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(p),
    ]
    result = _run_subprocess(cmd)
    try:
        data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise CorruptedMediaError(
            f"could not parse ffprobe output for {p}",
            cause=exc,
        ) from exc

    streams = data.get("streams", []) or []
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    fmt = data.get("format", {}) or {}
    duration_str = fmt.get("duration") or (
        video_stream or {}).get("duration") or (audio_stream or {}).get("duration")
    try:
        duration = float(duration_str) if duration_str is not None else 0.0
    except (TypeError, ValueError):
        duration = 0.0

    if duration <= 0:
        raise CorruptedMediaError(
            f"media file has no valid duration: {p} (duration={duration!r})"
        )

    width = int(video_stream["width"]) if video_stream and "width" in video_stream else None
    height = int(video_stream["height"]) if video_stream and "height" in video_stream else None
    fps = _parse_fps(video_stream.get("r_frame_rate")) if video_stream else None

    return MediaProbe(
        path=p,
        duration_seconds=duration,
        has_video=video_stream is not None,
        has_audio=audio_stream is not None,
        video_codec=video_stream.get("codec_name") if video_stream else None,
        audio_codec=audio_stream.get("codec_name") if audio_stream else None,
        width=width,
        height=height,
        fps=fps,
    )


def _parse_fps(rate: str | None) -> float | None:
    if not rate or "/" not in rate:
        try:
            return float(rate) if rate else None
        except (TypeError, ValueError):
            return None
    num_str, _, den_str = rate.partition("/")
    try:
        num = float(num_str)
        den = float(den_str)
    except ValueError:
        return None
    if den == 0:
        return None
    return num / den


def validate_media(path: str | os.PathLike, *, expect_audio: bool = False,
                   expect_video: bool = False) -> MediaProbe:
    """Validate a media file via ffprobe and return the probe.

    When ``expect_audio``/``expect_video`` is set, the probe must report the
    corresponding stream or :class:`CorruptedMediaError` is raised.
    """
    probe = probe_media(path)
    if expect_audio and not probe.has_audio:
        raise CorruptedMediaError(f"file has no audio stream: {probe.path}")
    if expect_video and not probe.has_video:
        raise CorruptedMediaError(f"file has no video stream: {probe.path}")
    return probe


# --- ffmpeg operations ------------------------------------------------------

def mute_video(src: str | os.PathLike, dst: str | os.PathLike) -> Path:
    """Strip the audio track from ``src`` and write to ``dst``.

    Uses ``-c copy -an`` when possible (no re-encode) – fast and lossless.
    """
    src_path = Path(src)
    dst_path = Path(dst)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        FFMPEG_BIN, "-y", "-i", str(src_path),
        "-an", "-c:v", "copy",
        str(dst_path),
    ]
    _run_subprocess(cmd)
    return dst_path


def concat_demuxer(
    clips: Iterable[str | os.PathLike],
    dst: str | os.PathLike,
) -> Path:
    """Concatenate media files using the FFmpeg concat demuxer.

    All inputs MUST share the same codec/resolution/fps. Use
    :func:`concat_with_reencode` when they don't.
    """
    clips_list = list(clips)
    if not clips_list:
        raise FFmpegExecutionError("concat_demuxer called with no inputs")

    dst_path = Path(dst)
    dst_path.parent.mkdir(parents=True, exist_ok=True)

    listfile = dst_path.with_suffix(".concat.txt")
    with listfile.open("w", encoding="utf-8") as fh:
        for c in clips_list:
            # FFmpeg concat list uses file paths; escape single quotes.
            safe = str(Path(c).resolve()).replace("'", r"'\''")
            fh.write(f"file '{safe}'\n")

    cmd = [
        FFMPEG_BIN, "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(listfile),
        "-c", "copy",
        str(dst_path),
    ]
    try:
        _run_subprocess(cmd)
    finally:
        listfile.unlink(missing_ok=True)
    return dst_path


def concat_with_reencode(
    clips: Iterable[str | os.PathLike],
    dst: str | os.PathLike,
    *,
    width: int,
    height: int,
    fps: int,
    video_codec: str,
    audio_codec: str,
) -> Path:
    """Concatenate clips that may differ in codec/resolution/fps.

    Each input is normalised via scale+fps filter then concatenated using the
    ``concat`` filter. This is the safe fallback when the demuxer path fails.
    """
    clips_list = list(clips)
    if not clips_list:
        raise FFmpegExecutionError("concat_with_reencode called with no inputs")

    dst_path = Path(dst)
    dst_path.parent.mkdir(parents=True, exist_ok=True)

    inputs: list[str] = []
    for c in clips_list:
        inputs.extend(["-i", str(Path(c).resolve())])

    # Build filter: scale each input to WxH + set fps + concat.
    filter_parts = []
    for i in range(len(clips_list)):
        filter_parts.append(
            f"[{i}:v]scale={width}:{height}:force_original_aspect_ratio=disable,"
            f"setsar=1,fps={fps}[v{i}]"
        )
    concat_inputs = "".join(f"[v{i}]" for i in range(len(clips_list)))
    filter_parts.append(f"{concat_inputs}concat=n={len(clips_list)}:v=1:a=0[outv]")
    filter_complex = ";".join(filter_parts)

    cmd = [
        FFMPEG_BIN, "-y", *inputs,
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-c:v", video_codec,
        "-r", str(fps),
        "-pix_fmt", "yuv420p",
        "-an",
        str(dst_path),
    ]
    _run_subprocess(cmd)
    return dst_path


def trim_video(src: str | os.PathLike, dst: str | os.PathLike, *, duration: float) -> Path:
    """Trim ``src`` to ``duration`` seconds (from the start).

    Uses ``-c copy -t`` when possible for speed.
    """
    src_path = Path(src)
    dst_path = Path(dst)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        FFMPEG_BIN, "-y", "-i", str(src_path),
        "-t", f"{duration:.3f}",
        "-c", "copy",
        "-avoid_negative_ts", "make_zero",
        str(dst_path),
    ]
    _run_subprocess(cmd)
    return dst_path


def extract_audio_clip(
    src_audio: str | os.PathLike,
    dst: str | os.PathLike,
    *,
    start: float,
    duration: float,
    audio_codec: str = "aac",
) -> Path:
    """Extract a clip of ``duration`` seconds starting at ``start`` from an audio file.

    Re-encodes to ``audio_codec`` rather than using ``-c copy`` because the
    source (typically mp3) and the temp clip container (m4a/aac) usually
    differ. Re-encoding a 60s clip is fast and avoids container/codec
    incompatibilities.
    """
    src_path = Path(src_audio)
    dst_path = Path(dst)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        FFMPEG_BIN, "-y",
        "-ss", f"{start:.3f}",
        "-i", str(src_path),
        "-t", f"{duration:.3f}",
        "-c:a", audio_codec,
        "-vn",
        str(dst_path),
    ]
    _run_subprocess(cmd)
    return dst_path


def merge_audio_video(
    video: str | os.PathLike,
    audio: str | os.PathLike,
    dst: str | os.PathLike,
    *,
    video_codec: str,
    audio_codec: str,
    fps: int,
    width: int,
    height: int,
    duration: float | None = None,
) -> Path:
    """Merge a muted video with an audio file, normalising the output format.

    The video stream comes from ``video`` (which is already muted), the audio
    stream from ``audio``. Both are re-encoded to the target codec/resolution
    to guarantee consistent outputs across the batch.
    """
    video_path = Path(video)
    audio_path = Path(audio)
    dst_path = Path(dst)
    dst_path.parent.mkdir(parents=True, exist_ok=True)

    cmd: list[str] = [
        FFMPEG_BIN, "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", video_codec,
        "-c:a", audio_codec,
        "-r", str(fps),
        "-vf", f"scale={width}:{height}:force_original_aspect_ratio=disable,setsar=1",
        "-pix_fmt", "yuv420p",
        "-shortest",
    ]
    if duration is not None:
        cmd += ["-t", f"{duration:.3f}"]
    cmd.append(str(dst_path))
    _run_subprocess(cmd)
    return dst_path


__all__ = [
    "FFMPEG_BIN",
    "FFPROBE_BIN",
    "MediaProbe",
    "probe_media",
    "validate_media",
    "mute_video",
    "concat_demuxer",
    "concat_with_reencode",
    "trim_video",
    "extract_audio_clip",
    "merge_audio_video",
]
