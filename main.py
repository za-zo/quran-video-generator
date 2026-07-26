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
import signal
import sys
from datetime import datetime, timezone
from typing import Any

from src.config.settings import Settings, get_settings
from src.database.mongo_client import get_db, ping, reset_client
from src.database.repository import (
    AudioRepo,
    CategoryRepo,
    ExecutionRunRepo,
    ExecutionSliceRepo,
    VideoRepo,
    ensure_indexes,
)
from src.exceptions import AppBaseException
from src.services.generation_orchestrator import GenerationOrchestrator
from src.services.silence_detector import SilenceDetector
from src.utils import media_downloader
from src.utils import ffmpeg_utils as ff
from src.utils.file_utils import temp_workdir
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
    run_repo = ExecutionRunRepo(db)
    print("MongoDB ready. Indexes ensured.")
    print(f"  audios:      {len(audio_repo.list_all())}")
    print(f"  categories:  {len(category_repo.list_all())}")
    print(f"  videos:      {sum(len(video_repo.list_for_category(c.id)) for c in category_repo.list_all())}")
    runs = run_repo.list_recent(limit=1000)
    print(f"  runs:        {len(runs)}")
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
    print("EXECUTION RUNS")
    print("=" * 70)
    runs = db["executions"].find({}).sort("created_at", -1)
    for run in runs:
        print(f"  {str(run['_id'])[-8:]} | {run.get('status', 'unknown'):<10} | Slices: {run.get('success_count',0)}/{run.get('total_slices',0)} | Run: {run.get('github_run_id', 'N/A')}")

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
    if args.recency_decay_minutes is not None:
        # C'est un modèle Pydantic imbriqué, on le met à jour proprement
        new_selection = settings.selection.model_copy(update={"recency_decay_minutes": args.recency_decay_minutes})
        override["selection"] = new_selection
    if args.category_cooldown is not None:
        override["category_cooldown"] = args.category_cooldown

    if override:
        settings = settings.model_copy(update=override)
        log.info("CLI overrides applied: %s", override)

    audio_count = args.batch or args.audio_count or 1
    if audio_count <= 0:
        print("--batch / --audio-count must be >= 1", file=sys.stderr)
        return 2

    rng = random.Random(args.seed) if args.seed is not None else random.Random()
    db = get_db()

    # --- Graceful shutdown handler ---
    def handle_interrupt(signum, frame):
        sig_name = signal.Signals(signum).name
        log.warning("Received %s. Marking run and pending slices as canceled...", sig_name)
        try:
            runs = db["executions"].find({"status": "running", "github_run_id": settings.github_run_id})
            for run in runs:
                db["executions"].update_one({"_id": run["_id"]}, {"$set": {"status": "canceled", "completed_at": datetime.now(timezone.utc)}})
                db["execution_slices"].update_many(
                    {"execution_id": run["_id"], "status": "pending"},
                    {"$set": {"status": "canceled", "error_message": f"Run interrupted by {sig_name} signal.", "completed_at": datetime.now(timezone.utc)}}
                )
            log.info("Marked run and pending slices as canceled.")
        except Exception as exc:
            log.error("Failed to mark executions as canceled: %s", exc)
        sys.exit(1)

    signal.signal(signal.SIGINT, handle_interrupt)
    signal.signal(signal.SIGTERM, handle_interrupt)
    # ----------------------------------

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
# Silence analysis (standalone command)
# ---------------------------------------------------------------------------

def cmd_analyze_audio(args: argparse.Namespace, settings: Settings) -> int:
    """Analyse silence positions for one or all audios.

    Usage:
        python main.py analyze-audio --audio-id <id>
        python main.py analyze-audio --all
        python main.py analyze-audio --force --all
    """
    settings.require_cloud_credentials()
    db = get_db()
    audio_repo = AudioRepo(db)
    detector = SilenceDetector(settings)

    # Determine the target set of audios.
    if args.all:
        audios = audio_repo.list_all()
    elif args.audio_id:
        single = audio_repo.get(args.audio_id)
        if single is None:
            print(f"ERROR: audio id={args.audio_id} not found", file=sys.stderr)
            return 2
        audios = [single]
    else:
        print("ERROR: provide --audio-id <id> or --all", file=sys.stderr)
        return 2

    if not args.force:
        # Skip audios that have already been analysed (unless --force).
        audios = [a for a in audios if not a.silence_analyzed]
        if not audios:
            print("Nothing to do — all selected audios are already analysed. "
                  "Use --force to re-analyse.", file=sys.stderr)
            return 0

    print(f"Analysing {len(audios)} audio(s)…", file=sys.stderr)
    succeeded = 0
    failed = 0
    for a in audios:
        with temp_workdir(prefix=f"analyze_{a.id}_", base_dir=settings.temp_dir) as tmp:
            try:
                local = media_downloader.download_to_temp(
                    a.source_url, tmp,
                    expected_extension=".mp3",
                    filename_hint=f"audio_{a.id}",
                    expect_audio=True,
                )
                positions = detector.analyze(local)
                audio_repo.save_silence_positions(a.id, positions)
                print(f"  {a.name}: {len(positions)} positions trouvées")
                succeeded += 1
            except AppBaseException as exc:
                print(f"  {a.name}: ÉCHEC — {exc}", file=sys.stderr)
                log.warning("silence analysis failed for %s: %s", a.name, exc)
                failed += 1
            except Exception as exc:
                print(f"  {a.name}: ÉCHEC — {exc}", file=sys.stderr)
                log.exception("silence analysis crashed for %s", a.name)
                failed += 1

    print(f"\nDone: {succeeded} succeeded, {failed} failed.", file=sys.stderr)
    return 0 if failed == 0 else 1


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
    p_gen.add_argument("--recency-decay-minutes", type=int, default=None,
                       help="override selection.recency_decay_minutes from config")
    p_gen.add_argument("--category-cooldown", type=int, default=None,
                       help="override category_cooldown from config")
    p_gen.add_argument("--seed", type=int, default=None,
                       help="RNG seed for reproducible selection")
    p_gen.set_defaults(func=cmd_generate)

    p_analyze = sub.add_parser(
        "analyze-audio",
        help="analyse silence positions in source audios (cached on the audio doc)",
    )
    p_analyze.add_argument("--audio-id", type=str, default=None,
                           help="analyse a single audio by its MongoDB id")
    p_analyze.add_argument("--all", action="store_true",
                           help="analyse all audios that haven't been analysed yet")
    p_analyze.add_argument("--force", action="store_true",
                           help="re-analyse even if silence_analyzed is already True")
    p_analyze.set_defaults(func=cmd_analyze_audio)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = get_settings()
    return args.func(args, settings)


if __name__ == "__main__":
    sys.exit(main())
