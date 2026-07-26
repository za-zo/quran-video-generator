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
:class:`SilenceDetector`), each clip's end_seconds is snapped to the
nearest silence position within ``±tolerance_seconds`` of the ideal
mechanical end. The start_seconds is then adjusted to keep the clip
duration equal to ``clip_duration``. If no silence is found in the
tolerance window, the mechanical cut is kept (graceful degradation).
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
            ``{position_seconds, duration_ms}``). When provided, each
            clip's end is snapped to the nearest silence within
            ``settings.silence_detection.tolerance_seconds``.
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
        tolerance = float(self.settings.silence_detection.tolerance_seconds)

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

            # --- Silence snapping (ayat-respecting cuts) ------------------
            # If we have a silence detector and cached positions, try to
            # move the END of the clip to the nearest silence within the
            # tolerance window. Then shift START back so the clip keeps
            # the same duration.
            if self.silence_detector and silence_positions:
                nearest = self.silence_detector.find_nearest_position(
                    end, silence_positions, tolerance_seconds=tolerance,
                )
                if nearest is not None:
                    new_end = nearest
                    new_start = new_end - clip_dur
                    # Keep within bounds — if shifting would push start
                    # below 0 or end beyond the audio, fall back to the
                    # mechanical cut.
                    if new_start >= 0.0 and new_end <= audio.duration_seconds:
                        start = new_start
                        end = new_end
                        log.debug(
                            "clip %d snapped to silence at %.3fs (was %.3fs)",
                            i, end, start + clip_dur,
                        )

            clips.append(
                AudioClip(
                    audio_id=audio.id,
                    index=i,
                    start_seconds=round(start, 3),
                    end_seconds=round(end, 3),
                )
            )

        log.info(
            "ClipExtractor produced %d clip(s) from audio id=%s (dur=%.2fs)",
            len(clips), audio.id, audio.duration_seconds,
        )
        return clips


__all__ = ["ClipExtractor"]
