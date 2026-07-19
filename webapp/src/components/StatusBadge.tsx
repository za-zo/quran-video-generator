"use client";

import type { ExecutionSliceStatus } from "@/lib/types";

const STATUS_STYLES: Record<string, { label: string; cls: string }> = {
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
  canceled: {
    label: "CANCELED",
    cls: "text-mute border-rule/40 bg-rule/5",
  },
};

export function StatusBadge({ status }: { status: string }) {
  const s = STATUS_STYLES[status] ?? STATUS_STYLES.pending;
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 border font-mono text-2xs uppercase tracking-wide-2 ${s.cls}`}
    >
      {s.label}
    </span>
  );
}
