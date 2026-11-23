"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { AlertCircle, ArrowLeft, CreditCard, ExternalLink } from "lucide-react";
import { paymentsApi, type ApiPaymentTransaction } from "@/lib/api";

export default function PaymentDetailPage() {
  const params = useParams<{ id: string }>();
  const identifier = params?.id || "";

  const [payment, setPayment] = useState<ApiPaymentTransaction | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await paymentsApi.getById(identifier);
        if (active) setPayment(res.data);
      } catch (err) {
        if (active) {
          setError(
            err instanceof Error ? err.message : "Payment transaction not found."
          );
        }
      } finally {
        if (active) setLoading(false);
      }
    };
    if (identifier) void load();
    return () => {
      active = false;
    };
  }, [identifier]);

  return (
    <div className="space-y-6 max-w-4xl">
      <Link
        href="/admin/payments"
        className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900"
      >
        <ArrowLeft size={16} />
        Back to Payments
      </Link>

      {loading ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-8 text-sm text-slate-500">
          Loading payment record...
        </div>
      ) : error || !payment ? (
        <div className="bg-rose-50 border border-rose-200 rounded-2xl p-6 text-rose-700 text-sm flex items-center gap-2">
          <AlertCircle size={18} />
          <span>{error || "Payment record not found."}</span>
        </div>
      ) : (
        <div className="bg-white rounded-2xl border border-slate-200 p-6 space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-slate-100">
            <div className="flex items-center gap-3">
              <div className="w-11 h-11 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
                <CreditCard size={22} />
              </div>
              <div>
                <h1 className="text-xl font-bold text-slate-900 font-mono">
                  {payment.transaction_ref}
                </h1>
                <p className="text-xs text-slate-500">
                  Recorded {new Date(payment.created_at).toLocaleString()}
                </p>
              </div>
            </div>
            <div className="text-right">
              <p className="text-2xl font-bold text-slate-900">
                ${Number(payment.amount).toFixed(2)} {payment.currency}
              </p>
              <span className="inline-flex px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-800 capitalize mt-1">
                {payment.status}
              </span>
            </div>
          </div>

          <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
            <div className="p-3.5 bg-slate-50 rounded-xl">
              <dt className="text-xs text-slate-500">Payment Method</dt>
              <dd className="font-semibold text-slate-900 mt-1">{payment.payment_method}</dd>
            </div>
            <div className="p-3.5 bg-slate-50 rounded-xl">
              <dt className="text-xs text-slate-500">Provider</dt>
              <dd className="font-semibold text-slate-900 mt-1 uppercase">{payment.provider}</dd>
            </div>
            <div className="p-3.5 bg-slate-50 rounded-xl">
              <dt className="text-xs text-slate-500">Related Order</dt>
              <dd className="font-semibold text-blue-600 mt-1">
                <Link
                  href={`/admin/orders/${payment.order_id}`}
                  className="inline-flex items-center gap-1 hover:underline"
                >
                  Order #{payment.order_id} ({payment.order_status || "unknown"})
                  <ExternalLink size={13} />
                </Link>
              </dd>
            </div>
            <div className="p-3.5 bg-slate-50 rounded-xl">
              <dt className="text-xs text-slate-500">Customer</dt>
              <dd className="font-semibold text-slate-900 mt-1">
                {payment.customer_name || "Guest / Walk-in"}
                {payment.customer_email ? ` (${payment.customer_email})` : ""}
              </dd>
            </div>
            <div className="p-3.5 bg-slate-50 rounded-xl">
              <dt className="text-xs text-slate-500">Gateway / Stripe Reference</dt>
              <dd className="font-mono text-xs text-slate-800 mt-1 break-all">
                {payment.provider_reference || "None"}
              </dd>
            </div>
            <div className="p-3.5 bg-slate-50 rounded-xl">
              <dt className="text-xs text-slate-500">Card Details</dt>
              <dd className="font-semibold text-slate-900 mt-1">
                {payment.card_last4
                  ? `${payment.card_brand || "Card"} •••• ${payment.card_last4}`
                  : "Not applicable"}
              </dd>
            </div>
          </dl>

          {payment.failure_reason && (
            <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs">
              <strong>Failure Reason:</strong> {payment.failure_reason}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
