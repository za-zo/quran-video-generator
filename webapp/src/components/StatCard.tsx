/**
 * StatCard — small block for a single metric on the dashboard.
 *
 * No boxed border, no shadow. A top hairline + an oversized mono number
 * + a quiet caption. A grid of these reads as a row of index cards in
 * a card catalog rather than a SaaS KPI panel.
 */

import { ReactNode } from "react";

export function StatCard({
  eyebrow,
  value,
  caption,
  children,
}: {
  eyebrow: string;
  value: ReactNode;
  caption?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="hairline-t pt-5 flex flex-col">
      <div className="eyebrow mb-3">{eyebrow}</div>
      <div className="num text-5xl font-light leading-none mb-3 text-ink">{value}</div>
      {caption && <div className="text-2xs text-mute leading-relaxed">{caption}</div>}
      {children && <div className="mt-3 text-xs text-mute">{children}</div>}
    </div>
  );
}
