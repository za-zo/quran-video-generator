"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ConfirmDialog } from "./ConfirmDialog";
import { FormField, useFormValidation, validators } from "./FormField";
import { FormStatus } from "./FormStatus";

type AudioValues = {
  name: string;
  sourceUrl: string;
  duration: string;
};

export function AudioForm({ audio }: { audio?: { _id: string; name: string; source_url: string; duration_seconds: number } }) {
  const router = useRouter();
  const isNew = !audio;
  const [name, setName] = useState(audio?.name ?? "");
  const [sourceUrl, setSourceUrl] = useState(audio?.source_url ?? "");
  const [duration, setDuration] = useState(audio?.duration_seconds?.toString() ?? "");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const { errors, validate, clearField, setFieldError } = useFormValidation<AudioValues>({
    name: validators.required("Name"),
    sourceUrl: (v) => {
      const r = validators.required("Source URL")(v);
      if (r) return r;
      return validators.url("Source URL")(v);
    },
    duration: validators.nonNegativeNumber("Duration"),
  });

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    setSuccess(null);

    const ok = validate({ name, sourceUrl, duration });
    if (!ok) return;

    setSubmitting(true);

    const payload: Record<string, unknown> = {
      name: name.trim(),
      source_url: sourceUrl.trim(),
    };
    if (duration) {
      payload.duration_seconds = Number(duration);
    }

    try {
      const url = isNew ? "/api/audios" : `/api/audios/${audio!._id}`;
      const res = await fetch(url, {
        method: isNew ? "POST" : "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        const msg = body.error || `request failed (${res.status})`;
        // If the server flagged a duplicate-name, surface it on the name
        // field rather than as a generic form error.
        if (res.status === 409 && /already exists/i.test(msg)) {
          setFieldError("name", msg);
        } else {
          setFormError(msg);
        }
        setSubmitting(false);
        return;
      }
      if (isNew) {
        router.push("/audios");
      } else {
        setSuccess(`Audio "${name}" updated.`);
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
      const res = await fetch(`/api/audios/${audio!._id}`, { method: "DELETE" });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setFormError(body.error || `delete failed (${res.status})`);
        setSubmitting(false);
        return;
      }
      router.push("/audios");
    } catch (err) {
      setFormError(String(err));
      setSubmitting(false);
    }
  }

  return (
    <>
      <form onSubmit={onSubmit} noValidate className="space-y-6 max-w-2xl">
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
            {submitting ? "Saving…" : isNew ? "Add audio" : "Save changes"}
          </button>
        </div>
        {!isNew && (
          <div className="pt-6 hairline-t">
            <button
              type="button"
              onClick={() => setConfirmDelete(true)}
              className="btn-danger"
            >
              Delete audio
            </button>
          </div>
        )}
      </form>
      {confirmDelete && (
        <ConfirmDialog
          title="Delete audio?"
          message={`This will permanently remove "${audio!.name}" from the database. The pipeline will no longer be able to use this recitation.`}
          confirmLabel="Delete"
          onConfirm={onDelete}
          onCancel={() => setConfirmDelete(false)}
        />
      )}
    </>
  );
}
