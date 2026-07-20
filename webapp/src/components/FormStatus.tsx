"use client";

import { useEffect } from "react";

/**
 * FormStatus — inline success/error banner shown above the submit button.
 *
 * Used to confirm that a save succeeded (since the page often doesn't
 * navigate away after a successful PUT — the form just stays put and
 * the user has no feedback that their change took effect).
 *
 * Pass `success` to show a success banner, or `error` to show an error.
 * If both are passed, error wins. Pass `onDismiss` to allow dismissal.
 *
 * The banner auto-dismisses after 4 seconds when `success` is shown.
 */

export function FormStatus({
  success,
  error,
  onDismiss,
}: {
  success?: string | null;
  error?: string | null;
  onDismiss?: () => void;
}) {
  useEffect(() => {
    if (success && onDismiss) {
      const t = setTimeout(onDismiss, 4000);
      return () => clearTimeout(t);
    }
  }, [success, onDismiss]);

  if (error) {
    return (
      <div className="hairline-t pt-4 flex items-start gap-2">
        <span className="inline-block w-1.5 h-1.5 rounded-full bg-failed mt-1.5 shrink-0" aria-hidden />
        <div className="flex-1">
          <div className="eyebrow text-failed mb-1">ERROR</div>
          <p className="text-sm text-failed leading-relaxed">{error}</p>
        </div>
        {onDismiss && (
          <button
            type="button"
            onClick={onDismiss}
            className="text-2xs text-failed/60 hover:text-failed transition-colors uppercase tracking-wide-2 font-mono"
            aria-label="Dismiss"
          >
            ✕
          </button>
        )}
      </div>
    );
  }

  if (success) {
    return (
      <div className="hairline-t pt-4 flex items-start gap-2">
        <span className="inline-block w-1.5 h-1.5 rounded-full bg-success mt-1.5 shrink-0" aria-hidden />
        <div className="flex-1">
          <div className="eyebrow text-success mb-1">SAVED</div>
          <p className="text-sm text-success leading-relaxed">{success}</p>
        </div>
        {onDismiss && (
          <button
            type="button"
            onClick={onDismiss}
            className="text-2xs text-success/60 hover:text-success transition-colors uppercase tracking-wide-2 font-mono"
            aria-label="Dismiss"
          >
            ✕
          </button>
        )}
      </div>
    );
  }

  return null;
}
