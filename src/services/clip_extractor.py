"""Audio clip extractor.

Given an :class:`AudioRecord` and the configured ``clip_duration`` /
``clips_per_audio`` values, produce a list of non-overlapping
:class:`AudioClip` instances.

Algorithm (per spec §5 Step 2):
  1. If ``audio.duration_seconds < clip_duration`` raise
     :class:`InsufficientAudioDurationError`.
  2. Compute ``N = min(clips_per_audio, floor(duration / clip_duration))``.
     If N == 0 the duration check above already failed.
  3. Divide the audio into N roughly-equal zones. In each zone pick a random
     start offset such that ``start + clip_duration <= zone_end`` and
     ``start >= zone_start``. This guarantees no two clips overlap because
     their zones are disjoint.

Ayat-respecting cuts (silence snapping)
---------------------------------------
When ``silence_positions`` is passed to :meth:`extract` (a list of
``{position_seconds, duration_ms}`` dicts as produced by
:class:`SilenceDetector`):

* **Start snapping**: the clip's start_seconds is snapped to the nearest
  silence position within ``±tolerance_seconds``. If found, the start
  moves to the silence centre.

* **End snapping (FLEXIBLE DURATION)**: the clip's end_seconds is snapped
  to the nearest silence position within ``±end_tolerance_percent`` %
  of ``clip_duration`` (default ±10% → ±6s for a 60s clip). If found,
  the end moves to the silence centre, making the actual clip duration
  slightly longer or shorter than ``clip_duration``. The video output
  respects this actual duration — it's NOT cut back to exactly
  ``clip_duration``.

* **No rounding**: positions are kept as raw floats to preserve
  millisecond precision. Rounding was causing the cut to land on the
  wrong spot (the silence centre at 231.445s became 231.000s).
"""

from __future__ import annotations

import random

from src.config.settings import Settings
from src.exceptions import InsufficientAudioDurationError
from src.models import AudioClip, AudioRecord
from src.services.silence_detector import SilenceDetector
from src.utils.logger import get_logger

log = get_logger(__name__)


class ClipExtractor:
    def __init__(
        self,
        settings: Settings,
        rng: random.Random | None = None,
        *,
        silence_detector: SilenceDetector | None = None,
    ) -> None:
        self.settings = settings
        self.rng = rng or random.Random()
        self.silence_detector = silence_detector

    def extract(
        self,
        audio: AudioRecord,
        *,
        silence_positions: list[dict] | None = None,
    ) -> list[AudioClip]:
        """Produce a list of non-overlapping clips from ``audio``.

        Parameters
        ----------
        audio
            The source audio record. Must have ``duration_seconds > 0``.
        silence_positions
            Optional cached silence positions (list of
            ``{position_seconds, duration_ms}``). When provided, the clip
            START is snapped to the nearest silence within
            ``settings.silence_detection.tolerance_seconds``, and the clip
            END is snapped to the nearest silence within
            ``settings.silence_detection.end_tolerance_percent`` % of
            ``clip_duration``. The actual clip duration may therefore
            differ slightly from ``clip_duration``.
        """
        clip_dur = float(self.settings.clip_duration)
        max_clips = int(self.settings.clips_per_audio)

        if audio.duration_seconds < clip_dur:
            raise InsufficientAudioDurationError(
                f"audio {audio.name!r} duration {audio.duration_seconds:.2f}s "
                f"is shorter than clip_duration {clip_dur:.2f}s"
            )

        n_fitting = int(audio.duration_seconds // clip_dur)
        n_clips = min(max_clips, n_fitting)
        if n_clips <= 0:
            # Should be unreachable due to the check above, but keep defensive.
            raise InsufficientAudioDurationError(
                f"audio {audio.name!r} cannot fit even one clip "
                f"of {clip_dur:.2f}s"
            )
        if n_clips < max_clips:
            log.warning(
                "audio %r can fit only %d non-overlapping clip(s) of %.2fs "
                "(requested %d) – proceeding with %d",
                audio.name, n_clips, clip_dur, max_clips, n_clips,
            )

        zone_size = audio.duration_seconds / n_clips
        start_tolerance = float(self.settings.silence_detection.tolerance_seconds)
        end_tolerance_pct = float(self.settings.silence_detection.end_tolerance_percent)
        # End search window = ±N% of clip_duration.
        end_tolerance = clip_dur * (end_tolerance_pct / 100.0)

        clips: list[AudioClip] = []
        for i in range(n_clips):
            zone_start = i * zone_size
            zone_end = (i + 1) * zone_size
            # Allowable start range inside the zone (mechanical).
            lo = zone_start
            hi = max(lo, zone_end - clip_dur)
            start = self.rng.uniform(lo, hi) if hi > lo else lo
            # Guard against tiny floating-point overshoot.
            start = max(0.0, min(start, audio.duration_seconds - clip_dur))
            end = start + clip_dur

            # --- Start snapping (ayat-respecting start) -------------------
            # Snap the START to the nearest silence within start_tolerance.
            # This makes the clip begin at a silence centre rather than
            # mid-word.
            if self.silence_detector and silence_positions:
                nearest_start = self.silence_detector.find_nearest_position(
                    start, silence_positions, tolerance_seconds=start_tolerance,
                )
                if nearest_start is not None:
                    new_start = nearest_start
                    # Keep the end = new_start + clip_dur (mechanical end
                    # shifts with the start). Bounds check.
                    new_end = new_start + clip_dur
                    if new_start >= 0.0 and new_end <= audio.duration_seconds:
                        start = new_start
                        end = new_end
                        log.debug(
                            "clip %d start snapped to silence at %.6fs",
                            i, start,
                        )

            # --- End snapping (FLEXIBLE DURATION) ------------------------
            # Snap the END to the nearest silence within ±end_tolerance.
            # This makes the clip END on a silence centre, even if that
            # means the actual duration differs from clip_dur. The video
            # output uses the actual duration — it's NOT cut back.
            if self.silence_detector and silence_positions:
                nearest_end = self.silence_detector.find_nearest_position(
                    end, silence_positions, tolerance_seconds=end_tolerance,
                )
                if nearest_end is not None:
                    new_end = nearest_end
                    # Bounds: end must be > start and <= audio duration.
                    if new_end > start and new_end <= audio.duration_seconds:
                        end = new_end
                        log.debug(
                            "clip %d end snapped to silence at %.6fs "
                            "(actual duration %.3fs vs target %.3fs)",
                            i, end, end - start, clip_dur,
                        )

            # NO rounding — preserve millisecond precision exactly as
            # the silence detector computed it.
            clips.append(
                AudioClip(
                    audio_id=audio.id,
                    index=i,
                    start_seconds=start,
                    end_seconds=end,
                )
            )

        log.info(
            "ClipExtractor produced %d clip(s) from audio id=%s (dur=%.2fs)",
            len(clips), audio.id, audio.duration_seconds,
        )
        return clips


__all__ = ["ClipExtractor"]
