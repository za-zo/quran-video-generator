"use client";

/**
 * AudioForm — shared form for creating and editing audios.
 *
 * Client Component so we can handle form state, submission, and
 * validation feedback without a round-trip per keystroke.
 */

import { useRouter } from "next/navigation";
import { useState } from "react";

export function AudioForm({
  mode,
  audio,
}: {
  mode: "create" | "edit";
  audio?: { _id: string; name: string; source_url: string; duration_seconds: number };
}) {
  const router = useRouter();
  const [name, setName] = useState(audio?.name ?? "");
  const [sourceUrl, setSourceUrl] = useState(audio?.source_url ?? "");
  const [durationSeconds, setDurationSeconds] = useState(
    audio?.duration_seconds?.toString() ?? "",
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    const payload: Record<string, unknown> = {
      name: name.trim(),
      source_url: sourceUrl.trim(),
    };
    if (durationSeconds) {
      const d = Number(durationSeconds);
      if (isNaN(d) || d < 0) {
        setError("duration_seconds must be a non-negative number");
        setSubmitting(false);
        return;
      }
      payload.duration_seconds = d;
    }

    try {
      const url =
        mode === "create" ? "/api/audios" : `/api/audios/${audio!._id}`;
      const method = mode === "create" ? "POST" : "PUT";
      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(body.error || `request failed (${res.status})`);
        setSubmitting(false);
        return;
      }
      router.push("/audios");
      router.refresh();
    } catch (err) {
      setError(String(err));
      setSubmitting(false);
    }
  }

  async function onDelete() {
    if (!confirm("Delete this audio? This cannot be undone.")) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch(`/api/audios/${audio!._id}`, { method: "DELETE" });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(body.error || `delete failed (${res.status})`);
        setSubmitting(false);
        return;
      }
      const body = await res.json();
      if (body.warning) {
        alert(body.warning);
      }
      router.push("/audios");
      router.refresh();
    } catch (err) {
      setError(String(err));
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-6">
      <Field label="Name" required hint="A short identifier (e.g. 001, surah_al-fatiha)">
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
          className="w-full hairline-all px-3 py-2 bg-paper font-mono text-sm focus:outline-none focus:border-ink"
        />
      </Field>

      <Field label="Source URL" required hint="Direct http(s) URL the pipeline will download at runtime">
        <input
          type="url"
          value={sourceUrl}
          onChange={(e) => setSourceUrl(e.target.value)}
          required
          placeholder="https://example.com/audio.mp3"
          className="w-full hairline-all px-3 py-2 bg-paper font-mono text-sm focus:outline-none focus:border-ink"
        />
      </Field>

      <Field label="Duration (seconds)" hint="Optional — leave blank to probe at runtime">
        <input
          type="number"
          step="0.1"
          min="0"
          value={durationSeconds}
          onChange={(e) => setDurationSeconds(e.target.value)}
          className="w-full hairline-all px-3 py-2 bg-paper font-mono text-sm focus:outline-none focus:border-ink"
        />
      </Field>

      {error && (
        <div className="hairline-all p-3 text-sm text-failed bg-failed/5">
          {error}
        </div>
      )}

      <div className="flex items-center gap-3 pt-2">
        <button
          type="submit"
          disabled={submitting}
          className="px-5 py-2 hairline-all bg-ink text-paper text-sm font-medium hover:bg-rule transition-colors disabled:opacity-50"
        >
          {submitting ? "Saving…" : mode === "create" ? "Create audio" : "Save changes"}
        </button>
        {mode === "edit" && (
          <button
            type="button"
            onClick={onDelete}
            disabled={submitting}
            className="px-5 py-2 hairline-all text-sm text-failed hover:bg-failed/5 transition-colors disabled:opacity-50"
          >
            Delete
          </button>
        )}
      </div>
    </form>
  );
}

function Field({
  label,
  required,
  hint,
  children,
}: {
  label: string;
  required?: boolean;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block eyebrow mb-2">
        {label}
        {required && <span className="text-accent ml-1">*</span>}
      </label>
      {children}
      {hint && <p className="mt-1 text-2xs text-mute">{hint}</p>}
    </div>
  );
}
