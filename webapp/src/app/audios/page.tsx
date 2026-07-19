export const dynamic = "force-dynamic";

import Link from "next/link";
import { getDb } from "@/lib/mongo";
import { stringifyIds } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { Pagination } from "@/components/Pagination";
import { formatDuration, formatRelative, truncateUrl } from "@/lib/format";

const PAGE_SIZE = 30;

async function getAudios(search: string, page: number) {
  const db = await getDb();
  const filter: Record<string, unknown> = {};
  if (search) {
    filter.name = { $regex: search, $options: "i" };
  }
  const total = await db.collection("audios").countDocuments(filter);
  const docs = await db
    .collection("audios")
    .find(filter)
    .sort({ usage_count: -1, _id: 1 })
    .skip((page - 1) * PAGE_SIZE)
    .limit(PAGE_SIZE)
    .toArray();
  return {
    audios: docs.map((d) => stringifyIds(d)),
    totalPages: Math.ceil(total / PAGE_SIZE),
  };
}

export default async function AudiosPage({
  searchParams,
}: {
  searchParams: { search?: string; page?: string };
}) {
  const search = searchParams.search ?? "";
  const page = Math.max(1, parseInt(searchParams.page ?? "1", 10) || 1);
  const { audios, totalPages } = await getAudios(search, page);

  return (
    <>
      <PageHeader
        eyebrow="MEDIA"
        title="Audios"
        actions={
          <Link href="/audios/new" className="btn-primary">
            + Add audio
          </Link>
        }
        meta="Source Quran recitations. The pipeline downloads these at runtime — no file is stored locally."
      />

      <div className="px-8 py-10">
        {/* Search */}
        <form className="mb-8 max-w-md">
          <input
            type="text"
            name="search"
            defaultValue={search}
            placeholder="Search audios…"
            className="field-input"
          />
        </form>

        {audios.length === 0 ? (
          <div className="hairline-t pt-12 text-center">
            <div className="eyebrow mb-3">EMPTY</div>
            <h2 className="font-serif text-3xl mb-3">No audios found</h2>
            <p className="text-mute text-sm mb-8 max-w-md mx-auto">
              {search ? "Try a different search term." : "Add a remote URL for each Quran recitation you want the pipeline to draw from."}
            </p>
            {!search && (
              <Link href="/audios/new" className="btn-primary inline-flex">
                Add your first audio
              </Link>
            )}
          </div>
        ) : (
          <>
            <div>
              <div className="grid grid-cols-12 gap-4 px-2 py-3 hairline-b">
                <div className="col-span-1 eyebrow">#</div>
                <div className="col-span-3 eyebrow">NAME</div>
                <div className="col-span-3 eyebrow">SOURCE URL</div>
                <div className="col-span-2 eyebrow">DURATION</div>
                <div className="col-span-1 eyebrow text-right">USES</div>
                <div className="col-span-2 eyebrow text-right">LAST USED</div>
              </div>
              <ul>
                {audios.map((audio: any, i: number) => (
                  <li key={audio._id} className="hairline-b-soft last:border-b-0">
                    <Link
                      href={`/audios/${audio._id}/edit`}
                      className="grid grid-cols-12 gap-4 px-2 py-4 items-center hover:bg-paperRaised/50 transition-colors"
                    >
                      <div className="col-span-1 num text-2xs text-mute">
                        {String((page - 1) * PAGE_SIZE + i + 1).padStart(3, "0")}
                      </div>
                      <div className="col-span-3 truncate text-sm font-medium text-ink">
                        {audio.name}
                      </div>
                      <div className="col-span-3 truncate text-xs text-mute font-mono">
                        {truncateUrl(audio.source_url, 50)}
                      </div>
                      <div className="col-span-2 num text-sm text-inkSoft">
                        {formatDuration(audio.duration_seconds)}
                      </div>
                      <div className="col-span-1 num text-sm text-right text-inkSoft">
                        {audio.usage_count}
                      </div>
                      <div className="col-span-2 num text-2xs text-mute text-right">
                        {formatRelative(audio.last_used_at)}
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
            <Pagination
              basePath="/audios"
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
