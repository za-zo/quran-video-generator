import { ObjectId } from "mongodb";
import { notFound } from "next/navigation";
import { getDb } from "@/lib/mongo";
import { stringifyIds } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { SliceEditForm } from "@/components/SliceEditForm";
import { BackLink } from "@/components/BackLink";

export const dynamic = "force-dynamic";

async function getSlice(id: string) {
  let oid: ObjectId;
  try {
    oid = new ObjectId(id);
  } catch {
    return null;
  }
  const db = await getDb();
  const doc = await db.collection("execution_slices").findOne({ _id: oid });
  if (!doc) return null;
  const s = stringifyIds(doc) as any;
  return {
    _id: String(s._id),
    posted_in: s.posted_in ?? null,
    bad_result: s.bad_result ?? false,
  };
}

export default async function EditSlicePage({
  params,
}: {
  params: { id: string };
}) {
  const slice = await getSlice(params.id);
  if (!slice) notFound();

  return (
    <>
      <PageHeader
        eyebrow="PIPELINE / SLICE"
        title="Edit slice"
        meta="Track where this video was posted and flag bad results. These fields are curated manually — the pipeline does not set them."
      />
      <div className="px-8 py-10 max-w-2xl">
        <SliceEditForm slice={slice} />
        <div className="mt-8 text-sm">
          <BackLink href={`/slices/${params.id}`}>← back to slice</BackLink>
        </div>
      </div>
    </>
  );
}
