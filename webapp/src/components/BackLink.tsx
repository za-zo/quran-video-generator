"use client";

import { useRouter } from "next/navigation";
import { useCallback } from "react";

/**
 * BackLink — a link that forces a re-fetch of the destination route
 * when clicked.
 *
 * Used for "← back to videos" / "← back to audios" style links on
 * detail/edit pages. The default Next.js <Link> reuses the cached RSC
 * payload, which means if the user mutated data on the detail page
 * (e.g. deleted a video) and then clicks "back", they see the stale
 * list. BackLink calls router.refresh() before router.push() to force
 * a fresh fetch.
 *
 * Visually identical to a plain quiet-link.
 */

import Link from "next/link";
import type { ReactNode } from "react";

export function BackLink({
  href,
  children,
  className = "quiet-link text-sm",
}: {
  href: string;
  children: ReactNode;
  className?: string;
}) {
  const router = useRouter();

  const onClick = useCallback(
    (e: React.MouseEvent<HTMLAnchorElement>) => {
      e.preventDefault();
      router.refresh();
      router.push(href);
    },
    [router, href],
  );

  return (
    <Link href={href} onClick={onClick} className={className}>
      {children}
    </Link>
  );
}
