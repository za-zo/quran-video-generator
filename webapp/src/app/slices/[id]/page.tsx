export const dynamic = "force-dynamic";

import { ObjectId } from "mongodb";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getDb } from "@/lib/mongo";
import { stringifyIds } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { StatusBadge } from "@/components/StatusBadge";
import { SliceTimeline } from "@/components/SliceTimeline";
import { BackLink } from "@/components/BackLink";
import {
  formatDuration,
  formatTimestamp,
  truncateUrl,
} from "@/lib/format";

async function getSlice(id: string) {
  let oid;
  try {
    oid = new ObjectId(id);
  } catch {
    return null;
  }
  const db = await getDb();
  const slice = await db.collection("execution_slices").findOne({ _id: oid });
  if (!slice) return null;

  const enriched: any = { ...stringifyIds(slice) };

  // Lookup audio
  if (slice.audio_id) {
    try {
      const audioId = slice.audio_id instanceof ObjectId ? slice.audio_id : new ObjectId(slice.audio_id as string);
      const audio = await db.collection("audios").findOne({ _id: audioId });
      if (audio) enriched._audio = stringifyIds(audio);
    } catch {}
  }

  // Lookup category
  if (slice.selected_category_id) {
    try {
      const catId = slice.selected_category_id instanceof ObjectId ? slice.selected_category_id : new ObjectId(slice.selected_category_id as string);
      const cat = await db.collection("categories").findOne({ _id: catId });
      if (cat) enriched._category = stringifyIds(cat);
    } catch {}
  }

  // Lookup videos
  if (slice.selected_video_ids && slice.selected_video_ids.length > 0) {
    const videoOids = slice.selected_video_ids
      .map((vid: any) => {
        if (vid instanceof ObjectId) return vid;
        try { return new ObjectId(vid as string); } catch { return null; }
      })
      .filter(Boolean);
    if (videoOids.length) {
      const videos = await db.collection("videos").find({ _id: { $in: videoOids } }).toArray();
      enriched._videos = videos.map((v) => stringifyIds(v));
    }
  }

  return enriched;
}

