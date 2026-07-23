/**
 * InfoBadge — small inline badge for slice metadata (posted_in, bad_result).
 *
 * Used on the slice detail page and the /outputs gallery cards to
 * surface at-a-glance info: where a video was posted, and whether
 * the result was flagged as bad.
 *
 * Variants:
 * - "posted": muted/success tone, shows "POSTED: account-name"
 * - "bad": failed/crimson tone, shows "BAD RESULT"
 */

import type { ReactNode } from "react";

export function PostedInBadge({ account }: { account: string }) {
  if (!account) return null;
  return (
    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 hairline-all text-2xs uppercase tracking-wide-2 font-mono text-success bg-success/5">
      <span className="inline-block w-1.5 h-1.5 rounded-full bg-success" aria-hidden />
      POSTED: {account}
    </span>
  );
}

export function BadResultBadge() {
  return (
    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 hairline-all text-2xs uppercase tracking-wide-2 font-mono text-failed bg-failed/5">
      <span className="inline-block w-1.5 h-1.5 rounded-full bg-failed" aria-hidden />
      BAD RESULT
    </span>
  );
}
