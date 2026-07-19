export const dynamic = "force-dynamic";

import Link from "next/link";
import { getDb } from "@/lib/mongo";
import { stringifyIds } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { StatusBadge } from "@/components/StatusBadge";
import { Pagination } from "@/components/Pagination";
import { formatRelative, formatDuration } from "@/lib/format";

const PAGE_SIZE = 30;

async function getRuns(status: string | null, page: number) {
  const db = await getDb();
  const match: Record<string, unknown> = {};
  if (status && ["running", "success", "failed", "partial", "canceled"].includes(status)) {
    match.status = status;
  }
  const total = await db.collection("executions").countDocuments(match);
  const docs = await db
    .collection("executions")
    .find(match)
    .sort({ created_at: -1 })
    .skip((page - 1) * PAGE_SIZE)
    .limit(PAGE_SIZE)
    .toArray();
  return {
    runs: docs.map((d) => stringifyIds(d)),
    totalPages: Math.ceil(total / PAGE_SIZE),
  };
}

export default async function ExecutionsPage({
  searchParams,
}: {
  searchParams: { status?: string; page?: string };
}) {
  const status = searchParams.status ?? null;
  const page = Math.max(1, parseInt(searchParams.page ?? "1", 10) || 1);
  const { runs, totalPages } = await getRuns(status, page);

  const tabs = [
    { label: "all", value: null },
    { label: "running", value: "running" },
    { label: "success", value: "success" },
    { label: "failed", value: "failed" },
    { label: "partial", value: "partial" },
    { label: "canceled", value: "canceled" },
  ];

  return (
    <>
      <PageHeader
        eyebrow="PIPELINE"
        title="Execution Runs"
        meta="One record per GitHub Actions run. Click to see individual slices."
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
        {runs.length === 0 ? (
          <div className="hairline-all p-12 text-center">
            <div className="eyebrow mb-3">EMPTY</div>
            <h2 className="font-serif text-2xl mb-2">No runs found</h2>
            <p className="text-mute text-sm">
              Try a different status filter, or trigger a pipeline run via GitHub Actions.
            </p>
          </div>
        ) : (
          <>
            <div className="hairline-all">
              <div className="grid grid-cols-12 gap-4 px-4 py-2 hairline-b bg-rule/[0.03]">
                <div className="col-span-2 eyebrow">STATUS</div>
                <div className="col-span-2 eyebrow">GITHUB RUN</div>
                <div className="col-span-2 eyebrow">SLICES</div>
                <div className="col-span-1 eyebrow text-right">SUCCESS</div>
                <div className="col-span-1 eyebrow text-right">FAILED</div>
                <div className="col-span-2 eyebrow">DURATION</div>
                <div className="col-span-2 eyebrow text-right">CREATED</div>
              </div>
              <ul>
                {runs.map((run: any) => (
                  <li key={run._id} className="hairline-b last:border-b-0">
                    <Link
                      href={`/executions/${run._id}`}
                      className="grid grid-cols-12 gap-4 px-4 py-3 items-center hover:bg-rule/[0.03] transition-colors"
                    >
                      <div className="col-span-2">
                        <StatusBadge status={run.status} />
                      </div>
                      <div className="col-span-2 num text-xs text-mute truncate">
                        {run.github_run_id ?? "—"}
                      </div>
                      <div className="col-span-2 num text-sm">
                        {run.total_slices ?? "—"}
                      </div>
                      <div className="col-span-1 num text-sm text-success text-right">
                        {run.success_count ?? 0}
                      </div>
                      <div className="col-span-1 num text-sm text-failed text-right">
                        {run.failed_count ?? 0}
                      </div>
                      <div className="col-span-2">
                        {run.completed_at && run.created_at
                          ? formatRelative(new Date(run.completed_at).getTime() - new Date(run.created_at).getTime() > 0
                              ? (new Date(run.completed_at).getTime() - new Date(run.created_at).getTime()) / 1000
                              : 0)
                          : run.status === "running" ? "in progress…" : "—"}
                      </div>
                      <div className="col-span-2 num text-2xs text-mute text-right">
                        {formatRelative(run.created_at)}
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
            <Pagination
              basePath="/executions"
              currentPage={page}
              totalPages={totalPages}
              searchParams={searchParams}
            />
          </>
        )}
      </div>
    </>
  );
}
