/**
 * Persistent left-rail navigation.
 *
 * Reads like a library catalog index: section labels (DASHBOARD / AUDIOS / …)
 * are uppercase mono eyebrows; the count next to each item is the real number
 * of records in that collection — not decoration.
 *
 * The active section is marked with a thin oxblood rule on the left, not a
 * background fill, so the rail stays quiet.
 */

import Link from "next/link";
import { getDb } from "@/lib/mongo";

async function getCounts() {
  try {
    const db = await getDb();
    const [audios, categories, videos, execs] = await Promise.all([
      db.collection("audios").countDocuments(),
      db.collection("categories").countDocuments(),
      db.collection("videos").countDocuments(),
      db.collection("executions").countDocuments(),
    ]);
    return { audios, categories, videos, execs };
  } catch {
    return { audios: 0, categories: 0, videos: 0, execs: 0 };
  }
}

export const dynamic = "force-dynamic";

export async function Nav() {
  const counts = await getCounts();
  const items = [
    { href: "/", label: "Dashboard", count: null, eyebrow: "OVERVIEW" },
    { href: "/audios", label: "Audios", count: counts.audios, eyebrow: "MEDIA" },
    { href: "/categories", label: "Categories", count: counts.categories, eyebrow: "MEDIA" },
    { href: "/executions", label: "Executions", count: counts.execs, eyebrow: "PIPELINE" },
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
        {items.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="group block px-6 py-3 border-l-2 border-transparent hover:border-rule hover:bg-paper/50 transition-colors"
          >
            <div className="eyebrow mb-1">{item.eyebrow}</div>
            <div className="flex items-baseline justify-between">
              <span className="text-sm font-medium text-inkSoft group-hover:text-ink transition-colors">
                {item.label}
              </span>
              {item.count !== null && (
                <span className="num text-2xs text-mute">{item.count}</span>
              )}
            </div>
          </Link>
        ))}
      </nav>
      <div className="px-6 py-4 mt-8 hairline-t">
        <div className="eyebrow mb-1">VERSION</div>
        <div className="num text-2xs text-mute">cloud / 0.1.0</div>
      </div>
    </aside>
  );
}
