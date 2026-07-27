"""Silence detector — finds natural cut points (end-of-ayah silences) in
source Quran recitations.

The pipeline cuts audio clips mechanically (every N seconds), which can
split an ayah mid-recitation. To avoid this, we analyse each audio once
and store the silence centres on the audio document. The
:class:`ClipExtractor` then snaps each clip's end_seconds to the nearest
silence position within a configurable tolerance, so cuts land on a
natural pause rather than mid-word.

Algorithm
---------
This implementation uses **librosa + RMS energy + percentile-based
relative thresholding** instead of pydub's absolute dBFS threshold. The
relative threshold adapts to variable-volume recordings (Quran
recitations where the recitant's volume varies), which pydub could not
handle correctly.

Steps:
1. Load the audio with librosa (mono conversion if stereo).
2. Compute high-resolution RMS energy (hop_length=256, frame_length=1024).
3. Convert to dB and compute the threshold as the ``threshold_percentile``
   percentile of the RMS-dB distribution — this is relative to the
   audio itself, not an absolute value.
4. Detect continuous zones where RMS-dB < threshold, keeping only those
   longer than ``min_silence_len_ms`` (converted to frames).
5. For each detected silence, compute the **centre** (midpoint of start
   and end) — this is the best cut point because it maximises distance
   from speech on both sides.
6. Return ``[{position_seconds, duration_ms}, ...]`` capped at
   ``max_positions``.

Caching strategy
----------------
Analysis is expensive (decoding the full audio), so it runs ONCE per
audio and the result is persisted via
:meth:`AudioRepo.save_silence_positions`. Subsequent pipeline runs
read the cached positions and skip re-analysis.

Failure modes
-------------
* ``librosa`` not installed → :class:`AppBaseException` with a clear
  message pointing to ``pip install librosa``.
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
    """Detects silence positions in an audio file using librosa + RMS energy.

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
        * ``position_seconds`` (float) — **centre** of the silence (midpoint
          of start + end), used as the cut point.
        * ``duration_ms`` (int) — full duration of the silence.

        The list is sorted by ``position_seconds`` ascending and capped
        at ``cfg.max_positions``.

        Raises
        ------
        AppBaseException
            If librosa is not installed, or if analysis fails for any
            other reason.
        """
        # Lazy import so the module loads even when librosa is absent
        # (the silence detector is optional in the pipeline flow).
        try:
            import librosa
            import numpy as np
        except ImportError as exc:
            raise AppBaseException(
                "librosa est requis : pip install librosa"
            ) from exc

        path = Path(audio_local_path)
        if not path.is_file():
            raise AppBaseException(
                f"silence analysis: audio file not found: {path}"
            )

        try:
            # --- Step 1: Load audio with librosa ---------------------
            y, sr = librosa.load(str(path), sr=None, mono=False)
            if y.ndim > 1:
                y = librosa.to_mono(y)

            # --- Step 2: Compute RMS energy at high resolution --------
            hop_length = 256
            frame_length = 1024
            rms = librosa.feature.rms(
                y=y, hop_length=hop_length, frame_length=frame_length
            )[0]
            times = librosa.times_like(rms, sr=sr, hop_length=hop_length)
            rms_db = librosa.amplitude_to_db(rms, ref=np.max)

            # --- Step 3: Compute relative threshold via percentile ----
            threshold_db = float(np.percentile(rms_db, self.cfg.threshold_percentile))

            # --- Step 4: Detect continuous zones below threshold -------
            silence_mask = rms_db < threshold_db
            min_frames = int(
                self.cfg.min_silence_len_ms / 1000.0 * sr / hop_length
            )

            silences: list[dict[str, float]] = []
            in_silence = False
            silence_start = 0

            for i, is_silent in enumerate(silence_mask):
                if is_silent and not in_silence:
                    in_silence = True
                    silence_start = i
                elif not is_silent and in_silence:
                    in_silence = False
                    silence_length = i - silence_start
                    if silence_length >= min_frames:
                        start_time = float(times[silence_start])
                        end_time = float(times[min(i, len(times) - 1)])
                        avg_energy = float(np.mean(rms_db[silence_start:i]))
                        min_energy = float(np.min(rms_db[silence_start:i]))
                        silences.append({
                            "start": start_time,
                            "end": end_time,
                            "duration": end_time - start_time,
                            "avg_db": avg_energy,
                            "min_db": min_energy,
                        })

            # Handle trailing silence if we're still in one at the end
            if in_silence:
                silence_length = len(silence_mask) - silence_start
                if silence_length >= min_frames:
                    start_time = float(times[silence_start])
                    end_time = float(times[-1])
                    avg_energy = float(np.mean(rms_db[silence_start:]))
                    min_energy = float(np.min(rms_db[silence_start:]))
                    silences.append({
                        "start": start_time,
                        "end": end_time,
                        "duration": end_time - start_time,
                        "avg_db": avg_energy,
                        "min_db": min_energy,
                    })

            # --- Step 5: Extract the CENTRE of each silence -----------
            # CRITICAL: the stored position is the centre (midpoint of
            # start + end), not the start or end. The centre maximises
            # distance from speech on both sides, making it the safest
            # cut point.
            positions: list[dict[str, Any]] = []
            for s in silences:
                centre = (s["start"] + s["end"]) / 2.0
                positions.append({
                    "position_seconds": round(float(centre), 3),
                    "duration_ms": int(s["duration"] * 1000),
                })

            # --- Step 6: Sort + cap + return --------------------------
            positions.sort(key=lambda d: d["position_seconds"])
            if len(positions) > self.cfg.max_positions:
                positions = positions[: self.cfg.max_positions]

            audio_duration = float(len(y) / sr) if sr > 0 else 0.0
            log.debug(
                "silence analysis: %d positions found in %s "
                "(dur=%.2fs, min_len=%dms, percentile=%d, thresh=%.1fdB)",
                len(positions), path.name, audio_duration,
                self.cfg.min_silence_len_ms,
                self.cfg.threshold_percentile, threshold_db,
            )
            return positions

        except AppBaseException:
            raise
        except Exception as exc:
            raise AppBaseException(
                f"silence analysis failed for {path}: {exc}",
                cause=exc,
            ) from exc

    def find_nearest_position(
        self,
        target_seconds: float,
        positions: list[dict[str, Any]],
        tolerance_seconds: float | None = None,
    ) -> float | None:
        """Return the silence position nearest to ``target_seconds``.

        Only positions within ``±tolerance_seconds`` of the target are
        considered. Returns ``None`` if no position falls inside the
        window (or if ``positions`` is empty).

        ``tolerance_seconds`` defaults to ``cfg.tolerance_seconds`` when
        ``None``.
        """
        if not positions:
            return None
        tol = (
            tolerance_seconds
            if tolerance_seconds is not None
            else self.cfg.tolerance_seconds
        )
        best: float | None = None
        best_dist = float("inf")
        for p in positions:
            pos = p.get("position_seconds")
            if pos is None:
                continue
            dist = abs(float(pos) - target_seconds)
            if dist <= tol and dist < best_dist:
                best_dist = dist
                best = float(pos)
        return best


__all__ = ["SilenceDetector"]
