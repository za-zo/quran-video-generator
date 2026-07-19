/**
 * PageHeader — consistent header at the top of every page.
 *
 * Eyebrow encodes the page's role within the system (MEDIA / PIPELINE /
 * OVERVIEW). Title is the page name. Actions slot on the right.
 *
 * Signature: a single oxblood dot before the eyebrow — the only recurring
 * mark of colour on otherwise neutral page headers. It reads as a
 * calligrapher's marginalia rather than a SaaS accent.
 */

import { ReactNode } from "react";

export function PageHeader({
  eyebrow,
  title,
  actions,
  meta,
}: {
  eyebrow: string;
  title: string;
  actions?: ReactNode;
  meta?: ReactNode;
}) {
  return (
    <header className="hairline-b">
      <div className="px-8 py-10">
        <div className="flex items-center gap-2 mb-3">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-accent" aria-hidden />
          <div className="eyebrow">{eyebrow}</div>
        </div>
        <div className="flex items-baseline justify-between gap-6 flex-wrap">
          <h1 className="font-serif text-4xl leading-tight tracking-tight">{title}</h1>
          {actions && <div className="flex items-center gap-3">{actions}</div>}
        </div>
        {meta && <div className="mt-3 text-sm text-mute max-w-3xl">{meta}</div>}
      </div>
    </header>
  );
}
