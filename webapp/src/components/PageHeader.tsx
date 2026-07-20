/**
 * PageHeader — consistent header at the top of every page.
 *
 * Eyebrow encodes the page's role within the system (MEDIA / PIPELINE /
 * OVERVIEW). Title is the page name. Actions slot on the right.
 *
 * Signature: a single oxblood dot before the eyebrow — the only recurring
 * mark of colour on otherwise neutral page headers. It reads as a
 * calligrapher's marginalia rather than a SaaS accent.
 *
 * Long names: title and eyebrow use break-words + min-w-0 so very long
 * names wrap instead of pushing the actions slot off-screen. The title
 * also gets a native title= attribute so the full name is visible on
 * hover even if it wraps.
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
        <div className="flex items-center gap-2 mb-3 min-w-0">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-accent shrink-0" aria-hidden />
          <div
            className="eyebrow break-words min-w-0"
            title={eyebrow}
          >
            {eyebrow}
          </div>
        </div>
        <div className="flex items-baseline justify-between gap-6 flex-wrap min-w-0">
          <h1
            className="font-serif text-4xl leading-tight tracking-tight break-words min-w-0 flex-1 min-w-[0]"
            title={title}
          >
            {title}
          </h1>
          {actions && <div className="flex items-center gap-3 shrink-0">{actions}</div>}
        </div>
        {meta && <div className="mt-3 text-sm text-mute max-w-3xl break-words">{meta}</div>}
      </div>
    </header>
  );
}
