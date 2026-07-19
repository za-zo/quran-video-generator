"use client";

import type { ExecutionSliceStatus } from "@/lib/types";

const STATUS_STYLES: Record<string, { label: string; dot: string; text: string }> = {
  pending: {
    label: "PENDING",
    dot: "bg-warn",
    text: "text-warn",
  },
  success: {
    label: "SUCCESS",
    dot: "bg-success",
    text: "text-success",
  },
  failed: {
    label: "FAILED",
    dot: "bg-failed",
    text: "text-failed",
  },
  canceled: {
    label: "CANCELED",
    dot: "bg-mute",
    text: "text-mute",
  },
  running: {
    label: "RUNNING",
    dot: "bg-accent",
    text: "text-accent",
  },
  partial: {
    label: "PARTIAL",
    dot: "bg-warn",
    text: "text-warn",
  },
};

export function StatusBadge({ status }: { status: string }) {
  const s = STATUS_STYLES[status] ?? STATUS_STYLES.pending;
  return (
    <span className={`inline-flex items-center gap-1.5 font-mono text-2xs uppercase tracking-wide-2 ${s.text}`}>
      <span className={`inline-block w-1.5 h-1.5 rounded-full ${s.dot}`} aria-hidden />
      {s.label}
    </span>
  );
}
