"use client";

import Link from "next/link";

export function Pagination({ basePath, currentPage, totalPages, searchParams }: { basePath: string; currentPage: number; totalPages: number; searchParams: Record<string, string | undefined> }) {
  if (totalPages <= 1) return null;

  const createHref = (page: number) => {
    const params = new URLSearchParams(searchParams as any);
    params.set("page", String(page));
    return `${basePath}?${params.toString()}`;
  };

  return (
    <div className="flex items-center justify-between mt-8 pt-6 hairline-t">
      <div className="text-sm text-mute num">
        Page {currentPage} of {totalPages}
      </div>
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
    </div>
  );
}
