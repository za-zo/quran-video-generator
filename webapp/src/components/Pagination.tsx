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
    <div className="flex items-center justify-between mt-6">
      <div className="text-sm text-mute">
        Page {currentPage} of {totalPages}
      </div>
      <div className="flex gap-2">
        {currentPage > 1 && (
          <Link href={createHref(currentPage - 1)} className="px-3 py-1 hairline-all text-sm hover:bg-rule/10">
            ← Prev
          </Link>
        )}
        {currentPage < totalPages && (
          <Link href={createHref(currentPage + 1)} className="px-3 py-1 hairline-all text-sm hover:bg-rule/10">
            Next →
          </Link>
        )}
      </div>
    </div>
  );
}
