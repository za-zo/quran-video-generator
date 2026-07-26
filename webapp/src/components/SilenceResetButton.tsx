"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ConfirmDialog } from "./ConfirmDialog";
import { FormStatus } from "./FormStatus";

/**
 * SilenceResetButton — clears the cached silence analysis for an audio.
 *
 * Calls DELETE /api/audios/[id]/silence, which sets silence_analyzed=
 * false and empties silence_positions. The next pipeline run (or
 * `python main.py analyze-audio --audio-id <id>`) will re-analyse.
 *
 * Asks for confirmation first because re-analysis requires downloading
 * the full audio file again — it's not free.
 */
export function SilenceResetButton({ audioId }: { audioId: string }) {
  const router = useRouter();
  const [confirming, setConfirming] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onConfirm() {
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch(`/api/audios/${audioId}/silence`, {
        method: "DELETE",
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(body.error || `request failed (${res.status})`);
        setSubmitting(false);
        return;
      }
      // Force a refetch of the page so the SilenceTimeline disappears.
      router.refresh();
    } catch (err) {
      setError(String(err));
      setSubmitting(false);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setConfirming(true)}
        className="btn-danger"
      >
        Réinitialiser l&apos;analyse
      </button>
      {error && (
        <div className="mt-3">
          <FormStatus
            error={error}
            onDismiss={() => setError(null)}
          />
        </div>
      )}
      {confirming && (
        <ConfirmDialog
          title="Réinitialiser l'analyse des silences ?"
          message="L'analyse actuelle sera effacée. Le prochain run du pipeline (ou `python main.py analyze-audio`) devra re-télécharger l'audio et refaire l'analyse."
          confirmLabel="Réinitialiser"
          onConfirm={onConfirm}
          onCancel={() => setConfirming(false)}
        />
      )}
    </>
  );
}
