"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { AlertCircle, ArrowLeft } from "lucide-react";
import {
  paymentsApi,
  refundsApi,
  type ApiPaymentTransaction,
  type ApiRefund,
} from "@/lib/api";

export default function TransactionDetailPage() {
  const params = useParams<{ id: string }>();
  const identifier = decodeURIComponent(params?.id || "");

  const [payment, setPayment] = useState<ApiPaymentTransaction | null>(null);
  const [refund, setRefund] = useState<ApiRefund | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const load = async () => {
      setLoading(true);
      setError(null);
      setPayment(null);
      setRefund(null);
      try {
        if (identifier.toUpperCase().startsWith("REF-")) {
          const res = await refundsApi.getById(identifier);
          if (active) setRefund(res.data);
        } else {
          const res = await paymentsApi.getById(identifier);
          if (active) setPayment(res.data);
        }
      } catch (err) {
        if (active) {
          setError(
            err instanceof Error ? err.message : "Transaction record not found."
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
        href="/admin/transactions"
        className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900"
      >
        <ArrowLeft size={16} />
        Back to Transactions
      </Link>

      {loading ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-8 text-sm text-slate-500">
          Loading transaction details...
        </div>
      ) : error ? (
        <div className="bg-rose-50 border border-rose-200 rounded-2xl p-6 text-rose-700 text-sm flex items-center gap-2">
          <AlertCircle size={18} />
          <span>{error}</span>
        </div>
      ) : payment ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-4">
            <div>
              <p className="text-xs font-semibold text-emerald-700 uppercase">Payment Capture</p>
              <h1 className="text-xl font-bold font-mono text-slate-900 mt-0.5">
                {payment.transaction_ref}
              </h1>
            </div>
            <p className="text-2xl font-bold text-emerald-700">
              +${Number(payment.amount).toFixed(2)} {payment.currency}
            </p>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-xs text-slate-500 block">Method</span>
              <span className="font-semibold text-slate-900">{payment.payment_method}</span>
            </div>
            <div>
              <span className="text-xs text-slate-500 block">Status</span>
              <span className="font-semibold text-slate-900 capitalize">{payment.status}</span>
            </div>
            <div>
              <span className="text-xs text-slate-500 block">Order</span>
              <Link href={`/admin/orders/${payment.order_id}`} className="font-semibold text-blue-600 hover:underline">
                Order #{payment.order_id}
              </Link>
            </div>
            <div>
              <span className="text-xs text-slate-500 block">Provider Reference</span>
              <span className="font-mono text-xs text-slate-800">{payment.provider_reference || "None"}</span>
            </div>
          </div>
        </div>
      ) : refund ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-4">
            <div>
              <p className="text-xs font-semibold text-rose-700 uppercase">Refund Ledger Record</p>
              <h1 className="text-xl font-bold font-mono text-slate-900 mt-0.5">
                {refund.refund_number}
              </h1>
            </div>
            <p className="text-2xl font-bold text-rose-700">
              -${Number(refund.amount).toFixed(2)} {refund.currency}
            </p>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-xs text-slate-500 block">Refund Method</span>
              <span className="font-semibold text-slate-900">{refund.refund_method}</span>
            </div>
            <div>
              <span className="text-xs text-slate-500 block">Status</span>
              <span className="font-semibold text-slate-900 capitalize">{refund.status}</span>
            </div>
            <div>
              <span className="text-xs text-slate-500 block">Order</span>
              <Link href={`/admin/orders/${refund.order_id}`} className="font-semibold text-blue-600 hover:underline">
                Order #{refund.order_id}
              </Link>
            </div>
            <div>
              <span className="text-xs text-slate-500 block">Accounting Journal Entries</span>
              <Link
                href={`/admin/refunds/${encodeURIComponent(refund.refund_number)}`}
                className="font-semibold text-blue-600 hover:underline"
              >
                Inspect {refund.ledger_entries.length} ledger postings →
              </Link>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
