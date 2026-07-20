"use client";

import { useSearchParams, usePathname, useRouter } from "next/navigation";
import { useCallback } from "react";

/**
 * PageSizeSelector — dropdown to change how many items are shown per
 * page.
 *
 * Preserves all other search params (search, sort, dir, status, etc.)
 * and resets page to 1 when the page size changes (otherwise the
 * user could land on a page that doesn't exist with the new size).
 *
 * Renders as a small inline form that submits on change, so it works
 * without JS-driven navigation (progressive enhancement).
 */

const PAGE_SIZE_OPTIONS = [12, 20, 50, 100];

export function PageSizeSelector({
  currentSize,
  basePath,
  preserveParams = {},
}: {
  currentSize: number;
  basePath: string;
  preserveParams?: Record<string, string | undefined>;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const onChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      const params = new URLSearchParams();
      // Preserve existing params (from preserveParams prop, which the
      // server passes down, plus anything in the URL bar).
      for (const [k, v] of Object.entries(preserveParams)) {
        if (v !== undefined && v !== null && v !== "") params.set(k, v);
      }
      // Also walk the live searchParams (covers params the server
      // might not have forwarded).
      if (searchParams) {
        for (const key of Array.from(searchParams.keys())) {
          if (key === "page" || key === "pageSize") continue;
          const v = searchParams.get(key);
          if (v && !params.has(key)) params.set(key, v);
        }
      }
      params.set("pageSize", e.target.value);
      // Reset to page 1 — new size may have fewer pages.
      params.delete("page");
      const qs = params.toString();
      const href = basePath + (qs ? `?${qs}` : "");
      // Use router.push so we get a client-side transition + the
      // staleTimes:0 config forces a refetch.
      router.push(href);
    },
    [router, pathname, searchParams, preserveParams, basePath],
  );

  return (
    <label className="flex items-center gap-2 text-2xs uppercase tracking-wide-2 font-mono text-mute">
      <span>Per page</span>
      <select
        value={currentSize}
        onChange={onChange}
        className="bg-transparent hairline-all px-2 py-1 text-2xs font-mono text-ink focus:outline-none focus:border-ink cursor-pointer"
        aria-label="Items per page"
      >
        {PAGE_SIZE_OPTIONS.map((opt) => (
          <option key={opt} value={opt} className="text-ink">
            {opt}
          </option>
        ))}
      </select>
    </label>
  );
}
