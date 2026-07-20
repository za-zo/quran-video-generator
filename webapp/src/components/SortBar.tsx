"use client";

import Link from "next/link";

/**
 * SortBar — a compact sort control for list pages.
 *
 * Renders a row of sort options as text links (the active one
 * underlined in oxblood), plus a direction toggle button on the
 * right that flips asc/desc while keeping the current sort field.
 *
 * URL contract: the bar reads `sort` and `dir` from searchParams and
 * builds links that preserve all *other* search params (search, page,
 * status, etc.) so sorting never drops an active filter.
 *
 *   ?sort=name&dir=asc
 *   ?sort=duration&dir=desc
 *
 * If `sort` is missing or matches no option, the first option is
 * treated as active (matches the server-side default sort).
 */

export type SortOption = {
  label: string;
  value: string;
};

export function SortBar({
  options,
  activeSort,
  activeDir = "asc",
  preserveParams = {},
}: {
  options: SortOption[];
  activeSort?: string;
  activeDir?: "asc" | "desc";
  preserveParams?: Record<string, string | undefined>;
}) {
  const current = options.find((o) => o.value === activeSort) ?? options[0];
  const currentDir: "asc" | "desc" = activeDir === "desc" ? "desc" : "asc";

  function buildHref(value: string, dir: "asc" | "desc") {
    const params = new URLSearchParams();
    for (const [k, v] of Object.entries(preserveParams)) {
      if (v !== undefined && v !== null && v !== "") params.set(k, v);
    }
    params.set("sort", value);
    params.set("dir", dir);
    return `?${params.toString()}`;
  }

  const nextDir: "asc" | "desc" = currentDir === "asc" ? "desc" : "asc";

  return (
    <div className="flex items-center gap-4 flex-wrap">
      <div className="eyebrow">SORT</div>
      <div className="flex items-center gap-4 flex-wrap">
        {options.map((opt) => {
          const isActive = opt.value === current.value;
          return (
            <Link
              key={opt.value}
              href={buildHref(opt.value, isActive ? currentDir : "asc")}
              className={`text-2xs uppercase tracking-wide-2 font-mono transition-colors ${
                isActive
                  ? "text-accent border-b border-accent pb-0.5"
                  : "text-mute hover:text-ink"
              }`}
            >
              {opt.label}
            </Link>
          );
        })}
      </div>
      <button
        type="button"
        onClick={() => {
          // Direction toggle: just update the URL.
          window.location.href = buildHref(current.value, nextDir);
        }}
        className="ml-auto inline-flex items-center justify-center w-7 h-7 hairline-all text-mute hover:text-ink hover:bg-paperRaised transition-colors"
        aria-label={`Sort ${nextDir === "asc" ? "ascending" : "descending"}`}
        title={`Sort ${nextDir === "asc" ? "ascending" : "descending"}`}
      >
        <span className="text-xs font-mono" aria-hidden>
          {currentDir === "asc" ? "↑" : "↓"}
        </span>
      </button>
    </div>
  );
}
