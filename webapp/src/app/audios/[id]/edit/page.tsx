import { ObjectId } from "mongodb";
import { notFound } from "next/navigation";
import { getDb } from "@/lib/mongo";
import { stringifyIds } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { AudioForm } from "@/components/AudioForm";
import { BackLink } from "@/components/BackLink";
import { SilenceTimeline } from "@/components/SilenceTimeline";
import { SilenceResetButton } from "@/components/SilenceResetButton";
import { truncateName, formatDuration } from "@/lib/format";

export const dynamic = "force-dynamic";

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
    silence_positions: Array.isArray(s.silence_positions) ? s.silence_positions : [],
    silence_analyzed: Boolean(s.silence_analyzed),
    silence_analyzed_at: s.silence_analyzed_at ?? null,
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
        title={`Edit: ${truncateName(audio.name, 50)}`}
        meta="Update the source URL or duration."
      />
      <div className="px-8 py-10 max-w-2xl">
        <AudioForm audio={audio} />

        {/* Silence analysis section */}
        <section className="mt-16">
          <div className="eyebrow mb-4 hairline-b pb-3">POSITIONS DE SILENCE</div>
          {audio.silence_analyzed ? (
            <>
              <SilenceTimeline
                audioDuration={audio.duration_seconds}
                audioName={audio.name}
                positions={audio.silence_positions}
                analyzedAt={audio.silence_analyzed_at}
              />
              <div className="mt-6">
                <SilenceResetButton audioId={audio._id} />
              </div>
            </>
          ) : (
            <p className="text-mute italic text-sm">
              Non analysé — l&apos;analyse se fait automatiquement au prochain
              run, ou via{" "}
              <code className="font-mono text-xs bg-paperRaised px-1 py-0.5">
                python main.py analyze-audio --audio-id {audio._id}
              </code>
              .
            </p>
          )}
        </section>

        <div className="mt-8 text-sm">
          <BackLink href="/audios">← back to audios</BackLink>
        </div>
      </div>
    </>
  );
}
