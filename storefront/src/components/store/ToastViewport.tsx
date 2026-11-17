"use client";

import { CheckCircle2, Info, AlertCircle, X } from "lucide-react";
import { useShopStore } from "@/lib/store";

export default function ToastViewport() {
  const toasts = useShopStore((s) => s.toasts);
  const dismissToast = useShopStore((s) => s.dismissToast);

  // The live region stays mounted so assistive tech announces the first toast too.
  return (
    <div
      aria-live="polite"
      aria-relevant="additions"
      className="pointer-events-none fixed bottom-[max(1rem,env(safe-area-inset-bottom))] left-4 right-4 z-60 flex flex-col items-end gap-2 sm:left-auto sm:right-5 sm:w-96"
    >
      {toasts.map((toast) => {
        const icon =
          toast.tone === "error" ? (
            <AlertCircle size={18} aria-hidden="true" className="shrink-0 text-rose-400" />
          ) : toast.tone === "info" ? (
            <Info size={18} aria-hidden="true" className="shrink-0 text-sky" />
          ) : (
            <CheckCircle2 size={18} aria-hidden="true" className="shrink-0 text-lime" />
          );

        return (
          <div
            key={toast.id}
            role={toast.tone === "error" ? "alert" : "status"}
            className="pointer-events-auto flex w-full animate-enter items-start gap-3 rounded-2xl bg-ink py-3 pl-4 pr-2 text-white shadow-xl"
          >
            <div className="mt-0.5">{icon}</div>
            <div className="min-w-0 flex-1 py-0.5">
              <p className="text-sm font-semibold">{toast.title}</p>
              {toast.description && (
                <p className="mt-0.5 line-clamp-2 text-sm text-white/70">{toast.description}</p>
              )}
            </div>
            <button
              type="button"
              onClick={() => dismissToast(toast.id)}
              aria-label="Dismiss notification"
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-white/60 transition-colors hover:bg-white/10 hover:text-white"
            >
              <X size={16} aria-hidden="true" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
