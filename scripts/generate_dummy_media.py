#!/usr/bin/env python
"""Generate small dummy media for end-to-end pipeline testing.

Creates:
  audios/001.mp3, 002.mp3, 003.mp3      (~ 4 minutes each)
  videos/{sea,forest,waterfall,rivers,desert,mountains,sky}/*.mp4
                                         (~ 35s each, 3 videos per category)

All files are tiny (a few hundred KB) and produced with FFmpeg's internal
synth sources (sine + testsrc). No external assets required.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIOS = ROOT / "audios"
VIDEOS = ROOT / "videos"

CATEGORIES = ["sea", "forest", "waterfall", "rivers", "desert", "mountains", "sky"]

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)


def make_audio(path: Path, duration: int = 240, freq: int = 220) -> None:
    """Synthesise a sine-wave mp3 ~ `duration` seconds long."""
    path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        FFMPEG, "-y",
        "-f", "lavfi",
        "-i", f"sine=frequency={freq}:duration={duration}",
        "-c:a", "libmp3lame", "-b:a", "96k",
        str(path),
    ]
    run(cmd)


def make_video(path: Path, duration: int = 35, idx: int = 0) -> None:
    """Synthesise a coloured test-card mp4 (no audio) ~ `duration` seconds long."""
    path.parent.mkdir(parents=True, exist_ok=True)
    hue = (idx * 47) % 360
    cmd = [
        FFMPEG, "-y",
        "-f", "lavfi",
        "-i", f"testsrc=duration={duration}:size=640x360:rate=30",
        "-vf", f"hue=h={hue}:s=2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-t", str(duration),
        str(path),
    ]
    run(cmd)


def main() -> int:
    if not shutil.which("ffmpeg"):
        print("ffmpeg not found on PATH", file=sys.stderr)
        return 1

    # Three Quran-like audios, ~4 minutes each.
    for i in (1, 2, 3):
        make_audio(AUDIOS / f"{i:03d}.mp3", duration=240, freq=200 + i * 20)

    # 3 videos per category, ~35s each (so 2 videos cover a 60s clip).
    for cat in CATEGORIES:
        for i in range(3):
            make_video(VIDEOS / cat / f"{cat}_{i}.mp4", duration=35, idx=i)
    print("Done.")
    return 0


if __name__ == "__main__":
    # Argv parsing: --quick produces fewer, shorter clips for fast smoke tests.
    if "--quick" in sys.argv:
        AUDIOS_SAVED = AUDIOS
        for i in (1, 2):
            make_audio(AUDIOS_SAVED / f"{i:03d}.mp3", duration=130, freq=200 + i * 20)
        for cat in CATEGORIES[:3]:  # only 3 categories, 2 videos each
            for i in range(2):
                make_video(VIDEOS / cat / f"{cat}_{i}.mp4", duration=35, idx=i)
        print("Quick dummy media done.")
        sys.exit(0)
    sys.exit(main())
