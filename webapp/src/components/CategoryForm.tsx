"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ConfirmDialog } from "./ConfirmDialog";
import { FormField, useFormValidation, validators } from "./FormField";

type CategoryValues = {
  name: string;
};

export function CategoryForm({ category }: { category?: { _id: string; name: string } }) {
  const router = useRouter();
  const isNew = !category;
  const [name, setName] = useState(category?.name ?? "");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

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
      const url = isNew ? "/api/categories" : `/api/categories/${category!._id}`;
      const res = await fetch(url, {
        method: isNew ? "POST" : "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim() }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setFormError(body.error || `request failed (${res.status})`);
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
      setFormError(String(err));
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
        setFormError(body.error || `delete failed (${res.status})`);
        setSubmitting(false);
        return;
      }
      router.push("/categories");
    } catch (err) {
      setFormError(String(err));
      setSubmitting(false);
    }
  }

  return (
    <>
      <form onSubmit={onSubmit} noValidate className="space-y-6 max-w-lg">
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
            className={`field-input ${errors.name ? "field-input-error" : ""}`}
          />
        </FormField>

        {formError && (
          <div className="text-sm text-failed hairline-t pt-4">
            {formError}
          </div>
        )}

        <div className="flex items-center gap-4 pt-2">
          <button type="submit" disabled={submitting} className="btn-primary">
            {submitting ? "Saving…" : isNew ? "Add category" : "Save changes"}
          </button>
        </div>
        {!isNew && (
          <div className="pt-6 hairline-t">
            <button
              type="button"
              onClick={() => setConfirmDelete(true)}
              className="btn-danger"
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
