import { ObjectId } from "mongodb";
import { notFound } from "next/navigation";
import { getDb } from "@/lib/mongo";
import { stringifyIds } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { AudioForm } from "@/components/AudioForm";
import { BackLink } from "@/components/BackLink";

async function getAudio(id: string) {
  let oid: ObjectId;
  try {
    oid = new ObjectId(id);
  } catch {
    return null;
  }
  const db = await getDb();
  const doc = await db.collection("audios").findOne({ _id: oid });
  if (!doc) return null;
  const s = stringifyIds(doc) as any;
  return {
    _id: String(s._id),
    name: String(s.name ?? ""),
    source_url: String(s.source_url ?? ""),
    duration_seconds: Number(s.duration_seconds ?? 0),
  };
}

export default async function EditAudioPage({
  params,
}: {
  params: { id: string };
}) {
  const audio = await getAudio(params.id);
  if (!audio) notFound();

  return (
    <>
      <PageHeader
        eyebrow="MEDIA / AUDIOS"
        title={`Edit: ${audio.name}`}
        meta="Update the source URL or duration."
      />
      <div className="px-8 py-10 max-w-2xl">
        <AudioForm audio={audio} />
        <div className="mt-8 text-sm">
          <BackLink href="/audios">← back to audios</BackLink>
        </div>
      </div>
    </>
  );
}
