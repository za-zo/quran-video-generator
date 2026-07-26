"""Centralised logging setup.

Provides:

* :func:`get_logger(name)` — standard logger writing to stderr + a
  rotating file. Used by modules for ``log.debug(...)`` calls only.
* :class:`PipelineLogger` — a high-level, human-readable progress
  reporter used by the orchestrator and downstream utilities. Renders
  a step-by-step visual flow on stderr (timestamps, indentation,
  success/failure marks) instead of the noisy default format.

The two coexist: ``get_logger`` is for technical DEBUG spam, while
``pipeline_log`` is the user-facing console narrative shown during a
``generate`` run.
"""

from __future__ import annotations

import logging
import sys
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from src.config.settings import LoggingConfig, get_settings

_CONFIGURED = False


def _configure_root(cfg: LoggingConfig, level: str) -> None:
    """Attach handlers to the root logger exactly once."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    log_dir = Path(cfg.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / cfg.log_file

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(level)
    # Remove any pre-existing handlers so reconfiguration in tests is clean.
    for h in list(root.handlers):
        root.removeHandler(h)

    console = logging.StreamHandler(stream=sys.stderr)
    console.setFormatter(fmt)
    console.setLevel(level)
    root.addHandler(console)

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=cfg.max_log_size_mb * 1024 * 1024,
        backupCount=cfg.backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    file_handler.setLevel(level)
    root.addHandler(file_handler)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger.

    The first call triggers one-time configuration of the root logger using
    the current :class:`Settings`. Subsequent calls reuse that configuration.

    Use this for ``log.debug(...)`` calls only — user-facing progress is
    reported via the global :data:`pipeline_log` instance.
    """
    settings = get_settings()
    _configure_root(settings.logging, settings.log_level)
    return logging.getLogger(name)


def reset_logging() -> None:
    """Clear all handlers – primarily used by tests."""
    global _CONFIGURED
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
        try:
            h.close()
        except Exception:  # pragma: no cover
            pass
    _CONFIGURED = False


# ---------------------------------------------------------------------------
# PipelineLogger — user-facing step-by-step progress reporter
# ---------------------------------------------------------------------------

_DIVIDER = "─" * 60


def _fmt_duration(seconds: float) -> str:
    """Human-readable duration: '1.2s', '4.2s', '22s', '3m 12s'."""
    if seconds < 60:
        # Show one decimal below 10s, no decimal above.
        if seconds < 10:
            return f"{seconds:.1f}s"
        return f"{int(round(seconds))}s"
    minutes = int(seconds // 60)
    secs = int(round(seconds % 60))
    return f"{minutes}m {secs:02d}s"


def _fmt_size(size_bytes: int) -> str:
    """Human-readable size: '1.2 MB', '55 MB', '320 KB'."""
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.0f} KB"
    return f"{size_bytes} B"


def _fmt_clip_duration(seconds: float) -> str:
    """Same as _fmt_duration but used for clip/audio lengths."""
    return _fmt_duration(seconds)


