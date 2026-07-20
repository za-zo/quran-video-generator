"use client";

import Link from "next/link";
import { useEffect } from "react";
import { PageHeader } from "@/components/PageHeader";

/**
 * Custom error boundary (500-class errors).
 *
 * Catches unexpected runtime errors in any route segment below the
 * root layout. Logs to console for debugging, then renders an
 * on-brand error page with recovery options.
 *
 * This is a Client Component because Next.js requires error.tsx to
 * be one (it needs to catch errors during client-side rendering).
 */

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[webapp error boundary]", error);
  }, [error]);

  return (
    <>
      <PageHeader
        eyebrow="ERROR / 500"
        title="Something went wrong"
        meta="An unexpected error occurred while rendering this page. The error has been logged to the browser console."
      />
      <div className="px-8 py-16 max-w-2xl">
        <div className="font-serif text-7xl text-failed leading-none mb-8">500</div>

        <h2 className="font-serif text-2xl mb-4">What to try</h2>
        <ul className="space-y-3 text-sm text-inkSoft mb-8">
          <li className="hairline-b-soft pb-3">
            <span className="eyebrow text-failed mr-2">01</span>
            Reload the page using the button below — this re-runs the
            server component and may succeed if the error was transient
            (e.g. a MongoDB connection blip).
          </li>
          <li className="hairline-b-soft pb-3">
            <span className="eyebrow text-failed mr-2">02</span>
            Go back to a known-good page (Dashboard, Audios, Categories,
            Executions) and try again from there.
          </li>
          <li className="pb-3">
            <span className="eyebrow text-failed mr-2">03</span>
            If the error persists, open the browser console — the full
            stack trace is logged there. A common cause is a stale id
            pointing to a deleted record.
          </li>
        </ul>

        {error?.message && (
          <div className="hairline-t pt-6 mb-8">
            <div className="eyebrow mb-2">ERROR MESSAGE</div>
            <pre className="bg-paperRaised p-4 text-xs text-failed font-mono whitespace-pre-wrap break-words">
              {error.message}
            </pre>
            {error.digest && (
              <div className="eyebrow mt-2 text-mute">digest: {error.digest}</div>
            )}
          </div>
        )}

        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={reset}
            className="btn-primary"
          >
            Try again
          </button>
          <Link href="/" className="quiet-link text-sm">
            ← back to dashboard
          </Link>
        </div>
      </div>
    </>
  );
}
