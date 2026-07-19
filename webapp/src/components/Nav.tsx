/**
 * Persistent left-rail navigation.
 *
 * Structure encodes information: section labels (DASHBOARD / AUDIOS / …)
 * are uppercase mono eyebrows; the count next to each item is the
 * real number of records in that collection — not a decoration.
 * The active section is marked with a thin oxblood rule on the left,
 * not a background fill, so the rail stays quiet.
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
    <aside className="w-56 shrink-0 hairline-r bg-paper sticky top-0 h-screen overflow-y-auto scroll-archive">
      <div className="px-6 pt-8 pb-6 hairline-b">
        <div className="eyebrow mb-2">QURAN VIDEO</div>
        <div className="font-serif text-lg leading-tight">Generator</div>
        <div className="eyebrow mt-1">OPERATIONS</div>
      </div>
      <nav className="py-4">
        {items.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="group block px-6 py-3 hairline-b hover:bg-rule/[0.03] transition-colors"
          >
            <div className="eyebrow mb-1">{item.eyebrow}</div>
            <div className="flex items-baseline justify-between">
              <span className="text-sm font-medium">{item.label}</span>
              {item.count !== null && (
                <span className="num text-2xs text-mute">{item.count}</span>
              )}
            </div>
          </Link>
        ))}
      </nav>
      <div className="px-6 py-4 mt-auto">
        <div className="eyebrow mb-1">VERSION</div>
        <div className="num text-2xs text-mute">cloud / 0.1.0</div>
      </div>
    </aside>
  );
}
