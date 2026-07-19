# Quran Video Generator

A **cloud-native** Python + Next.js system that automatically generates
short Quran recitation videos optimised for TikTok, Instagram Reels, and
YouTube Shorts. The Python pipeline runs in **GitHub Actions**, metadata
lives in **MongoDB Atlas**, and final MP4s are uploaded to **Cloudinary**.
A companion Next.js webapp lets the operator register media and browse
results.

---

## ✨ Features

- **Weighted-random least-used selection** for audios, categories, and
  individual background videos — fair but varied distribution.
- **Non-overlapping random clip extraction** from full-surah audio files.
- **Category cooldown** to avoid the same scenery in back-to-back outputs.
- **FFmpeg pipeline** that re-encodes every stage (mute, concat, trim,
  merge) with a normalised, closed-GOP layout — no frozen frames or black
  flashes at concat boundaries.
- **Cloud-native execution**: GitHub Actions runs the pipeline; MongoDB
  Atlas stores all metadata; Cloudinary hosts the final MP4s.
- **Resilient batch mode** — a single clip failure never crashes the run.
- **Next.js admin webapp** with a slice-timeline visualisation showing
  exactly which portion of which audio became which video.
- **Fully configurable** via `config.yaml` and/or `.env`; nothing is
  hardcoded.

---

## 🏗 Architecture

```
                    ┌─────────────────────┐
                    │   MongoDB Atlas      │  ← single source of truth
                    │  (audios, categories,│
                    │   videos, executions)│
                    └──────────┬───────────┘
                               │
        ┌──────────────────────┼───────────────────────┐
        │                      │                        │
┌───────▼────────┐   ┌─────────▼─────────┐   ┌──────────▼─────────┐
│ GitHub Actions  │   │  Next.js Webapp    │   │   Cloudinary        │
│ runs Python     │   │  /webapp           │   │  (final MP4 videos) │
│ pipeline on a   │   │  - register media  │   │                     │
│ schedule/manual │   │  - browse results  │   │                     │
└─────────────────┘   └────────────────────┘   └─────────────────────┘
```

**Media lifecycle (audio/video INPUT):**
1. Operator registers a media file's remote URL via the Next.js webapp.
2. Webapp writes a document into MongoDB's `audios` / `videos` collection
   containing the URL + metadata (NOT the file itself).
3. When the Python pipeline runs (in GitHub Actions), it downloads the
   needed media file(s) into a runner-local temp directory just before
   processing, uses them, then discards them when the job finishes.

**Output lifecycle (generated video):**
1. Pipeline builds the final MP4 locally on the runner (FFmpeg).
2. Pipeline uploads the final MP4 to Cloudinary.
3. Pipeline writes an `executions` document in MongoDB with the Cloudinary
   URL + metadata.
4. Local temp file is deleted.

---

## 🗂 Project structure

```
quran-video-generator/
├── .github/workflows/
│   └── generate-videos.yml       # GitHub Actions: schedule + manual trigger
├── src/
│   ├── config/settings.py        # Pydantic settings (Mongo + Cloudinary + ffmpeg params)
│   ├── database/
│   │   ├── mongo_client.py       # cached MongoClient + test-injection hook
│   │   └── repository.py         # AudioRepo / CategoryRepo / VideoRepo / ExecutionRepo
│   ├── services/
│   │   ├── audio_selector.py     # weighted least-used selection
│   │   ├── category_selector.py  # weighted + cooldown
│   │   ├── video_selector.py     # per-clip selection until duration covered
│   │   ├── clip_extractor.py     # non-overlapping zone-based clip extraction
│   │   ├── video_processor.py    # FFmpeg operations (mute, concat, trim, merge)
│   │   └── generation_orchestrator.py  # Facade: select → download → ffmpeg → upload
│   ├── models/entities.py        # AudioRecord / VideoSegment / AudioClip / …
│   ├── utils/
│   │   ├── ffmpeg_utils.py       # subprocess wrappers + closed-GOP re-encoding
│   │   ├── media_downloader.py   # stream remote URLs → runner-local temp
│   │   ├── cloudinary_uploader.py # upload final MP4 → Cloudinary
│   │   ├── file_utils.py         # temp_workdir, cleanup, ensure_dir
│   │   └── logger.py             # rotating file + console
│   └── exceptions.py             # AppBaseException + subclasses
├── tests/                        # pytest (36 tests, mongomock-backed)
├── webapp/                       # Next.js 14 admin webapp (separate README)
├── main.py                       # CLI: init-db / generate / stats
├── requirements.txt              # Python deps (pymongo, cloudinary, requests, …)
├── config.example.yaml           # copy to config.yaml
└── .env.example                  # copy to .env
```

