export const dynamic = "force-dynamic";

import Link from "next/link";
import { getDb } from "@/lib/mongo";
import { stringifyIds } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { StatusBadge } from "@/components/StatusBadge";
import { Pagination } from "@/components/Pagination";
import { SortBar, type SortOption } from "@/components/SortBar";
import { formatRelative } from "@/lib/format";

const DEFAULT_PAGE_SIZE = 30;
const PAGE_SIZE_OPTIONS = [12, 20, 50, 100];

function resolvePageSize(raw: string | undefined): number {
  const n = parseInt(raw ?? "", 10);
  if (PAGE_SIZE_OPTIONS.includes(n)) return n;
  return DEFAULT_PAGE_SIZE;
}

const SORT_OPTIONS: SortOption[] = [
  { label: "Created", value: "created" },
  { label: "Status", value: "status" },
  { label: "Slices", value: "slices" },
  { label: "Success", value: "success" },
  { label: "Failed", value: "failed" },
  { label: "Run ID", value: "run" },
];

function buildSortSpec(sort: string, dir: "asc" | "desc"): Record<string, 1 | -1> {
  const d: 1 | -1 = dir === "desc" ? -1 : 1;
  switch (sort) {
    case "status":
      return { status: d, _id: 1 };
    case "slices":
      return { total_slices: d, _id: 1 };
    case "success":
      return { success_count: d, _id: 1 };
    case "failed":
      return { failed_count: d, _id: 1 };
    case "run":
      return { github_run_id: d, _id: 1 };
    case "created":
    default:
      return { created_at: d, _id: 1 };
  }
}

async function getRuns(status: string | null, page: number, sort: string, dir: "asc" | "desc", pageSize: number) {
  const db = await getDb();
  const match: Record<string, unknown> = {};
  if (status && ["running", "success", "failed", "partial", "canceled"].includes(status)) {
    match.status = status;
  }
  const total = await db.collection("executions").countDocuments(match);
  const docs = await db
    .collection("executions")
    .find(match)
    .sort(buildSortSpec(sort, dir))
    .skip((page - 1) * pageSize)
    .limit(pageSize)
    .toArray();
  return {
    runs: docs.map((d) => stringifyIds(d)),
    total,
    totalPages: Math.ceil(total / pageSize),
  };
}

export default async function ExecutionsPage({
  searchParams,
}: {
  searchParams: { status?: string; page?: string; sort?: string; dir?: string; pageSize?: string };
}) {
  const status = searchParams.status ?? null;
  const pageSize = resolvePageSize(searchParams.pageSize);
  const page = Math.max(1, parseInt(searchParams.page ?? "1", 10) || 1);
  const sort = searchParams.sort ?? "created";
  const dir: "asc" | "desc" = searchParams.dir === "desc" ? "desc" : "asc";
  const { runs, total, totalPages } = await getRuns(status, page, sort, dir, pageSize);

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
          <div className="flex items-center gap-1 flex-wrap">
            {tabs.map((t) => (
              <Link
                key={t.label}
                href={t.value ? `/executions?status=${t.value}` : "/executions"}
                className={`px-3 py-1.5 text-xs uppercase tracking-wide-2 font-mono transition-colors ${
                  status === t.value || (!status && !t.value)
                    ? "bg-ink text-paper"
                    : "text-mute hover:text-ink hover:bg-paperRaised"
                }`}
              >
                {t.label}
              </Link>
            ))}
          </div>
        }
      />

      <div className="px-8 py-10">
        {/* Sort */}
        <div className="mb-8">
          <SortBar
            options={SORT_OPTIONS}
            activeSort={sort}
            activeDir={dir}
            preserveParams={{ status: searchParams.status }}
          />
        </div>

        {runs.length === 0 ? (
          <div className="hairline-t pt-12 text-center">
            <div className="eyebrow mb-3">EMPTY</div>
            <h2 className="font-serif text-3xl mb-3">No runs found</h2>
            <p className="text-mute text-sm">
              Try a different status filter, or trigger a pipeline run via GitHub Actions.
            </p>
          </div>
        ) : (
          <>
            <div>
              <div className="grid grid-cols-12 gap-4 px-2 py-3 hairline-b">
                <div className="col-span-2 eyebrow">STATUS</div>
                <div className="col-span-3 eyebrow">GITHUB RUN</div>
                <div className="col-span-2 eyebrow">SLICES</div>
                <div className="col-span-2 eyebrow text-right">SUCCESS</div>
                <div className="col-span-2 eyebrow text-right">FAILED</div>
                <div className="col-span-1 eyebrow text-right">CREATED</div>
              </div>
              <ul>
                {runs.map((run: any) => (
                  <li key={run._id} className="hairline-b-soft last:border-b-0">
                    <Link
                      href={`/executions/${run._id}`}
                      className="grid grid-cols-12 gap-4 px-2 py-4 items-center hover:bg-paperRaised/50 transition-colors"
                    >
                      <div className="col-span-2">
                        <StatusBadge status={run.status} />
                      </div>
                      <div
                        className="col-span-3 num text-xs text-mute truncate"
                        title={run.github_run_id ?? undefined}
                      >
                        {run.github_run_id ?? "—"}
                      </div>
                      <div className="col-span-2 num text-sm text-inkSoft">
                        {run.total_slices ?? "—"}
                      </div>
                      <div className="col-span-2 num text-sm text-success text-right">
                        {run.success_count ?? 0}
                      </div>
                      <div className="col-span-2 num text-sm text-failed text-right">
                        {run.failed_count ?? 0}
                      </div>
                      <div className="col-span-1 num text-2xs text-mute text-right">
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
              pageSize={pageSize}
              totalItems={total}
            />
          </>
        )}
      </div>
    </>
  );
}
