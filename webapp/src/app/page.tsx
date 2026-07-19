/**
 * Dashboard — the signature page of the webapp.
 *
 * Structure:
 *   1. Hero: a single oversized "last execution" line (when did the
 *      pipeline last run, what status) — this is the operator's first
 *      question, so it leads.
 *   2. Stat grid: 3 small cards (audios / categories / executions
 *      total). Quiet, hairline-bordered.
 *   3. Two-column "media balance" section: most vs least used audio +
 *      category. Helps the operator spot a stale or over-used asset.
 *   4. Recent executions list with the duration-bar motif.
 *
 * No big SaaS-hero with gradient — the data IS the hero.
 */

import Link from "next/link";
import { getDb } from "@/lib/mongo";
import { stringifyIds } from "@/lib/types";
import { StatCard } from "@/components/StatCard";
import { StatusBadge } from "@/components/StatusBadge";
import { DurationBar } from "@/components/DurationBar";
import { PageHeader } from "@/components/PageHeader";
import {
  formatDuration,
  formatRelative,
} from "@/lib/format";

export const dynamic = "force-dynamic";

async function getData() {
  const db = await getDb();
  const audios = await db.collection("audios").countDocuments();
  const categories = await db.collection("categories").countDocuments();
  const videos = await db.collection("videos").countDocuments();

  const execCountsRaw = await db
    .collection("executions")
    .aggregate([{ $group: { _id: "$status", count: { $sum: 1 } } }])
    .toArray();
  const execByStatus: Record<string, number> = { pending: 0, success: 0, failed: 0 };
  for (const c of execCountsRaw) execByStatus[c._id] = c.count;
  const execTotal = execByStatus.pending + execByStatus.success + execByStatus.failed;

  const audiosByUsage = await db
    .collection("audios")
    .find({})
    .sort({ usage_count: -1 })
    .toArray();
  const catsByUsage = await db
    .collection("categories")
    .find({})
    .sort({ usage_count: -1 })
    .toArray();

  // Latest execution + recent executions (with audio names joined).
  const recentPipeline = [
    { $sort: { created_at: -1 } },
    { $limit: 8 },
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
      $project: {
        _id: 1,
        status: 1,
        slice: 1,
        output: 1,
        created_at: 1,
        audio_name: { $ifNull: ["$_audio.name", "[deleted]"] },
      },
    },
  ];
  const recent = await db.collection("executions").aggregate(recentPipeline).toArray();

  const latest = recent[0] ?? null;

  return {
    audios,
    categories,
    videos,
    execByStatus,
    execTotal,
    mostUsedAudio: audiosByUsage[0] ?? null,
    leastUsedAudio: audiosByUsage[audiosByUsage.length - 1] ?? null,
    mostUsedCategory: catsByUsage[0] ?? null,
    leastUsedCategory: catsByUsage[catsByUsage.length - 1] ?? null,
    recent: recent.map((d) => stringifyIds(d)),
    latest: latest ? stringifyIds(latest) : null,
    maxAudioDuration: audiosByUsage.reduce(
      (m, a) => Math.max(m, a.duration_seconds || 0),
      1,
    ),
  };
}

