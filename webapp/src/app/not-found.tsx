import Link from "next/link";
import { PageHeader } from "@/components/PageHeader";

/**
 * Custom 404 page.
 *
 * Replaces Next.js's default "404 | This page could not be found."
 * with an on-brand page that:
 *   - uses the archival palette and type system
 *   - explains what likely went wrong (typo, deleted record, stale
 *     link)
 *   - offers concrete next steps (Dashboard, Audios, Categories,
 *     Executions) rather than a bare "go home" link
 *
 * The page is a Server Component (no "use client") so it renders even
 * when the JS bundle hasn't loaded yet.
 */

export default function NotFound() {
  return (
    <>
      <PageHeader
        eyebrow="ERROR / 404"
        title="Page not found"
        meta="The page you tried to open doesn't exist. This usually happens when a record has been deleted, a link is stale, or the URL was typed by hand."
      />
      <div className="px-8 py-16 max-w-2xl">
        <div className="font-serif text-7xl text-accent leading-none mb-8">404</div>

        <h2 className="font-serif text-2xl mb-4">What might have happened</h2>
        <ul className="space-y-3 text-sm text-inkSoft mb-12">
          <li className="hairline-b-soft pb-3">
            <span className="eyebrow text-accent mr-2">01</span>
            You followed a link to a record (audio, category, video, run, slice)
            that has since been deleted from the database.
          </li>
          <li className="hairline-b-soft pb-3">
            <span className="eyebrow text-accent mr-2">02</span>
            The URL was typed by hand and contains a typo or a malformed id
            (MongoDB ids must be 24-character hex strings).
          </li>
          <li className="pb-3">
            <span className="eyebrow text-accent mr-2">03</span>
            A navigation shortcut pointed at a route that hasn&apos;t been
            implemented yet.
          </li>
        </ul>

        <h2 className="font-serif text-2xl mb-4">Where to go next</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          <Link href="/" className="hairline-t pt-4 hover:bg-paperRaised/30 transition-colors -mx-2 px-2 pb-2">
            <div className="eyebrow mb-2">OVERVIEW</div>
            <div className="text-sm font-medium">Dashboard</div>
          </Link>
          <Link href="/audios" className="hairline-t pt-4 hover:bg-paperRaised/30 transition-colors -mx-2 px-2 pb-2">
            <div className="eyebrow mb-2">MEDIA</div>
            <div className="text-sm font-medium">Audios</div>
          </Link>
          <Link href="/categories" className="hairline-t pt-4 hover:bg-paperRaised/30 transition-colors -mx-2 px-2 pb-2">
            <div className="eyebrow mb-2">MEDIA</div>
            <div className="text-sm font-medium">Categories</div>
          </Link>
          <Link href="/executions" className="hairline-t pt-4 hover:bg-paperRaised/30 transition-colors -mx-2 px-2 pb-2">
            <div className="eyebrow mb-2">PIPELINE</div>
            <div className="text-sm font-medium">Executions</div>
          </Link>
        </div>
      </div>
    </>
  );
}
