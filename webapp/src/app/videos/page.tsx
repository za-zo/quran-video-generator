export const dynamic = "force-dynamic";

import Link from "next/link";
import { ObjectId } from "mongodb";
import { getDb } from "@/lib/mongo";
import { stringifyIds } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { Pagination } from "@/components/Pagination";
import { SortBar, type SortOption } from "@/components/SortBar";
import { formatDuration, formatRelative, truncateUrl } from "@/lib/format";

const DEFAULT_PAGE_SIZE = 12;
const PAGE_SIZE_OPTIONS = [12, 20, 50, 100];

function resolvePageSize(raw: string | undefined): number {
  const n = parseInt(raw ?? "", 10);
  if (PAGE_SIZE_OPTIONS.includes(n)) return n;
  return DEFAULT_PAGE_SIZE;
}

const SORT_OPTIONS: SortOption[] = [
  { label: "Name", value: "name" },
  { label: "Duration", value: "duration" },
  { label: "Usage", value: "usage" },
  { label: "Last used", value: "last_used" },
  { label: "URL", value: "url" },
  { label: "Created", value: "created" },
  { label: "Category", value: "category" },
];

function buildSortSpec(sort: string, dir: "asc" | "desc"): Record<string, 1 | -1> {
  const d: 1 | -1 = dir === "desc" ? -1 : 1;
  switch (sort) {
    case "duration":
      return { duration_seconds: d, _id: 1 };
    case "usage":
      return { usage_count: d, _id: 1 };
    case "last_used":
      return { last_used_at: d, _id: 1 };
    case "url":
      return { source_url: d, _id: 1 };
    case "created":
      return { created_at: d, _id: 1 };
    case "category":
      // category_id is an ObjectId — sort by it as a proxy for category
      // name (avoids a join just for sort). Stable tiebreak.
      return { category_id: d, _id: 1 };
    case "name":
    default:
      return { name: d, _id: 1 };
  }
}

async function getVideos(
  page: number,
  sort: string,
  dir: "asc" | "desc",
  search: string,
  pageSize: number,
) {
  const db = await getDb();
  const filter: Record<string, unknown> = {};
  if (search) {
    // Search by video name OR source_url (case-insensitive)
    filter.$or = [
      { name: { $regex: search, $options: "i" } },
      { source_url: { $regex: search, $options: "i" } },
    ];
  }

  const total = await db.collection("videos").countDocuments(filter);
  const docs = await db
    .collection("videos")
    .find(filter)
    .sort(buildSortSpec(sort, dir))
    .skip((page - 1) * pageSize)
    .limit(pageSize)
    .toArray();

  // Lookup category names for the videos on this page only
  const catIds: ObjectId[] = [];
  for (const d of docs) {
    const raw = (d as any).category_id;
    if (!raw) continue;
    if (raw instanceof ObjectId) {
      catIds.push(raw);
    } else {
      try {
        catIds.push(new ObjectId(String(raw)));
      } catch {
        // skip invalid id
      }
    }
  }
  const uniqueCatIds = [...new Set(catIds.map((id) => id.toString()))].map(
    (s) => new ObjectId(s),
  );
  const catDocs = uniqueCatIds.length
    ? await db.collection("categories").find({ _id: { $in: uniqueCatIds } }).toArray()
    : [];
  const catMap = new Map(
    catDocs.map((c: any) => [
      String(c._id),
      { name: c.name ?? null, _id: String(c._id) },
    ]),
  );

  const enriched = docs.map((d: any) => {
    const cat = catMap.get(String(d.category_id));
    return {
      ...stringifyIds(d),
      _category_name: cat?.name ?? null,
      _category_id: cat?._id ?? null,
    };
  });

  return {
    videos: enriched,
    total,
    totalPages: Math.ceil(total / pageSize),
  };
}

