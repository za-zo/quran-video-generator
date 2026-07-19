/**
 * StatCard — small block for a single metric on the dashboard.
 *
 * Structure encodes information: an eyebrow label, a single oversized
 * number (IBM Plex Mono, tabular nums so columns of these align), and
 * an optional caption. No background fill, no shadow — just a hairline
 * border, so a grid of them reads as a quiet field.
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
    <div className="hairline-all p-5 flex flex-col">
      <div className="eyebrow mb-3">{eyebrow}</div>
      <div className="num text-4xl font-medium leading-none mb-2">{value}</div>
      {caption && <div className="text-2xs text-mute">{caption}</div>}
      {children && <div className="mt-3 text-xs text-mute">{children}</div>}
    </div>
  );
}
