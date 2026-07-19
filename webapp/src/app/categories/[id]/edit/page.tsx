/**
 * /categories/[id]/edit — rename or delete a category.
 *
 * DELETE requires the category to have no videos. The UI surfaces the
 * conflict clearly and links to the videos page so the operator can
 * reassign or delete them first.
 */

import { ObjectId } from "mongodb";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getDb } from "@/lib/mongo";
import { stringifyIds } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { CategoryEditForm } from "@/components/CategoryEditForm";

async function getCategory(id: string) {
  let oid: ObjectId;
  try {
    oid = new ObjectId(id);
  } catch {
    return null;
  }
  const db = await getDb();
  const doc = await db.collection("categories").findOne({ _id: oid });
  if (!doc) return null;
  const s = stringifyIds(doc) as any;
  const videoCount = await db
    .collection("videos")
    .countDocuments({ category_id: oid });
  return {
    _id: String(s._id),
    name: String(s.name ?? ""),
    video_count: videoCount,
  };
}

export default async function EditCategoryPage({
  params,
}: {
  params: { id: string };
}) {
  const cat = await getCategory(params.id);
  if (!cat) notFound();

  return (
    <>
      <PageHeader
        eyebrow="MEDIA / CATEGORIES"
        title={`Edit: ${cat.name}`}
        meta={
          cat.video_count > 0
            ? `This category has ${cat.video_count} video(s). Delete or reassign them before deleting the category.`
            : "This category has no videos — safe to delete."
        }
      />
      <div className="px-8 py-8 max-w-2xl">
        <CategoryEditForm category={cat} />
        <div className="mt-6 text-sm">
          <Link href={`/categories/${cat._id}/videos`} className="quiet-link">
            → manage videos in this category
          </Link>
        </div>
        <div className="mt-2 text-sm">
          <Link href="/categories" className="quiet-link">
            ← back to categories
          </Link>
        </div>
      </div>
    </>
  );
}
