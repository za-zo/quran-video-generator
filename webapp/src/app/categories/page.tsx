/**
 * /categories — list all categories with their video counts.
 *
 * Backend paginated: fetches only pageSize categories per request
 * (configurable via ?pageSize= URL param, default 12).
 * (skip/limit on the categories collection, or $skip/$limit stages
 * in the aggregation pipeline when sorting by video_count).
 */

export const dynamic = "force-dynamic";

import Link from "next/link";
import { getDb } from "@/lib/mongo";
import { stringifyIds } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { Pagination } from "@/components/Pagination";
import { SortBar, type SortOption } from "@/components/SortBar";
import { formatRelative, truncateName } from "@/lib/format";

const DEFAULT_PAGE_SIZE = 12;
const PAGE_SIZE_OPTIONS = [12, 20, 50, 100];

function resolvePageSize(raw: string | undefined): number {
  const n = parseInt(raw ?? "", 10);
  if (PAGE_SIZE_OPTIONS.includes(n)) return n;
  return DEFAULT_PAGE_SIZE;
}

const SORT_OPTIONS: SortOption[] = [
  { label: "Name", value: "name" },
  { label: "Videos", value: "videos" },
  { label: "Usage", value: "usage" },
  { label: "Last used", value: "last_used" },
  { label: "Created", value: "created" },
];

function buildSortSpec(sort: string, dir: "asc" | "desc"): Record<string, 1 | -1> {
  const d: 1 | -1 = dir === "desc" ? -1 : 1;
  switch (sort) {
    case "videos":
      return { video_count: d, _id: 1 };
    case "usage":
      return { usage_count: d, _id: 1 };
    case "last_used":
      return { last_used_at: d, _id: 1 };
    case "created":
      return { created_at: d, _id: 1 };
    case "name":
    default:
      return { name: d, _id: 1 };
  }
}

async function getCategories(
  search: string,
  sort: string,
  dir: "asc" | "desc",
  page: number,
  pageSize: number,
) {
  const db = await getDb();
  const filter: Record<string, unknown> = {};
  if (search) {
    filter.name = { $regex: search, $options: "i" };
  }

  const skip = (page - 1) * pageSize;

  // For sort by video_count we need an aggregation join with $lookup.
  // Use $facet to get both the paginated rows and the total count in
  // one round-trip.
  if (sort === "videos") {
    const pipeline = [
      { $match: filter },
      {
        $lookup: {
          from: "videos",
          localField: "_id",
          foreignField: "category_id",
          as: "_videos",
        },
      },
      {
        $addFields: {
          video_count: { $size: "$_videos" },
        },
      },
      { $project: { _videos: 0 } },
      { $sort: buildSortSpec(sort, dir) },
      {
        $facet: {
          metadata: [{ $count: "total" }],
          rows: [{ $skip: skip }, { $limit: pageSize }],
        },
      },
    ];
    const result = await db.collection("categories").aggregate(pipeline).toArray();
    const facet = result[0] ?? { metadata: [], rows: [] };
    const total = facet.metadata?.[0]?.total ?? 0;
    const cats = facet.rows ?? [];
    return {
      categories: cats.map((c: any) => stringifyIds(c)),
      total,
      totalPages: Math.ceil(total / pageSize),
    };
  }

  // Non-aggregation path: count + paginated find
  const total = await db.collection("categories").countDocuments(filter);
  const cats = await db
    .collection("categories")
    .find(filter)
    .sort(buildSortSpec(sort, dir))
    .skip(skip)
    .limit(pageSize)
    .toArray();

  // Lookup video counts only for the categories on this page
  const catIds = cats.map((c: any) => c._id);
  const counts = catIds.length
    ? await db
        .collection("videos")
        .aggregate([
          { $match: { category_id: { $in: catIds } } },
          { $group: { _id: "$category_id", count: { $sum: 1 } } },
        ])
        .toArray()
    : [];
  const countMap = new Map(counts.map((c: any) => [String(c._id), c.count]));

  return {
    categories: cats.map((c: any) => ({
      ...stringifyIds(c),
      video_count: countMap.get(String(c._id)) ?? 0,
    })),
    total,
    totalPages: Math.ceil(total / pageSize),
  };
}

export default async function CategoriesPage({
  searchParams,
}: {
  searchParams: { search?: string; sort?: string; dir?: string; page?: string; pageSize?: string };
}) {
  const search = searchParams.search ?? "";
  const sort = searchParams.sort ?? "name";
  const dir: "asc" | "desc" = searchParams.dir === "desc" ? "desc" : "asc";
  const pageSize = resolvePageSize(searchParams.pageSize);
  const page = Math.max(1, parseInt(searchParams.page ?? "1", 10) || 1);
  const { categories, total, totalPages } = await getCategories(search, sort, dir, page, pageSize);

  return (
    <>
      <PageHeader
        eyebrow="MEDIA"
        title="Categories"
        actions={
          <Link href="/categories/new" className="btn-primary">
            + Add category
          </Link>
        }
        meta="Scenery categories (sea, forest, desert, …). Each category holds one or more background videos."
      />

      <div className="px-8 py-10">
        {/* Search + sort */}
        <div className="flex items-end justify-between gap-8 mb-8 flex-wrap">
          <form className="max-w-md flex-1 min-w-[16rem]">
            <input
              type="text"
              name="search"
              defaultValue={search}
              placeholder="Search categories…"
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

        {categories.length === 0 ? (
          <div className="hairline-t pt-12 text-center">
            <div className="eyebrow mb-3">EMPTY</div>
            <h2 className="font-serif text-3xl mb-3">
              {search ? "No categories match your search" : "No categories registered"}
            </h2>
            <p className="text-mute text-sm mb-8 max-w-md mx-auto">
              {search
                ? "Try a different search term."
                : "Add a category (e.g. \"sea\", \"forest\") before registering videos — videos belong to a category."}
            </p>
            {!search && (
              <Link href="/categories/new" className="btn-primary inline-flex">
                Add your first category
              </Link>
            )}
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-12 gap-y-10">
              {categories.map((cat: any) => (
                <Link
                  key={cat._id}
                  href={`/categories/${cat._id}/videos`}
                  className="hairline-t pt-5 hover:bg-paperRaised/30 transition-colors -mx-2 px-2 pb-2 group min-w-0"
                >
                  <div className="eyebrow mb-3">CATEGORY</div>
                  <div
                    className="font-serif text-3xl mb-5 group-hover:text-accent transition-colors tracking-tight truncate"
                    title={cat.name}
                  >
                    {truncateName(cat.name, 40)}
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <div className="eyebrow mb-1">VIDEOS</div>
                      <div className="num text-lg text-ink">{cat.video_count}</div>
                    </div>
                    <div>
                      <div className="eyebrow mb-1">USAGE</div>
                      <div className="num text-lg text-ink">{cat.usage_count}</div>
                    </div>
                    <div className="col-span-2">
                      <div className="eyebrow mb-1">LAST USED</div>
                      <div className="num text-sm text-mute">
                        {formatRelative(cat.last_used_at)}
                      </div>
                    </div>
                  </div>
                </Link>
              ))}
            </div>

            <Pagination
              basePath="/categories"
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
