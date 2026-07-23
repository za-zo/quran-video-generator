export const dynamic = "force-dynamic";

import Link from "next/link";
import { getDb } from "@/lib/mongo";
import { stringifyIds } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { Pagination } from "@/components/Pagination";
import { SortBar, type SortOption } from "@/components/SortBar";
import { PostedInBadge, BadResultBadge } from "@/components/InfoBadge";
import { formatDuration, formatRelative } from "@/lib/format";

const DEFAULT_PAGE_SIZE = 12;
const PAGE_SIZE_OPTIONS = [12, 20, 50, 100];

function resolvePageSize(raw: string | undefined): number {
  const n = parseInt(raw ?? "", 10);
  if (PAGE_SIZE_OPTIONS.includes(n)) return n;
  return DEFAULT_PAGE_SIZE;
}

const SORT_OPTIONS: SortOption[] = [
  { label: "Created", value: "created" },
  { label: "Duration", value: "duration" },
  { label: "Audio", value: "audio" },
  { label: "Category", value: "category" },
  { label: "Resolution", value: "resolution" },
  { label: "Posted in", value: "posted_in" },
  { label: "Bad result", value: "bad_result" },
];

function buildSortSpec(sort: string, dir: "asc" | "desc"): Record<string, 1 | -1> {
  const d: 1 | -1 = dir === "desc" ? -1 : 1;
  switch (sort) {
    case "duration":
      return { "output.duration_seconds": d, created_at: d === 1 ? -1 : 1 };
    case "audio":
      return { audio_id: d, created_at: d === 1 ? -1 : 1 };
    case "category":
      return { selected_category_id: d, created_at: d === 1 ? -1 : 1 };
    case "resolution":
      return { "output.width": d, "output.height": d, created_at: d === 1 ? -1 : 1 };
    case "posted_in":
      // Sort by posted_in presence then alphabetical. nulls last when
      // ascending, first when descending (MongoDB default for null).
      return { posted_in: d, created_at: d === 1 ? -1 : 1 };
    case "bad_result":
      return { bad_result: d, created_at: d === 1 ? -1 : 1 };
    case "created":
    default:
      return { created_at: d, _id: 1 };
  }
}

async function getOutputs(
  page: number,
  sort: string,
  dir: "asc" | "desc",
  pageSize: number,
  badResultFilter: "all" | "good" | "bad",
) {
  const db = await getDb();
  // Base filter: only successful slices with an output
  const filter: Record<string, unknown> = {
    status: "success",
    output: { $ne: null },
  };
  if (badResultFilter === "bad") {
    filter.bad_result = true;
  } else if (badResultFilter === "good") {
    // Good = not flagged as bad (field missing or explicitly false)
    filter.$or = [{ bad_result: { $ne: true } }, { bad_result: { $exists: false } }];
  }

  const total = await db.collection("execution_slices").countDocuments(filter);
  const docs = await db
    .collection("execution_slices")
    .find(filter)
    .sort(buildSortSpec(sort, dir))
    .skip((page - 1) * pageSize)
    .limit(pageSize)
    .toArray();

  // Lookup audio names
  const audioIds = [...new Set(docs.map((d: any) => d.audio_id).filter(Boolean))];
  const audioDocs = audioIds.length
    ? await db.collection("audios").find({ _id: { $in: audioIds } }).toArray()
    : [];
  const audioMap = new Map(
    audioDocs.map((a: any) => [String(a._id), { name: a.name ?? "[deleted]", _id: String(a._id) }]),
  );

  // Lookup category names
  const catIds = [...new Set(docs.map((d: any) => d.selected_category_id).filter(Boolean))];
  const catDocs = catIds.length
    ? await db.collection("categories").find({ _id: { $in: catIds } }).toArray()
    : [];
  const catMap = new Map(
    catDocs.map((c: any) => [String(c._id), { name: c.name ?? null, _id: String(c._id) }]),
  );

  const enriched = docs.map((d: any) => {
    const audio = audioMap.get(String(d.audio_id));
    const cat = catMap.get(String(d.selected_category_id));
    return {
      ...stringifyIds(d),
      _audio_name: audio?.name ?? "[deleted]",
      _audio_id: audio?._id ?? null,
      _category_name: cat?.name ?? null,
      _category_id: cat?._id ?? null,
    };
  });

  return {
    outputs: enriched,
    total,
    totalPages: Math.ceil(total / pageSize),
  };
}