---

## 🚀 Setup

### 1. Provision cloud infrastructure

**MongoDB Atlas**: create a free M0 cluster, add a database user, and
allow access from anywhere (or from GitHub Actions IPs). Copy the
connection string.

**Cloudinary**: create a free account, copy your cloud name / API key /
API secret from the dashboard.

### 2. Set GitHub repository secrets

Go to your repo → Settings → Secrets and variables → Actions → New
repository secret, and add:

| Secret name                 | Value                                            |
| --------------------------- | ------------------------------------------------ |
| `MONGODB_URI`               | `mongodb+srv://user:password@cluster0.xxx.mongodb.net` |
| `MONGODB_DB_NAME`           | `quran_video_generator` (or your chosen name)    |
| `CLOUDINARY_CLOUD_NAME`     | your Cloudinary cloud name                       |
| `CLOUDINARY_API_KEY`        | your Cloudinary API key                          |
| `CLOUDINARY_API_SECRET`     | your Cloudinary API secret                       |

### 3. (Optional) Set up the webapp locally

```bash
cd webapp
npm install
cp .env.local.example .env.local
# edit .env.local: set MONGODB_URI to the same value as above
npm run dev
```

Register your audios and videos via the webapp (`/audios`, `/categories`,
`/categories/[id]/videos`). Each entry needs a remote URL pointing to a
directly downloadable file.

### 4. Run the pipeline

Trigger the GitHub Actions workflow manually:
- Go to your repo → Actions → "generate-videos" → Run workflow.
- Choose inputs: `audio_count` (how many audios to process), or tick
  `smoke_test` for a cheap 1-audio / 1-clip / 15s end-to-end check.

Or run locally (with env vars set):

```bash
pip install -r requirements.txt
python main.py init-db          # ensures MongoDB indexes + pings the cluster
python main.py generate --audio-count 1 --clips-per-audio 5
python main.py stats            # show usage counters
```

Final videos are uploaded to Cloudinary; the webapp's `/executions` page
shows them with an embedded player.

---

## ⚙️ Configuration reference

| Key                            | Default                  | Description                                              |
| ------------------------------ | ------------------------ | ------------------------------------------------------- |
| `mongodb_uri`                  | (required env)           | MongoDB Atlas connection string                         |
| `mongodb_db_name`              | `quran_video_generator`  | Database name                                            |
| `cloudinary_cloud_name`        | (required env)           | Cloudinary cloud name                                    |
| `cloudinary_api_key`           | (required env)           | Cloudinary API key                                       |
| `cloudinary_api_secret`        | (required env)           | Cloudinary API secret                                    |
| `github_run_id`                | (auto by workflow)       | Stored on each execution for traceability                |
| `clip_duration`                | `60`                     | Length (seconds) of each generated clip                  |
| `clips_per_audio`              | `5`                      | Max non-overlapping clips per audio                      |
| `resolution`                   | `1080x1920`              | Output video resolution (WxH)                            |
| `fps`                          | `30`                     | Output framerate                                         |
| `video_codec`                  | `libx264`                | FFmpeg video codec                                       |
| `audio_codec`                  | `aac`                    | FFmpeg audio codec                                       |
| `category_cooldown`            | `3`                      | Exclude categories used in the last K clips              |
| `allow_video_reuse_within_job` | `true`                   | Allow cycling videos if a category is exhausted          |

---

## 🗄 MongoDB collections

The schema is shared between the Python pipeline and the Next.js webapp.
Field names MUST stay in sync — see `src/database/repository.py` and
`webapp/src/lib/types.ts`.

### `audios`
```js
{
  _id: ObjectId,
  name: "001",
  source_url: "https://...",         // remote URL downloaded at runtime
  duration_seconds: 240.0,
  usage_count: 0,
  last_used_at: null,
  created_at: ISODate,
}
```

### `categories`
```js
{
  _id: ObjectId,
  name: "sea",
  usage_count: 0,
  last_used_at: null,
  created_at: ISODate,
}
```

### `videos`
```js
{
  _id: ObjectId,
  category_id: ObjectId,             // ref categories._id
  name: "sea_0",
  source_url: "https://...",
  duration_seconds: 35.0,
  usage_count: 0,
  last_used_at: null,
  created_at: ISODate,
}
```

