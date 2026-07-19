"""Application configuration.

Loads from (in order of increasing precedence):
1. Built-in defaults defined in this module.
2. ``config.yaml`` (or any YAML file specified via the ``QVG_CONFIG_FILE``
   environment variable).
3. Environment variables / ``.env`` file (Pydantic ``BaseSettings`` handles
   this automatically).

No configuration value is hardcoded anywhere else in the codebase – every
module receives a :class:`Settings` instance via dependency injection.

Cloud-native settings
---------------------
The pipeline runs in GitHub Actions and reads from / writes to cloud
services exclusively:
  * ``mongodb_uri`` + ``mongodb_db_name``: persistent single source of truth
    for audios / categories / videos / executions.
  * ``cloudinary_cloud_name`` / ``cloudinary_api_key`` /
    ``cloudinary_api_secret``: where final MP4 outputs are uploaded.

All four Cloudinary values plus ``mongodb_uri`` are required at runtime;
missing values raise a clear configuration error rather than silently
falling back to placeholders.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# --- Nested config models ---------------------------------------------------

class SelectionConfig(BaseModel):
    """Tuning knobs for the weighted selection algorithm."""

    recency_decay_minutes: int = Field(
        default=1440, gt=0, description="Larger = recency penalty decays slower."
    )
    usage_weight: float = Field(default=1.0, ge=0.0)
    recency_weight: float = Field(default=1.0, ge=0.0)


class LoggingConfig(BaseModel):
    """Rotating-file + console logging configuration."""

    log_dir: str = "./logs"
    log_file: str = "app.log"
    max_log_size_mb: int = Field(default=5, gt=0)
    backup_count: int = Field(default=5, ge=0)


# --- Top-level settings -----------------------------------------------------

class Settings(BaseSettings):
    """Top-level application settings.

    All fields can be supplied via:
      * a YAML config file (``config.yaml`` by default)
      * environment variables (case-insensitive) or a ``.env`` file
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Clip generation
    clip_duration: int = Field(default=60, gt=0)
    clips_per_audio: int = Field(default=5, gt=0)

    # Output video technical params
    resolution: str = Field(default="1080x1920")
    fps: int = Field(default=30, gt=0)
    video_codec: str = Field(default="libx264")
    video_preset: str = Field(default="veryfast") # Ajout du preset très rapide
    audio_codec: str = Field(default="aac")

    # Paths (local-only: temp working dir for FFmpeg intermediates,
    # output dir for the final MP4 before Cloudinary upload)
    output_dir: str = "./output"
    temp_dir: str = "./temp"

    # Selection behaviour
    category_cooldown: int = Field(default=3, ge=0)
    allow_video_reuse_within_job: bool = True

    # Logging
    log_level: str = "INFO"

    # --- Cloud-native infrastructure ----------------------------------------

    # MongoDB Atlas – single source of truth for all metadata.
    # Required: a clear error is raised at startup if missing.
    mongodb_uri: str = Field(default="", description="MongoDB Atlas connection string")
    mongodb_db_name: str = Field(default="quran_video_generator")

    # Cloudinary – where final MP4s are uploaded.
    cloudinary_cloud_name: str = Field(default="")
    cloudinary_api_key: str = Field(default="")
    cloudinary_api_secret: str = Field(default="")

    # GitHub Actions run ID (set automatically by the workflow; empty when
    # running locally). Stored on each execution document for traceability.
    github_run_id: str = Field(default="")

    # Nested config objects
    selection: SelectionConfig = Field(default_factory=SelectionConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    # --- Validation helpers -------------------------------------------------

    @field_validator("resolution")
    @classmethod
    def _validate_resolution(cls, v: str) -> str:
        v = v.strip()
        if "x" not in v:
            raise ValueError(
                f"resolution must be in the form 'WIDTHxHEIGHT', got {v!r}"
            )
        w_str, _, h_str = v.partition("x")
        try:
            w, h = int(w_str), int(h_str)
        except ValueError as exc:
            raise ValueError(f"resolution dimensions must be integers: {v!r}") from exc
        if w <= 0 or h <= 0:
            raise ValueError(f"resolution dimensions must be positive: {v!r}")
        return f"{w}x{h}"

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError(f"invalid log_level {v!r}")
        return v

    @model_validator(mode="after")
    def _ensure_dirs_exist(self) -> "Settings":
        # Best-effort creation of runtime directories. Failures are tolerated
        # because some CLI commands (e.g. `stats`) don't need them all.
        for p in (self.output_dir, self.temp_dir, self.logging.log_dir):
            try:
                Path(p).parent.mkdir(parents=True, exist_ok=True)
            except OSError:
                pass
        return self

    def require_cloud_credentials(self) -> None:
        """Raise a clear error if any cloud credential is missing.

        Called at the start of any command that actually needs Mongo or
        Cloudinary (``generate``, ``init-db``, ``stats``). Lets pure
        config-validation code paths still construct a Settings without
        crashing.
        """
        missing: list[str] = []
        if not self.mongodb_uri:
            missing.append("MONGODB_URI")
        if not self.cloudinary_cloud_name:
            missing.append("CLOUDINARY_CLOUD_NAME")
        if not self.cloudinary_api_key:
            missing.append("CLOUDINARY_API_KEY")
        if not self.cloudinary_api_secret:
            missing.append("CLOUDINARY_API_SECRET")
        if missing:
            raise RuntimeError(
                "Missing required cloud configuration: " + ", ".join(missing)
                + ". Set them via environment variables (or .env / GitHub"
                " Actions secrets). See README.md for the full list."
            )

    # --- Derived helpers ----------------------------------------------------

    @property
    def resolution_width(self) -> int:
        return int(self.resolution.split("x")[0])

    @property
    def resolution_height(self) -> int:
        return int(self.resolution.split("x")[1])


# --- Loader -----------------------------------------------------------------

def _load_yaml_into_env(yaml_path: Path) -> dict[str, Any]:
    """Read a YAML file and return a flat dict of scalar settings.

    Nested keys are ignored here because they are mapped to typed sub-models
    (``selection``, ``logging``). We only promote top-level scalars so they
    can override Pydantic defaults via ``Settings(**data)``.
    """
    if not yaml_path.exists():
        return {}
    with yaml_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"config file {yaml_path} must contain a top-level mapping")
    return data


