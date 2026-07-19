"use client";

import { Modal } from "./Modal";

export function ConfirmDialog({
  title,
  message,
  confirmLabel = "Confirm",
  onConfirm,
  onCancel,
}: {
  title: string;
  message: string;
  confirmLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <Modal onClose={onCancel}>
      <div className="flex items-center gap-2 mb-3">
        <span className="inline-block w-1.5 h-1.5 rounded-full bg-failed" aria-hidden />
        <div className="eyebrow text-failed">CONFIRM</div>
      </div>
      <h3 className="font-serif text-2xl mb-3 leading-tight">{title}</h3>
      <p className="text-sm text-mute mb-8 leading-relaxed">{message}</p>
      <div className="flex justify-end gap-3">
        <button onClick={onCancel} className="btn-ghost">
          Cancel
        </button>
        <button onClick={onConfirm} className="btn-primary bg-failed hover:bg-failed/90">
          {confirmLabel}
        </button>
      </div>
    </Modal>
  );
}
