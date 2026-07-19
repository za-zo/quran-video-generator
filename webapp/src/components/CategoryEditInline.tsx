"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ConfirmDialog } from "./ConfirmDialog";
import { FormField, useFormValidation, validators } from "./FormField";

type CategoryValues = {
  name: string;
};

export function CategoryEditInline({ category }: { category: { _id: string; name: string; video_count: number } }) {
  const router = useRouter();
  const [name, setName] = useState(category.name);
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
      const res = await fetch(`/api/categories/${category._id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim() }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setFormError(body.error || `request failed (${res.status})`);
        setSubmitting(false);
        return;
      }
      router.push("/categories");
      router.refresh();
    } catch (err) {
      setFormError(String(err));
      setSubmitting(false);
    }
  }

  async function onDelete() {
    setSubmitting(true);
    setFormError(null);
    try {
      const res = await fetch(`/api/categories/${category._id}`, { method: "DELETE" });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setFormError(body.error || `delete failed (${res.status})`);
        setSubmitting(false);
        return;
      }
      router.push("/categories");
      router.refresh();
    } catch (err) {
      setFormError(String(err));
      setSubmitting(false);
    }
  }

  return (
    <>
      <form onSubmit={onSubmit} noValidate className="space-y-6">
        <FormField
          label="Name"
          required
          error={errors.name}
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

        <div className="flex items-center gap-3 pt-2">
          <button type="submit" disabled={submitting} className="btn-primary">
            {submitting ? "Saving…" : "Save changes"}
          </button>
          <button
            type="button"
            onClick={() => {
              if (category.video_count > 0) {
                setFormError(`This category has ${category.video_count} video(s). Delete or reassign them first.`);
                return;
              }
              setConfirmDelete(true);
            }}
            disabled={submitting}
            className="btn-danger"
          >
            Delete
          </button>
        </div>
      </form>
      {confirmDelete && (
        <ConfirmDialog
          title="Delete category?"
          message={`This will permanently remove "${category.name}" and all its data from the database.`}
          confirmLabel="Delete"
          onConfirm={onDelete}
          onCancel={() => setConfirmDelete(false)}
        />
      )}
    </>
  );
}
