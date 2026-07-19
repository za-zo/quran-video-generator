"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ConfirmDialog } from "./ConfirmDialog";

export function AudioForm({ audio }: { audio?: { _id: string; name: string; source_url: string; duration_seconds: number } }) {
  const router = useRouter();
  const isNew = !audio;
  const [name, setName] = useState(audio?.name ?? "");
  const [sourceUrl, setSourceUrl] = useState(audio?.source_url ?? "");
  const [duration, setDuration] = useState(audio?.duration_seconds?.toString() ?? "");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    const payload: Record<string, unknown> = {
      name: name.trim(),
      source_url: sourceUrl.trim(),
    };
    if (duration) {
      const d = Number(duration);
      if (isNaN(d) || d < 0) {
        setError("duration must be a non-negative number");
        setSubmitting(false);
        return;
      }
      payload.duration_seconds = d;
    }

    try {
      const url = isNew ? "/api/audios" : `/api/audios/${audio!._id}`;
      const res = await fetch(url, {
        method: isNew ? "POST" : "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(body.error || `request failed (${res.status})`);
        setSubmitting(false);
        return;
      }
      if (isNew) {
        router.push("/audios");
      } else {
        router.refresh();
      }
    } catch (err) {
      setError(String(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function onDelete() {
    setSubmitting(true);
    try {
      const res = await fetch(`/api/audios/${audio!._id}`, { method: "DELETE" });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(body.error || `delete failed (${res.status})`);
        setSubmitting(false);
        return;
      }
      router.push("/audios");
    } catch (err) {
      setError(String(err));
      setSubmitting(false);
    }
  }

  return (
    <>
      <form onSubmit={onSubmit} className="space-y-8 max-w-2xl">
        <div>
          <label className="block eyebrow mb-3">
            Name<span className="text-accent ml-1">*</span>
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            className="field-input"
          />
        </div>
        <div>
          <label className="block eyebrow mb-3">
            Source URL<span className="text-accent ml-1">*</span>
          </label>
          <input
            type="url"
            value={sourceUrl}
            onChange={(e) => setSourceUrl(e.target.value)}
            required
            className="field-input"
          />
        </div>
        <div>
          <label className="block eyebrow mb-3">Duration (seconds)</label>
          <input
            type="number"
            step="0.1"
            min="0"
            value={duration}
            onChange={(e) => setDuration(e.target.value)}
            className="field-input w-48"
          />
        </div>
        <div className="flex items-center gap-4">
          <button
            type="submit"
            disabled={submitting}
            className="btn-primary"
          >
            {submitting ? "Saving…" : isNew ? "Add audio" : "Save changes"}
          </button>
          {error && <span className="text-sm text-failed">{error}</span>}
        </div>
        {!isNew && (
          <div className="pt-6 hairline-t">
            <button
              type="button"
              onClick={() => setConfirmDelete(true)}
              className="btn-danger"
            >
              Delete audio
            </button>
          </div>
        )}
      </form>
      {confirmDelete && (
        <ConfirmDialog
          title="Delete audio?"
          message={`This will permanently remove "${audio!.name}" from the database. The pipeline will no longer be able to use this recitation.`}
          confirmLabel="Delete"
          onConfirm={onDelete}
          onCancel={() => setConfirmDelete(false)}
        />
      )}
    </>
  );
}
