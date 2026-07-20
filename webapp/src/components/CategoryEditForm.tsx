"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { FormField, useFormValidation, validators } from "./FormField";
import { FormStatus } from "./FormStatus";
import { useNavigateWithRefresh } from "@/lib/navigate";

type CategoryValues = {
  name: string;
};

export function CategoryEditForm({
  category,
}: {
  category: { _id: string; name: string; video_count: number };
}) {
  const router = useRouter();
  const navigate = useNavigateWithRefresh();
  const [name, setName] = useState(category.name);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

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
      const res = await fetch(`/api/categories/${category._id}`, {
        method: "PUT",
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
      setSuccess(`Category "${name}" updated.`);
      router.refresh();
    } catch (err) {
      setFormError(String(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-6">
      <FormField label="Name" required error={errors.name}>
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

      <div className="flex items-center gap-3 pt-2">
        <button type="submit" disabled={submitting} className="btn-primary">
          {submitting ? "Saving…" : "Save changes"}
        </button>
      </div>
    </form>
  );
}
