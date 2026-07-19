"""CLI entrypoint for the Quran Video Generator.

Usage
-----
    python main.py init-db                       # ensure Mongo indexes + ping
    python main.py generate --audio-count 1 --clips-per-audio 5
    python main.py generate --batch 10           # process 10 audios in one run
    python main.py stats                          # show usage stats

Cloud-native flow
-----------------
1. Register media (audios / categories / videos) via the Next.js webapp
   (/webapp) — the webapp writes documents directly to MongoDB.
2. ``python main.py init-db`` ensures the MongoDB indexes exist and pings
   the cluster so misconfiguration surfaces immediately.
3. ``python main.py generate --batch N`` runs the full pipeline:
   select → download → FFmpeg → upload to Cloudinary → update Mongo.
   Typically invoked by the GitHub Actions workflow (.github/workflows/
   generate-videos.yml) but works identically when run locally if the
   env vars are set.
4. ``python main.py stats`` prints usage counters per audio/category/video.
"""

from __future__ import annotations

import argparse
import random
import sys
from typing import Any

from src.config.settings import Settings, get_settings
from src.database.mongo_client import get_db, ping, reset_client
from src.database.repository import (
    AudioRepo,
    CategoryRepo,
    ExecutionRepo,
    VideoRepo,
    ensure_indexes,
)
from src.services.generation_orchestrator import GenerationOrchestrator
from src.utils.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# DB initialisation (Mongo indexes + ping)
# ---------------------------------------------------------------------------

def cmd_init_db(args: argparse.Namespace, settings: Settings) -> int:
    settings.require_cloud_credentials()
    if not ping():
        print("ERROR: could not ping MongoDB cluster.", file=sys.stderr)
        print("Check MONGODB_URI and network access (Atlas IP allowlist).", file=sys.stderr)
        return 3
    db = get_db()
    ensure_indexes(db)
    # Quick summary so the operator can see what's already in the cluster.
    audio_repo = AudioRepo(db)
    category_repo = CategoryRepo(db)
    video_repo = VideoRepo(db)
    execution_repo = ExecutionRepo(db)
    print("MongoDB ready. Indexes ensured.")
    print(f"  audios:      {len(audio_repo.list_all())}")
    print(f"  categories:  {len(category_repo.list_all())}")
    print(f"  videos:      {sum(len(video_repo.list_for_category(c.id)) for c in category_repo.list_all())}")
    print(f"  executions:  {sum(execution_repo.count_by_status().values())}")
    return 0


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def cmd_stats(args: argparse.Namespace, settings: Settings) -> int:
    settings.require_cloud_credentials()
    db = get_db()
    audio_repo = AudioRepo(db)
    category_repo = CategoryRepo(db)
    video_repo = VideoRepo(db)
    execution_repo = ExecutionRepo(db)

    print("=" * 70)
    print("AUDIOS")
    print("=" * 70)
    print(f"{'ID':<26}  {'USAGE':>5}  {'DUR':>8}  {'LAST_USED':<20}  NAME")
    for a in audio_repo.list_all():
        last = a.last_used_at.strftime("%Y-%m-%d %H:%M") if a.last_used_at else "never"
        print(f"{a.id:<26}  {a.usage_count:>5}  {a.duration_seconds:>7.1f}s  {last:<20}  {a.name}")

    print("\n" + "=" * 70)
    print("CATEGORIES")
    print("=" * 70)
    print(f"{'ID':<26}  {'USAGE':>5}  {'VIDEOS':>6}  {'LAST_USED':<20}  NAME")
    for c in category_repo.list_all():
        last = c.last_used_at.strftime("%Y-%m-%d %H:%M") if c.last_used_at else "never"
        n_videos = category_repo.count_videos(c.id)
        print(f"{c.id:<26}  {c.usage_count:>5}  {n_videos:>6}  {last:<20}  {c.name}")

    print("\n" + "=" * 70)
    print("VIDEOS")
    print("=" * 70)
    print(f"{'ID':<26}  {'CAT':<26}  {'USAGE':>5}  {'DUR':>8}  NAME")
    for c in category_repo.list_all():
        for v in video_repo.list_for_category(c.id):
            print(f"{v.id:<26}  {c.id:<26}  {v.usage_count:>5}  {v.duration_seconds:>7.1f}s  {v.name}")

    print("\n" + "=" * 70)
    print("EXECUTIONS")
    print("=" * 70)
    counts = execution_repo.count_by_status()
    for status, n in sorted(counts.items()):
        print(f"  {status:<10} {n}")
    print(f"  total       {sum(counts.values())}")

    return 0


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def cmd_generate(args: argparse.Namespace, settings: Settings) -> int:
    settings.require_cloud_credentials()
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
    db = get_db()
    orchestrator = GenerationOrchestrator(
        db=db,
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
                print(f"  exec {r.job_id} (audio={r.audio_id}, clip={r.clip_index}): {r.error_message}")
    # Batch-resilience rule: a run with at least one success is not a
    # workflow failure. Only exit non-zero if literally nothing succeeded.
    if len(results) > 0 and succeeded == 0:
        return 1
    return 0


# ---------------------------------------------------------------------------
# Argparse
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="quran-video-generator",
        description="Generate short Quran recitation videos via FFmpeg and"
                    " upload them to Cloudinary. Metadata lives in MongoDB Atlas.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser(
        "init-db",
        help="ensure MongoDB indexes exist and ping the cluster",
    )
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