class PipelineLogger:
    """User-facing progress reporter for the video generation pipeline.

    All output goes to the root logger at INFO level, but with a custom
    message format that includes a timestamp and visual structure:

        08:30:53  [BATCH] Démarrage ▸ 1 audio · 5 clips · 60s chacun

    The structure is:

    * ``batch_start``     — top of the run, shows counts.
    * ``batch_divider``    — horizontal rule separating sections.
    * ``audio_selected``   — one per audio, with name + usage + duration.
    * ``download_ok``      — successful file download (size + elapsed).
    * ``silence_analyzed`` — silence positions detected for an audio.
    * ``clip_start``       — clip index + start/end seconds.
    * ``category_selected`` — chosen category name.
    * ``videos_selected``  — chosen video count + total duration.
    * ``encode_ok``        — FFmpeg encode success (elapsed).
    * ``upload_ok``        — Cloudinary upload success (URL).
    * ``clip_success``     — clip completed.
    * ``clip_failed``      — clip errored out.
    * ``batch_summary``    — end-of-run tally.
    """

    def __init__(self) -> None:
        # Use the root logger so the message goes through the configured
        # handlers (stderr + rotating file). We bypass the formatter by
        # pre-formatting the message ourselves.
        self._log = logging.getLogger("pipeline")

    # --- Internal ------------------------------------------------------------

    @staticmethod
    def _ts() -> str:
        return datetime.now().strftime("%H:%M:%S")

    def _emit(self, body: str, *, indent: int = 0) -> None:
        """Write a single line to the root logger at INFO level.

        ``indent`` is the number of leading spaces (0 = top-level, 2 = nested
        under an audio, 4 = nested under a clip).
        """
        ts = self._ts()
        prefix = " " * indent
        # The full message we hand to logging includes the timestamp +
        # indentation, so it survives the formatter's asctime. We use a
        # blank format pattern by emitting a single string with no
        # levelname/name prefixes via the message itself.
        line = f"{ts}  {prefix}{body}"
        self._log.info(line)

    # --- Public API ----------------------------------------------------------

    def batch_start(self, audio_count: int, clips_per_audio: int, clip_duration: int) -> None:
        parts = [
            f"{audio_count} audio",
            f"{clips_per_audio} clips",
            f"{clip_duration}s chacun",
        ]
        self._emit(f"[BATCH] Démarrage ▸ {' · '.join(parts)}")
        self.batch_divider()

    def batch_divider(self) -> None:
        self._emit(_DIVIDER)

    def audio_selected(
        self,
        index: int,
        total: int,
        name: str,
        usage_count: int,
        duration_s: float,
    ) -> None:
        self._emit("")
        self._emit(
            f"[AUDIO {index}/{total}] {name!r}  "
            f"usage: {usage_count} · durée: {_fmt_clip_duration(duration_s)}"
        )

    def download_ok(self, label: str, size_bytes: int, elapsed_s: float) -> None:
        self._emit(
            f"⋯ Téléchargement {label:<24} ✓  "
            f"{_fmt_size(size_bytes)} · {_fmt_duration(elapsed_s)}",
            indent=2,
        )

    def silence_analyzed(self, audio_name: str, count: int) -> None:
        self._emit(
            f"⋯ Analyse silences {audio_name!r:<24} ✓  {count} positions",
            indent=2,
        )

    def clip_start(self, index: int, total: int, start_s: float, end_s: float) -> None:
        self._emit(
            f"[CLIP {index}/{total}]  {int(start_s)}s → {int(end_s)}s",
            indent=2,
        )

    def category_selected(self, name: str, usage_count: int) -> None:
        self._emit(
            f"Catégorie : {name}  (usage: {usage_count})",
            indent=4,
        )

    def videos_selected(self, count: int, total_duration_s: float) -> None:
        self._emit(
            f"Vidéos    : {count} fichiers · {_fmt_clip_duration(total_duration_s)} total",
            indent=4,
        )

    def encode_ok(self, elapsed_s: float) -> None:
        self._emit(
            f"⋯ Encodage FFmpeg             ✓  {_fmt_duration(elapsed_s)}",
            indent=4,
        )

    def upload_ok(self, url: str, elapsed_s: float) -> None:
        # Truncate the URL so it doesn't break the layout.
        shown = url if len(url) <= 60 else url[:57] + "..."
        self._emit(
            f"⋯ Upload Cloudinary           ✓  {shown}",
            indent=4,
        )

    def clip_success(self, index: int, total: int) -> None:
        self._emit(f"✓ CLIP {index}/{total} réussi", indent=4)

    def clip_failed(self, index: int, total: int, error: str) -> None:
        # Truncate very long errors so a single clip failure doesn't
        # push the rest of the run off-screen.
        msg = str(error)
        if len(msg) > 200:
            msg = msg[:197] + "..."
        self._emit(f"✗ CLIP {index}/{total} échoué — {msg}", indent=4)

    def batch_summary(self, succeeded: int, failed: int, total_elapsed_s: float) -> None:
        self._emit("")
        self._emit(_DIVIDER)
        self._emit(
            f"[RÉSUMÉ]  ✓ {succeeded} réussis · ✗ {failed} échoués · "
            f"{_fmt_duration(total_elapsed_s)} total"
        )


# Module-level singleton imported by the orchestrator + utilities.
pipeline_log = PipelineLogger()


__all__ = [
    "PipelineLogger",
    "pipeline_log",
    "get_logger",
    "reset_logging",
]
