"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { FormField, useFormValidation, validators } from "./FormField";
import { FormStatus } from "./FormStatus";
import { useNavigateWithRefresh } from "@/lib/navigate";

type SliceEditValues = {
  postedIn: string;
  badResult: boolean;
};

export function SliceEditForm({
  slice,
}: {
  slice: {
    _id: string;
    posted_in?: string | null;
    bad_result?: boolean;
  };
}) {
  const router = useRouter();
  const navigate = useNavigateWithRefresh();
  const [postedIn, setPostedIn] = useState(slice.posted_in ?? "");
  const [badResult, setBadResult] = useState(slice.bad_result ?? false);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const { errors, validate, clearField } = useFormValidation<SliceEditValues>({
    postedIn: (v) => {
      if (!v) return null;
      const s = String(v).trim();
      if (s.length > 200) return "posted_in must be 200 characters or fewer";
      return null;
    },
  });

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    setSuccess(null);

    const ok = validate({ postedIn, badResult });
    if (!ok) return;

    setSubmitting(true);

    const payload: Record<string, unknown> = {
      bad_result: badResult,
    };
    // Send posted_in as null if empty (clears the field in DB)
    payload.posted_in = postedIn.trim() || null;

    try {
      const res = await fetch(`/api/slices/${slice._id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setFormError(body.error || `request failed (${res.status})`);
        setSubmitting(false);
        return;
      }
      setSuccess("Slice updated.");
      router.refresh();
    } catch (err) {
      setFormError(String(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-6 max-w-2xl">
      <FormField
        label="Posted in"
        error={errors.postedIn}
        hint="Account name where this video was published (e.g. @quran.daily). Leave blank to clear."
      >
        <input
          type="text"
          value={postedIn}
          onChange={(e) => {
            setPostedIn(e.target.value);
            clearField("postedIn");
            if (success) setSuccess(null);
          }}
          placeholder="e.g. @quran.daily"
          className={`field-input ${errors.postedIn ? "field-input-error" : ""}`}
        />
      </FormField>

      {/* Bad result toggle */}
      <div className="hairline-t pt-6">
        <label className="flex items-start gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={badResult}
            onChange={(e) => {
              setBadResult(e.target.checked);
              if (success) setSuccess(null);
            }}
            className="mt-1 w-4 h-4 accent-failed cursor-pointer"
          />
          <div>
            <div className="eyebrow mb-1">BAD RESULT</div>
            <p className="text-sm text-mute">
              Flag this slice&apos;s output as unsatisfactory. Bad outputs are
              highlighted with a crimson badge in the gallery and can be
              filtered out.
            </p>
          </div>
        </label>
      </div>

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
          {submitting ? "Saving…" : "Save changes"}
        </button>
      </div>
    </form>
  );
}
