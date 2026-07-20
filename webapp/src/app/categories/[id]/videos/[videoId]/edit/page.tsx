import { ObjectId } from "mongodb";
import { notFound } from "next/navigation";
import { getDb } from "@/lib/mongo";
import { stringifyIds } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { VideoForm } from "@/components/VideoForm";
import { BackLink } from "@/components/BackLink";

async function getVideo(categoryId: string, videoId: string) {
  let vidOid: ObjectId;
  let catOid: ObjectId;
  try {
    vidOid = new ObjectId(videoId);
    catOid = new ObjectId(categoryId);
  } catch {
    return null;
  }
  const db = await getDb();
  const doc = await db.collection("videos").findOne({ _id: vidOid, category_id: catOid });
  if (!doc) return null;
  const s = stringifyIds(doc) as any;
  return {
    _id: String(s._id),
    name: String(s.name ?? ""),
    source_url: String(s.source_url ?? ""),
    duration_seconds: Number(s.duration_seconds ?? 0),
    category_id: String(s.category_id ?? categoryId),
  };
}

async function getCategoryName(categoryId: string) {
  let catOid: ObjectId;
  try {
    catOid = new ObjectId(categoryId);
  } catch {
    return null;
  }
  const db = await getDb();
  const cat = await db.collection("categories").findOne({ _id: catOid });
  return cat?.name ?? null;
}

export default async function EditVideoPage({
  params,
}: {
  params: { id: string; videoId: string };
}) {
  const [video, categoryName] = await Promise.all([
    getVideo(params.id, params.videoId),
    getCategoryName(params.id),
  ]);
  if (!video) notFound();

  return (
    <>
      <PageHeader
        eyebrow={`MEDIA / ${categoryName?.toUpperCase() ?? "CATEGORY"} / VIDEOS`}
        title={`Edit: ${video.name}`}
        meta="Update the source URL or duration."
      />
      <div className="px-8 py-10 max-w-2xl">
        <VideoForm video={video} />
        <div className="mt-8 text-sm">
          <BackLink href={`/categories/${params.id}/videos`}>← back to videos</BackLink>
        </div>
      </div>
    </>
  );
}
