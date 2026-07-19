# Quran Video Generator — Admin Webapp

A Next.js 14 admin console for the cloud-native Quran Video Generator
pipeline. Register media (audios + background videos by remote URL),
browse executions, and inspect the exact slice of each audio that became
each generated video.

**No authentication** — this is an internal single-operator tool by design.
Do not expose it to the public internet without putting your own auth
gateway in front.

## Stack

- Next.js 14 (App Router) + TypeScript
- Tailwind CSS 3 with a custom design system (IBM Plex family, hairline
  rules, restrained oxblood accent — see `tailwind.config.ts`)
- `mongodb` driver (no Prisma — the Python pipeline owns the schema, the
  webapp reads/writes the same documents directly)
- Server Components + Route Handlers for all data access; no client-side
  MongoDB exposure

## Setup

```bash
cd webapp
npm install
cp .env.local.example .env.local
# edit .env.local: fill in MONGODB_URI (same value as the Python pipeline)
npm run dev
```

Open <http://localhost:3000>. The dashboard reads from the same MongoDB
cluster the Python pipeline writes to.

## Required environment variables

| Variable           | Required | Description                                                  |
| ------------------ | -------- | ------------------------------------------------------------ |
| `MONGODB_URI`      | yes      | MongoDB Atlas connection string (same as Python's)           |
| `MONGODB_DB_NAME`  | no       | Database name (default: `quran_video_generator`)             |
| `GITHUB_REPO`      | no       | `owner/repo` slug, used to build "view Actions run" links on the execution detail page |

`MONGODB_URI` is read server-side only — it is never exposed to the client
bundle.

## Pages

| Path                              | Purpose                                                          |
| --------------------------------- | ---------------------------------------------------------------- |
| `/`                               | Dashboard — last execution, stat grid, media balance, recent.   |
| `/audios`                         | List all audios with the duration-bar motif. Add / edit / delete.|
| `/audios/new`                     | Form to register a new audio by remote URL.                     |
| `/audios/[id]/edit`               | Edit existing audio + delete (soft-warns if executions reference it). |
| `/categories`                     | Grid of categories with video counts.                            |
| `/categories/new`                 | Create a new category.                                          |
| `/categories/[id]/edit`           | Rename / delete (refuses if videos exist).                      |
| `/categories/[id]/videos`         | CRUD for videos within a category (inline add + per-row edit).  |
| `/executions`                     | Paginated list with status filter tabs.                         |
| `/executions/[id]`                | Detail view — **slice timeline** signature element + Cloudinary video player + selected videos grid. |

## Design notes

The dashboard leads with "last execution" (the operator's first question)
instead of a generic SaaS hero. The signature element is the slice timeline
on `/executions/[id]` — a horizontal bar showing the selected slice within
the source audio's full duration, with mono tick labels. The duration-bar
motif recurs across list pages so duration becomes a visual quantity, not
just a number.

Typography is IBM Plex Sans / Serif / Mono throughout — open-source and
distinctive, reads as "technical archive" rather than generic SaaS. The
palette is warm ivory paper (`#FAF8F4`), near-black ink (`#0F1419`),
blue-grey rule lines, and a single restrained oxblood accent (`#A8331B`)
used only for emphasis and the slice-timeline fill.

## Development

```bash
npm run dev      # dev server on port 3000
npm run lint     # ESLint
npm run build    # production build (verifies all routes compile)
```

All dynamic pages set `export const dynamic = "force-dynamic"` so they
render server-side on every request (they all need a live MongoDB
connection).