### `executions` (one document per generated clip)
```js
{
  _id: ObjectId,
  audio_id: ObjectId,
  status: "pending" | "success" | "failed",
  error_message: null,
  slice: {
    index: 0,
    start_seconds: 12.4,
    end_seconds: 72.4,
    duration_seconds: 60.0,
  },
  selected_category_id: ObjectId,
  selected_video_ids: [ObjectId, ...],
  output: {
    cloudinary_url: "https://res.cloudinary.com/.../video.mp4",
    cloudinary_public_id: "quran-video-generator/executions/<id>",
    duration_seconds: 60.0,
    width: 1080,
    height: 1920,
  } | null,
  github_run_id: "1234567890",
  created_at: ISODate,
  completed_at: ISODate | null,
}
```

**Indexes** (created by `init-db` / `ensure_indexes`):
- `audios`: `usage_count`, unique `name`
- `categories`: `usage_count`, `last_used_at`, unique `name`
- `videos`: compound `(category_id, usage_count)`, unique `(category_id, name)`
- `executions`: `created_at` (desc), `status`

**Compatibility note**: the previous SQLite table was named
`generation_jobs`. The Mongo collection is renamed to `executions` to
match the new terminology used throughout the webapp. The Python
repository exposes a `JobRepo = ExecutionRepo` alias for backwards
compatibility, but new code should use `ExecutionRepo` directly.

---

## 🧠 Selection algorithm

For each candidate, a weight is computed as:

```
inv_usage = 1 / (1 + usage_count)
recency   = 1 - 0.5 ^ (age_minutes / recency_decay_minutes)   # or 1 if never used
weight    = usage_weight * inv_usage + recency_weight * recency
```

A candidate is then chosen via `random.choices(candidates, weights=weights)`.
If all weights are zero, the selector falls back to uniform sampling.

Category selection additionally filters out any category whose
`last_used_at` is among the K most-recent uses (configurable via
`category_cooldown`).

---

## 🛡 Error handling

Custom exception hierarchy rooted at `AppBaseException`. Every FFmpeg /
download / upload call is retried once on transient failure. If a clip
fails at any step, the execution is marked `failed` in MongoDB with the
error message, temp files are cleaned up, and the next clip proceeds —
the batch never crashes. A run with at least one success exits 0 (Actions
green); only exits non-zero if literally nothing succeeded.

---

## 🧪 Tests

```bash
pytest -v
```

36 unit tests, fully offline (mongomock for the DB, mocked subprocesses
for FFmpeg, mocked `requests` for downloads, mocked Cloudinary SDK for
uploads):

- `test_selectors.py` — weighted distribution statistics, cooldown, reuse.
- `test_clip_extractor.py` — non-overlap, bounds, indices, reproducibility.
- `test_video_processor.py` — FFmpeg command construction (re-encode +
  closed-GOP flags at every stage).
- `test_media_downloader.py` — happy path, non-2xx, network errors,
  retry-once, empty file, ffprobe validation hook.
- `test_cloudinary_uploader.py` — happy path, SDK exception translation,
  missing credentials, missing file, unexpected response.

---

## 🔒 Constraints respected

- ❌ No media files committed to the repo — only remote URLs in MongoDB.
- ❌ No local SQLite — MongoDB Atlas is the single source of truth.
- ❌ No output files left on disk — final MP4s go to Cloudinary.
- ❌ No batch crashes on a single failure.
- ❌ No `random.choice()` for selection — weighted `random.choices()`.
- ❌ No original video audio in the final output — every background video
  is muted with `-an` before merging.
- ❌ No auth on the webapp — intentional single-operator tool. Don't
  expose it to the public internet without your own gateway.

---

## 🛣 Future extensions

- **Subtitles / translations** — overlay text via FFmpeg's `subtitles`
  filter in `VideoProcessor.build_clip`.
- **Multiple reciters** — add a `reciter` field to `audios` and a
  `ReciterSelector`.
- **Different aspect ratios** — already configurable via `resolution`.
- **Scheduling** — tune the cron in `.github/workflows/generate-videos.yml`.
- **Webapp auth** — wrap with NextAuth.js or a reverse-proxy gateway if
  multi-operator use is ever needed.

---

## 📄 License

MIT — see `LICENSE` (add your own if distributing).
