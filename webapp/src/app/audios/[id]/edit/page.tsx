/**
 * /audios/[id]/edit — edit an existing audio.
 */

import { ObjectId } from "mongodb";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getDb } from "@/lib/mongo";
import { stringifyIds } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { AudioForm } from "@/components/AudioForm";

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
        meta="Update the source URL or duration. Name changes propagate to all executions that reference this audio."
      />
      <div className="px-8 py-8 max-w-2xl">
        <AudioForm mode="edit" audio={audio} />
        <div className="mt-4 text-sm">
          <Link href="/audios" className="quiet-link">
            ← back to audios
          </Link>
        </div>
      </div>
    </>
  );
}
