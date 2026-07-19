/**

 * /executions — paginated list with status filter.
 *
 * Each row shows: status badge, audio name, slice range, duration bar,
 * relative time. Filter by status via the tabs at the top.
 */

export const dynamic = "force-dynamic";

import Link from "next/link";
import { getDb } from "@/lib/mongo";
import { stringifyIds } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { StatusBadge } from "@/components/StatusBadge";
import { DurationBar } from "@/components/DurationBar";
import { formatDuration, formatRelative } from "@/lib/format";

async function getExecutions(status: string | null) {
  const db = await getDb();
  const match: Record<string, unknown> = {};
  if (status && ["pending", "success", "failed"].includes(status)) {
    match.status = status;
  }
  const pipeline = [
    ...(Object.keys(match).length ? [{ $match: match }] : []),
    { $sort: { created_at: -1 } },
    { $limit: 200 },
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
      $project: {
        _id: 1,
        status: 1,
        slice: 1,
        output: 1,
        created_at: 1,
        audio_name: { $ifNull: ["$_audio.name", "[deleted]"] },
        audio_duration: { $ifNull: ["$_audio.duration_seconds", 0] },
        category_name: { $ifNull: ["$_category.name", null] },
      },
    },
  ];
  const docs = await db.collection("executions").aggregate(pipeline).toArray();
  const maxAudioDur = docs.reduce(
    (m, d) => Math.max(m, d.audio_duration || 0),
    1,
  );
  return {
    executions: docs.map((d) => stringifyIds(d)),
    maxAudioDur,
  };
}

export default async function ExecutionsPage({
  searchParams,
}: {
  searchParams: { status?: string };
}) {
  const status = searchParams.status ?? null;
  const { executions, maxAudioDur } = await getExecutions(status);

  const tabs = [
    { label: "all", value: null, count: null },
    { label: "success", value: "success", count: null },
    { label: "failed", value: "failed", count: null },
    { label: "pending", value: "pending", count: null },
  ];

  return (
    <>
      <PageHeader
        eyebrow="PIPELINE"
        title="Executions"
        meta="One record per generated clip. Filter by status to triage failures or review recent successes."
        actions={
          <div className="flex items-center gap-1">
            {tabs.map((t) => (
              <Link
                key={t.label}
                href={t.value ? `/executions?status=${t.value}` : "/executions"}
                className={`px-3 py-1.5 hairline-all text-xs uppercase tracking-wide-2 font-mono transition-colors ${
                  status === t.value || (!status && !t.value)
                    ? "bg-ink text-paper"
                    : "hover:bg-rule/[0.05]"
                }`}
              >
                {t.label}
              </Link>
            ))}
          </div>
        }
      />

      <div className="px-8 py-8">
        {executions.length === 0 ? (
          <div className="hairline-all p-12 text-center">
            <div className="eyebrow mb-3">EMPTY</div>
            <h2 className="font-serif text-2xl mb-2">No executions match</h2>
            <p className="text-mute text-sm">
              Try a different status filter, or trigger a pipeline run via GitHub Actions.
            </p>
          </div>
        ) : (
          <div className="hairline-all">
            <div className="grid grid-cols-12 gap-4 px-4 py-2 hairline-b bg-rule/[0.03]">
              <div className="col-span-1 eyebrow">STATUS</div>
              <div className="col-span-3 eyebrow">AUDIO</div>
              <div className="col-span-2 eyebrow">CATEGORY</div>
              <div className="col-span-3 eyebrow">SLICE</div>
              <div className="col-span-2 eyebrow">DURATION</div>
              <div className="col-span-1 eyebrow text-right">CREATED</div>
            </div>
            <ul>
              {executions.map((exec: any) => (
                <li key={exec._id} className="hairline-b last:border-b-0">
                  <Link
                    href={`/executions/${exec._id}`}
                    className="grid grid-cols-12 gap-4 px-4 py-3 items-center hover:bg-rule/[0.03] transition-colors"
                  >
                    <div className="col-span-1">
                      <StatusBadge status={exec.status} />
                    </div>
                    <div className="col-span-3 truncate text-sm font-medium">
                      {exec.audio_name}
                    </div>
                    <div className="col-span-2 truncate text-sm text-mute">
                      {exec.category_name ?? "—"}
                    </div>
                    <div className="col-span-3 num text-xs text-mute">
                      {exec.slice
                        ? `${formatDuration(exec.slice.start_seconds)} → ${formatDuration(exec.slice.end_seconds)}`
                        : "—"}
                    </div>
                    <div className="col-span-2">
                      {exec.slice && (
                        <DurationBar
                          value={exec.slice.duration_seconds}
                          max={maxAudioDur}
                          label={formatDuration(exec.slice.duration_seconds)}
                        />
                      )}
                    </div>
                    <div className="col-span-1 num text-2xs text-mute text-right">
                      {formatRelative(exec.created_at)}
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
