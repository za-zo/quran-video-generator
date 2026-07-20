/**
 * /categories — list all categories with their video counts.
 */

export const dynamic = "force-dynamic";

import Link from "next/link";
import { getDb } from "@/lib/mongo";
import { stringifyIds } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { formatRelative } from "@/lib/format";

async function getCategories(search: string) {
  const db = await getDb();
  const filter: Record<string, unknown> = {};
  if (search) {
    filter.name = { $regex: search, $options: "i" };
  }
  const cats = await db
    .collection("categories")
    .find(filter)
    .sort({ _id: 1 })
    .toArray();
  const counts = await db
    .collection("videos")
    .aggregate([{ $group: { _id: "$category_id", count: { $sum: 1 } } }])
    .toArray();
  const countMap = new Map(counts.map((c) => [String(c._id), c.count]));
  return cats.map((c) => ({
    ...stringifyIds(c),
    video_count: countMap.get(String(c._id)) ?? 0,
  }));
}

export default async function CategoriesPage({
  searchParams,
}: {
  searchParams: { search?: string };
}) {
  const search = searchParams.search ?? "";
  const categories = await getCategories(search);

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
        {/* Search */}
        <form className="mb-8 max-w-md">
          <input
            type="text"
            name="search"
            defaultValue={search}
            placeholder="Search categories…"
            className="field-input"
          />
        </form>

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
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-12 gap-y-10">
            {categories.map((cat: any) => (
              <Link
                key={cat._id}
                href={`/categories/${cat._id}/videos`}
                className="hairline-t pt-5 hover:bg-paperRaised/30 transition-colors -mx-2 px-2 pb-2 group"
              >
                <div className="eyebrow mb-3">CATEGORY</div>
                <div className="font-serif text-3xl mb-5 group-hover:text-accent transition-colors tracking-tight">
                  {cat.name}
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
        )}
      </div>
    </>
  );
}
