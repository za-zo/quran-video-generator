"""CLI entrypoint for the Quran Video Generator.

Usage
-----
    python main.py init-db                       # init DB + scan audios/videos
    python main.py generate --audio-count 1 --clips-per-audio 5
    python main.py generate --batch 10           # process 10 audios in one run
    python main.py stats                          # show usage stats
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path
from typing import Any

from src.config.settings import Settings, get_settings
from src.database.repository import AudioRepo, CategoryRepo, VideoRepo
from src.database.session import get_session, init_db
from src.services.audio_selector import AudioSelector
from src.services.category_selector import CategorySelector
from src.services.clip_extractor import ClipExtractor
from src.services.generation_orchestrator import GenerationOrchestrator
from src.services.video_processor import VideoProcessor
from src.services.video_selector import VideoSelector
from src.utils import file_utils
from src.utils.ffmpeg_utils import probe_media
from src.utils.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# DB initialisation & folder scan
# ---------------------------------------------------------------------------

def cmd_init_db(args: argparse.Namespace, settings: Settings) -> int:
    init_db()
    session = get_session()
    try:
        audio_repo = AudioRepo(session)
        category_repo = CategoryRepo(session)
        video_repo = VideoRepo(session)

        # --- Audios ---
        audio_files = file_utils.scan_audio_files(settings.audios_dir)
        n_audio_added = 0
        for af in audio_files:
            try:
                probe = probe_media(af)
            except Exception as exc:
                log.warning("skipping %s: %s", af, exc)
                continue
            audio_repo.get_or_create(str(af.resolve()), probe.duration_seconds)
            n_audio_added += 1

        # --- Categories + Videos ---
        categories = file_utils.scan_category_dirs(settings.videos_dir)
        n_cat_added = 0
        n_vid_added = 0
        for cat_name, cat_dir in categories.items():
            cat = category_repo.get_or_create(cat_name)
            n_cat_added += 1
            for vf in file_utils.videos_in_category(cat_dir):
                try:
                    probe = probe_media(vf)
                except Exception as exc:
                    log.warning("skipping %s: %s", vf, exc)
                    continue
                video_repo.get_or_create(cat.id, str(vf.resolve()), probe.duration_seconds)
                n_vid_added += 1

        session.commit()
        log.info(
            "init-db complete: %d audios, %d categories, %d videos",
            n_audio_added, n_cat_added, n_vid_added,
        )
        print(f"Initialised DB at {settings.db_path}")
        print(f"  audios:     {n_audio_added}")
        print(f"  categories: {n_cat_added}")
        print(f"  videos:     {n_vid_added}")
    finally:
        session.close()
    return 0


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def cmd_stats(args: argparse.Namespace, settings: Settings) -> int:
    init_db()
    session = get_session()
    try:
        audio_repo = AudioRepo(session)
        category_repo = CategoryRepo(session)
        video_repo = VideoRepo(session)

        print("=" * 70)
        print("AUDIOS")
        print("=" * 70)
        print(f"{'ID':>4}  {'USAGE':>5}  {'DUR':>8}  {'LAST_USED':<20}  FILENAME")
        for a in audio_repo.list_all():
            last = a.last_used_at.strftime("%Y-%m-%d %H:%M") if a.last_used_at else "never"
            short = _short_path(a.filename)
            print(f"{a.id:>4}  {a.usage_count:>5}  {a.duration_seconds:>7.1f}s  {last:<20}  {short}")

        print("\n" + "=" * 70)
        print("CATEGORIES")
        print("=" * 70)
        print(f"{'ID':>4}  {'USAGE':>5}  {'LAST_USED':<20}  NAME")
        for c in category_repo.list_all():
            last = c.last_used_at.strftime("%Y-%m-%d %H:%M") if c.last_used_at else "never"
            print(f"{c.id:>4}  {c.usage_count:>5}  {last:<20}  {c.name}")

        print("\n" + "=" * 70)
        print("VIDEOS")
        print("=" * 70)
        print(f"{'ID':>4}  {'CAT':>4}  {'USAGE':>5}  {'DUR':>8}  FILENAME")
        for c in category_repo.list_all():
            for v in video_repo.list_for_category(c.id):
                short = _short_path(v.filename)
                print(f"{v.id:>4}  {c.id:>4}  {v.usage_count:>5}  {v.duration_seconds:>7.1f}s  {short}")
    finally:
        session.close()
    return 0


def _short_path(p: str, max_len: int = 50) -> str:
    if len(p) <= max_len:
        return p
    return "..." + p[-(max_len - 3):]


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def cmd_generate(args: argparse.Namespace, settings: Settings) -> int:
    init_db()
    # Allow CLI overrides without mutating the cached settings.
    override: dict[str, Any] = {}
    if args.clips_per_audio is not None:
        override["clips_per_audio"] = args.clips_per_audio
    if args.clip_duration is not None:
        override["clip_duration"] = args.clip_duration
    if override:
        settings = settings.model_copy(update=override)
        log.info("CLI overrides applied: %s", override)

    audio_count = args.batch or args.audio_count or 1
    if audio_count <= 0:
        print("--batch / --audio-count must be >= 1", file=sys.stderr)
        return 2

    rng = random.Random(args.seed) if args.seed is not None else random.Random()
    session = get_session()
    try:
        orchestrator = GenerationOrchestrator(
            session=session,
            settings=settings,
            rng=rng,
        )
        results = orchestrator.run_batch(audio_count=audio_count)
        succeeded = sum(1 for r in results if r.status == "success")
        failed = sum(1 for r in results if r.status == "failed")
        print(f"\nGeneration complete: {succeeded} succeeded, {failed} failed, {len(results)} total.")
        if failed:
            print("Failed jobs:")
            for r in results:
                if r.status == "failed":
                    print(f"  job {r.job_id} (audio={r.audio_id}, clip={r.clip_index}): {r.error_message}")
    finally:
        session.close()
    return 0 if failed == 0 else 1


# ---------------------------------------------------------------------------
# Argparse
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="quran-video-generator",
        description="Generate short Quran recitation videos locally with FFmpeg.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init-db", help="initialise database and scan audios/videos folders")
    p_init.set_defaults(func=cmd_init_db)

    p_stats = sub.add_parser("stats", help="show usage stats per audio/category/video")
    p_stats.set_defaults(func=cmd_stats)

    p_gen = sub.add_parser("generate", help="generate short Quran videos")
    p_gen.add_argument("--audio-count", type=int, default=None,
                       help="how many distinct audios to process in this run")
    p_gen.add_argument("--batch", type=int, default=None,
                       help="alias for --audio-count (process N audios in one run)")
    p_gen.add_argument("--clips-per-audio", type=int, default=None,
                       help="override clips_per_audio from config")
    p_gen.add_argument("--clip-duration", type=int, default=None,
                       help="override clip_duration (seconds) from config")
    p_gen.add_argument("--seed", type=int, default=None,
                       help="RNG seed for reproducible selection")
    p_gen.set_defaults(func=cmd_generate)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = get_settings()
    return args.func(args, settings)


if __name__ == "__main__":
    sys.exit(main())
