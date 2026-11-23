"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { AlertCircle, ArrowLeft, CheckCircle2, RotateCcw } from "lucide-react";
import { refundsApi, type ApiRefund } from "@/lib/api";

export default function RefundDetailPage() {
  const params = useParams<{ id: string }>();
  const identifier = decodeURIComponent(params?.id || "");

  const [refund, setRefund] = useState<ApiRefund | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [externalRef, setExternalRef] = useState("");
  const [busy, setBusy] = useState(false);

  const loadRefund = useCallback(async () => {
    if (!identifier) return;
    setLoading(true);
    setError(null);
    try {
      const res = await refundsApi.getById(identifier);
      setRefund(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Refund record not found.");
    } finally {
      setLoading(false);
    }
  }, [identifier]);

  useEffect(() => {
    void loadRefund();
  }, [loadRefund]);

  const handleAction = async (action: "approve" | "process" | "reject") => {
    if (!refund) return;
    setBusy(true);
    setError(null);
    setFeedback(null);
    try {
      if (action === "approve") {
        const res = await refundsApi.approve(refund.refund_number);
        setRefund(res.data);
        setFeedback("Refund approved and accrued in GL.");
      } else if (action === "process") {
        const res = await refundsApi.process(refund.refund_number, {
          external_reference: externalRef.trim() || undefined,
        });
        setRefund(res.data);
        setFeedback("Refund processed and settled in GL.");
      } else {
        if (rejectReason.trim().length < 3) {
          setError("Enter a rejection reason (minimum 3 characters).");
          setBusy(false);
          return;
        }
        const res = await refundsApi.reject(refund.refund_number, {
          reason: rejectReason.trim(),
        });
        setRefund(res.data);
        setFeedback("Refund request rejected.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : `Action '${action}' failed.`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6 max-w-5xl">
      <Link
        href="/admin/refunds"
        className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900"
      >
        <ArrowLeft size={16} />
        Back to Refunds & Accounting Ledger
      </Link>

      {loading ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-8 text-sm text-slate-500">
          Loading refund audit record...
        </div>
      ) : error && !refund ? (
        <div className="bg-rose-50 border border-rose-200 rounded-2xl p-6 text-rose-700 text-sm flex items-center gap-2">
          <AlertCircle size={18} />
          <span>{error}</span>
        </div>
      ) : refund ? (
        <>
          <div className="bg-white rounded-2xl border border-slate-200 p-6 space-y-5">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-100 pb-4">
              <div className="flex items-center gap-3">
                <div className="w-11 h-11 rounded-xl bg-rose-50 text-rose-600 flex items-center justify-center">
                  <RotateCcw size={22} />
                </div>
                <div>
                  <h1 className="text-xl font-bold font-mono text-slate-900">
                    {refund.refund_number}
                  </h1>
                  <p className="text-xs text-slate-500">
                    Requested {new Date(refund.requested_at).toLocaleString()}
                  </p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-2xl font-bold text-slate-900">
                  ${Number(refund.amount).toFixed(2)} {refund.currency}
                </p>
                <span className="inline-flex px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-800 capitalize mt-1">
                  {refund.status}
                </span>
              </div>
            </div>

            {feedback && (
              <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center gap-2">
                <CheckCircle2 size={15} />
                {feedback}
              </div>
            )}

            {error && (
              <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2">
                <AlertCircle size={15} />
                {error}
              </div>
            )}

            <dl className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 text-sm">
              <div className="p-3.5 bg-slate-50 rounded-xl">
                <dt className="text-xs text-slate-500">Order</dt>
                <dd className="font-semibold text-blue-600 mt-1">
                  <Link href={`/admin/orders/${refund.order_id}`} className="hover:underline">
                    Order #{refund.order_id} (${Number(refund.order_total || 0).toFixed(2)})
                  </Link>
                </dd>
              </div>
              <div className="p-3.5 bg-slate-50 rounded-xl">
                <dt className="text-xs text-slate-500">Customer</dt>
                <dd className="font-semibold text-slate-900 mt-1">
                  {refund.customer_name || "Customer"}{" "}
                  {refund.customer_email ? `(${refund.customer_email})` : ""}
                </dd>
              </div>
              <div className="p-3.5 bg-slate-50 rounded-xl">
                <dt className="text-xs text-slate-500">Method & Restock</dt>
                <dd className="font-semibold text-slate-900 mt-1">
                  {refund.refund_method} ({refund.restocked ? "Restocked" : refund.restock_items ? "Will restock" : "No restock"})
                </dd>
              </div>
              <div className="p-3.5 bg-slate-50 rounded-xl sm:col-span-2 lg:col-span-3">
                <dt className="text-xs text-slate-500">Reason</dt>
                <dd className="font-medium text-slate-900 mt-1">{refund.reason}</dd>
              </div>
            </dl>

            {(refund.status === "requested" || refund.status === "approved") && (
              <div className="pt-3 border-t border-slate-100 flex flex-col lg:flex-row lg:items-center justify-between gap-3">
                <div className="flex flex-wrap items-center gap-2">
                  {refund.status === "requested" && (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void handleAction("approve")}
                      className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-semibold cursor-pointer"
                    >
                      Approve & Accrue GL
                    </button>
                  )}
                  {refund.status === "approved" && (
                    <>
                      <input
                        type="text"
                        value={externalRef}
                        onChange={(e) => setExternalRef(e.target.value)}
                        placeholder="Optional Stripe / bank ref"
                        className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs"
                      />
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => void handleAction("process")}
                        className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-semibold cursor-pointer"
                      >
                        Settle & Post GL
                      </button>
                    </>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={rejectReason}
                    onChange={(e) => setRejectReason(e.target.value)}
                    placeholder="Rejection reason..."
                    className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs"
                  />
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void handleAction("reject")}
                    className="px-3.5 py-2 bg-rose-50 hover:bg-rose-100 text-rose-700 rounded-xl text-xs font-semibold cursor-pointer"
                  >
                    Reject
                  </button>
                </div>
              </div>
            )}
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-100">
              <h2 className="font-bold text-slate-900">
                Accounting Journal Postings ({refund.ledger_entries.length})
              </h2>
            </div>
            {refund.ledger_entries.length === 0 ? (
              <div className="p-6 text-sm text-slate-500">
                No accounting entries posted yet (posted automatically on Approve & Process).
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left">
                  <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 uppercase font-semibold">
                    <tr>
                      <th className="px-4 py-3">Journal Ref</th>
                      <th className="px-4 py-3">Account</th>
                      <th className="px-4 py-3">Type</th>
                      <th className="px-4 py-3 text-right">Debit</th>
                      <th className="px-4 py-3 text-right">Credit</th>
                      <th className="px-4 py-3">Memo</th>
                      <th className="px-4 py-3">Posted At</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {refund.ledger_entries.map((entry) => (
                      <tr key={entry.id}>
                        <td className="px-4 py-3 font-mono font-semibold text-slate-900">
                          {entry.journal_ref}
                        </td>
                        <td className="px-4 py-3">
                          <span className="font-mono font-semibold text-blue-700">
                            {entry.account_code}
                          </span>{" "}
                          {entry.account_name}
                        </td>
                        <td className="px-4 py-3 capitalize">{entry.entry_type}</td>
                        <td className="px-4 py-3 text-right font-semibold text-emerald-700">
                          {Number(entry.debit_amount) > 0
                            ? `$${Number(entry.debit_amount).toFixed(2)}`
                            : "-"}
                        </td>
                        <td className="px-4 py-3 text-right font-semibold text-rose-700">
                          {Number(entry.credit_amount) > 0
                            ? `$${Number(entry.credit_amount).toFixed(2)}`
                            : "-"}
                        </td>
                        <td className="px-4 py-3 text-slate-600">{entry.memo || "-"}</td>
                        <td className="px-4 py-3 text-slate-500 whitespace-nowrap">
                          {new Date(entry.created_at).toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      ) : null}
    </div>
  );
}
