/**
 * /categories/new — create a new category.
 */

"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import Link from "next/link";
import { PageHeader } from "@/components/PageHeader";

export default function NewCategoryPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const res = await fetch("/api/categories", {
        method: "POST",
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

  return (
    <>
      <PageHeader
        eyebrow="MEDIA / CATEGORIES"
        title="Add category"
        meta="Categories are scenery groupings (sea, forest, desert, …). Add videos to a category after creating it."
      />
      <div className="px-8 py-8 max-w-2xl">
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
              placeholder="e.g. sea, forest, mountains"
              className="w-full hairline-all px-3 py-2 bg-paper font-mono text-sm focus:outline-none focus:border-ink"
            />
            <p className="mt-1 text-2xs text-mute">
              Lower-case, hyphen-separated names work best (e.g. &quot;sea&quot;, &quot;high-mountains&quot;).
            </p>
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
              {submitting ? "Saving…" : "Create category"}
            </button>
          </div>
        </form>

        <div className="mt-4 text-sm">
          <Link href="/categories" className="quiet-link">
            ← back to categories
          </Link>
        </div>
      </div>
    </>
  );
}
