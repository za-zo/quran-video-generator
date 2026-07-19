"""Custom exception hierarchy for the Quran Video Generator.

The hierarchy is rooted at :class:`AppBaseException` so callers can either
catch a single, application-wide base class or one of the more specific
subclasses. FFmpeg execution failures are translated into the most appropriate
custom exception inside :mod:`src.utils.ffmpeg_utils`.
"""

from __future__ import annotations


class AppBaseException(Exception):
    """Root exception for the application.

    Every custom exception inherits from this so callers can use a single
    ``except AppBaseException`` clause to handle any application-level error
    while still letting unexpected bugs bubble up.
    """

    def __init__(self, message: str = "", *, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.cause = cause

    def __str__(self) -> str:  # pragma: no cover - trivial
        if self.cause is not None:
            return f"{self.message} (caused by: {self.cause!r})"
        return self.message


# --- Media-related errors ---------------------------------------------------

class InsufficientAudioDurationError(AppBaseException):
    """Raised when an audio file is shorter than the configured clip duration."""


class InsufficientCategoryContentError(AppBaseException):
    """Raised when a category cannot provide enough video footage to fill a clip.

    Only raised when ``allow_video_reuse_within_job`` is ``False``. When reuse
    is allowed, the selector logs a warning instead and continues.
    """


class CorruptedMediaError(AppBaseException):
    """Raised when an input audio/video file fails ffprobe validation."""


class UnsupportedCodecError(AppBaseException):
    """Raised when FFmpeg reports an unsupported / unknown codec."""


# --- FFmpeg / external tool errors -----------------------------------------

class FFmpegExecutionError(AppBaseException):
    """Raised when an FFmpeg subprocess call exits with a non-zero status.

    The original stderr is preserved in :attr:`stderr` for debugging.
    """

    def __init__(
        self,
        message: str,
        *,
        cmd: list[str] | None = None,
        stderr: str | None = None,
        returncode: int | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, cause=cause)
        self.cmd = cmd or []
        self.stderr = stderr or ""
        self.returncode = returncode


# --- Selection / orchestration errors --------------------------------------

class NoAvailableCategoryError(AppBaseException):
    """Raised when no category can be selected (e.g. all on cooldown)."""


class DatabaseIntegrityError(AppBaseException):
    """Raised when an inconsistency is detected in the database state."""


__all__ = [
    "AppBaseException",
    "InsufficientAudioDurationError",
    "InsufficientCategoryContentError",
    "CorruptedMediaError",
    "UnsupportedCodecError",
    "FFmpegExecutionError",
    "NoAvailableCategoryError",
    "DatabaseIntegrityError",
]
