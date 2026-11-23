"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowLeft, CheckCircle2, Mail, AlertCircle } from "lucide-react";
import { authApi } from "@/lib/api";

export default function ManagementForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submittedMessage, setSubmittedMessage] = useState<string | null>(null);
  const [devResetUrl, setDevResetUrl] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmittedMessage(null);
    setDevResetUrl(null);
    const trimmed = email.trim();
    if (!trimmed) {
      setError("Please enter your account email address.");
      return;
    }

    setLoading(true);
    try {
      const res = await authApi.forgotPassword(trimmed);
      setSubmittedMessage(
        res.message ||
          "If an account exists for this email address, password reset instructions have been sent."
      );
      if (res.data?.reset_url) {
        setDevResetUrl(res.data.reset_url);
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to process password reset request. Please try again."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-white rounded-3xl shadow-xl border border-slate-200/80 p-8">
        <div className="mb-6">
          <Link
            href="/login"
            className="inline-flex items-center gap-2 text-xs font-semibold text-slate-500 hover:text-slate-900 transition"
          >
            <ArrowLeft size={14} />
            Back to Sign In
          </Link>
        </div>

        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 rounded-xl bg-blue-600/10 text-blue-600 flex items-center justify-center">
            <Mail size={20} />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-900">Reset Staff Password</h1>
            <p className="text-xs text-slate-500">Blue Panda Management Portal</p>
          </div>
        </div>

        <p className="text-sm text-slate-600 mt-3 mb-6">
          Enter your staff or administrator email address and we will send a single-use password reset link.
        </p>

        {error && (
          <div className="mb-4 p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-start gap-2">
            <AlertCircle size={16} className="shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {submittedMessage ? (
          <div className="space-y-4">
            <div className="p-4 rounded-2xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm flex items-start gap-3">
              <CheckCircle2 size={18} className="shrink-0 mt-0.5 text-emerald-600" />
              <div className="space-y-1">
                <p className="font-semibold">Check your email inbox</p>
                <p className="text-xs text-emerald-700">{submittedMessage}</p>
              </div>
            </div>

            {devResetUrl && (
              <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-900 space-y-1">
                <p className="font-semibold">Local Dev Console Email Link</p>
                <a
                  href={devResetUrl}
                  className="text-blue-700 underline break-all font-mono"
                >
                  {devResetUrl}
                </a>
              </div>
            )}

            <div className="flex items-center justify-between pt-2">
              <button
                type="button"
                onClick={() => {
                  setSubmittedMessage(null);
                  setDevResetUrl(null);
                }}
                className="text-xs font-semibold text-slate-600 hover:text-slate-900"
              >
                Send another link
              </button>
              <Link
                href="/login"
                className="text-xs font-semibold text-blue-600 hover:text-blue-700"
              >
                Return to Sign In
              </Link>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label
                htmlFor="reset-email"
                className="block text-xs font-semibold text-slate-700 mb-1.5"
              >
                Work Email Address
              </label>
              <input
                id="reset-email"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@bluepanda.store"
                className="w-full bg-slate-50 border border-slate-200 text-sm rounded-xl py-3 px-4 focus:outline-none focus:ring-2 focus:ring-blue-600/20 focus:border-blue-600 focus:bg-white transition"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 px-4 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white text-sm font-semibold rounded-xl transition cursor-pointer"
            >
              {loading ? "Sending Reset Link..." : "Send Reset Link"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
