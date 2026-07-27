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

type PostedFilter = "all" | "posted" | "unposted";
type BadFilter = "all" | "good" | "bad";

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
  postedFilter: PostedFilter,
  badFilter: BadFilter,
  postedInSearch: string,
) {
  const db = await getDb();
  const filter: Record<string, unknown> = {
    status: "success",
    output: { $ne: null },
  };

  // Posted-in filter: posted / unposted / all
  if (postedFilter === "posted") {
    filter.posted_in = { $exists: true, $nin: [null, ""] };
  } else if (postedFilter === "unposted") {
    // unposted = field missing, null, or empty string
    filter.$or = [
      { posted_in: { $exists: false } },
      { posted_in: null },
      { posted_in: "" },
    ];
  }

  // Bad-result filter: good / bad / all
  if (badFilter === "bad") {
    filter.bad_result = true;
  } else if (badFilter === "good") {
    // If we already have a $or from the unposted filter, we need to
    // merge with $and. Otherwise just add a new condition.
    const goodCond = { bad_result: { $ne: true } };
    if (filter.$or) {
      filter.$and = [{ $or: filter.$or }, goodCond];
      delete filter.$or;
    } else {
      filter.bad_result = { $ne: true };
    }
  }

  // Posted-in search (regex) — only meaningful when postedFilter is "posted"
  // or "all" (searching unposted makes no sense since the field is empty).
  if (postedInSearch && postedFilter !== "unposted") {
    filter.posted_in = { $regex: postedInSearch, $options: "i" };
  }

  const total = await db.collection("execution_slices").countDocuments(filter);
  const docs = await db
    .collection("execution_slices")
    .find(filter)
    .sort(buildSortSpec(sort, dir))
    .skip((page - 1) * pageSize)
    .limit(pageSize)
    .toArray();

  const audioIds = [...new Set(docs.map((d: any) => d.audio_id).filter(Boolean))];
  const audioDocs = audioIds.length
    ? await db.collection("audios").find({ _id: { $in: audioIds } }).toArray()
    : [];
  const audioMap = new Map(
    audioDocs.map((a: any) => [String(a._id), { name: a.name ?? "[deleted]", _id: String(a._id) }]),
  );

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
    posted_filter?: string;
    posted?: string;
  };
}) {
  const page = Math.max(1, parseInt(searchParams.page ?? "1", 10) || 1);
  const sort = searchParams.sort ?? "created";
  const dir: "asc" | "desc" = searchParams.dir === "desc" ? "desc" : "asc";
  const pageSize = resolvePageSize(searchParams.pageSize);

  const postedFilter: PostedFilter =
    searchParams.posted_filter === "posted" ? "posted"
    : searchParams.posted_filter === "unposted" ? "unposted"
    : "all";

  const badFilter: BadFilter =
    searchParams.bad === "bad" ? "bad"
    : searchParams.bad === "good" ? "good"
    : "all";

  // The posted_in search only applies when the posted filter is "posted" or "all".
  // When "unposted" is selected, the search bar is hidden and the search is ignored.
  const postedInSearch = postedFilter === "unposted" ? "" : (searchParams.posted ?? "");

  const { outputs, total, totalPages } = await getOutputs(
    page, sort, dir, pageSize,
    postedFilter, badFilter, postedInSearch,
  );

  // Build a URL that preserves all filter/sort state but lets one
  // specific param change. Used by the filter-tab links so switching
  // one filter doesn't drop the other.
  function buildHref(changes: Record<string, string | undefined>): string {
    const params = new URLSearchParams();
    const current: Record<string, string | undefined> = {
      posted_filter: searchParams.posted_filter,
      posted: postedInSearch || undefined,
      bad: searchParams.bad,
      sort: sort !== "created" ? sort : undefined,
      dir: dir === "desc" ? "desc" : undefined,
      ...changes,
    };
    for (const [k, v] of Object.entries(current)) {
      if (v !== undefined && v !== null && v !== "") {
        params.set(k, v);
      }
    }
    const qs = params.toString();
    return qs ? `/outputs?${qs}` : "/outputs";
  }

  const postedTabs: { label: string; value: PostedFilter }[] = [
    { label: "All", value: "all" },
    { label: "Posted", value: "posted" },
    { label: "Not posted", value: "unposted" },
  ];

  const badTabs: { label: string; value: BadFilter }[] = [
    { label: "All", value: "all" },
    { label: "Good", value: "good" },
    { label: "Bad", value: "bad" },
  ];

  // Determine the empty-state message.
  let emptyTitle = "No outputs yet";
  let emptyMsg = "Successful pipeline runs will appear here as a gallery. Trigger a run via GitHub Actions to see generated videos.";
  if (postedInSearch) {
    emptyTitle = "No outputs match your search";
    emptyMsg = "Try a different posted_in search term.";
  } else if (postedFilter === "posted") {
    emptyTitle = "No posted outputs";
    emptyMsg = "Mark outputs as posted via the slice edit page to see them here.";
  } else if (postedFilter === "unposted") {
    emptyTitle = "No unposted outputs";
    emptyMsg = "All outputs have been posted.";
  } else if (badFilter === "bad") {
    emptyTitle = "No bad-result outputs";
    emptyMsg = "No outputs have been flagged as bad.";
  } else if (badFilter === "good") {
    emptyTitle = "No good outputs";
    emptyMsg = "Try a different filter.";
  }

  return (
    <>
      <PageHeader
        eyebrow="GALLERY"
        title="Video Outputs"
        meta="All successful slice outputs. Filter by posted status and quality, then sort as you choose. Click a card to open the slice detail; click ↗ to play the video in a new tab."
      />

      <div className="px-8 py-10">
        {/* --- Two independent filter rows --- */}

        {/* Posted-in filter */}
        <div className="mb-4">
          <div className="eyebrow mb-2">FILTER BY POSTED STATUS</div>
          <div className="flex items-center gap-1 flex-wrap">
            {postedTabs.map((t) => (
              <Link
                key={t.value}
                href={buildHref({
                  posted_filter: t.value === "all" ? undefined : t.value,
                  // Clear posted search when switching to unposted
                  posted: t.value === "unposted" ? undefined : (postedInSearch || undefined),
                  page: undefined,
                })}
                className={`px-3 py-1.5 text-xs uppercase tracking-wide-2 font-mono transition-colors ${
                  postedFilter === t.value
                    ? "bg-ink text-paper"
                    : "text-mute hover:text-ink hover:bg-paperRaised"
                }`}
              >
                {t.label}
              </Link>
            ))}
          </div>
          {/* Search bar — only when "posted" or "all" is selected */}
          {postedFilter !== "unposted" && (
            <form className="mt-3 max-w-md">
              <input
                type="text"
                name="posted"
                defaultValue={postedInSearch}
                placeholder="Search posted_in (e.g. ila.allah.almasir)…"
                className="field-input"
              />
              {/* Hidden fields to preserve other filters on form submit */}
              {searchParams.posted_filter && (
                <input type="hidden" name="posted_filter" value={searchParams.posted_filter} />
              )}
              {searchParams.bad && (
                <input type="hidden" name="bad" value={searchParams.bad} />
              )}
              {sort !== "created" && (
                <input type="hidden" name="sort" value={sort} />
              )}
              {dir === "desc" && (
                <input type="hidden" name="dir" value="desc" />
              )}
            </form>
          )}
        </div>

        {/* Bad-result filter */}
        <div className="mb-6">
          <div className="eyebrow mb-2">FILTER BY QUALITY</div>
          <div className="flex items-center gap-1 flex-wrap">
            {badTabs.map((t) => (
              <Link
                key={t.value}
                href={buildHref({
                  bad: t.value === "all" ? undefined : t.value,
                  page: undefined,
                })}
                className={`px-3 py-1.5 text-xs uppercase tracking-wide-2 font-mono transition-colors ${
                  badFilter === t.value
                    ? "bg-ink text-paper"
                    : "text-mute hover:text-ink hover:bg-paperRaised"
                }`}
              >
                {t.label}
              </Link>
            ))}
          </div>
        </div>

        {/* Sort bar */}
        <div className="mb-8">
          <SortBar
            options={SORT_OPTIONS}
            activeSort={sort}
            activeDir={dir}
            preserveParams={{
              bad: searchParams.bad,
              posted_filter: searchParams.posted_filter,
              posted: postedInSearch || undefined,
            }}
          />
        </div>

        {outputs.length === 0 ? (
          <div className="hairline-t pt-12 text-center">
            <div className="eyebrow mb-3">EMPTY</div>
            <h2 className="font-serif text-3xl mb-3">{emptyTitle}</h2>
            <p className="text-mute text-sm max-w-md mx-auto">{emptyMsg}</p>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-8">
              {outputs.map((slice: any) => (
                <div
                  key={slice._id}
                  className="hairline-t pt-5 group relative hover:bg-paperRaised/30 transition-colors -mx-2 px-2 pb-3"
                >
                  {/* Video player — natural aspect ratio */}
                  <div className="relative bg-ink mb-4 flex items-center justify-center overflow-hidden">
                    <video
                      src={slice.output?.cloudinary_url}
                      controls
                      preload="metadata"
                      className="w-full h-auto max-h-[70vh] block"
                    />
                  </div>

                  {/* Curation badges */}
                  {(slice.posted_in || slice.bad_result) && (
                    <div className="flex items-center gap-2 flex-wrap mb-2 min-w-0">
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

                  {/* Links */}
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
