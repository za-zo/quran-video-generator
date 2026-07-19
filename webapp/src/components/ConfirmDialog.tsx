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
      <h3 className="font-serif text-xl mb-2">{title}</h3>
      <p className="text-sm text-mute mb-6">{message}</p>
      <div className="flex justify-end gap-3">
        <button onClick={onCancel} className="px-4 py-2 hairline-all text-sm hover:bg-rule/10">
          Cancel
        </button>
        <button onClick={onConfirm} className="px-4 py-2 hairline-all bg-accent text-paper text-sm font-medium hover:opacity-90">
          {confirmLabel}
        </button>
      </div>
    </Modal>
  );
}