export default async function VideosPage({
  searchParams,
}: {
  searchParams: {
    page?: string;
    sort?: string;
    dir?: string;
    search?: string;
    pageSize?: string;
  };
}) {
  const page = Math.max(1, parseInt(searchParams.page ?? "1", 10) || 1);
  const sort = searchParams.sort ?? "created";
  const dir: "asc" | "desc" = searchParams.dir === "desc" ? "desc" : "asc";
  const search = searchParams.search ?? "";
  const pageSize = resolvePageSize(searchParams.pageSize);
  const { videos, total, totalPages } = await getVideos(page, sort, dir, search, pageSize);

  return (
    <>
      <PageHeader
        eyebrow="MEDIA"
        title="Videos"
        meta="All background videos across all categories. Watch inline, click a card to edit the video, or click ↗ to open the source URL in a new tab."
      />

      <div className="px-8 py-10">
        {/* Search + sort */}
        <div className="flex items-end justify-between gap-8 mb-8 flex-wrap">
          <form className="max-w-md flex-1 min-w-[16rem]">
            <input
              type="text"
              name="search"
              defaultValue={search}
              placeholder="Search videos by name or URL…"
              className="field-input"
            />
          </form>
          <SortBar
            options={SORT_OPTIONS}
            activeSort={sort}
            activeDir={dir}
            preserveParams={{ search: searchParams.search }}
          />
        </div>

        {videos.length === 0 ? (
          <div className="hairline-t pt-12 text-center">
            <div className="eyebrow mb-3">EMPTY</div>
            <h2 className="font-serif text-3xl mb-3">
              {search ? "No videos match your search" : "No videos registered"}
            </h2>
            <p className="text-mute text-sm max-w-md mx-auto">
              {search
                ? "Try a different search term."
                : "Add a category first, then add videos to it from the category's video list."}
            </p>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-8">
              {videos.map((video: any) => (
                <div
                  key={video._id}
                  className="hairline-t pt-5 group relative hover:bg-paperRaised/30 transition-colors -mx-2 px-2 pb-3 min-w-0"
                >
                  {/* Video player — uses the video's natural aspect ratio
                      instead of forcing 16:9. Vertical (9:16) videos
                      display tall, landscape (16:9) videos display wide. */}
                  <div className="relative bg-ink mb-4 flex items-center justify-center overflow-hidden">
                    <video
                      src={video.source_url}
                      controls
                      preload="metadata"
                      className="w-full h-auto max-h-[70vh] block"
                    />
                  </div>

                  {/* Video name + duration */}
                  <div className="flex items-baseline justify-between mb-2 gap-2 min-w-0">
                    {video._category_id ? (
                      <Link
                        href={`/categories/${video._category_id}/videos/${video._id}/edit`}
                        className="text-sm font-medium text-ink hover:text-accent transition-colors truncate flex-1 min-w-0"
                        title={video.name}
                      >
                        {video.name}
                      </Link>
                    ) : (
                      <span
                        className="text-sm font-medium text-mute truncate flex-1 min-w-0"
                        title={video.name}
                      >
                        {video.name}
                      </span>
                    )}
                    <span className="num text-2xs text-mute shrink-0">
                      {formatDuration(video.duration_seconds)}
                    </span>
                  </div>

                  {/* Category + usage */}
                  <div className="flex items-center justify-between text-2xs text-mute font-mono gap-2 mb-2">
                    <span className="truncate flex items-center gap-1 min-w-0">
                      {video._category_id ? (
                        <Link
                          href={`/categories/${video._category_id}/videos`}
                          className="quiet-link hover:text-accent transition-colors truncate"
                          title={video._category_name ?? undefined}
                        >
                          {video._category_name}
                        </Link>
                      ) : (
                        <span className="truncate">{video._category_name ?? "—"}</span>
                      )}
                      <span className="text-mute/60 shrink-0">·</span>
                      <span className="shrink-0">
                        {video.usage_count ?? 0} uses
                      </span>
                    </span>
                    <span className="shrink-0">{formatRelative(video.last_used_at)}</span>
                  </div>

                  {/* Links: edit video + open source in new tab */}
                  <div className="flex items-center gap-4 flex-wrap">
                    <Link
                      href={
                        video._category_id
                          ? `/categories/${video._category_id}/videos/${video._id}/edit`
                          : "#"
                      }
                      className="quiet-link text-2xs"
                    >
                      Edit video →
                    </Link>
                    <a
                      href={video.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="quiet-link text-2xs"
                    >
                      Open in new tab ↗
                    </a>
                  </div>
                </div>
              ))}
            </div>

            <Pagination
              basePath="/videos"
              currentPage={page}
              totalPages={totalPages}
              searchParams={searchParams}
              pageSize={pageSize}
              totalItems={total}
            />
          </>
        )}
      </div>
    </>
  );
}
