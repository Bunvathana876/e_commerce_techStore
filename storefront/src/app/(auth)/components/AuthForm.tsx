"use client";

import { Suspense, useState, useEffect, useRef } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  Eye,
  EyeOff,
  Lock,
  Mail,
  ShieldCheck,
  Truck,
  User,
} from "lucide-react";
import { authApi } from "@/lib/api";
import {
  isLoggedIn,
  saveAuthSession,
  getCurrentUser,
  getSafeRoleDestination,
} from "@/lib/auth";

type Mode = "login" | "register";

interface AuthFormProps {
  mode: Mode;
}

function AuthFormInner({ mode }: AuthFormProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectParam = searchParams.get("redirect");

  const [isLogin, setIsLogin] = useState(mode === "login");
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const isSubmittingRef = useRef(false);

  useEffect(() => {
    setIsLogin(mode === "login");
    setErrorMessage(null);
  }, [mode]);

  useEffect(() => {
    if (isLoggedIn()) {
      const current = getCurrentUser();
      router.replace(getSafeRoleDestination(current?.role, redirectParam));
    }
  }, [router, redirectParam]);

  // Form state
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (isSubmittingRef.current) return;

    setErrorMessage(null);

    // Client-side validation
    const trimmedEmail = email.trim();
    if (!trimmedEmail) {
      setErrorMessage("Please enter your email address.");
      return;
    }

    if (!password) {
      setErrorMessage("Please enter your password.");
      return;
    }

    if (!isLogin) {
      const trimmedName = name.trim();
      if (!trimmedName) {
        setErrorMessage("Please provide your full name.");
        return;
      }

      if (password.length < 6) {
        setErrorMessage("Password must be at least 6 characters.");
        return;
      }

      if (password !== confirmPassword) {
        setErrorMessage("Passwords do not match. Please re-enter your password.");
        return;
      }
    }

    isSubmittingRef.current = true;
    setLoading(true);

    try {
      if (isLogin) {
        const res = await authApi.login({ email: trimmedEmail, password });
        if (!res?.data?.access_token || !res?.data?.user) {
          throw new Error("Invalid response received from authentication server.");
        }
        saveAuthSession(res.data.access_token, res.data.user);
        router.push(getSafeRoleDestination(res.data.user.role, redirectParam));
      } else {
        const res = await authApi.register({
          name: name.trim(),
          email: trimmedEmail,
          password,
        });
        if (!res?.data?.access_token || !res?.data?.user) {
          throw new Error("Account creation could not be confirmed by the server.");
        }
        saveAuthSession(res.data.access_token, res.data.user);
        router.push(getSafeRoleDestination(res.data.user.role, redirectParam));
      }
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message
          : "Authentication failed. Please verify your credentials and try again.";
      setErrorMessage(msg);
    } finally {
      setLoading(false);
      isSubmittingRef.current = false;
    }
  };

  const switchToRegister = () => {
    setIsLogin(false);
    setErrorMessage(null);
    router.push(
      redirectParam
        ? `/register?redirect=${encodeURIComponent(redirectParam)}`
        : "/register"
    );
  };

  const switchToLogin = () => {
    setIsLogin(true);
    setErrorMessage(null);
    router.push(
      redirectParam
        ? `/login?redirect=${encodeURIComponent(redirectParam)}`
        : "/login"
    );
  };

  return (
    <div className="w-full max-w-5xl space-y-4">
      {/* Top Breadcrumb Navigation */}
      <div className="flex items-center justify-between px-2">
        <Link
          href="/"
          className="inline-flex min-h-11 items-center gap-2 text-sm font-medium text-ink-soft hover:text-ink"
        >
          <ArrowLeft size={16} aria-hidden="true" />
          Back to the store
        </Link>
      </div>

      <div className="relative flex min-h-[600px] w-full flex-col overflow-hidden border border-line bg-white lg:flex-row">
        {/* Quiet brand panel */}
        <div className="relative isolate flex w-full flex-col justify-between overflow-hidden bg-ink p-8 text-white sm:p-12 lg:w-5/12">

          <div>
            <Link href="/" className="inline-flex items-center gap-3">
              <img
                src="/images/logo_panda_blue.png"
                alt=""
                width={44}
                height={44}
                className="h-11 w-11 rounded-xl bg-white object-contain"
              />
              <span className="font-display text-2xl font-bold tracking-tight text-white">
                Blue Panda
              </span>
            </Link>

            <h2 className="mt-12 text-3xl font-bold leading-tight text-white sm:text-4xl">
              {isLogin ? "Welcome back." : "Shop tech with an account."}
            </h2>
            <p className="mt-4 max-w-sm text-[15px] leading-7 text-white/75">
              {isLogin
                ? "Sign in to see your orders, your bag and the products you saved."
                : "Track deliveries, keep a wishlist and check out faster next time."}
            </p>
          </div>

          <ul className="mt-10 space-y-3 border-t border-white/15 pt-8 text-sm text-white/80">
            {[
              { icon: Truck, text: "Delivery status for every order" },
              { icon: ShieldCheck, text: "Receipts kept in your account" },
              { icon: CheckCircle2, text: "Bag and wishlist on every device" },
            ].map(({ icon: Icon, text }) => (
              <li key={text} className="flex items-center gap-3">
                <Icon size={18} aria-hidden="true" className="shrink-0 text-lime" />
                {text}
              </li>
            ))}
          </ul>
        </div>

        {/* Right Column: Clean White Authentication Form */}
        <div className="w-full lg:w-7/12 p-8 sm:p-12 lg:p-16 flex flex-col justify-center bg-white">
          <div className="max-w-md mx-auto w-full">
            <div className="mb-8">
              <h1 className="text-3xl font-bold text-ink sm:text-4xl">
                {isLogin ? "Sign in" : "Create an account"}
              </h1>
              <p className="text-xs sm:text-sm text-slate-500 mt-2">
                {isLogin
                  ? "Enter your account email and password to access your orders and bag."
                  : "Register with Blue Panda to track orders, save hardware, and access member perks."}
              </p>
            </div>

            {/* Error Feedback Banner */}
            {errorMessage && (
              <div
                role="alert"
                aria-live="polite"
                className="mb-6 p-4 bg-rose-50 border border-rose-200 text-rose-800 text-xs font-bold rounded-2xl flex items-start gap-2.5 animate-fadeIn"
              >
                <AlertCircle size={16} className="text-rose-600 shrink-0 mt-0.5" />
                <span className="leading-relaxed">{errorMessage}</span>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Registration: Full Name */}
              {!isLogin && (
                <div>
                  <label
                    htmlFor="auth-name"
                    className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5"
                  >
                    Full Name *
                  </label>
                  <div className="relative">
                    <User
                      size={16}
                      className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400"
                    />
                    <input
                      id="auth-name"
                      type="text"
                      autoComplete="name"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="Alex Rivera"
                      required={!isLogin}
                      disabled={loading}
                      className="w-full pl-10 pr-4 min-h-12 rounded-xl border border-line-strong bg-white text-base text-ink placeholder:text-muted focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20 sm:text-sm"
                    />
                  </div>
                </div>
              )}

              {/* Email Address */}
              <div>
                <label
                  htmlFor="auth-email"
                  className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5"
                >
                  Email Address *
                </label>
                <div className="relative">
                  <Mail
                    size={16}
                    className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400"
                  />
                  <input
                    id="auth-email"
                    type="email"
                    autoComplete="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="alex@example.com"
                    required
                    disabled={loading}
                    className="w-full pl-10 pr-4 min-h-12 rounded-xl border border-line-strong bg-white text-base text-ink placeholder:text-muted focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20 sm:text-sm"
                  />
                </div>
              </div>

              {/* Password */}
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label
                    htmlFor="auth-password"
                    className="block text-xs font-bold text-slate-700 uppercase tracking-wider"
                  >
                    Password *
                  </label>
                  {!isLogin && (
                    <span className="text-[11px] font-semibold text-slate-400">
                      Min 6 characters
                    </span>
                  )}
                </div>
                <div className="relative">
                  <Lock
                    size={16}
                    className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400"
                  />
                  <input
                    id="auth-password"
                    type={showPassword ? "text" : "password"}
                    autoComplete={isLogin ? "current-password" : "new-password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    required
                    disabled={loading}
                    className="w-full pl-10 pr-10 min-h-12 rounded-xl border border-line-strong bg-white text-base text-ink placeholder:text-muted focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20 sm:text-sm"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                    className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 cursor-pointer p-1"
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              {/* Registration: Confirm Password */}
              {!isLogin && (
                <div>
                  <label
                    htmlFor="auth-confirm-password"
                    className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5"
                  >
                    Confirm Password *
                  </label>
                  <div className="relative">
                    <Lock
                      size={16}
                      className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400"
                    />
                    <input
                      id="auth-confirm-password"
                      type={showConfirmPassword ? "text" : "password"}
                      autoComplete="new-password"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      placeholder="••••••••"
                      required={!isLogin}
                      disabled={loading}
                      className="w-full pl-10 pr-10 min-h-12 rounded-xl border border-line-strong bg-white text-base text-ink placeholder:text-muted focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20 sm:text-sm"
                    />
                    <button
                      type="button"
                      onClick={() => setShowConfirmPassword((v) => !v)}
                      aria-label={
                        showConfirmPassword
                          ? "Hide confirmed password"
                          : "Show confirmed password"
                      }
                      className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 cursor-pointer p-1"
                    >
                      {showConfirmPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                </div>
              )}

              {/* Primary Action Button */}
              <button
                type="submit"
                disabled={loading}
                className="bp-press mt-2 flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-ink px-5 text-[15px] font-semibold text-white hover:bg-brand disabled:opacity-60"
              >
                {loading ? (
                  <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                ) : isLogin ? (
                  "Sign In to Blue Panda"
                ) : (
                  "Create Blue Panda Account"
                )}
              </button>

              {/* Switch View Link */}
              <div className="pt-6 border-t border-slate-100 text-center">
                {isLogin ? (
                  <p className="text-xs text-slate-500">
                    Don&apos;t have an account yet?{" "}
                    <button
                      type="button"
                      onClick={switchToRegister}
                      className="font-bold text-brand hover:underline cursor-pointer ml-1"
                    >
                      Create customer account
                    </button>
                  </p>
                ) : (
                  <p className="text-xs text-slate-500">
                    Already registered?{" "}
                    <button
                      type="button"
                      onClick={switchToLogin}
                      className="font-bold text-brand hover:underline cursor-pointer ml-1"
                    >
                      Sign in to your account
                    </button>
                  </p>
                )}
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function AuthForm({ mode }: AuthFormProps) {
  return (
    <Suspense
      fallback={
        <div className="w-full max-w-5xl min-h-[600px] rounded-[2.5rem] bg-white border border-slate-200 animate-pulse flex items-center justify-center">
          <div className="w-8 h-8 border-3 border-[#245BE7] border-t-transparent rounded-full animate-spin" />
        </div>
      }
    >
      <AuthFormInner mode={mode} />
    </Suspense>
  );
}
