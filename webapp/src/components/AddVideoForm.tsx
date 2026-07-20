"use client";

/**
 * AddVideoForm — inline form to add a video to a category.
 */

import { useRouter } from "next/navigation";
import { useState } from "react";
import { FormField, useFormValidation, validators } from "./FormField";
import { FormStatus } from "./FormStatus";

type AddVideoValues = {
  name: string;
  sourceUrl: string;
  duration: string;
};

export function AddVideoForm({ categoryId }: { categoryId: string }) {
  const router = useRouter();
  const [name, setName] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [duration, setDuration] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const { errors, validate, clearField, setFieldError } = useFormValidation<AddVideoValues>({
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
      category_id: categoryId,
      name: name.trim(),
      source_url: sourceUrl.trim(),
    };
    if (duration) {
      payload.duration_seconds = Number(duration);
    }

    try {
      const res = await fetch("/api/videos", {
        method: "POST",
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
      setSuccess(`Video "${name}" added.`);
      setName("");
      setSourceUrl("");
      setDuration("");
      router.refresh();
    } catch (err) {
      setFormError(String(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
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
        <div className="md:col-span-2">
          <FormField label="Source URL" required error={errors.sourceUrl}>
            <input
              type="url"
              value={sourceUrl}
              onChange={(e) => {
                setSourceUrl(e.target.value);
                clearField("sourceUrl");
                if (success) setSuccess(null);
              }}
              placeholder="https://example.com/sea_0.mp4"
              className={`field-input ${errors.sourceUrl ? "field-input-error" : ""}`}
            />
          </FormField>
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 items-start">
        <FormField
          label="Duration (s)"
          error={errors.duration}
          hint="Optional."
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
            className={`field-input ${errors.duration ? "field-input-error" : ""}`}
          />
        </FormField>
        <div className="md:col-span-3 space-y-4 pt-1">
          <FormStatus
            success={success}
            error={formError}
            onDismiss={() => {
              if (success) setSuccess(null);
              if (formError) setFormError(null);
            }}
          />
          <div className="pt-2">
            <button type="submit" disabled={submitting} className="btn-primary">
              {submitting ? "Adding…" : "Add video"}
            </button>
          </div>
        </div>
      </div>
    </form>
  );
}
