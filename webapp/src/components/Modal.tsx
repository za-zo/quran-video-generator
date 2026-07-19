"use client";

import { ReactNode } from "react";

export function Modal({ children, onClose }: { children: ReactNode; onClose: () => void }) {
  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
      <div className="bg-paper hairline-all p-6 max-w-md w-full">
        {children}
      </div>
    </div>
  );
}
