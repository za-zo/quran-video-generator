"""Silence detector — finds natural cut points (end-of-ayah silences) in
source Quran recitations.

The pipeline cuts audio clips mechanically (every N seconds), which can
split an ayah mid-recitation. To avoid this, we analyse each audio once
with :mod:`pydub`'s ``detect_silence`` and store the silence midpoints
on the audio document. The :class:`ClipExtractor` then snaps each clip's
end_seconds to the nearest silence position within a configurable
tolerance, so cuts land on a natural pause rather than mid-word.

Caching strategy
----------------
Analysis is expensive (decoding the full audio), so it runs ONCE per
audio and the result is persisted via
:meth:`AudioRepo.save_silence_positions`. Subsequent pipeline runs
read the cached positions and skip re-analysis.

Failure modes
-------------
* ``pydub`` not installed → :class:`AppBaseException` with a clear
  message pointing to ``pip install pydub``.
* Any other analysis failure → :class:`AppBaseException`. The
  orchestrator catches this and falls back to mechanical cuts, so a
  broken audio analysis never blocks the pipeline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.config.settings import Settings
from src.exceptions import AppBaseException
from src.utils.logger import get_logger

log = get_logger(__name__)


class SilenceDetector:
    """Detects silence positions in an audio file using pydub.

    Constructed once per pipeline run with the global :class:`Settings`.
    The :meth:`analyze` method is called per audio (when not already
    cached) and returns a list of ``{position_seconds, duration_ms}``
    dicts sorted by ``position_seconds``.
    """

    def __init__(self, settings: Settings) -> None:
        self.cfg = settings.silence_detection

    def analyze(self, audio_local_path: Path) -> list[dict[str, Any]]:
        """Analyse ``audio_local_path`` and return silence positions.

        Each returned dict has:
        * ``position_seconds`` (float) — midpoint of the silence, used as
          the cut point.
        * ``duration_ms`` (int) — full duration of the silence.

        The list is sorted by ``position_seconds`` ascending and capped
        at ``cfg.max_positions``.

        Raises
        ------
        AppBaseException
            If pydub is not installed, or if analysis fails for any
            other reason.
        """
        # Lazy import so the module loads even when pydub is absent
        # (the silence detector is optional in the pipeline flow).
        try:
            from pydub import AudioSegment
            from pydub.silence import detect_silence
        except ImportError as exc:
            raise AppBaseException(
                "pydub is not installed. Install it with"
                " `pip install pydub` to enable silence detection."
            ) from exc

        path = Path(audio_local_path)
        if not path.is_file():
            raise AppBaseException(
                f"silence analysis: audio file not found: {path}"
            )

        try:
            audio = AudioSegment.from_file(path)
        except Exception as exc:
            raise AppBaseException(
                f"silence analysis: could not load audio {path}: {exc}",
                cause=exc,
            ) from exc

        # pydub's detect_silence returns a list of [start_ms, end_ms]
        # pairs. The threshold is relative to the audio's own loudness
        # (dBFS) so it adapts to quiet vs loud recordings.
        thresh_db = audio.dBFS - self.cfg.silence_thresh_offset_db
        try:
            raw = detect_silence(
                audio,
                min_silence_len=self.cfg.min_silence_len_ms,
                silence_thresh=thresh_db,
            )
        except Exception as exc:
            raise AppBaseException(
                f"silence analysis: detect_silence failed for {path}: {exc}",
                cause=exc,
            ) from exc

        positions: list[dict[str, Any]] = []
        for start_ms, end_ms in raw:
            duration_ms = end_ms - start_ms
            if duration_ms <= 0:
                continue
            midpoint_ms = (start_ms + end_ms) / 2
            positions.append({
                "position_seconds": round(midpoint_ms / 1000.0, 3),
                "duration_ms": int(duration_ms),
            })

        positions.sort(key=lambda d: d["position_seconds"])
        if len(positions) > self.cfg.max_positions:
            positions = positions[: self.cfg.max_positions]

        log.debug(
            "silence analysis: %d positions found in %s (min_len=%dms, thresh=%.1fdB)",
            len(positions), path.name, self.cfg.min_silence_len_ms, thresh_db,
        )
        return positions

    def find_nearest_position(
        self,
        target_seconds: float,
        positions: list[dict[str, Any]],
        tolerance_seconds: float | None = None,
    ) -> float | None:
        """Return the silence position nearest to ``target_seconds``.

        Only positions within ``±tolerance_seconds`` of the target are
        considered. Returns ``None`` if no position falls inside the
        window. ``tolerance_seconds`` defaults to
        ``cfg.tolerance_seconds`` when ``None``.
        """
        if not positions:
            return None
        tol = tolerance_seconds if tolerance_seconds is not None else self.cfg.tolerance_seconds
        best: float | None = None
        best_dist = float("inf")
        for p in positions:
            pos = p.get("position_seconds")
            if pos is None:
                continue
            dist = abs(pos - target_seconds)
            if dist <= tol and dist < best_dist:
                best_dist = dist
                best = float(pos)
        return best


__all__ = ["SilenceDetector"]
