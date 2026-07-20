"use client";

import Link from "next/link";
import { PageSizeSelector } from "./PageSizeSelector";

export function Pagination({
  basePath,
  currentPage,
  totalPages,
  searchParams,
  pageSize,
  totalItems,
}: {
  basePath: string;
  currentPage: number;
  totalPages: number;
  searchParams: Record<string, string | undefined>;
  pageSize?: number;
  totalItems?: number;
}) {
  // Build preserve params (everything except `page` and `pageSize` —
  // those are managed by the pagination links and the selector).
  const preserveParams: Record<string, string | undefined> = {};
  for (const [k, v] of Object.entries(searchParams)) {
    if (k !== "page" && k !== "pageSize") preserveParams[k] = v;
  }

  const createHref = (page: number) => {
    const params = new URLSearchParams(searchParams as any);
    params.set("page", String(page));
    return `${basePath}?${params.toString()}`;
  };

  // Range info: "1–12 of 200"
  const rangeStart = totalItems !== undefined && pageSize
    ? (currentPage - 1) * pageSize + 1
    : null;
  const rangeEnd = totalItems !== undefined && pageSize
    ? Math.min(currentPage * pageSize, totalItems)
    : null;

  return (
    <div className="flex items-center justify-between mt-8 pt-6 hairline-t gap-4 flex-wrap">
      <div className="flex items-center gap-6 flex-wrap">
        <div className="text-sm text-mute num">
          {rangeStart !== null && rangeEnd !== null && totalItems !== undefined
            ? `${rangeStart}–${rangeEnd} of ${totalItems}`
            : `Page ${currentPage} of ${Math.max(totalPages, 1)}`}
        </div>
        {pageSize !== undefined && (
          <PageSizeSelector
            currentSize={pageSize}
            basePath={basePath}
            preserveParams={preserveParams}
          />
        )}
      </div>
      {totalPages > 1 && (
        <div className="flex gap-3">
          {currentPage > 1 && (
            <Link href={createHref(currentPage - 1)} className="btn-ghost">
              ← Prev
            </Link>
          )}
          {currentPage < totalPages && (
            <Link href={createHref(currentPage + 1)} className="btn-ghost">
              Next →
            </Link>
          )}
        </div>
      )}
    </div>
  );
}
