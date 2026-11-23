"use client";

import { useState } from "react";
import Link from "next/link";
import { AlertCircle, ArrowLeft, CheckCircle2, Mail } from "lucide-react";
import { authApi } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [submittedMessage, setSubmittedMessage] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleaned = email.trim();
    if (!cleaned) {
      setErrorMessage("Please enter your account email address.");
      return;
    }

    setLoading(true);
    setErrorMessage(null);
    try {
      const res = await authApi.forgotPassword({
        email: cleaned,
        client: "storefront",
      });
      setSubmittedMessage(
        res.message ||
          "If an active account exists for that email, password reset instructions have been sent."
      );
    } catch (err: unknown) {
      setErrorMessage(
        err instanceof Error
          ? err.message
          : "Unable to send password reset email right now."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full max-w-md space-y-6">
      <Link
        href="/login"
        className="inline-flex min-h-11 items-center gap-2 text-sm font-medium text-ink-soft hover:text-ink"
      >
        <ArrowLeft size={16} aria-hidden="true" />
        Back to sign in
      </Link>

      <div className="rounded-3xl border border-line bg-white p-8 shadow-sm space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-ink">Reset your password</h1>
          <p className="mt-2 text-sm text-slate-500">
            Enter the email address associated with your Blue Panda account and we will send a recovery link.
          </p>
        </div>

        {errorMessage && (
          <div
            role="alert"
            className="flex items-start gap-2.5 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-xs font-semibold text-rose-800"
          >
            <AlertCircle size={16} className="shrink-0 mt-0.5 text-rose-600" />
            <span>{errorMessage}</span>
          </div>
        )}

        {submittedMessage ? (
          <div className="space-y-4">
            <div className="flex items-start gap-2.5 rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-xs font-semibold text-emerald-800">
              <CheckCircle2 size={16} className="shrink-0 mt-0.5 text-emerald-600" />
              <span>{submittedMessage}</span>
            </div>
            <Link
              href="/reset-password"
              className="flex min-h-11 w-full items-center justify-center rounded-xl border border-line-strong text-sm font-semibold text-ink hover:bg-slate-50"
            >
              Already have a reset token? Enter it here
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label
                htmlFor="forgot-email"
                className="mb-1.5 block text-xs font-bold uppercase tracking-wider text-slate-700"
              >
                Email Address *
              </label>
              <div className="relative">
                <Mail
                  size={16}
                  className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400"
                />
                <input
                  id="forgot-email"
                  type="email"
                  autoComplete="email"
                  required
                  disabled={loading}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="alex@example.com"
                  className="min-h-12 w-full rounded-xl border border-line-strong bg-white pl-10 pr-4 text-sm text-ink placeholder:text-muted focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="flex min-h-12 w-full items-center justify-center rounded-xl bg-ink px-5 text-sm font-semibold text-white hover:bg-brand disabled:opacity-60"
            >
              {loading ? "Sending instructions…" : "Send Reset Link"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
