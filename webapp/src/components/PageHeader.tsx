/**
 * PageHeader — consistent header at the top of every page.
 *
 * Eyebrow encodes the page's role within the system (MEDIA / PIPELINE /
 * OVERVIEW). Title is the page name. Actions slot on the right.
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
      <div className="px-8 py-8">
        <div className="eyebrow mb-2">{eyebrow}</div>
        <div className="flex items-baseline justify-between gap-6 flex-wrap">
          <h1 className="font-serif text-3xl leading-tight">{title}</h1>
          {actions && <div className="flex items-center gap-3">{actions}</div>}
        </div>
        {meta && <div className="mt-3 text-sm text-mute">{meta}</div>}
      </div>
    </header>
  );
}
