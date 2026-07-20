export const dynamic = "force-dynamic";

import Link from "next/link";
import { notFound } from "next/navigation";
import { getDb } from "@/lib/mongo";
import { stringifyIds } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { StatusBadge } from "@/components/StatusBadge";
import { Pagination } from "@/components/Pagination";
import { BackLink } from "@/components/BackLink";
import { formatDuration, formatRelative, formatTimestamp } from "@/lib/format";

const PAGE_SIZE = 30;

async function getRun(id: string) {
  const db = await getDb();
  let oid;
  try {
    const { ObjectId } = await import("mongodb");
    oid = new ObjectId(id);
  } catch {
    return null;
  }
  const run = await db.collection("executions").findOne({ _id: oid });
  return run ? stringifyIds(run) : null;
}

async function getSlices(executionId: string, page: number) {
  const db = await getDb();
  const { ObjectId } = await import("mongodb");
  let oid;
  try {
    oid = new ObjectId(executionId);
  } catch {
    return { slices: [], totalPages: 0 };
  }
  const filter = { execution_id: oid };
  const total = await db.collection("execution_slices").countDocuments(filter);
  const docs = await db
    .collection("execution_slices")
    .find(filter)
    .sort({ "slice.index": 1 })
    .skip((page - 1) * PAGE_SIZE)
    .limit(PAGE_SIZE)
    .toArray();

  // Lookup audio names (audio_id is stored as ObjectId in MongoDB)
  const audioIds = [...new Set(docs.map((d: any) => d.audio_id).filter(Boolean))];
  const audioDocs = audioIds.length
    ? await db.collection("audios").find({ _id: { $in: audioIds } }).toArray()
    : [];
  const audioMap = new Map(audioDocs.map((a: any) => [String(a._id), a]));

  // Lookup category names
  const catIds = [...new Set(docs.map((d: any) => d.selected_category_id).filter(Boolean))];
  const catDocs = catIds.length
    ? await db.collection("categories").find({ _id: { $in: catIds } }).toArray()
    : [];
  const catMap = new Map(catDocs.map((c: any) => [String(c._id), c]));

  const enriched = docs.map((d: any) => {
    const audio = audioMap.get(String(d.audio_id));
    const cat = catMap.get(String(d.selected_category_id));
    return {
      ...stringifyIds(d),
      _audio_name: audio?.name ?? "[deleted]",
      _category_name: cat?.name ?? null,
    };
  });

  return {
    slices: enriched,
    totalPages: Math.ceil(total / PAGE_SIZE),
  };
}

export default async function ExecutionDetailPage({
  params,
  searchParams,
}: {
  params: { id: string };
  searchParams: { page?: string };
}) {
  const run = await getRun(params.id);
  if (!run) notFound();

  const page = Math.max(1, parseInt(searchParams.page ?? "1", 10) || 1);
  const { slices, totalPages } = await getSlices(String(run._id), page);

  const githubRepo = process.env.GITHUB_REPO || "";
  const actionsUrl =
    githubRepo && (run as any).github_run_id
      ? `https://github.com/${githubRepo}/actions/runs/${(run as any).github_run_id}`
      : null;

  return (
    <>
      <PageHeader
        eyebrow="PIPELINE / RUN"
        title="Execution Run"
        actions={<StatusBadge status={(run as any).status} />}
        meta={
          <span>
            <span className="num text-xs">{String(run._id)}</span>
            {" · "}
            created {formatTimestamp((run as any).created_at)}
            {(run as any).completed_at && (
              <>
                {" · "}
                completed {formatTimestamp((run as any).completed_at)}
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

      <div className="px-8 py-10 space-y-12">
        {/* Summary stats */}
        <section className="grid grid-cols-2 md:grid-cols-4 gap-8">
          <div className="hairline-t pt-4">
            <div className="eyebrow mb-2">TOTAL SLICES</div>
            <div className="num text-2xl text-ink">{(run as any).total_slices ?? "—"}</div>
          </div>
          <div className="hairline-t pt-4">
            <div className="eyebrow mb-2">SUCCESS</div>
            <div className="num text-2xl text-success">{(run as any).success_count ?? 0}</div>
          </div>
          <div className="hairline-t pt-4">
            <div className="eyebrow mb-2">FAILED</div>
            <div className="num text-2xl text-failed">{(run as any).failed_count ?? 0}</div>
          </div>
          <div className="hairline-t pt-4">
            <div className="eyebrow mb-2">CREATED</div>
            <div className="num text-sm text-inkSoft">{formatRelative((run as any).created_at)}</div>
          </div>
        </section>

        {/* Slices list */}
        <section>
          <div className="eyebrow mb-4 hairline-b pb-3">
            SLICES ({(run as any).total_slices ?? 0})
          </div>
          {slices.length === 0 ? (
            <p className="text-mute italic text-sm">No slices found for this run.</p>
          ) : (
            <>
              <div>
                <div className="grid grid-cols-12 gap-4 px-2 py-3 hairline-b">
                  <div className="col-span-1 eyebrow">#</div>
                  <div className="col-span-1 eyebrow">STATUS</div>
                  <div className="col-span-3 eyebrow">AUDIO</div>
                  <div className="col-span-2 eyebrow">CATEGORY</div>
                  <div className="col-span-2 eyebrow">SLICE</div>
                  <div className="col-span-2 eyebrow">DURATION</div>
                  <div className="col-span-1 eyebrow text-right">CREATED</div>
                </div>
                <ul>
                  {slices.map((slice: any, i: number) => (
                    <li key={slice._id} className="hairline-b-soft last:border-b-0">
                      <Link
                        href={`/slices/${slice._id}`}
                        className="grid grid-cols-12 gap-4 px-2 py-4 items-center hover:bg-paperRaised/50 transition-colors"
                      >
                        <div className="col-span-1 num text-2xs text-mute">
                          {String((page - 1) * PAGE_SIZE + i + 1).padStart(3, "0")}
                        </div>
                        <div className="col-span-1">
                          <StatusBadge status={slice.status} />
                        </div>
                        <div className="col-span-3 truncate text-sm font-medium text-ink">
                          {slice._audio_name}
                        </div>
                        <div className="col-span-2 truncate text-sm text-mute">
                          {slice._category_name ?? "—"}
                        </div>
                        <div className="col-span-2 num text-xs text-mute">
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
              </div>
              <Pagination
                basePath={`/executions/${run._id}`}
                currentPage={page}
                totalPages={totalPages}
                searchParams={searchParams}
              />
            </>
          )}
        </section>

        <div className="pt-4">
          <BackLink href="/executions">← back to runs</BackLink>
        </div>
      </div>
    </>
  );
}
