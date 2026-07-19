# Quran Video Generator

A **100% offline, local** Python application that automatically generates
short Quran recitation videos optimised for TikTok, Instagram Reels, and
YouTube Shorts. It uses **FFmpeg** (via `subprocess`) for every media
operation and **SQLite + SQLAlchemy** for usage tracking. No cloud APIs, no
AI services — everything runs on your own machine.

---

## ✨ Features

- **Weighted-random least-used selection** for audios, categories, and
  individual background videos — never purely random, never purely
  deterministic, so content distribution stays fair but varied.
- **Non-overlapping random clip extraction** from full-surah audio files.
- **Category cooldown** to avoid the same scenery appearing in back-to-back
  outputs.
- **Mute → concat → trim → merge** FFmpeg pipeline that strips all original
  video audio and re-encodes every stage with a normalised, closed-GOP
  layout for seamless concat boundaries (no frozen frames / black flashes).
- **Resilient batch mode** — a single clip failure never crashes the run.
- **Fully configurable** via `config.yaml` and/or `.env`; nothing is
  hardcoded.
- **Modular, SOLID architecture** (Strategy / Repository / Facade) so new
  features (subtitles, translations, GUI, scheduling) can be added without
  major refactoring.

---

## 🗂 Folder layout (input)

The application expects this layout (do **not** rename the folders):

```
project/
  audios/
      001.mp3
      002.mp3
      ...
  videos/
      sea/*.mp4
      forest/*.mp4
      waterfall/*.mp4
      rivers/*.mp4
      desert/*.mp4
      mountains/*.mp4
      sky/*.mp4
```

Each sub-folder of `videos/` becomes one **category**; any sub-folder that
contains at least one `.mp4` is treated as a category.

---

## 🏗 Project structure

```
src/
  config/settings.py          – Pydantic BaseSettings (config.yaml + .env)
  database/
    models.py                 – SQLAlchemy ORM (audios, categories, videos, generation_jobs)
    session.py                – engine + session factory (SQLite)
    repository.py             – AudioRepo / CategoryRepo / VideoRepo / JobRepo
  services/
    base_selector.py          – Strategy base class (weighted random core)
    audio_selector.py         – Weighted least-used audio selection
    category_selector.py      – Weighted least-used + cooldown
    video_selector.py         – Per-clip video selection until duration covered
    clip_extractor.py         – Non-overlapping zone-based clip extraction
    video_processor.py        – All FFmpeg operations (mute, concat, trim, merge, export)
    generation_orchestrator.py – Facade that runs the full pipeline
  models/entities.py          – Dataclasses (AudioClip, VideoSegment, …)
  utils/
    ffmpeg_utils.py           – subprocess wrappers + stderr classification + retry
    logger.py                 – Rotating file + console logger
    file_utils.py             – folder scanning, temp dir cleanup
  exceptions.py               – AppBaseException + 7 specific subclasses
main.py                       – CLI: init-db / generate / stats
tests/                        – pytest unit tests (selectors, clip_extractor, video_processor)
```

---

## 🚀 Setup

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

> Python 3.10+ is required.

### 2. Install FFmpeg

`ffmpeg` and `ffprobe` must be on your `PATH`. On Debian/Ubuntu:

```bash
sudo apt-get install -ffmpeg
```

On macOS: `brew install ffmpeg`. On Windows: download from
<https://ffmpeg.org/> and add the `bin/` folder to `PATH`.

### 3. Configure the app

```bash
cp config.example.yaml config.yaml
cp .env.example .env
```

Edit `config.yaml` to taste. All values are documented inline. Environment
variables in `.env` override the YAML values.

### 4. Initialise the database and scan your media folders

```bash
python main.py init-db
```

This creates `data/app.db` and scans `audios/` and `videos/`, probing every
file with `ffprobe` to record its duration. Any unreadable file is skipped
with a warning.

---

## 🎬 Usage

### Generate videos

```bash
# Process 1 audio, generate up to 5 clips of 60s each
python main.py generate --audio-count 1 --clips-per-audio 5

# Process 10 audios in one batch run
python main.py generate --batch 10

# Override clip duration for this run only
python main.py generate --audio-count 3 --clip-duration 45

# Reproducible run (fixed RNG seed)
python main.py generate --audio-count 1 --seed 42
```

Final videos land in `output/` with deterministic, traceable filenames:

```
output/{audio_id}_{clip_index}_{YYYYMMDD_HHMMSS}.mp4
```

### Inspect usage stats

```bash
python main.py stats
```

Prints a per-audio / per-category / per-video table showing `usage_count`
and `last_used_at` so you can verify the weighted selection is fair.

---

## ⚙️ Configuration reference

