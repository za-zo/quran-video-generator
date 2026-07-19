"""Filesystem helpers.

Responsibilities:
* Temp-file & temp-directory lifecycle management with guaranteed cleanup.
* Path normalisation helpers.

The legacy folder-scanning helpers (``scan_audio_files``,
``scan_category_dirs``, ``videos_in_category``) were removed during the
cloud migration: media registration now happens exclusively through the
Next.js webapp, which writes documents directly to MongoDB. The pipeline
downloads files at runtime via :mod:`src.utils.media_downloader`.
"""

from __future__ import annotations

import contextlib
import shutil
import tempfile
from pathlib import Path
from typing import Iterator

from src.utils.logger import get_logger

log = get_logger(__name__)


# --- Temp helpers -----------------------------------------------------------

@contextlib.contextmanager
def temp_workdir(prefix: str = "qvg_", base_dir: str | None = None) -> Iterator[Path]:
    """Context manager yielding a temporary directory.

    The directory is removed recursively on exit, even if errors occur.
    """
    path = Path(tempfile.mkdtemp(prefix=prefix, dir=base_dir))
    log.debug("created temp dir: %s", path)
    try:
        yield path
    finally:
        cleanup_path(path)


def cleanup_path(p: str | Path) -> None:
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


def ensure_dir(p: str | Path) -> Path:
    """Create the directory (and parents) if needed and return it."""
    path = Path(p)
    path.mkdir(parents=True, exist_ok=True)
    return path


__all__ = [
    "temp_workdir",
    "cleanup_path",
    "ensure_dir",
]