export default async function DashboardPage() {
  const data = await getData();

  return (
    <>
      <PageHeader
        eyebrow="OVERVIEW"
        title="Dashboard"
        meta="Operations console for the Quran Video Generator pipeline."
      />

      <div className="px-8 py-8 space-y-12">
        {/* Hero — the operator's first question: did the pipeline run? */}
        <section>
          <div className="eyebrow mb-3">LAST EXECUTION</div>
          {data.latest ? (
            <div className="flex items-baseline gap-6 flex-wrap">
              <div className="font-serif text-5xl leading-none">
                {data.latest.status === "success" ? (
                  <>Ran <span className="text-success">{formatRelative(data.latest.created_at)}</span></>
                ) : data.latest.status === "failed" ? (
                  <>Failed <span className="text-failed">{formatRelative(data.latest.created_at)}</span></>
                ) : (
                  <>Pending <span className="text-warn">{formatRelative(data.latest.created_at)}</span></>
                )}
              </div>
              <div className="text-mute">
                on <span className="italic">{data.latest.audio_name}</span>
                {" — "}
                <Link
                  href={`/executions/${data.latest._id}`}
                  className="quiet-link"
                >
                  view execution →
                </Link>
              </div>
            </div>
          ) : (
            <div className="font-serif text-3xl text-mute italic">
              No executions yet — trigger the pipeline via GitHub Actions.
            </div>
          )}
        </section>

        {/* Stat grid */}
        <section className="grid grid-cols-1 sm:grid-cols-3 gap-px bg-rule/20">
          <StatCard
            eyebrow="AUDIOS REGISTERED"
            value={data.audios}
            caption="Source Quran recitations available for clip generation."
          />
          <StatCard
            eyebrow="CATEGORIES"
            value={data.categories}
            caption="Scenery categories used as background footage."
          />
          <StatCard
            eyebrow="EXECUTIONS TOTAL"
            value={data.execTotal}
            caption={
              <>
                <span className="text-success">{data.execByStatus.success}</span>
                {" success · "}
                <span className="text-failed">{data.execByStatus.failed}</span>
                {" failed · "}
                <span className="text-warn">{data.execByStatus.pending}</span>
                {" pending"}
              </>
            }
          />
        </section>

        {/* Media balance — most vs least used */}
        <section className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <div>
            <div className="eyebrow mb-3 hairline-b pb-2">AUDIO BALANCE</div>
            <div className="space-y-4">
              <BalanceRow
                label="Most used"
                name={data.mostUsedAudio?.name}
                usageCount={data.mostUsedAudio?.usage_count}
                href={data.mostUsedAudio ? `/audios` : null}
              />
              <BalanceRow
                label="Least used"
                name={data.leastUsedAudio?.name}
                usageCount={data.leastUsedAudio?.usage_count}
                href={data.leastUsedAudio ? `/audios` : null}
              />
            </div>
          </div>
          <div>
            <div className="eyebrow mb-3 hairline-b pb-2">CATEGORY BALANCE</div>
            <div className="space-y-4">
              <BalanceRow
                label="Most used"
                name={data.mostUsedCategory?.name}
                usageCount={data.mostUsedCategory?.usage_count}
                href={data.mostUsedCategory ? `/categories` : null}
              />
              <BalanceRow
                label="Least used"
                name={data.leastUsedCategory?.name}
                usageCount={data.leastUsedCategory?.usage_count}
                href={data.leastUsedCategory ? `/categories` : null}
              />
            </div>
          </div>
        </section>

        {/* Recent executions */}
        <section>
          <div className="flex items-baseline justify-between hairline-b pb-3 mb-4">
            <div className="eyebrow">RECENT EXECUTIONS</div>
            <Link href="/executions" className="quiet-link text-sm">
              view all →
            </Link>
          </div>
          {data.recent.length === 0 ? (
            <p className="text-mute italic">
              No executions yet. The pipeline runs via GitHub Actions.
            </p>
          ) : (
            <ul className="space-y-px">
              {data.recent.map((exec: any) => (
                <li key={exec._id}>
                  <Link
                    href={`/executions/${exec._id}`}
                    className="grid grid-cols-12 gap-4 items-center py-3 px-2 hover:bg-rule/[0.03] transition-colors"
                  >
                    <div className="col-span-1">
                      <StatusBadge status={exec.status} />
                    </div>
                    <div className="col-span-4 truncate">
                      <span className="text-sm font-medium">{exec.audio_name}</span>
                    </div>
                    <div className="col-span-3 num text-xs text-mute">
                      {exec.slice
                        ? `${formatDuration(exec.slice.start_seconds)} → ${formatDuration(exec.slice.end_seconds)}`
                        : "—"}
                    </div>
                    <div className="col-span-3">
                      {exec.slice && (
                        <DurationBar
                          value={exec.slice.duration_seconds}
                          max={data.maxAudioDuration}
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
          )}
        </section>
      </div>
    </>
  );
}

function BalanceRow({
  label,
  name,
  usageCount,
  href,
}: {
  label: string;
  name?: string;
  usageCount?: number;
  href: string | null;
}) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <div className="min-w-0">
        <div className="eyebrow mb-1">{label}</div>
        {name ? (
          <div className="text-sm truncate">
            {href ? (
              <Link href={href} className="quiet-link">
                {name}
              </Link>
            ) : (
              name
            )}
          </div>
        ) : (
          <div className="text-sm text-mute italic">none registered</div>
        )}
      </div>
      <div className="num text-lg text-mute shrink-0">
        {usageCount ?? 0}
        <span className="text-2xs ml-1">uses</span>
      </div>
    </div>
  );
}
