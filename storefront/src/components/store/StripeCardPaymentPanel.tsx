"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { loadStripe, type Stripe } from "@stripe/stripe-js";
import {
  Elements,
  PaymentElement,
  useElements,
  useStripe,
} from "@stripe/react-stripe-js";
import { AlertCircle, ArrowLeft, CreditCard, Lock, ShieldCheck } from "lucide-react";

const stripePromiseCache = new Map<string, Promise<Stripe | null>>();

function getStripePromise(publishableKey: string): Promise<Stripe | null> {
  const existing = stripePromiseCache.get(publishableKey);
  if (existing) return existing;
  const created = loadStripe(publishableKey);
  stripePromiseCache.set(publishableKey, created);
  return created;
}

interface InnerCardFormProps {
  orderId: number;
  amount: number;
  onPaymentSucceeded: (paymentIntentId: string) => Promise<void>;
  onCancelCardStep: () => void;
}

function InnerStripeCardForm({
  orderId,
  amount,
  onPaymentSucceeded,
  onCancelCardStep,
}: InnerCardFormProps) {
  const stripe = useStripe();
  const elements = useElements();
  const [submitting, setSubmitting] = useState(false);
  const [cardError, setCardError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!stripe || !elements || submitting) return;

    setSubmitting(true);
    setCardError(null);
    try {
      const returnUrl =
        typeof window !== "undefined"
          ? `${window.location.origin}/checkout?order_id=${orderId}`
          : "http://localhost:3000/checkout";

      const result = await stripe.confirmPayment({
        elements,
        confirmParams: {
          return_url: returnUrl,
        },
        redirect: "if_required",
      });

      if (result.error) {
        setCardError(result.error.message || "Card authorization failed. Please check your card details.");
        return;
      }

      if (result.paymentIntent?.status === "succeeded" || result.paymentIntent?.status === "requires_capture") {
        await onPaymentSucceeded(result.paymentIntent.id);
        return;
      }

      setCardError(
        `Payment status is '${result.paymentIntent?.status || "incomplete"}'. Please complete card authentication and try again.`
      );
    } catch (err: unknown) {
      setCardError(
        err instanceof Error ? err.message : "Unable to verify card payment with the server."
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div className="rounded-2xl border border-slate-200 bg-slate-50/60 p-4">
        <PaymentElement options={{ layout: "tabs" }} />
      </div>

      {cardError && (
        <div
          role="alert"
          aria-live="assertive"
          className="flex items-start gap-2.5 rounded-xl border border-rose-200 bg-rose-50 p-3.5 text-xs font-medium text-rose-900"
        >
          <AlertCircle size={16} className="shrink-0 mt-0.5 text-rose-600" aria-hidden="true" />
          <span>{cardError}</span>
        </div>
      )}

      <div className="flex flex-col sm:flex-row gap-3">
        <button
          type="button"
          onClick={onCancelCardStep}
          disabled={submitting}
          className="min-h-12 px-5 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 text-sm font-semibold inline-flex items-center justify-center gap-2 transition"
        >
          <ArrowLeft size={16} aria-hidden="true" />
          Change Payment Method
        </button>

        <button
          type="submit"
          disabled={!stripe || !elements || submitting}
          className="bp-press min-h-12 flex-1 px-6 rounded-xl bg-brand hover:bg-brand-hover disabled:opacity-55 text-white text-sm font-bold inline-flex items-center justify-center gap-2 transition cursor-pointer"
        >
          <Lock size={16} aria-hidden="true" />
          {submitting ? "Verifying Card…" : `Pay $${amount.toFixed(2)}`}
        </button>
      </div>
    </form>
  );
}

export interface StripeCardPaymentPanelProps {
  orderId: number;
  amount: number;
  currency: string;
  clientSecret: string;
  publishableKey: string;
  onPaymentSucceeded: (paymentIntentId: string) => Promise<void>;
  onCancelCardStep: () => void;
}

export default function StripeCardPaymentPanel({
  orderId,
  amount,
  clientSecret,
  publishableKey,
  onPaymentSucceeded,
  onCancelCardStep,
}: StripeCardPaymentPanelProps) {
  const headingRef = useRef<HTMLHeadingElement | null>(null);
  const stripePromise = useMemo(
    () => (publishableKey ? getStripePromise(publishableKey) : null),
    [publishableKey]
  );

  useEffect(() => {
    headingRef.current?.focus();
  }, [clientSecret]);

  if (!stripePromise || !clientSecret) {
    return (
      <div
        role="alert"
        className="rounded-3xl bg-white p-6 ring-1 ring-rose-200 space-y-4 max-w-xl mx-auto"
      >
        <p className="text-sm font-semibold text-rose-800">
          Stripe publishable key or PaymentIntent secret is missing. Please verify server payment configuration.
        </p>
        <button
          type="button"
          onClick={onCancelCardStep}
          className="px-4 py-2.5 rounded-xl border border-slate-200 text-sm font-semibold text-slate-700"
        >
          Back to Checkout
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto rounded-3xl bg-white p-6 sm:p-8 ring-1 ring-line shadow-lg space-y-6">
      <div className="flex items-start justify-between gap-4 border-b border-line pb-4">
        <div className="space-y-1">
          <div className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-brand">
            <CreditCard size={14} aria-hidden="true" />
            Secure Card Authorization
          </div>
          <h2
            ref={headingRef}
            tabIndex={-1}
            className="text-2xl font-bold text-ink focus:outline-none"
          >
            Complete Card Payment · Order #{orderId}
          </h2>
          <p className="text-sm text-slate-500">
            Enter your Credit or Debit Card details below. Card data is encrypted directly with Stripe.
          </p>
        </div>

        <div className="text-right shrink-0">
          <span className="text-xs font-semibold text-slate-400 block">Amount Due</span>
          <span className="bp-price text-2xl font-bold text-brand">${amount.toFixed(2)}</span>
        </div>
      </div>

      <Elements
        stripe={stripePromise}
        options={{
          clientSecret,
          appearance: {
            theme: "stripe",
            variables: {
              colorPrimary: "#245BE7",
              borderRadius: "12px",
            },
          },
        }}
      >
        <InnerStripeCardForm
          orderId={orderId}
          amount={amount}
          onPaymentSucceeded={onPaymentSucceeded}
          onCancelCardStep={onCancelCardStep}
        />
      </Elements>

      <p className="flex items-center gap-2 text-xs text-slate-500 pt-1">
        <ShieldCheck size={15} className="text-emerald-600 shrink-0" aria-hidden="true" />
        <span>Your card is charged once, then verified by Blue Panda before order confirmation.</span>
      </p>
    </div>
  );
}
