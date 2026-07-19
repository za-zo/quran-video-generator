"""Centralised logging setup.

Provides a single ``get_logger(name)`` factory that returns a logger writing
to both the console (stderr) and a rotating file. Configuration is taken from
:class:`src.config.settings.LoggingConfig` – nothing is hardcoded.
"""

from __future__ import annotations

import logging
import sys
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


__all__ = ["get_logger", "reset_logging"]
