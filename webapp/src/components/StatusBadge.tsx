/**
 * Status badge for executions.
 *
 * Uses colour + a textual label so meaning never relies on colour alone.
 * Border and text colours are tuned to the archive palette (deep, not
 * garish) — these badges sit inside data tables and shouldn't dominate.
 */

import type { ExecutionStatus } from "@/lib/types";

const STATUS_STYLES: Record<ExecutionStatus, { label: string; cls: string }> = {
  pending: {
    label: "PENDING",
    cls: "text-warn border-warn/40 bg-warn/5",
  },
  success: {
    label: "SUCCESS",
    cls: "text-success border-success/40 bg-success/5",
  },
  failed: {
    label: "FAILED",
    cls: "text-failed border-failed/40 bg-failed/5",
  },
};

export function StatusBadge({ status }: { status: ExecutionStatus }) {
  const s = STATUS_STYLES[status] ?? STATUS_STYLES.pending;
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 border font-mono text-2xs uppercase tracking-wide-2 ${s.cls}`}
    >
      {s.label}
    </span>
  );
}
