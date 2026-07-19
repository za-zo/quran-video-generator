"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ConfirmDialog } from "./ConfirmDialog";

export function CategoryForm({ category }: { category?: { _id: string; name: string } }) {
  const router = useRouter();
  const isNew = !category;
  const [name, setName] = useState(category?.name ?? "");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      const url = isNew ? "/api/categories" : `/api/categories/${category!._id}`;
      const res = await fetch(url, {
        method: isNew ? "POST" : "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim() }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(body.error || `request failed (${res.status})`);
        setSubmitting(false);
        return;
      }
      if (isNew) {
        const result = await res.json();
        router.push(`/categories/${result.id}/videos`);
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
      const res = await fetch(`/api/categories/${category!._id}`, { method: "DELETE" });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(body.error || `delete failed (${res.status})`);
        setSubmitting(false);
        return;
      }
      router.push("/categories");
    } catch (err) {
      setError(String(err));
      setSubmitting(false);
    }
  }

  return (
    <>
      <form onSubmit={onSubmit} className="space-y-6 max-w-lg">
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
        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={submitting}
            className="px-4 py-2 hairline-all bg-ink text-paper text-sm font-medium hover:bg-rule transition-colors disabled:opacity-50"
          >
            {submitting ? "Saving…" : isNew ? "Add category" : "Save changes"}
          </button>
          {error && <span className="text-sm text-failed">{error}</span>}
        </div>
        {!isNew && (
          <div className="pt-4 hairline-t">
            <button
              type="button"
              onClick={() => setConfirmDelete(true)}
              className="px-4 py-2 hairline-all text-sm text-failed hover:bg-failed/5"
            >
              Delete category
            </button>
          </div>
        )}
      </form>
      {confirmDelete && (
        <ConfirmDialog
          title="Delete category?"
          message={`This will permanently remove "${category!.name}" and all its videos from the database.`}
          confirmLabel="Delete"
          onConfirm={onDelete}
          onCancel={() => setConfirmDelete(false)}
        />
      )}
    </>
  );
}
