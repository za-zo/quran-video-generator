"""Stream media files from remote URLs into a runner-local temp directory.

The Quran Video Generator pipeline no longer reads media from the local
filesystem – every audio/video file lives at a remote URL registered in
MongoDB. This module downloads exactly the files a single clip needs, just
in time, into the existing ``temp_workdir()`` so cleanup is automatic.

Design notes
------------
* Uses ``requests`` with ``stream=True`` to avoid loading the whole file
  into memory.
* Reuses the same retry-once-on-failure pattern as ``ffmpeg_utils``.
* Validates the downloaded file with ffprobe before returning, so a 200
  response that actually contains HTML (S3 error page, CDN landing page,
  etc.) is caught here instead of producing a confusing FFmpeg failure
  downstream.
* Raises :class:`CorruptedMediaError` for any failure – downloads are
  treated like any other media-acquisition step.
* Reports each successful download to :data:`pipeline_log` so the
  operator sees the file size and elapsed time inline in the run log.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

from src.exceptions import CorruptedMediaError
from src.utils.ffmpeg_utils import validate_media
from src.utils.logger import get_logger, pipeline_log

log = get_logger(__name__)

# 5 MB chunks – large enough to amortise per-call overhead, small enough
# that memory stays flat regardless of file size.
_CHUNK_SIZE = 5 * 1024 * 1024
# Generous per-request timeout: connect fast (10s), allow long reads (300s)
# so a slow CDN doesn't kill a legitimate download.
_CONNECT_TIMEOUT = 10.0
_READ_TIMEOUT = 300.0


def _filename_from_url(url: str, fallback: str = "media") -> str:
    """Best-effort extraction of a filename from a URL."""
    path = urlparse(url).path
    name = os.path.basename(path) if path else ""
    return name or fallback


def download_to_temp(
    url: str,
    dest_dir: Path,
    *,
    expected_extension: str | None = None,
    filename_hint: str | None = None,
    expect_audio: bool = False,
    expect_video: bool = False,
    retries: int = 1,
    label: str | None = None,
) -> Path:
    """Download ``url`` into ``dest_dir`` and return the local path.

    Parameters
    ----------
    url
        Remote URL to fetch.
    dest_dir
        Existing directory to write the file into.
    expected_extension
        If given, the file is saved with this extension (e.g. ``.mp4``).
        When ``None``, the extension is inferred from the URL.
    filename_hint
        Optional basename (without extension) for the local file. Useful
        when the URL itself is opaque (e.g. signed CDN URLs).
    expect_audio / expect_video
        If either is True, the downloaded file is validated with ffprobe
        for the corresponding stream before returning.
    retries
        Number of retries on transient failure (default 1 = one retry).
    label
        Optional short label passed to ``pipeline_log.download_ok`` so
        the run log reads ``⋯ Téléchargement audio ✓ 1.2 MB · 0.8s``
        instead of a raw URL. Defaults to ``expect_audio=True`` →
        ``"audio"``, ``expect_video=True`` → ``"vidéo"``.

    Raises
    ------
    CorruptedMediaError
        If the download fails, returns a non-2xx status, is empty, or
        fails ffprobe validation.
    """
    if not url:
        raise CorruptedMediaError("download_to_temp called with empty URL")

    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    name = filename_hint or _filename_from_url(url)
    if expected_extension:
        # Force the extension regardless of what the URL says.
        base = os.path.splitext(name)[0]
        name = base + expected_extension
    elif not os.path.splitext(name)[1]:
        # No extension at all – give it a generic one so ffprobe/ffmpeg
        # don't refuse to open it based on the suffix.
        name = name + ".bin"

    dst = dest_dir / name

    # Pick a sensible label for the pipeline log if none was supplied.
    if label is None:
        if expect_audio:
            label = "audio"
        elif expect_video:
            label = "vidéo"
        else:
            label = "fichier"

    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        start = time.time()
        try:
            _stream_to_file(url, dst)
            # Validate non-empty.
            size = dst.stat().st_size
            if size == 0:
                raise CorruptedMediaError(
                    f"downloaded file is empty (0 bytes) from {url}"
                )
            # Optional ffprobe check.
            if expect_audio or expect_video:
                validate_media(dst, expect_audio=expect_audio, expect_video=expect_video)
            elapsed = time.time() - start
            pipeline_log.download_ok(label, size, elapsed)
            log.debug("downloaded %s -> %s (%d bytes, %.2fs)", url, dst, size, elapsed)
            return dst
        except CorruptedMediaError as exc:
            last_exc = exc
            # Best-effort cleanup so the next attempt starts fresh.
            try:
                dst.unlink(missing_ok=True)
            except OSError:
                pass
            if attempt < retries:
                log.warning(
                    "download attempt %d/%d failed for %s: %s – retrying",
                    attempt + 1, retries + 1, url, exc,
                )
                time.sleep(0.5)
                continue
            break
        except requests.RequestException as exc:
            last_exc = exc
            try:
                dst.unlink(missing_ok=True)
            except OSError:
                pass
            if attempt < retries:
                log.warning(
                    "network error on attempt %d/%d for %s: %s – retrying",
                    attempt + 1, retries + 1, url, exc,
                )
                time.sleep(0.5)
                continue
            break

    raise CorruptedMediaError(
        f"failed to download {url} after {retries + 1} attempt(s): {last_exc}",
        cause=last_exc,
    )


def _stream_to_file(url: str, dst: Path) -> None:
    """Perform a single streaming download. Raises on any non-success."""
    try:
        with requests.get(
            url,
            stream=True,
            timeout=(_CONNECT_TIMEOUT, _READ_TIMEOUT),
            allow_redirects=True,
        ) as resp:
            if resp.status_code >= 400:
                raise CorruptedMediaError(
                    f"HTTP {resp.status_code} fetching {url}: "
                    f"{resp.reason or 'no reason'}"
                )
            with dst.open("wb") as fh:
                for chunk in resp.iter_content(chunk_size=_CHUNK_SIZE):
                    if chunk:
                        fh.write(chunk)
    except requests.RequestException as exc:
        raise CorruptedMediaError(f"network error fetching {url}: {exc}", cause=exc) from exc


__all__ = ["download_to_temp"]