| Key                            | Default       | Description                                              |
| ------------------------------ | ------------- | ------------------------------------------------------- |
| `clip_duration`                | `60`          | Length (seconds) of each generated clip                  |
| `clips_per_audio`              | `5`           | Max non-overlapping clips per audio                      |
| `resolution`                   | `1080x1920`   | Output video resolution (WxH)                            |
| `fps`                          | `30`          | Output framerate                                         |
| `video_codec`                  | `libx264`     | FFmpeg video codec                                       |
| `audio_codec`                  | `aac`         | FFmpeg audio codec                                       |
| `output_dir`                   | `./output`    | Where final MP4s are written                             |
| `temp_dir`                     | `./temp`      | Temp working dir for intermediate FFmpeg artefacts       |
| `category_cooldown`            | `3`           | Exclude categories used in the last K clips              |
| `allow_video_reuse_within_job` | `true`        | Allow cycling videos if a category is exhausted          |
| `log_level`                    | `INFO`        | `DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL`              |
| `db_path`                      | `./data/app.db` | SQLite database file                                   |
| `audios_dir`                   | `./audios`    | Source audio folder                                      |
| `videos_dir`                   | `./videos`    | Source background videos root                            |
| `selection.recency_decay_minutes` | `1440`     | Recency penalty half-life (minutes)                      |
| `selection.usage_weight`       | `1.0`         | Weight applied to inverse-usage score                    |
| `selection.recency_weight`     | `1.0`         | Weight applied to recency score                          |
| `logging.log_dir`              | `./logs`      | Log directory                                            |
| `logging.max_log_size_mb`      | `5`           | Max log file size before rotation                        |
| `logging.backup_count`         | `5`           | Rotated log files to keep                                |

---

## 🧠 Selection algorithm

For each candidate, a weight is computed as:

```
inv_usage = 1 / (1 + usage_count)
recency   = 1 - 0.5 ^ (age_minutes / recency_decay_minutes)   # or 1 if never used
weight    = usage_weight * inv_usage + recency_weight * recency
```

A candidate is then chosen via `random.choices(candidates, weights=weights)`.
If all weights are zero (e.g. all candidates fresh), the selector falls back
to uniform sampling so the pipeline always makes progress.

Category selection additionally filters out any category whose
`last_used_at` is among the K most-recent uses (configurable via
`category_cooldown`), guaranteeing visual variety in back-to-back outputs.

---

## 🛡 Error handling

Custom exception hierarchy rooted at `AppBaseException`:

```
AppBaseException
  ├── InsufficientAudioDurationError
  ├── InsufficientCategoryContentError
  ├── CorruptedMediaError
  ├── UnsupportedCodecError
  ├── FFmpegExecutionError
  ├── NoAvailableCategoryError
  └── DatabaseIntegrityError
```

Every FFmpeg call captures stderr and translates well-known failure
signatures (`Invalid data found`, `moov atom not found`, `Unknown codec`,
…) into the matching exception. Each FFmpeg call is retried once on
transient failure. If a clip fails at any step, the job is marked `failed`
in the database with the error message, temp files are cleaned up, and the
next clip proceeds — the batch never crashes.

---

## 🧪 Tests

```bash
pytest -v
```

Unit tests cover:

- **`test_selectors.py`** — weighted selection statistics over many runs
  (low-usage candidates are picked significantly more often than high-usage
  ones), cooldown filtering, video-reuse behaviour.
- **`test_clip_extractor.py`** — non-overlap property, bounds, indices,
  reproducibility with seed, error on too-short audio.
- **`test_video_processor.py`** — FFmpeg command construction (mocked
  subprocess) verifies re-encode + closed-GOP flags at every stage
  (mute, concat demuxer, concat filter_complex fallback, trim), plus
  extract/merge flags.

---

## 🔒 Constraints respected

- ❌ No AI/cloud APIs — 100% offline, local FFmpeg + Python.
- ❌ No single giant script — strict modular architecture.
- ❌ No hardcoded config — everything flows through `Settings`.
- ❌ No `random.choice()` for selection — weighted `random.choices()` everywhere.
- ❌ No batch crashes on a single failure.
- ❌ No original video audio in the final output — every background video is
  muted with `-an` before merging.

---

## 🛣 Future extensions

The architecture is intentionally open for extension:

- **Subtitles / translations** — add a new `SubtitleService` that overlays
  text via FFmpeg's `subtitles` filter in `VideoProcessor.build_clip`.
- **Multiple reciters** — add a `reciter` column to `audios` and a new
  `ReciterSelector` (same `BaseSelector` interface).
- **Different aspect ratios** — already configurable via `resolution`; just
  change `config.yaml`.
- **GUI** — `GenerationOrchestrator` is UI-agnostic; wrap it with a
  Streamlit / Tkinter / Electron shell.
- **Scheduling** — call `main.py generate --batch N` from a cron job or
  systemd timer.

---

## 📄 License

MIT — see `LICENSE` (add your own if distributing).
