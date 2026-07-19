"""Upload final MP4 videos to Cloudinary.

Called from :class:`GenerationOrchestrator._process_clip` immediately after
``video_processor.build_clip()`` succeeds. The Cloudinary ``public_id`` is
set to the execution's id (guaranteed unique), so the resulting URL is
stable and predictable.

Configuration
-------------
Read from :class:`Settings` (which reads from env vars / GitHub Actions
secrets). All three values are required; missing values raise a clear
``RuntimeError`` at upload time rather than silently producing anonymous
uploads.

Error handling
--------------
On any failure the uploader raises :class:`FFmpegExecutionError`-style
exceptions (actually ``CloudinaryUploadError``) so the orchestrator can
treat it like any other pipeline failure: mark the execution ``failed``,
don't leave a dangling local file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import cloudinary
import cloudinary.uploader
import cloudinary.api

from src.config.settings import Settings
from src.exceptions import AppBaseException
from src.utils.logger import get_logger

log = get_logger(__name__)


class CloudinaryUploadError(AppBaseException):
    """Raised when a Cloudinary upload fails or returns an unexpected response."""


@dataclass(frozen=True)
class CloudinaryUploadResult:
    """Normalised result of a Cloudinary upload."""

    secure_url: str
    public_id: str
    duration_seconds: float
    width: int
    height: int


# Module-level flag so we configure the SDK at most once per process.
_configured = False


def _configure(settings: Settings) -> None:
    global _configured
    if _configured:
        return
    if not (settings.cloudinary_cloud_name and settings.cloudinary_api_key
            and settings.cloudinary_api_secret):
        raise RuntimeError(
            "Cloudinary credentials are not configured. Set CLOUDINARY_CLOUD_NAME, "
            "CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET via env vars / GitHub secrets."
        )
    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
        secure=True,
    )
    _configured = True


def reset_config() -> None:
    """Clear the cached Cloudinary config (used by tests)."""
    global _configured
    _configured = False


def upload_video(
    local_path: Path,
    execution_id: str,
    settings: Settings,
    *,
    folder: str = "quran-video-generator/executions",
) -> CloudinaryUploadResult:
    """Upload ``local_path`` to Cloudinary and return a normalised result.

    The Cloudinary ``public_id`` is set to ``execution_id`` (no extension)
    so the same execution always maps to the same URL. Re-uploading (which
    shouldn't happen in normal flow, but might during a manual retry)
    overwrites the previous file.
    """
    _configure(settings)

    if not local_path.is_file():
        raise CloudinaryUploadError(
            f"cannot upload: local file does not exist: {local_path}"
        )

    public_id = f"{folder}/{execution_id}"
    log.info("uploading %s -> cloudinary public_id=%s", local_path, public_id)

    try:
        # Use upload_large to automatically chunk the file.
        # We explicitly set chunk_size to 20MB to bypass Nginx 413 Request Entity Too Large errors.
        resp = cloudinary.uploader.upload_large(
            str(local_path),
            resource_type="video",
            public_id=public_id,
            overwrite=True,
            invalidate=False,
            chunk_size=20 * 1024 * 1024,  # Force des chunks de 20 Mo
        )
    except Exception as exc:
        raise CloudinaryUploadError(
            f"Cloudinary upload failed for {local_path}: {exc}",
            cause=exc,
        ) from exc

    if not isinstance(resp, dict) or "secure_url" not in resp:
        raise CloudinaryUploadError(
            f"Cloudinary upload returned unexpected response: {resp!r}"
        )

    # Cloudinary returns duration/width/height for video resources.
    duration = float(resp.get("duration") or 0.0)
    width = int(resp.get("width") or 0)
    height = int(resp.get("height") or 0)

    log.info(
        "cloudinary upload ok: url=%s dur=%.2fs %dx%d",
        resp["secure_url"], duration, width, height,
    )

    return CloudinaryUploadResult(
        secure_url=resp["secure_url"],
        public_id=resp.get("public_id") or public_id,
        duration_seconds=duration,
        width=width,
        height=height,
    )


def delete_video(public_id: str, settings: Settings) -> bool:
    """Delete a video from Cloudinary by public_id. Returns True on success."""
    _configure(settings)
    try:
        cloudinary.api.delete_resources([public_id], resource_type="video")
        return True
    except Exception as exc:
        log.warning("cloudinary delete failed for %s: %s", public_id, exc)
        return False


__all__ = [
    "CloudinaryUploadError",
    "CloudinaryUploadResult",
    "upload_video",
    "delete_video",
    "reset_config",
]
