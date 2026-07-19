import Link from "next/link";
import { getDb } from "@/lib/mongo";
import { stringifyIds } from "@/lib/types";
import { StatCard } from "@/components/StatCard";
import { StatusBadge } from "@/components/StatusBadge";
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

  // Run-level stats
  const runCountsRaw = await db
    .collection("executions")
    .aggregate([{ $group: { _id: "$status", count: { $sum: 1 } } }])
    .toArray();
  const runsByStatus: Record<string, number> = { running: 0, success: 0, failed: 0, partial: 0, canceled: 0 };
  for (const c of runCountsRaw) runsByStatus[c._id] = c.count;
  const runsTotal = Object.values(runsByStatus).reduce((a, b) => a + b, 0);

  // Slice-level stats
  const sliceCountsRaw = await db
    .collection("execution_slices")
    .aggregate([{ $group: { _id: "$status", count: { $sum: 1 } } }])
    .toArray();
  const slicesByStatus: Record<string, number> = { pending: 0, success: 0, failed: 0, canceled: 0 };
  for (const c of sliceCountsRaw) slicesByStatus[c._id] = c.count;
  const slicesTotal = Object.values(slicesByStatus).reduce((a, b) => a + b, 0);

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

  // Latest run
  const latestRun = await db.collection("executions").findOne({}, { sort: { created_at: -1 } });

  // Recent slices (for the dashboard list, show individual clips)
  const recentSlicesPipeline = [
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
        execution_id: 1,
        audio_name: { $ifNull: ["$_audio.name", "[deleted]"] },
      },
    },
  ];
  const recentSlices = await db.collection("execution_slices").aggregate(recentSlicesPipeline).toArray();

  return {
    audios,
    categories,
    videos,
    runsByStatus,
    runsTotal,
    slicesByStatus,
    slicesTotal,
    mostUsedAudio: audiosByUsage[0] ?? null,
    leastUsedAudio: audiosByUsage[audiosByUsage.length - 1] ?? null,
    mostUsedCategory: catsByUsage[0] ?? null,
    leastUsedCategory: catsByUsage[catsByUsage.length - 1] ?? null,
    recentSlices: recentSlices.map((d) => stringifyIds(d)),
    latestRun: latestRun ? stringifyIds(latestRun) : null,
    maxAudioDuration: audiosByUsage.reduce(
      (m, a) => Math.max(m, (a as any).duration_seconds || 0),
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

      <div className="px-8 py-12 space-y-16">
        {/* Hero — last run */}
        <section>
          <div className="eyebrow mb-4">LAST RUN</div>
          {data.latestRun ? (
            <div className="flex items-baseline gap-6 flex-wrap">
              <div className="font-serif text-6xl leading-none tracking-tight">
                {(data.latestRun as any).status === "success" ? (
                  <>Ran <span className="text-success">{formatRelative((data.latestRun as any).created_at)}</span></>
                ) : (data.latestRun as any).status === "failed" ? (
                  <>Failed <span className="text-failed">{formatRelative((data.latestRun as any).created_at)}</span></>
                ) : (data.latestRun as any).status === "canceled" ? (
                  <>Canceled <span className="text-mute">{formatRelative((data.latestRun as any).created_at)}</span></>
                ) : (
                  <>Running <span className="text-accent">{formatRelative((data.latestRun as any).created_at)}</span></>
                )}
              </div>
              <div className="text-mute">
                <Link
                  href={`/executions/${(data.latestRun as any)._id}`}
                  className="quiet-link"
                >
                  view run →
                </Link>
              </div>
            </div>
          ) : (
            <div className="font-serif text-3xl text-mute italic">
              No runs yet — trigger the pipeline via GitHub Actions.
            </div>
          )}
        </section>

        {/* Stat grid */}
        <section className="grid grid-cols-1 sm:grid-cols-4 gap-8">
          <StatCard
            eyebrow="AUDIOS"
            value={data.audios}
            caption="Source Quran recitations."
          />
          <StatCard
            eyebrow="CATEGORIES"
            value={data.categories}
            caption="Scenery categories."
          />
          <StatCard
            eyebrow="RUNS TOTAL"
            value={data.runsTotal}
            caption={
              <>
                <span className="text-success">{data.runsByStatus.success}</span>
                {" success · "}
                <span className="text-failed">{data.runsByStatus.failed}</span>
                {" failed · "}
                <span className="text-mute">{data.runsByStatus.canceled}</span>
                {" canceled"}
              </>
            }
          />
          <StatCard
            eyebrow="SLICES TOTAL"
            value={data.slicesTotal}
            caption={
              <>
                <span className="text-success">{data.slicesByStatus.success}</span>
                {" success · "}
                <span className="text-failed">{data.slicesByStatus.failed}</span>
                {" failed"}
              </>
            }
          />
        </section>

        {/* Media balance */}
        <section className="grid grid-cols-1 md:grid-cols-2 gap-16">
          <div>
            <div className="eyebrow mb-4 hairline-b pb-3">AUDIO BALANCE</div>
            <div className="space-y-6">
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
            <div className="eyebrow mb-4 hairline-b pb-3">CATEGORY BALANCE</div>
            <div className="space-y-6">
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

        {/* Recent slices */}
        <section>
          <div className="flex items-baseline justify-between hairline-b pb-3 mb-6">
            <div className="eyebrow">RECENT SLICES</div>
            <Link href="/executions" className="quiet-link text-sm">
              view runs →
            </Link>
          </div>
          {data.recentSlices.length === 0 ? (
            <p className="text-mute italic">
              No slices yet. The pipeline runs via GitHub Actions.
            </p>
          ) : (
            <ul className="space-y-px">
              {data.recentSlices.map((slice: any) => (
                <li key={slice._id}>
                  <Link
                    href={`/slices/${slice._id}`}
                    className="grid grid-cols-12 gap-4 items-center py-4 px-2 hover:bg-paperRaised/50 transition-colors"
                  >
                    <div className="col-span-2">
                      <StatusBadge status={slice.status} />
                    </div>
                    <div className="col-span-4 truncate">
                      <span className="text-sm font-medium">{slice.audio_name}</span>
                    </div>
                    <div className="col-span-3 num text-xs text-mute">
                      {slice.slice
                        ? `${formatDuration(slice.slice.start_seconds)} → ${formatDuration(slice.slice.end_seconds)}`
                        : "—"}
                    </div>
                    <div className="col-span-2 num text-xs text-inkSoft">
                      {slice.slice ? formatDuration(slice.slice.duration_seconds) : "—"}
                    </div>
                    <div className="col-span-1 num text-2xs text-mute text-right">
                      {formatRelative(slice.created_at)}
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
          <div className="text-base truncate">
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
      <div className="num text-xl text-mute shrink-0">
        {usageCount ?? 0}
        <span className="text-2xs ml-1">uses</span>
      </div>
    </div>
  );
}
