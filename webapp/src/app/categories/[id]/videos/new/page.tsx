import { ObjectId } from "mongodb";
import { notFound } from "next/navigation";
import { getDb } from "@/lib/mongo";
import { PageHeader } from "@/components/PageHeader";
import { AddVideoForm } from "@/components/AddVideoForm";
import { BackLink } from "@/components/BackLink";

async function getCategory(id: string) {
  let oid: ObjectId;
  try {
    oid = new ObjectId(id);
  } catch {
    return null;
  }
  const db = await getDb();
  const cat = await db.collection("categories").findOne({ _id: oid });
  if (!cat) return null;
  return {
    _id: String(cat._id),
    name: String(cat.name ?? ""),
  };
}

export default async function NewVideoPage({
  params,
}: {
  params: { id: string };
}) {
  const cat = await getCategory(params.id);
  if (!cat) notFound();

  return (
    <>
      <PageHeader
        eyebrow={`MEDIA / ${cat.name.toUpperCase()} / VIDEOS`}
        title="Add video"
        meta={`Register a background video for the "${cat.name}" category. The pipeline picks from these when this category is selected.`}
      />
      <div className="px-8 py-10 max-w-2xl">
        <AddVideoForm categoryId={cat._id} />
        <div className="mt-8 text-sm">
          <BackLink href={`/categories/${cat._id}/videos`}>← back to videos</BackLink>
        </div>
      </div>
    </>
  );
}
