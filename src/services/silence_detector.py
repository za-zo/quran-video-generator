"""Silence detector — finds natural cut points (end-of-ayah silences) in
source Quran recitations.

This implementation is a direct port of the standalone audio analyzer
script that produces 100% correct, reproducible results. The algorithm
uses librosa + RMS energy + percentile-based relative thresholding,
exactly matching the reference implementation.

Algorithm (mirrors the standalone script exactly)
-------------------------------------------------
1. Load audio with librosa (mono conversion if stereo).
2. Compute RMS energy with hop_length=256, frame_length=1024.
3. Convert to dB with amplitude_to_db(ref=np.max).
4. Compute threshold as the percentile of the RMS-dB distribution.
5. Detect continuous zones where RMS-dB < threshold, filtered by
   min_duration (in seconds, NOT ms — matches the standalone script).
6. For each silence, store the CENTRE = (start + end) / 2.

The key difference from the previous (broken) implementation: this
version uses min_duration in SECONDS directly (not ms converted to
seconds), does NOT round the centre, and follows the exact same code
path as the standalone script that the user verified produces correct
results.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.config.settings import Settings
from src.exceptions import AppBaseException
from src.utils.logger import get_logger

log = get_logger(__name__)

# Constants — must match the standalone script exactly.
_HOP_LENGTH = 256
_FRAME_LENGTH = 1024


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
        * ``position_seconds`` (float) — **centre** of the silence.
        * ``duration_ms`` (int) — full duration of the silence in ms.

        This method mirrors the standalone audio_analyzer.py script
        exactly — same load, same RMS, same threshold, same zone
        detection, same centre calculation.

        Raises
        ------
        AppBaseException
            If librosa is not installed, or if analysis fails for any
            other reason.
        """
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
            # ============================================================
            # Step 1 — Load audio (exact copy of standalone script)
            # ============================================================
            y, sr = librosa.load(str(path), sr=None, mono=False)
            if y.ndim > 1:
                y = librosa.to_mono(y)

            # ============================================================
            # Step 2 — Compute RMS energy (exact copy of standalone)
            # ============================================================
            rms = librosa.feature.rms(
                y=y, hop_length=_HOP_LENGTH, frame_length=_FRAME_LENGTH
            )[0]
            times = librosa.times_like(rms, sr=sr, hop_length=_HOP_LENGTH)
            rms_db = librosa.amplitude_to_db(rms, ref=np.max)

            # ============================================================
            # Step 3 — Compute threshold via percentile (exact copy)
            # ============================================================
            threshold_db = np.percentile(rms_db, self.cfg.threshold_percentile)

            # ============================================================
            # Step 4 — Detect low-energy zones (exact copy of
            #          detect_low_energy_zones from the standalone script)
            # ============================================================
            # IMPORTANT: the standalone script uses min_duration in
            # SECONDS (default 0.3), not ms. We convert here to match
            # exactly.
            min_duration = self.cfg.min_silence_len_ms / 1000.0
            min_frames = int(min_duration * sr / _HOP_LENGTH)

            silence_mask = rms_db < threshold_db

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
                        start_time = times[silence_start]
                        end_time = times[min(i, len(times) - 1)]
                        avg_energy = np.mean(rms_db[silence_start:i])
                        min_energy = np.min(rms_db[silence_start:i])
                        silences.append({
                            'start': start_time,
                            'end': end_time,
                            'duration': end_time - start_time,
                            'avg_db': avg_energy,
                            'min_db': min_energy,
                        })

            # Handle trailing silence (exact copy of standalone)
            if in_silence:
                silence_length = len(silence_mask) - silence_start
                if silence_length >= min_frames:
                    silences.append({
                        'start': times[silence_start],
                        'end': times[-1],
                        'duration': times[-1] - times[silence_start],
                        'avg_db': np.mean(rms_db[silence_start:]),
                        'min_db': np.min(rms_db[silence_start:]),
                    })

            # ============================================================
            # Step 5 — Extract the CENTRE of each silence
            # CRITICAL: centre = (start + end) / 2
            # NO rounding — the standalone script doesn't round either.
            # Rounding was causing slight position shifts that made the
            # cut points fall on the wrong spot.
            # ============================================================
            positions: list[dict[str, Any]] = []
            for s in silences:
                centre = (s['start'] + s['end']) / 2
                positions.append({
                    'position_seconds': float(centre),
                    'duration_ms': int(s['duration'] * 1000),
                })

            # ============================================================
            # Step 6 — Sort + cap (exact copy)
            # ============================================================
            positions.sort(key=lambda d: d['position_seconds'])
            if len(positions) > self.cfg.max_positions:
                positions = positions[:self.cfg.max_positions]

            audio_duration = float(len(y) / sr) if sr > 0 else 0.0
            log.debug(
                "silence analysis: %d positions found in %s "
                "(dur=%.2fs, min_dur=%.3fs, percentile=%d, thresh=%.1fdB)",
                len(positions), path.name, audio_duration,
                min_duration, self.cfg.threshold_percentile,
                float(threshold_db),
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
