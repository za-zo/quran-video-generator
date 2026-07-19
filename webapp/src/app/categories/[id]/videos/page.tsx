export const dynamic = "force-dynamic";

import { ObjectId } from "mongodb";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getDb } from "@/lib/mongo";
import { stringifyIds } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { AddVideoForm } from "@/components/AddVideoForm";
import { formatDuration, truncateUrl } from "@/lib/format";

async function getCategoryAndVideos(id: string) {
  let oid: ObjectId;
  try {
    oid = new ObjectId(id);
  } catch {
    return null;
  }
  const db = await getDb();
  const cat = await db.collection("categories").findOne({ _id: oid });
  if (!cat) return null;
  const vids = await db
    .collection("videos")
    .find({ category_id: oid })
    .sort({ _id: 1 })
    .toArray();
  const catS = stringifyIds(cat) as any;
  return {
    category: { _id: String(catS._id), name: String(catS.name ?? "") },
    videos: vids.map((v) => stringifyIds(v)),
  };
}

export default async function CategoryVideosPage({
  params,
}: {
  params: { id: string };
}) {
  const data = await getCategoryAndVideos(params.id);
  if (!data) notFound();

  return (
    <>
      <PageHeader
        eyebrow={`MEDIA / ${data.category.name.toUpperCase()}`}
        title={`Videos in "${data.category.name}"`}
        actions={
          <Link
            href={`/categories/${data.category._id}/edit`}
            className="btn-ghost"
          >
            Edit category
          </Link>
        }
        meta="Background videos for this scenery category. The pipeline picks from these when this category is selected. Click a row to edit or delete."
      />

      <div className="px-8 py-10 space-y-12">
        {/* Add form */}
        <section className="max-w-2xl">
          <div className="eyebrow mb-4 hairline-b pb-3">ADD VIDEO</div>
          <AddVideoForm categoryId={data.category._id} />
        </section>

        {/* List */}
        {data.videos.length === 0 ? (
          <p className="text-mute italic">No videos in this category yet.</p>
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
                      <div className="col-span-4 truncate text-sm font-medium text-ink">
                        {v.name}
                      </div>
                      <div className="col-span-4 truncate text-xs text-mute font-mono">
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