export default async function OutputsPage({
  searchParams,
}: {
  searchParams: {
    page?: string;
    sort?: string;
    dir?: string;
    pageSize?: string;
    bad?: string;
  };
}) {
  const page = Math.max(1, parseInt(searchParams.page ?? "1", 10) || 1);
  const sort = searchParams.sort ?? "created";
  const dir: "asc" | "desc" = searchParams.dir === "desc" ? "desc" : "asc";
  const pageSize = resolvePageSize(searchParams.pageSize);
  const badResultFilter: "all" | "good" | "bad" =
    searchParams.bad === "bad" ? "bad" : searchParams.bad === "good" ? "good" : "all";
  const { outputs, total, totalPages } = await getOutputs(
    page,
    sort,
    dir,
    pageSize,
    badResultFilter,
  );

  // Bad result filter tabs — preserve sort/dir but reset page
  const filterTabs = [
    { label: "all", value: "all" as const },
    { label: "good", value: "good" as const },
    { label: "bad", value: "bad" as const },
  ];
  function filterTabHref(value: "all" | "good" | "bad") {
    const params = new URLSearchParams();
    if (value !== "all") params.set("bad", value);
    if (sort && sort !== "created") params.set("sort", sort);
    if (dir === "desc") params.set("dir", "desc");
    const qs = params.toString();
    return qs ? `/outputs?${qs}` : "/outputs";
  }

  return (
    <>
      <PageHeader
        eyebrow="GALLERY"
        title="Video Outputs"
        meta="All successful slice outputs. Bad results can be filtered out. Click a card to open the slice detail; click ↗ to play the video in a new tab."
      />

      <div className="px-8 py-10">
        {/* Bad result filter */}
        <div className="flex items-center gap-1 mb-6">
          {filterTabs.map((t) => (
            <Link
              key={t.label}
              href={filterTabHref(t.value)}
              className={`px-3 py-1.5 text-xs uppercase tracking-wide-2 font-mono transition-colors ${
                badResultFilter === t.value
                  ? "bg-ink text-paper"
                  : "text-mute hover:text-ink hover:bg-paperRaised"
              }`}
            >
              {t.label}
            </Link>
          ))}
        </div>

        {/* Sort bar */}
        <div className="mb-8">
          <SortBar
            options={SORT_OPTIONS}
            activeSort={sort}
            activeDir={dir}
            preserveParams={{ bad: searchParams.bad }}
          />
        </div>

        {outputs.length === 0 ? (
          <div className="hairline-t pt-12 text-center">
            <div className="eyebrow mb-3">EMPTY</div>
            <h2 className="font-serif text-3xl mb-3">
              {badResultFilter === "bad"
                ? "No bad-result outputs"
                : badResultFilter === "good"
                  ? "No good outputs"
                  : "No outputs yet"}
            </h2>
            <p className="text-mute text-sm max-w-md mx-auto">
              {badResultFilter !== "all"
                ? "Try a different filter."
                : "Successful pipeline runs will appear here as a gallery. Trigger a run via GitHub Actions to see generated videos."}
            </p>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-8">
              {outputs.map((slice: any) => (
                <div
                  key={slice._id}
                  className="hairline-t pt-5 group relative hover:bg-paperRaised/30 transition-colors -mx-2 px-2 pb-3"
                >
                  {/* Thumbnail / video preview */}
                  <div className="relative bg-ink mb-4 aspect-video">
                    <video
                      src={slice.output?.cloudinary_url}
                      controls
                      preload="metadata"
                      className="w-full h-full"
                    />
                  </div>

                  {/* Curation badges */}
                  {(slice.posted_in || slice.bad_result) && (
                    <div className="flex items-center gap-2 flex-wrap mb-2">
                      {slice.posted_in && <PostedInBadge account={slice.posted_in} />}
                      {slice.bad_result && <BadResultBadge />}
                    </div>
                  )}

                  {/* Meta */}
                  <div className="flex items-baseline justify-between mb-2 gap-2">
                    {slice._audio_id ? (
                      <Link
                        href={`/audios/${slice._audio_id}/edit`}
                        className="text-sm font-medium text-ink hover:text-accent transition-colors truncate flex-1 min-w-0"
                        title={slice._audio_name}
                      >
                        {slice._audio_name}
                      </Link>
                    ) : (
                      <span
                        className="text-sm font-medium text-mute truncate flex-1 min-w-0"
                        title={slice._audio_name}
                      >
                        {slice._audio_name}
                      </span>
                    )}
                    <span className="num text-2xs text-mute shrink-0">
                      {formatDuration(slice.output?.duration_seconds)}
                    </span>
                  </div>

                  <div className="flex items-center justify-between text-2xs text-mute font-mono gap-2">
                    <span className="truncate flex items-center gap-1 min-w-0">
                      {slice._category_id ? (
                        <Link
                          href={`/categories/${slice._category_id}/videos`}
                          className="quiet-link hover:text-accent transition-colors truncate"
                          title={slice._category_name ?? undefined}
                        >
                          {slice._category_name}
                        </Link>
                      ) : (
                        <span className="truncate">{slice._category_name ?? "—"}</span>
                      )}
                      <span className="text-mute/60 shrink-0">·</span>
                      <span className="shrink-0">
                        {slice.output ? `${slice.output.width}×${slice.output.height}` : "—"}
                      </span>
                    </span>
                    <span className="shrink-0">{formatRelative(slice.created_at)}</span>
                  </div>

                  {/* Links: open slice + open output in new tab */}
                  <div className="mt-3 flex items-center gap-4 flex-wrap">
                    <Link
                      href={`/slices/${slice._id}`}
                      className="quiet-link text-2xs"
                    >
                      Open slice →
                    </Link>
                    <a
                      href={slice.output?.cloudinary_url}
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
              basePath="/outputs"
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
