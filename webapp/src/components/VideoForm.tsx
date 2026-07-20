"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ConfirmDialog } from "./ConfirmDialog";
import { FormField, useFormValidation, validators } from "./FormField";
import { FormStatus } from "./FormStatus";
import { useNavigateWithRefresh } from "@/lib/navigate";

type VideoValues = {
  name: string;
  sourceUrl: string;
  duration: string;
  categoryId: string;
};

export function VideoForm({
  video,
  categoryOptions,
}: {
  video?: { _id: string; name: string; source_url: string; duration_seconds: number; category_id: string };
  categoryOptions?: { _id: string; name: string }[];
}) {
  const router = useRouter();
  const navigate = useNavigateWithRefresh();
  const isNew = !video;
  const [name, setName] = useState(video?.name ?? "");
  const [sourceUrl, setSourceUrl] = useState(video?.source_url ?? "");
  const [duration, setDuration] = useState(video?.duration_seconds?.toString() ?? "");
  const [categoryId, setCategoryId] = useState(video?.category_id ?? "");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const { errors, validate, clearField, setFieldError } = useFormValidation<VideoValues>({
    name: validators.required("Name"),
    sourceUrl: (v) => {
      const r = validators.required("Source URL")(v);
      if (r) return r;
      return validators.url("Source URL")(v);
    },
    duration: validators.nonNegativeNumber("Duration"),
    ...(categoryOptions
      ? {
          categoryId: (v: unknown) =>
            v ? null : "Category is required",
        }
      : {}),
  });

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    setSuccess(null);

    const ok = validate({ name, sourceUrl, duration, categoryId });
    if (!ok) return;

    setSubmitting(true);

    const payload: Record<string, unknown> = {
      name: name.trim(),
      source_url: sourceUrl.trim(),
    };
    if (duration) {
      payload.duration_seconds = Number(duration);
    }
    if (categoryId) payload.category_id = categoryId;

    try {
      const url = isNew ? "/api/videos" : `/api/videos/${video!._id}`;
      const res = await fetch(url, {
        method: isNew ? "POST" : "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
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
        // Use the server-returned category_id so navigation lands on
        // the right category even if the user changed it mid-edit.
        const result = await res.json();
        const finalCatId = result?.video?.category_id ?? categoryId;
        navigate(`/categories/${finalCatId}/videos`);
      } else {
        setSuccess(`Video "${name}" updated.`);
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
      const res = await fetch(`/api/videos/${video!._id}`, { method: "DELETE" });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setFormError(body.error || `delete failed (${res.status})`);
        setSubmitting(false);
        return;
      }
      navigate(`/categories/${video!.category_id}/videos`);
    } catch (err) {
      setFormError(String(err));
      setSubmitting(false);
    }
  }

  return (
    <>
      <form onSubmit={onSubmit} noValidate className="space-y-6 max-w-2xl">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
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
          {categoryOptions && (
            <FormField label="Category" required error={errors.categoryId}>
              <select
                value={categoryId}
                onChange={(e) => {
                  setCategoryId(e.target.value);
                  clearField("categoryId");
                  if (success) setSuccess(null);
                }}
                className={`field-input ${errors.categoryId ? "field-input-error" : ""}`}
              >
                <option value="">Select category</option>
                {categoryOptions.map((c) => (
                  <option key={c._id} value={c._id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </FormField>
          )}
        </div>
        <FormField label="Source URL" required error={errors.sourceUrl}>
          <input
            type="url"
            value={sourceUrl}
            onChange={(e) => {
              setSourceUrl(e.target.value);
              clearField("sourceUrl");
              if (success) setSuccess(null);
            }}
            className={`field-input ${errors.sourceUrl ? "field-input-error" : ""}`}
          />
        </FormField>
        <FormField
          label="Duration (seconds)"
          error={errors.duration}
          hint="Optional — leave blank to let the pipeline probe it."
          className="max-w-xs"
        >
          <input
            type="number"
            step="0.1"
            min="0"
            value={duration}
            onChange={(e) => {
              setDuration(e.target.value);
              clearField("duration");
              if (success) setSuccess(null);
            }}
            className={`field-input w-48 ${errors.duration ? "field-input-error" : ""}`}
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
            {submitting ? "Saving…" : isNew ? "Add video" : "Save changes"}
          </button>
        </div>
        {!isNew && (
          <div className="pt-6 hairline-t">
            <button
              type="button"
              onClick={() => setConfirmDelete(true)}
              className="btn-danger"
            >
              Delete video
            </button>
          </div>
        )}
      </form>
      {confirmDelete && (
        <ConfirmDialog
          title="Delete video?"
          message={`This will permanently remove "${video!.name}" from the database.`}
          confirmLabel="Delete"
          onConfirm={onDelete}
          onCancel={() => setConfirmDelete(false)}
        />
      )}
    </>
  );
}
