"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export function CategoryEditForm({
  category,
}: {
  category: { _id: string; name: string; video_count: number };
}) {
  const router = useRouter();
  const [name, setName] = useState(category.name);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const res = await fetch(`/api/categories/${category._id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim() }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(body.error || `request failed (${res.status})`);
        setSubmitting(false);
        return;
      }
      router.push("/categories");
      router.refresh();
    } catch (err) {
      setError(String(err));
      setSubmitting(false);
    }
  }

  async function onDelete() {
    if (category.video_count > 0) {
      alert(
        `This category has ${category.video_count} video(s). Delete or reassign them first.`,
      );
      return;
    }
    if (!confirm("Delete this category? This cannot be undone.")) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch(`/api/categories/${category._id}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(body.error || `delete failed (${res.status})`);
        setSubmitting(false);
        return;
      }
      router.push("/categories");
      router.refresh();
    } catch (err) {
      setError(String(err));
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-6">
      <div>
        <label className="block eyebrow mb-2">
          Name<span className="text-accent ml-1">*</span>
        </label>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
          className="w-full hairline-all px-3 py-2 bg-paper font-mono text-sm focus:outline-none focus:border-ink"
        />
      </div>

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
          {submitting ? "Saving…" : "Save changes"}
        </button>
        <button
          type="button"
          onClick={onDelete}
          disabled={submitting}
          className="px-5 py-2 hairline-all text-sm text-failed hover:bg-failed/5 transition-colors disabled:opacity-50"
          title={
            category.video_count > 0
              ? "Delete or reassign the videos first"
              : "Delete this category"
          }
        >
          Delete
        </button>
      </div>
    </form>
  );
}
