"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import Link from "next/link";
import { PageHeader } from "@/components/PageHeader";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { FormField, useFormValidation, validators } from "@/components/FormField";

type CategoryValues = {
  name: string;
};

export default function NewCategoryPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const { errors, validate, clearField } = useFormValidation<CategoryValues>({
    name: validators.required("Name"),
  });

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);

    const ok = validate({ name });
    if (!ok) return;

    setSubmitting(true);
    try {
      const res = await fetch("/api/categories", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim() }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setFormError(body.error || `request failed (${res.status})`);
        setSubmitting(false);
        return;
      }
      const result = await res.json();
      router.push(`/categories/${result.id}/videos`);
      router.refresh();
    } catch (err) {
      setFormError(String(err));
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
      <div className="px-8 py-10 max-w-2xl">
        <form onSubmit={onSubmit} noValidate className="space-y-6">
          <FormField
            label="Name"
            required
            error={errors.name}
            hint="Lower-case, hyphen-separated names work best (e.g. 'sea', 'high-mountains')."
          >
            <input
              type="text"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                clearField("name");
              }}
              placeholder="e.g. sea, forest, mountains"
              className={`field-input ${errors.name ? "field-input-error" : ""}`}
            />
          </FormField>

          {formError && (
            <div className="text-sm text-failed hairline-t pt-4">
              {formError}
            </div>
          )}

          <div className="flex items-center gap-3 pt-2">
            <button type="submit" disabled={submitting} className="btn-primary">
              {submitting ? "Saving…" : "Create category"}
            </button>
          </div>
        </form>

        <div className="mt-8 text-sm">
          <Link href="/categories" className="quiet-link">
            ← back to categories
          </Link>
        </div>
      </div>
    </>
  );
}
