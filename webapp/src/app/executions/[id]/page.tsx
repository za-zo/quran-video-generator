/**

 * /executions/[id] — detail view of one execution.
 *
 * Contains the signature element: the slice timeline (a horizontal bar
 * showing the selected slice within the source audio's full duration).
 * Below it: the selected videos as a grid, the embedded Cloudinary
 * video player (if successful), error details (if failed), and the
 * GitHub Actions run link.
 */

export const dynamic = "force-dynamic";

import { ObjectId } from "mongodb";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getDb } from "@/lib/mongo";
import { stringifyIds } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { StatusBadge } from "@/components/StatusBadge";
import { SliceTimeline } from "@/components/SliceTimeline";
import {
  formatDuration,
  formatTimestamp,
  truncateUrl,
} from "@/lib/format";

async function getExecution(id: string) {
  let oid: ObjectId;
  try {
    oid = new ObjectId(id);
  } catch {
    return null;
  }
  const db = await getDb();
  const pipeline = [
    { $match: { _id: oid } },
    {
      $lookup: {
        from: "audios",
        localField: "audio_id",
        foreignField: "_id",
        as: "_audio",
      },
    },
    { $unwind: { path: "$_audio", preserveNullAndEmptyArrays: true } },
    {
      $lookup: {
        from: "categories",
        localField: "selected_category_id",
        foreignField: "_id",
        as: "_category",
      },
    },
    { $unwind: { path: "$_category", preserveNullAndEmptyArrays: true } },
    {
      $lookup: {
        from: "videos",
        localField: "selected_video_ids",
        foreignField: "_id",
        as: "_videos",
      },
    },
    {
      $project: {
        _id: 1,
        status: 1,
        error_message: 1,
        slice: 1,
        output: 1,
        github_run_id: 1,
        created_at: 1,
        completed_at: 1,
        audio: {
          _id: { $ifNull: ["$_audio._id", null] },
          name: { $ifNull: ["$_audio.name", null] },
          source_url: { $ifNull: ["$_audio.source_url", null] },
          duration_seconds: { $ifNull: ["$_audio.duration_seconds", 0] },
        },
        category: {
          _id: { $ifNull: ["$_category._id", null] },
          name: { $ifNull: ["$_category.name", null] },
        },
        videos: {
          $map: {
            input: "$_videos",
            as: "v",
            in: {
              _id: "$$v._id",
              name: "$$v.name",
              source_url: "$$v.source_url",
              duration_seconds: "$$v.duration_seconds",
            },
          },
        },
      },
    },
  ];
  const docs = await db.collection("executions").aggregate(pipeline).toArray();
  return docs.length ? stringifyIds(docs[0]) : null;
}

