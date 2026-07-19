"""Filesystem helpers.

Responsibilities:
* Safe scanning of audio/video folders (skip unreadable files, return paths).
* Temp-file & temp-directory lifecycle management with guaranteed cleanup.
* Path normalisation helpers.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import tempfile
from pathlib import Path
from typing import Iterator

from src.utils.logger import get_logger

log = get_logger(__name__)

AUDIO_EXTENSIONS = {".mp3", ".m4a", ".wav", ".aac", ".flac"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}


def scan_audio_files(audios_dir: str | os.PathLike) -> list[Path]:
    """Return a sorted list of audio file paths in ``audios_dir``."""
    return _scan_dir(audios_dir, AUDIO_EXTENSIONS)


def scan_video_files(videos_dir: str | os.PathLike) -> list[Path]:
    """Return a list of all video file paths anywhere under ``videos_dir``."""
    return _scan_dir_recursive(videos_dir, VIDEO_EXTENSIONS)


def scan_category_dirs(videos_dir: str | os.PathLike) -> dict[str, Path]:
    """Map ``category_name -> directory`` for every sub-dir of ``videos_dir``.

    A category is any immediate child directory of ``videos_dir`` that
    contains at least one video file.
    """
    root = Path(videos_dir)
    if not root.is_dir():
        return {}
    mapping: dict[str, Path] = {}
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        if any(_iter_files_by_ext(child, VIDEO_EXTENSIONS)):
            mapping[child.name] = child
    return mapping


def videos_in_category(category_dir: str | os.PathLike) -> list[Path]:
    """List video files for a single category directory."""
    return _scan_dir(category_dir, VIDEO_EXTENSIONS)


# --- Temp helpers -----------------------------------------------------------

@contextlib.contextmanager
def temp_workdir(prefix: str = "qvg_", base_dir: str | os.PathLike | None = None) -> Iterator[Path]:
    """Context manager yielding a temporary directory.

    The directory is removed recursively on exit, even if errors occur.
    """
    path = Path(tempfile.mkdtemp(prefix=prefix, dir=str(base_dir) if base_dir else None))
    log.debug("created temp dir: %s", path)
    try:
        yield path
    finally:
        cleanup_path(path)


def cleanup_path(p: str | os.PathLike) -> None:
    """Recursively remove a path, ignoring missing files."""
    path = Path(p)
    if not path.exists():
        return
    try:
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)
        log.debug("cleaned up: %s", path)
    except OSError as exc:  # pragma: no cover
        log.warning("failed to clean up %s: %s", path, exc)


def ensure_dir(p: str | os.PathLike) -> Path:
    """Create the directory (and parents) if needed and return it."""
    path = Path(p)
    path.mkdir(parents=True, exist_ok=True)
    return path


# --- Internals --------------------------------------------------------------

def _scan_dir(directory: str | os.PathLike, exts: set[str]) -> list[Path]:
    root = Path(directory)
    if not root.is_dir():
        log.warning("directory does not exist: %s", root)
        return []
    return sorted(
        p for p in _iter_files_by_ext(root, exts)
    )


def _scan_dir_recursive(directory: str | os.PathLike, exts: set[str]) -> list[Path]:
    root = Path(directory)
    if not root.is_dir():
        log.warning("directory does not exist: %s", root)
        return []
    out: list[Path] = []
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            p = Path(dirpath) / f
            if p.suffix.lower() in exts:
                out.append(p)
    out.sort()
    return out


def _iter_files_by_ext(directory: Path, exts: set[str]) -> Iterator[Path]:
    for entry in directory.iterdir():
        if entry.is_file() and entry.suffix.lower() in exts:
            yield entry


__all__ = [
    "AUDIO_EXTENSIONS",
    "VIDEO_EXTENSIONS",
    "scan_audio_files",
    "scan_video_files",
    "scan_category_dirs",
    "videos_in_category",
    "temp_workdir",
    "cleanup_path",
    "ensure_dir",
]