export default async function SliceDetailPage({
  params,
}: {
  params: { id: string };
}) {
  const slice = await getSlice(params.id);
  if (!slice) notFound();

  const githubRepo = process.env.GITHUB_REPO || "";
  const actionsUrl =
    githubRepo && slice.github_run_id
      ? `https://github.com/${githubRepo}/actions/runs/${slice.github_run_id}`
      : null;

  const runUrl = slice.execution_id ? `/executions/${slice.execution_id}` : null;

  return (
    <>
      <PageHeader
        eyebrow="PIPELINE / SLICE"
        title="Slice Detail"
        actions={<StatusBadge status={slice.status} />}
        meta={
          <span>
            <span className="num text-xs">{slice._id}</span>
            {slice.execution_id && (
              <>
                {" · "}
                run:{" "}
                <Link href={`/executions/${slice.execution_id}`} className="quiet-link">
                  {slice.execution_id}
                </Link>
              </>
            )}
            {actionsUrl && (
              <>
                {" · "}
                <a
                  href={actionsUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="quiet-link"
                >
                  Actions ↗
                </a>
              </>
            )}
          </span>
        }
      />

      <div className="px-8 py-10 space-y-16">
        {/* Slice timeline */}
        {slice.slice && slice._audio && (
          <SliceTimeline
            audioDuration={slice._audio.duration_seconds}
            audioName={slice._audio.name}
            sliceStart={slice.slice.start_seconds}
            sliceEnd={slice.slice.end_seconds}
            sliceDuration={slice.slice.duration_seconds}
          />
        )}

        {/* Output: Cloudinary player if success */}
        {slice.status === "success" && slice.output && (
          <section>
            <div className="flex items-baseline justify-between hairline-b pb-3 mb-6">
              <div className="eyebrow">OUTPUT</div>
              <a
                href={slice.output.cloudinary_url}
                target="_blank"
                rel="noopener noreferrer"
                className="quiet-link text-sm"
              >
                Open in new tab ↗
              </a>
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              {/* Video player — constrained to max-w-xs (320px) so it
                  doesn't dominate the page. The full URL + open-in-new-
                  tab link live in the details column. */}
              <div className="lg:col-span-1 max-w-xs">
                <video
                  src={slice.output.cloudinary_url}
                  controls
                  className="w-full bg-ink"
                  preload="metadata"
                />
              </div>
              <div className="lg:col-span-2 space-y-4 text-sm">
                <Detail label="Duration" value={formatDuration(slice.output.duration_seconds)} />
                <Detail label="Resolution" value={`${slice.output.width}×${slice.output.height}`} />
                <Detail
                  label="Cloudinary URL"
                  value={
                    <a
                      href={slice.output.cloudinary_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="quiet-link font-mono text-xs break-all"
                    >
                      {truncateUrl(slice.output.cloudinary_url, 80)}
                    </a>
                  }
                />
                <Detail
                  label="Public ID"
                  value={
                    <span className="font-mono text-xs break-all">
                      {slice.output.cloudinary_public_id}
                    </span>
                  }
                />
              </div>
            </div>
          </section>
        )}

        {/* Error: if failed or canceled */}
        {(slice.status === "failed" || slice.status === "canceled") && slice.error_message && (
          <section>
            <div className={`eyebrow mb-3 hairline-b pb-3 ${slice.status === "canceled" ? "text-mute" : "text-failed"}`}>
              {slice.status === "canceled" ? "CANCELED" : "ERROR"}
            </div>
            <pre className="bg-paperRaised p-5 text-sm text-failed font-mono whitespace-pre-wrap break-words">
              {slice.error_message}
            </pre>
          </section>
        )}

        {/* Source audio + category */}
        <section className="grid grid-cols-1 md:grid-cols-2 gap-12">
          <div>
            <div className="eyebrow mb-4 hairline-b pb-3">SOURCE AUDIO</div>
            {slice._audio ? (
              <div className="block">
                <Link
                  href={`/audios/${slice._audio._id}/edit`}
                  className="block hover:bg-paperRaised/50 transition-colors -mx-2 px-2 py-2"
                >
                  <div className="text-sm font-medium text-ink">{slice._audio.name}</div>
                  <div className="num text-xs text-mute mt-1">
                    {formatDuration(slice._audio.duration_seconds)} total
                  </div>
                  <div className="font-mono text-2xs text-mute mt-1 truncate">
                    {truncateUrl(slice._audio.source_url, 60)}
                  </div>
                </Link>
                <div className="mt-2">
                  <a
                    href={slice._audio.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="quiet-link text-sm"
                  >
                    Listen in new tab ↗
                  </a>
                </div>
              </div>
            ) : (
              <div className="text-mute italic text-sm">
                [deleted audio]
              </div>
            )}
          </div>
          <div>
            <div className="eyebrow mb-4 hairline-b pb-3">SELECTED CATEGORY</div>
            {slice._category ? (
              <Link
                href={`/categories/${slice._category._id}/videos`}
                className="block hover:bg-paperRaised/50 transition-colors -mx-2 px-2 py-2"
              >
                <div className="font-serif text-lg text-ink">{slice._category.name}</div>
                <div className="text-2xs text-mute mt-1">
                  → view videos in this category
                </div>
              </Link>
            ) : (
              <div className="text-mute italic text-sm">
                {slice.status === "failed"
                  ? "no category was selected (pipeline failed before selection)"
                  : "[deleted category]"}
              </div>
            )}
          </div>
        </section>

        {/* Selected videos */}
        {slice._videos && slice._videos.length > 0 && (
          <section>
            <div className="eyebrow mb-4 hairline-b pb-3">
              SELECTED VIDEOS ({slice._videos.length})
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
              {slice._videos.map((v: any, i: number) => (
                <div key={v._id} className="hairline-t pt-4">
                  <div className="flex items-baseline justify-between mb-2">
                    <span className="num text-2xs text-mute">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <div className="flex items-center gap-2">
                      <a
                        href={v.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="quiet-link text-2xs"
                        aria-label={`Open ${v.name} in new tab`}
                      >
                        open ↗
                      </a>
                      <span className="num text-xs text-mute">
                        {formatDuration(v.duration_seconds)}
                      </span>
                    </div>
                  </div>
                  <div className="text-sm font-medium text-ink truncate">{v.name}</div>
                  <div className="font-mono text-2xs text-mute mt-1 truncate">
                    {truncateUrl(v.source_url, 50)}
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Slice details */}
        {slice.slice && (
          <section>
            <div className="eyebrow mb-4 hairline-b pb-3">SLICE DETAILS</div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
              <Detail label="Index" value={slice.slice.index} />
              <Detail label="Start" value={formatDuration(slice.slice.start_seconds)} />
              <Detail label="End" value={formatDuration(slice.slice.end_seconds)} />
              <Detail label="Duration" value={formatDuration(slice.slice.duration_seconds)} />
            </div>
          </section>
        )}

        <div className="pt-6">
          {runUrl ? (
            <BackLink href={runUrl}>← back to run</BackLink>
          ) : (
            <BackLink href="/executions">← back to runs</BackLink>
          )}
        </div>
      </div>
    </>
  );
}

function Detail({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="hairline-t pt-4">
      <div className="eyebrow mb-2">{label}</div>
      <div className="num text-sm text-ink">{value}</div>
    </div>
  );
}
