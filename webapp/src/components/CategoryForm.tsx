"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ConfirmDialog } from "./ConfirmDialog";
import { FormField, useFormValidation, validators } from "./FormField";
import { FormStatus } from "./FormStatus";

type CategoryValues = {
  name: string;
};

export function CategoryForm({ category }: { category?: { _id: string; name: string } }) {
  const router = useRouter();
  const isNew = !category;
  const [name, setName] = useState(category?.name ?? "");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const { errors, validate, clearField, setFieldError } = useFormValidation<CategoryValues>({
    name: validators.required("Name"),
  });

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    setSuccess(null);

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
        const msg = body.error || `request failed (${res.status})`;
        if (res.status === 409 && /already exists/i.test(msg)) {
          setFieldError("name", msg);
        } else {
          setFormError(msg);
        }
        setSubmitting(false);
        return;
      }
      if (isNew) {
        // API returns { category: { _id, ... } } — read the id from there.
        const result = await res.json();
        const newId = result?.category?._id ?? result?.category?.id;
        if (!newId) {
          // Fallback: redirect to the categories list rather than
          // navigating to /categories/undefined/videos (which 404s).
          router.push("/categories");
        } else {
          router.push(`/categories/${newId}/videos`);
        }
      } else {
        setSuccess(`Category "${name}" updated.`);
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
    setFormError(null);
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
              if (success) setSuccess(null);
            }}
            className={`field-input ${errors.name ? "field-input-error" : ""}`}
          />
        </FormField>

        <FormStatus
          success={success}
          error={formError}
          onDismiss={() => {
            if (success) setSuccess(null);
            if (formError) setFormError(null);
          }}
        />

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
