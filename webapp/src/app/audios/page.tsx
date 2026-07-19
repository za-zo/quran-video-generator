/**

 * /audios — list all registered audios.
 *
 * Renders a dense table with the duration-bar motif on each row.
 * Each row links to the edit form. Add button in the header.
 */

export const dynamic = "force-dynamic";

import Link from "next/link";
import { getDb } from "@/lib/mongo";
import { stringifyIds } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { DurationBar } from "@/components/DurationBar";
import { formatDuration, formatRelative, truncateUrl } from "@/lib/format";

async function getAudios() {
  const db = await getDb();
  const docs = await db
    .collection("audios")
    .find({})
    .sort({ _id: 1 })
    .toArray();
  const maxDur = docs.reduce((m, d) => Math.max(m, d.duration_seconds || 0), 1);
  return {
    audios: docs.map((d) => stringifyIds(d)),
    maxDur,
  };
}

export default async function AudiosPage() {
  const { audios, maxDur } = await getAudios();

  return (
    <>
      <PageHeader
        eyebrow="MEDIA"
        title="Audios"
        actions={
          <Link
            href="/audios/new"
            className="px-4 py-2 hairline-all text-sm font-medium hover:bg-rule/[0.05] transition-colors"
          >
            + Add audio
          </Link>
        }
        meta="Source Quran recitations. The pipeline downloads these at runtime — no file is stored locally."
      />

      <div className="px-8 py-8">
        {audios.length === 0 ? (
          <EmptyState
            title="No audios registered"
            body="Add a remote URL for each Quran recitation you want the pipeline to draw from."
            ctaHref="/audios/new"
            ctaLabel="Add your first audio"
          />
        ) : (
          <div className="hairline-all">
            {/* Header row */}
            <div className="grid grid-cols-12 gap-4 px-4 py-2 hairline-b bg-rule/[0.03]">
              <div className="col-span-1 eyebrow">#</div>
              <div className="col-span-3 eyebrow">NAME</div>
              <div className="col-span-3 eyebrow">SOURCE URL</div>
              <div className="col-span-3 eyebrow">DURATION</div>
              <div className="col-span-1 eyebrow text-right">USES</div>
              <div className="col-span-1 eyebrow text-right">LAST USED</div>
            </div>
            {/* Rows */}
            <ul>
              {audios.map((audio: any, i: number) => (
                <li key={audio._id} className="hairline-b last:border-b-0">
                  <Link
                    href={`/audios/${audio._id}/edit`}
                    className="grid grid-cols-12 gap-4 px-4 py-3 items-center hover:bg-rule/[0.03] transition-colors"
                  >
                    <div className="col-span-1 num text-2xs text-mute">
                      {String(i + 1).padStart(3, "0")}
                    </div>
                    <div className="col-span-3 truncate text-sm font-medium">
                      {audio.name}
                    </div>
                    <div className="col-span-3 truncate text-xs text-mute font-mono">
                      {truncateUrl(audio.source_url, 50)}
                    </div>
                    <div className="col-span-3">
                      <DurationBar
                        value={audio.duration_seconds}
                        max={maxDur}
                        label={formatDuration(audio.duration_seconds)}
                      />
                    </div>
                    <div className="col-span-1 num text-sm text-right">
                      {audio.usage_count}
                    </div>
                    <div className="col-span-1 num text-2xs text-mute text-right">
                      {formatRelative(audio.last_used_at)}
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </>
  );
}

function EmptyState({
  title,
  body,
  ctaHref,
  ctaLabel,
}: {
  title: string;
  body: string;
  ctaHref: string;
  ctaLabel: string;
}) {
  return (
    <div className="hairline-all p-12 text-center">
      <div className="eyebrow mb-3">EMPTY</div>
      <h2 className="font-serif text-2xl mb-2">{title}</h2>
      <p className="text-mute text-sm mb-6 max-w-md mx-auto">{body}</p>
      <Link
        href={ctaHref}
        className="inline-block px-4 py-2 hairline-all text-sm font-medium hover:bg-rule/[0.05] transition-colors"
      >
        {ctaLabel}
      </Link>
    </div>
  );
}
