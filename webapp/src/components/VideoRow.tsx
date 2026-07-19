"use client";

/**
 * VideoRow — per-row edit/delete controls for a video.
 *
 * Click "edit" to expand an inline form; click "delete" to remove.
 */

import { useRouter } from "next/navigation";
import { useState } from "react";
import { formatDuration } from "@/lib/format";

export function VideoRow({
  video,
}: {
  video: { _id: string; name: string; source_url: string; duration_seconds: number };
}) {
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(video.name);
  const [sourceUrl, setSourceUrl] = useState(video.source_url);
  const [duration, setDuration] = useState(
    video.duration_seconds?.toString() ?? "",
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSave() {
    setError(null);
    setSubmitting(true);
    const payload: Record<string, unknown> = {
      name: name.trim(),
      source_url: sourceUrl.trim(),
    };
    if (duration) payload.duration_seconds = Number(duration);
    try {
      const res = await fetch(`/api/videos/${video._id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(body.error || `request failed (${res.status})`);
        setSubmitting(false);
        return;
      }
      setEditing(false);
      router.refresh();
    } catch (err) {
      setError(String(err));
      setSubmitting(false);
    }
  }

  async function onDelete() {
    if (!confirm("Delete this video?")) return;
    setSubmitting(true);
    try {
      const res = await fetch(`/api/videos/${video._id}`, { method: "DELETE" });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(body.error || `delete failed (${res.status})`);
        setSubmitting(false);
        return;
      }
      router.refresh();
    } catch (err) {
      setError(String(err));
      setSubmitting(false);
    }
  }

  if (editing) {
    return (
      <div className="flex items-center gap-2 justify-end">
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="w-24 hairline-all px-2 py-1 bg-paper font-mono text-2xs"
        />
        <input
          type="url"
          value={sourceUrl}
          onChange={(e) => setSourceUrl(e.target.value)}
          className="w-40 hairline-all px-2 py-1 bg-paper font-mono text-2xs"
        />
        <input
          type="number"
          step="0.1"
          value={duration}
          onChange={(e) => setDuration(e.target.value)}
          className="w-16 hairline-all px-2 py-1 bg-paper font-mono text-2xs"
        />
        <button
          onClick={onSave}
          disabled={submitting}
          className="px-2 py-1 hairline-all text-2xs hover:bg-rule/[0.05]"
        >
          ✓
        </button>
        <button
          onClick={() => setEditing(false)}
          className="px-2 py-1 hairline-all text-2xs hover:bg-rule/[0.05]"
        >
          ✕
        </button>
        {error && <span className="text-2xs text-failed">{error}</span>}
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 justify-end">
      <button
        onClick={() => setEditing(true)}
        className="px-2 py-1 hairline-all text-2xs hover:bg-rule/[0.05]"
      >
        edit
      </button>
      <button
        onClick={onDelete}
        disabled={submitting}
        className="px-2 py-1 hairline-all text-2xs text-failed hover:bg-failed/5"
      >
        delete
      </button>
    </div>
  );
}
