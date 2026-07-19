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
"""

from __future__ import annotations

import random

from src.config.settings import Settings
from src.exceptions import InsufficientAudioDurationError
from src.models import AudioClip, AudioRecord
from src.utils.logger import get_logger

log = get_logger(__name__)


class ClipExtractor:
    def __init__(
        self,
        settings: Settings,
        rng: random.Random | None = None,
    ) -> None:
        self.settings = settings
        self.rng = rng or random.Random()

    def extract(self, audio: AudioRecord) -> list[AudioClip]:
        clip_dur = float(self.settings.clip_duration)
        max_clips = int(self.settings.clips_per_audio)

        if audio.duration_seconds < clip_dur:
            raise InsufficientAudioDurationError(
                f"audio {audio.filename!r} duration {audio.duration_seconds:.2f}s "
                f"is shorter than clip_duration {clip_dur:.2f}s"
            )

        n_fitting = int(audio.duration_seconds // clip_dur)
        n_clips = min(max_clips, n_fitting)
        if n_clips <= 0:
            # Should be unreachable due to the check above, but keep defensive.
            raise InsufficientAudioDurationError(
                f"audio {audio.filename!r} cannot fit even one clip "
                f"of {clip_dur:.2f}s"
            )
        if n_clips < max_clips:
            log.warning(
                "audio %r can fit only %d non-overlapping clip(s) of %.2fs "
                "(requested %d) – proceeding with %d",
                audio.filename, n_clips, clip_dur, max_clips, n_clips,
            )

        zone_size = audio.duration_seconds / n_clips
        clips: list[AudioClip] = []
        for i in range(n_clips):
            zone_start = i * zone_size
            zone_end = (i + 1) * zone_size
            # Allowable start range inside the zone.
            lo = zone_start
            hi = max(lo, zone_end - clip_dur)
            start = self.rng.uniform(lo, hi) if hi > lo else lo
            # Guard against tiny floating-point overshoot.
            start = max(0.0, min(start, audio.duration_seconds - clip_dur))
            end = start + clip_dur
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