@lru_cache(maxsize=1)
def get_settings(config_path: str | None = None) -> Settings:
    """Build and cache the singleton :class:`Settings` instance.

    Precedence (highest wins): env vars > .env > YAML > defaults.

    ``config_path`` lets tests inject a custom YAML file; in normal operation
    the path comes from ``QVG_CONFIG_FILE`` or defaults to ``config.yaml``.

    Implementation note
    -------------------
    Pydantic v2 ``BaseSettings`` gives explicit kwargs precedence over
    environment variables. That means if a YAML file contains
    ``mongodb_uri: ""`` (an empty string placeholder, as our
    ``config.example.yaml`` does for every secret), passing that empty
    string as a kwarg would *silently override* the real value coming
    from ``MONGODB_URI`` in the environment — which is exactly the bug
    that broke the GitHub Actions run even when secrets were set.

    Fix: drop any top-level YAML scalar that is empty / None / whitespace
    before constructing ``Settings``. Those fields then fall back to
    either the env var (if set) or the field default (empty string),
    and ``require_cloud_credentials()`` can surface a clear error if
    both are missing.
    """
    yaml_path = Path(
        config_path
        or os.environ.get("QVG_CONFIG_FILE")
        or "config.yaml"
    )
    yaml_data = _load_yaml_into_env(yaml_path)

    # Build nested sub-models from YAML sections if present.
    if "selection" in yaml_data and isinstance(yaml_data["selection"], dict):
        yaml_data["selection"] = SelectionConfig(**yaml_data["selection"])
    if "logging" in yaml_data and isinstance(yaml_data["logging"], dict):
        yaml_data["logging"] = LoggingConfig(**yaml_data["logging"])

    # Drop empty/None top-level scalars so env vars can fill them in.
    # (Nested sub-models like `selection` / `logging` are kept as-is.)
    filtered: dict[str, Any] = {}
    for k, v in yaml_data.items():
        if isinstance(v, str):
            if v.strip():
                filtered[k] = v
            # else: skip empty/whitespace string → let env var or default apply
        elif v is None:
            # skip None → let env var or default apply
            continue
        else:
            filtered[k] = v

    # ``Settings`` itself will pick up env vars / .env on top of these kwargs.
    return Settings(**filtered)


def reload_settings(config_path: str | None = None) -> Settings:
    """Force-rebuild the cached :class:`Settings` (used by tests)."""
    get_settings.cache_clear()
    return get_settings(config_path)


__all__ = [
    "Settings",
    "SelectionConfig",
    "LoggingConfig",
    "get_settings",
    "reload_settings",
]
