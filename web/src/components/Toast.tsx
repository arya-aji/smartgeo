"use client";

import { useEffect, useState } from "react";

export type ToastType = "success" | "error" | "info";

interface Toast {
  id: string;
  message: string;
  type: ToastType;
}

let toastListeners: ((toasts: Toast[]) => void)[] = [];
let toasts: Toast[] = [];

function emit() {
  toastListeners.forEach((fn) => fn([...toasts]));
}

export function showToast(message: string, type: ToastType = "info") {
  const id = `${Date.now()}-${Math.random()}`;
  toasts = [...toasts, { id, message, type }];
  emit();
  setTimeout(() => {
    toasts = toasts.filter((t) => t.id !== id);
    emit();
  }, 4000);
}

export default function ToastContainer() {
  const [list, setList] = useState<Toast[]>([]);

  useEffect(() => {
    const fn = (t: Toast[]) => setList(t);
    toastListeners.push(fn);
    return () => {
      toastListeners = toastListeners.filter((l) => l !== fn);
    };
  }, []);

  return (
    <div className="fixed right-4 top-4 z-50 flex flex-col gap-2">
      {list.map((t) => (
        <div
          key={t.id}
          className={`rounded-md px-4 py-3 text-sm font-medium shadow-lg ring-1 ring-inset transition-all ${
            t.type === "success"
              ? "bg-emerald-50 text-emerald-800 ring-emerald-600/20"
              : t.type === "error"
              ? "bg-red-50 text-red-800 ring-red-600/20"
              : "bg-surface-50 text-surface-800 ring-surface-600/20"
          }`}
        >
          {t.message}
        </div>
      ))}
    </div>
  );
}
