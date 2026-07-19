"use client";

import { ReactNode, useState, useEffect } from "react";

/**
 * FormField — shared field wrapper that renders the label, the input,
 * and an inline error message below the input (replaces the browser's
 * default validation tooltip).
 *
 * Usage:
 *   <FormField
 *     label="Name"
 *     required
 *     error={errors.name}
 *   >
 *     <input className="field-input" ... />
 *   </FormField>
 *
 * The error slot is always rendered as a fixed-height line so the form
 * doesn't jump when an error appears/disappears.
 */

export function FormField({
  label,
  required,
  error,
  hint,
  children,
  className = "",
}: {
  label: string;
  required?: boolean;
  error?: string | null;
  hint?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={className}>
      <label className="block eyebrow mb-3">
        {label}
        {required && <span className="text-accent ml-1">*</span>}
      </label>
      {children}
      <div className="min-h-[1.25rem] mt-2">
        {error ? (
          <p className="text-2xs text-failed font-mono leading-tight flex items-start gap-1.5">
            <span className="inline-block w-1 h-1 rounded-full bg-failed mt-1.5 shrink-0" aria-hidden />
            <span>{error}</span>
          </p>
        ) : hint ? (
          <p className="text-2xs text-mute leading-tight">{hint}</p>
        ) : null}
      </div>
    </div>
  );
}

/**
 * useFormValidation — tiny helper to manage per-field error state.
 *
 * Pass validators as `{ fieldName: (value) => string | null }`. Returns
 * `{ errors, validate, clearField }` where:
 *   - validate(values) runs all validators and sets errors; returns
 *     true if all valid
 *   - clearField(name) clears a single field's error (call from
 *     onChange)
 */
export function useFormValidation<T extends Record<string, unknown>>(
  validators: Partial<Record<keyof T, (value: unknown, all: T) => string | null>>,
) {
  const [errors, setErrors] = useState<Partial<Record<keyof T, string>>>({});

  const validate = (values: T): boolean => {
    const next: Partial<Record<keyof T, string>> = {};
    for (const key of Object.keys(validators) as (keyof T)[]) {
      const fn = validators[key];
      if (!fn) continue;
      const msg = fn(values[key], values);
      if (msg) next[key] = msg;
    }
    setErrors(next);
    return Object.keys(next).length === 0;
  };

  const clearField = (name: keyof T) => {
    setErrors((prev) => {
      if (!prev[name]) return prev;
      const next = { ...prev };
      delete next[name];
      return next;
    });
  };

  const setFieldError = (name: keyof T, msg: string) => {
    setErrors((prev) => ({ ...prev, [name]: msg }));
  };

  // Allow setting form-level (non-field) errors via a special "_form" key
  // by setting a top-level error.
  return { errors, validate, clearField, setFieldError };
}

/**
 * Common validators. Each takes the raw value and returns an error
 * message or null.
 */
export const validators = {
  required:
    (label: string) =>
    (value: unknown): string | null => {
      if (value == null) return `${label} is required`;
      const s = String(value).trim();
      if (!s) return `${label} is required`;
      return null;
    },

  url:
    (label = "URL") =>
    (value: unknown): string | null => {
      if (value == null) return null;
      const s = String(value).trim();
      if (!s) return null;
      try {
        const u = new URL(s);
        if (u.protocol !== "http:" && u.protocol !== "https:") {
          return `${label} must start with http:// or https://`;
        }
        return null;
      } catch {
        return `${label} must be a valid URL`;
      }
    },

  nonNegativeNumber:
    (label: string) =>
    (value: unknown): string | null => {
      if (value == null) return null;
      const s = String(value).trim();
      if (!s) return null;
      const n = Number(s);
      if (isNaN(n)) return `${label} must be a number`;
      if (n < 0) return `${label} must be 0 or greater`;
      return null;
    },
};