export default async function ExecutionDetailPage({
  params,
}: {
  params: { id: string };
}) {
  const exec = await getExecution(params.id);
  if (!exec) notFound();

  const githubRepo = process.env.GITHUB_REPO || "";
  const actionsUrl =
    githubRepo && exec.github_run_id
      ? `https://github.com/${githubRepo}/actions/runs/${exec.github_run_id}`
      : null;

  return (
    <>
      <PageHeader
        eyebrow="PIPELINE / EXECUTION"
        title={`Execution`}
        actions={<StatusBadge status={exec.status} />}
        meta={
          <span>
            <span className="num text-xs">{exec._id}</span>
            {" · "}
            created {formatTimestamp(exec.created_at)}
            {exec.completed_at && (
              <>
                {" · "}
                completed {formatTimestamp(exec.completed_at)}
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
                  view Actions run ↗
                </a>
              </>
            )}
          </span>
        }
      />

      <div className="px-8 py-8 space-y-12">
        {/* Signature element: slice timeline */}
        {exec.slice && exec.audio && (
          <SliceTimeline
            audioDuration={exec.audio.duration_seconds}
            audioName={exec.audio.name}
            sliceStart={exec.slice.start_seconds}
            sliceEnd={exec.slice.end_seconds}
            sliceDuration={exec.slice.duration_seconds}
          />
        )}

        {/* Output: Cloudinary player if success */}
        {exec.status === "success" && exec.output && (
          <section>
            <div className="eyebrow mb-3 hairline-b pb-2">OUTPUT</div>
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="lg:col-span-2">
                <video
                  src={exec.output.cloudinary_url}
                  controls
                  className="w-full hairline-all bg-ink"
                  preload="metadata"
                />
              </div>
              <div className="space-y-3 text-sm">
                <Detail label="Duration" value={formatDuration(exec.output.duration_seconds)} />
                <Detail label="Resolution" value={`${exec.output.width}×${exec.output.height}`} />
                <Detail
                  label="Cloudinary URL"
                  value={
                    <a
                      href={exec.output.cloudinary_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="quiet-link font-mono text-xs break-all"
                    >
                      {truncateUrl(exec.output.cloudinary_url, 80)}
                    </a>
                  }
                />
                <Detail
                  label="Public ID"
                  value={
                    <span className="font-mono text-xs break-all">
                      {exec.output.cloudinary_public_id}
                    </span>
                  }
                />
              </div>
            </div>
          </section>
        )}

        {/* Error: if failed or canceled */}
        {(exec.status === "failed" || exec.status === "canceled") && exec.error_message && (
          <section>
            <div className={`eyebrow mb-3 hairline-b pb-2 ${exec.status === "canceled" ? "text-mute" : "text-failed"}`}>
              {exec.status === "canceled" ? "CANCELED" : "ERROR"}
            </div>
            <pre className="hairline-all p-4 bg-failed/[0.03] text-sm text-failed font-mono whitespace-pre-wrap break-words">
              {exec.error_message}
            </pre>
          </section>
        )}

        {/* Source audio + category */}
        <section className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <div>
            <div className="eyebrow mb-3 hairline-b pb-2">SOURCE AUDIO</div>
            {exec.audio?._id ? (
              <Link
                href={`/audios/${exec.audio._id}/edit`}
                className="block hover:bg-rule/[0.03] transition-colors -mx-2 px-2 py-1"
              >
                <div className="text-sm font-medium">{exec.audio.name}</div>
                <div className="num text-xs text-mute mt-1">
                  {formatDuration(exec.audio.duration_seconds)} total
                </div>
                <div className="font-mono text-2xs text-mute mt-1 truncate">
                  {truncateUrl(exec.audio.source_url, 60)}
                </div>
              </Link>
            ) : (
              <div className="text-mute italic text-sm">
                [deleted audio — execution references a missing record]
              </div>
            )}
          </div>
          <div>
            <div className="eyebrow mb-3 hairline-b pb-2">SELECTED CATEGORY</div>
            {exec.category?._id ? (
              <Link
                href={`/categories/${exec.category._id}/videos`}
                className="block hover:bg-rule/[0.03] transition-colors -mx-2 px-2 py-1"
              >
                <div className="font-serif text-lg">{exec.category.name}</div>
                <div className="text-2xs text-mute mt-1">
                  → view videos in this category
                </div>
              </Link>
            ) : (
              <div className="text-mute italic text-sm">
                {exec.status === "failed"
                  ? "no category was selected (pipeline failed before selection)"
                  : "[deleted category]"}
              </div>
            )}
          </div>
        </section>

        {/* Selected videos */}
        {exec.videos && exec.videos.length > 0 && (
          <section>
            <div className="eyebrow mb-3 hairline-b pb-2">
              SELECTED VIDEOS ({exec.videos.length})
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-px bg-rule/20">
              {exec.videos.map((v: any, i: number) => (
                <div key={v._id} className="bg-paper p-4">
                  <div className="flex items-baseline justify-between mb-2">
                    <span className="num text-2xs text-mute">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <span className="num text-xs text-mute">
                      {formatDuration(v.duration_seconds)}
                    </span>
                  </div>
                  <div className="text-sm font-medium truncate">{v.name}</div>
                  <div className="font-mono text-2xs text-mute mt-1 truncate">
                    {truncateUrl(v.source_url, 50)}
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Slice details (numeric backup to the timeline) */}
        {exec.slice && (
          <section>
            <div className="eyebrow mb-3 hairline-b pb-2">SLICE DETAILS</div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
              <Detail label="Index" value={exec.slice.index} />
              <Detail label="Start" value={formatDuration(exec.slice.start_seconds)} />
              <Detail label="End" value={formatDuration(exec.slice.end_seconds)} />
              <Detail label="Duration" value={formatDuration(exec.slice.duration_seconds)} />
            </div>
          </section>
        )}

        <div className="pt-6">
          <Link href="/executions" className="quiet-link text-sm">
            ← back to executions
          </Link>
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
    <div>
      <div className="eyebrow mb-1">{label}</div>
      <div className="num text-sm">{value}</div>
    </div>
  );
}
