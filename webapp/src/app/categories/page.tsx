/**

 * /categories — list all categories with their video counts.
 */

export const dynamic = "force-dynamic";

import Link from "next/link";
import { getDb } from "@/lib/mongo";
import { stringifyIds } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { formatRelative } from "@/lib/format";

async function getCategories() {
  const db = await getDb();
  const cats = await db
    .collection("categories")
    .find({})
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

export default async function CategoriesPage() {
  const categories = await getCategories();

  return (
    <>
      <PageHeader
        eyebrow="MEDIA"
        title="Categories"
        actions={
          <Link
            href="/categories/new"
            className="px-4 py-2 hairline-all text-sm font-medium hover:bg-rule/[0.05] transition-colors"
          >
            + Add category
          </Link>
        }
        meta="Scenery categories (sea, forest, desert, …). Each category holds one or more background videos."
      />

      <div className="px-8 py-8">
        {categories.length === 0 ? (
          <div className="hairline-all p-12 text-center">
            <div className="eyebrow mb-3">EMPTY</div>
            <h2 className="font-serif text-2xl mb-2">No categories registered</h2>
            <p className="text-mute text-sm mb-6 max-w-md mx-auto">
              Add a category (e.g. &quot;sea&quot;, &quot;forest&quot;) before registering
              videos — videos belong to a category.
            </p>
            <Link
              href="/categories/new"
              className="inline-block px-4 py-2 hairline-all text-sm font-medium hover:bg-rule/[0.05] transition-colors"
            >
              Add your first category
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-px bg-rule/20">
            {categories.map((cat: any) => (
              <Link
                key={cat._id}
                href={`/categories/${cat._id}/videos`}
                className="bg-paper p-6 hover:bg-rule/[0.03] transition-colors group"
              >
                <div className="eyebrow mb-3">CATEGORY</div>
                <div className="font-serif text-2xl mb-4 group-hover:text-accent transition-colors">
                  {cat.name}
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="eyebrow mb-1">VIDEOS</div>
                    <div className="num text-lg">{cat.video_count}</div>
                  </div>
                  <div>
                    <div className="eyebrow mb-1">USAGE</div>
                    <div className="num text-lg">{cat.usage_count}</div>
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
