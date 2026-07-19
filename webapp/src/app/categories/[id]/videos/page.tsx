/**

 * /categories/[id]/videos — CRUD for videos within one category.
 *
 * Combines a list of the category's videos with an inline add form and
 * per-row edit/delete. Reuses the duration-bar motif.
 */

export const dynamic = "force-dynamic";

import { ObjectId } from "mongodb";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getDb } from "@/lib/mongo";
import { stringifyIds } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { DurationBar } from "@/components/DurationBar";
import { VideoRow } from "@/components/VideoRow";
import { AddVideoForm } from "@/components/AddVideoForm";
import { formatDuration, formatRelative, truncateUrl } from "@/lib/format";

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
  const maxDur = vids.reduce(
    (m, d) => Math.max(m, (d as any).duration_seconds || 0),
    1,
  );
  const catS = stringifyIds(cat) as any;
  return {
    category: { _id: String(catS._id), name: String(catS.name ?? "") },
    videos: vids.map((v) => stringifyIds(v)),
    maxDur,
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
        title={`Videos in “${data.category.name}”`}
        actions={
          <Link
            href={`/categories/${data.category._id}/edit`}
            className="quiet-link text-sm"
          >
            edit category →
          </Link>
        }
        meta="Background videos for this scenery category. The pipeline picks from these when this category is selected."
      />

      <div className="px-8 py-8 space-y-10">
        {/* Add form */}
        <section className="hairline-all p-6 max-w-2xl">
          <div className="eyebrow mb-3">ADD VIDEO</div>
          <AddVideoForm categoryId={data.category._id} />
        </section>

        {/* List */}
        {data.videos.length === 0 ? (
          <p className="text-mute italic">No videos in this category yet.</p>
        ) : (
          <section className="hairline-all">
            <div className="grid grid-cols-12 gap-4 px-4 py-2 hairline-b bg-rule/[0.03]">
              <div className="col-span-1 eyebrow">#</div>
              <div className="col-span-3 eyebrow">NAME</div>
              <div className="col-span-4 eyebrow">SOURCE URL</div>
              <div className="col-span-2 eyebrow">DURATION</div>
              <div className="col-span-1 eyebrow text-right">USES</div>
              <div className="col-span-1 eyebrow text-right">ACTIONS</div>
            </div>
            <ul>
              {data.videos.map((v: any, i: number) => (
                <li key={v._id} className="hairline-b last:border-b-0">
                  <div className="grid grid-cols-12 gap-4 px-4 py-3 items-center">
                    <div className="col-span-1 num text-2xs text-mute">
                      {String(i + 1).padStart(3, "0")}
                    </div>
                    <div className="col-span-3 truncate text-sm font-medium">
                      {v.name}
                    </div>
                    <div className="col-span-4 truncate text-xs text-mute font-mono">
                      {truncateUrl(v.source_url, 60)}
                    </div>
                    <div className="col-span-2">
                      <DurationBar
                        value={v.duration_seconds}
                        max={data.maxDur}
                        label={formatDuration(v.duration_seconds)}
                      />
                    </div>
                    <div className="col-span-1 num text-sm text-right">
                      {v.usage_count}
                    </div>
                    <div className="col-span-1 text-right">
                      <VideoRow video={v} />
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </>
  );
}
