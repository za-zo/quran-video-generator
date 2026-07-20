export const dynamic = "force-dynamic";

import { ObjectId } from "mongodb";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getDb } from "@/lib/mongo";
import { stringifyIds } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { SortBar, type SortOption } from "@/components/SortBar";
import { formatDuration, truncateUrl, truncateName } from "@/lib/format";

const SORT_OPTIONS: SortOption[] = [
  { label: "Name", value: "name" },
  { label: "Duration", value: "duration" },
  { label: "Usage", value: "usage" },
  { label: "Last used", value: "last_used" },
  { label: "URL", value: "url" },
  { label: "Created", value: "created" },
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
    case "name":
    default:
      return { name: d, _id: 1 };
  }
}

async function getCategoryAndVideos(id: string, search: string, sort: string, dir: "asc" | "desc") {
  let oid: ObjectId;
  try {
    oid = new ObjectId(id);
  } catch {
    return null;
  }
  const db = await getDb();
  const cat = await db.collection("categories").findOne({ _id: oid });
  if (!cat) return null;

  const filter: Record<string, unknown> = { category_id: oid };
  if (search) {
    filter.name = { $regex: search, $options: "i" };
  }
  const vids = await db
    .collection("videos")
    .find(filter)
    .sort(buildSortSpec(sort, dir))
    .toArray();
  const catS = stringifyIds(cat) as any;
  return {
    category: { _id: String(catS._id), name: String(catS.name ?? "") },
    videos: vids.map((v) => stringifyIds(v)),
  };
}

export default async function CategoryVideosPage({
  params,
  searchParams,
}: {
  params: { id: string };
  searchParams: { search?: string; sort?: string; dir?: string };
}) {
  const search = searchParams.search ?? "";
  const sort = searchParams.sort ?? "name";
  const dir: "asc" | "desc" = searchParams.dir === "desc" ? "desc" : "asc";
  const data = await getCategoryAndVideos(params.id, search, sort, dir);
  if (!data) notFound();

  return (
    <>
      <PageHeader
        eyebrow={`MEDIA / ${truncateName(data.category.name.toUpperCase(), 40)}`}
        title={`Videos in "${truncateName(data.category.name, 50)}"`}
        actions={
          <div className="flex items-center gap-3">
            <Link
              href={`/categories/${data.category._id}/videos/new`}
              className="btn-primary"
            >
              + Add video
            </Link>
            <Link
              href={`/categories/${data.category._id}/edit`}
              className="btn-ghost"
            >
              Edit category
            </Link>
          </div>
        }
        meta="Background videos for this scenery category. The pipeline picks from these when this category is selected. Click a row to edit or delete."
      />

      <div className="px-8 py-10 space-y-8">
        {/* Search + sort */}
        <div className="flex items-end justify-between gap-8 flex-wrap">
          <form className="max-w-md flex-1 min-w-[16rem]">
            <input
              type="text"
              name="search"
              defaultValue={search}
              placeholder="Search videos in this category…"
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

        {/* List */}
        {data.videos.length === 0 ? (
          <div className="hairline-t pt-12 text-center">
            <div className="eyebrow mb-3">EMPTY</div>
            <h2 className="font-serif text-3xl mb-3">
              {search ? "No videos match your search" : "No videos in this category yet"}
            </h2>
            <p className="text-mute text-sm mb-8 max-w-md mx-auto">
              {search
                ? "Try a different search term."
                : "Add a background video for the pipeline to draw from when this category is selected."}
            </p>
            {!search && (
              <Link
                href={`/categories/${data.category._id}/videos/new`}
                className="btn-primary inline-flex"
              >
                Add your first video
              </Link>
            )}
          </div>
        ) : (
          <section>
            <div>
              <div className="grid grid-cols-12 gap-4 px-2 py-3 hairline-b">
                <div className="col-span-1 eyebrow">#</div>
                <div className="col-span-4 eyebrow">NAME</div>
                <div className="col-span-4 eyebrow">SOURCE URL</div>
                <div className="col-span-2 eyebrow">DURATION</div>
                <div className="col-span-1 eyebrow text-right">USES</div>
              </div>
              <ul>
                {data.videos.map((v: any, i: number) => (
                  <li key={v._id} className="hairline-b-soft last:border-b-0">
                    <Link
                      href={`/categories/${data.category._id}/videos/${v._id}/edit`}
                      className="grid grid-cols-12 gap-4 px-2 py-4 items-center hover:bg-paperRaised/50 transition-colors"
                    >
                      <div className="col-span-1 num text-2xs text-mute">
                        {String(i + 1).padStart(3, "0")}
                      </div>
                      <div
                        className="col-span-4 truncate text-sm font-medium text-ink"
                        title={v.name}
                      >
                        {v.name}
                      </div>
                      <div
                        className="col-span-4 truncate text-xs text-mute font-mono"
                        title={v.source_url}
                      >
                        {truncateUrl(v.source_url, 60)}
                      </div>
                      <div className="col-span-2 num text-sm text-inkSoft">
                        {formatDuration(v.duration_seconds)}
                      </div>
                      <div className="col-span-1 num text-sm text-right text-inkSoft">
                        {v.usage_count}
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          </section>
        )}
      </div>
    </>
  );
}
