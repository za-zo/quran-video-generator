/**
 * ExternalMediaLink — small "open in new tab" icon link for media URLs.
 *
 * Renders as a tiny ↗ glyph that opens the URL in a new browser tab.
 * Used on list pages (next to source_url) and detail pages (next to
 * output URLs) so users can listen to / watch the media without leaving
 * the operations console.
 *
 * When used inside a clickable row (a <Link> that wraps the whole row),
 * pass `stopPropagation` so clicking the ↗ doesn't also trigger the
 * row navigation. The `relative z-10` classes ensure the link sits
 * above any stretched-link overlay.
 */

import type { ReactNode } from "react";

export function ExternalMediaLink({
  href,
  label = "Open in new tab",
  className = "",
  stopPropagation = false,
}: {
  href: string;
  label?: string;
  className?: string;
  stopPropagation?: boolean;
}) {
  if (!href) return null;
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      aria-label={label}
      title={label}
      onClick={stopPropagation ? (e) => e.stopPropagation() : undefined}
      className={`relative z-10 inline-flex items-center justify-center w-5 h-5 text-mute hover:text-accent transition-colors ${className}`}
    >
      <span className="text-xs" aria-hidden>↗</span>
    </a>
  );
}
