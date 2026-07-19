"use client";

/**
 * AddVideoForm — inline form to add a video to a category.
 */

import { useRouter } from "next/navigation";
import { useState } from "react";

export function AddVideoForm({ categoryId }: { categoryId: string }) {
  const router = useRouter();
  const [name, setName] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [duration, setDuration] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    const payload: Record<string, unknown> = {
      category_id: categoryId,
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
      const res = await fetch("/api/videos", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(body.error || `request failed (${res.status})`);
        setSubmitting(false);
        return;
      }
      setName("");
      setSourceUrl("");
      setDuration("");
      router.refresh();
    } catch (err) {
      setError(String(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
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
        <div className="md:col-span-2">
          <label className="block eyebrow mb-3">
            Source URL<span className="text-accent ml-1">*</span>
          </label>
          <input
            type="url"
            value={sourceUrl}
            onChange={(e) => setSourceUrl(e.target.value)}
            required
            placeholder="https://example.com/sea_0.mp4"
            className="field-input"
          />
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 items-end">
        <div>
          <label className="block eyebrow mb-3">Duration (s)</label>
          <input
            type="number"
            step="0.1"
            min="0"
            value={duration}
            onChange={(e) => setDuration(e.target.value)}
            className="field-input"
          />
        </div>
        <div className="md:col-span-3 flex items-center gap-4">
          <button
            type="submit"
            disabled={submitting}
            className="btn-primary"
          >
            {submitting ? "Adding…" : "Add video"}
          </button>
          {error && <span className="text-sm text-failed">{error}</span>}
        </div>
      </div>
    </form>
  );
}
