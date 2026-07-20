"use client";

/**
 * Persistent left-rail navigation (Client Component).
 *
 * WHY CLIENT
 * The Nav lives in the root layout, which in Next.js App Router is NOT
 * re-rendered on navigation between child routes. So a Server Component
 * Nav would fetch counts ONCE on first paint and never again — counts
 * would stay stale forever, even with experimental.staleTimes: 0.
 *
 * By making it a Client Component, we can use usePathname() to detect
 * navigation and re-fetch counts from /api/nav-counts after every
 * route change. This covers the user's requirement: counts refresh
 * after every add/delete (since every mutation is followed by a
 * navigation back to the list).
 *
 * DESIGN
 * Reads like a library catalog index: section labels (DASHBOARD /
 * AUDIOS / …) are uppercase mono eyebrows; the count next to each
 * item is the real number of records in that collection. The active
 * section is marked with a thin oxblood rule on the left, not a
 * background fill, so the rail stays quiet.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

type Counts = {
  audios: number;
  categories: number;
  videos: number;
  execs: number;
  outputs: number;
};

const EMPTY_COUNTS: Counts = {
  audios: 0,
  categories: 0,
  videos: 0,
  execs: 0,
  outputs: 0,
};

export function Nav() {
  const pathname = usePathname();
  const [counts, setCounts] = useState<Counts>(EMPTY_COUNTS);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/nav-counts", { cache: "no-store" })
      .then((r) => r.json())
      .then((data: Counts) => {
        if (!cancelled) setCounts(data);
      })
      .catch(() => {
        // Silently keep previous counts on network error.
      });
    return () => {
      cancelled = true;
    };
  }, [pathname]);

  const items = [
    { href: "/", label: "Dashboard", count: null, eyebrow: "OVERVIEW" },
    { href: "/audios", label: "Audios", count: counts.audios, eyebrow: "MEDIA" },
    { href: "/categories", label: "Categories", count: counts.categories, eyebrow: "MEDIA" },
    { href: "/executions", label: "Executions", count: counts.execs, eyebrow: "PIPELINE" },
    { href: "/outputs", label: "Outputs", count: counts.outputs, eyebrow: "GALLERY" },
  ];

  return (
    <aside className="w-60 shrink-0 bg-paperRaised sticky top-0 h-screen overflow-y-auto scroll-archive hairline-r">
      <div className="px-6 pt-10 pb-8">
        <div className="flex items-center gap-2 mb-3">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-accent" aria-hidden />
          <div className="eyebrow">QURAN VIDEO</div>
        </div>
        <div className="font-serif text-xl leading-tight">Generator</div>
        <div className="eyebrow mt-1">OPERATIONS</div>
      </div>
      <nav className="py-2">
        {items.map((item) => {
          const isActive =
            item.href === "/"
              ? pathname === "/"
              : pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`group block px-6 py-3 border-l-2 transition-colors ${
                isActive
                  ? "border-accent bg-paper/60"
                  : "border-transparent hover:border-rule hover:bg-paper/50"
              }`}
            >
              <div className="eyebrow mb-1">{item.eyebrow}</div>
              <div className="flex items-baseline justify-between">
                <span
                  className={`text-sm font-medium transition-colors ${
                    isActive ? "text-ink" : "text-inkSoft group-hover:text-ink"
                  }`}
                >
                  {item.label}
                </span>
                {item.count !== null && (
                  <span className="num text-2xs text-mute">{item.count}</span>
                )}
              </div>
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
