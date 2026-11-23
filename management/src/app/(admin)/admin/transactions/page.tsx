"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  ArrowDownLeft,
  ArrowUpRight,
  Download,
  RefreshCw,
  Search,
} from "lucide-react";
import {
  paymentsApi,
  refundsApi,
  reportsApi,
  type ApiPaymentTransaction,
  type ApiRefund,
} from "@/lib/api";

interface FinancialTransactionRow {
  ref: string;
  direction: "inflow" | "outflow";
  category: "Payment" | "Refund";
  orderId: number;
  party: string;
  method: string;
  amount: number;
  currency: string;
  status: string;
  createdAt: string;
}

export default function TransactionsPage() {
  const [payments, setPayments] = useState<ApiPaymentTransaction[]>([]);
  const [refunds, setRefunds] = useState<ApiRefund[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [typeFilter, setTypeFilter] = useState<"all" | "Payment" | "Refund">("all");
  const [search, setSearch] = useState("");
  const [exporting, setExporting] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [payRes, refRes] = await Promise.all([
        paymentsApi.getAll(),
        refundsApi.getAll(),
      ]);
      setPayments(payRes.data || []);
      setRefunds(refRes.data || []);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load transaction ledger."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const rows = useMemo<FinancialTransactionRow[]>(() => {
    const mappedPayments: FinancialTransactionRow[] = payments.map((p) => ({
      ref: p.transaction_ref,
      direction: "inflow",
      category: "Payment",
      orderId: p.order_id,
      party: p.customer_name || p.customer_email || `Order #${p.order_id}`,
      method: p.payment_method,
      amount: Number(p.amount || 0),
      currency: p.currency || "USD",
      status: p.status,
      createdAt: p.created_at,
    }));

    const mappedRefunds: FinancialTransactionRow[] = refunds.map((r) => ({
      ref: r.refund_number,
      direction: "outflow",
      category: "Refund",
      orderId: r.order_id,
      party: r.customer_name || r.customer_email || `Order #${r.order_id}`,
      method: r.refund_method,
      amount: Number(r.amount || 0),
      currency: r.currency || "USD",
      status: r.status,
      createdAt: r.created_at,
    }));

    const needle = search.trim().toLowerCase();
    return [...mappedPayments, ...mappedRefunds]
      .filter((row) => {
        if (typeFilter !== "all" && row.category !== typeFilter) return false;
        if (!needle) return true;
        return (
          row.ref.toLowerCase().includes(needle) ||
          row.party.toLowerCase().includes(needle) ||
          row.method.toLowerCase().includes(needle) ||
          String(row.orderId).includes(needle)
        );
      })
      .sort(
        (a, b) =>
          new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
      );
  }, [payments, refunds, search, typeFilter]);

  const handleExportRefundLedger = async () => {
    setExporting(true);
    try {
      const csv = await reportsApi.downloadLedgerCsv("refunds");
      const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "refund-accounting-ledger.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "CSV export failed.");
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Financial Transactions</h1>
          <p className="text-sm text-slate-500 mt-1">
            Unified view of Card/COD/POS payment captures and accounting refund entries
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={exporting}
            onClick={() => void handleExportRefundLedger()}
            className="inline-flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 rounded-xl text-sm font-medium text-slate-700 hover:bg-slate-50 transition cursor-pointer"
          >
            <Download size={15} />
            {exporting ? "Exporting..." : "Export Refund Ledger CSV"}
          </button>
          <button
            type="button"
            onClick={() => void loadData()}
            className="inline-flex items-center gap-2 px-4 py-2 bg-slate-900 text-white rounded-xl text-sm font-medium hover:bg-slate-800 transition cursor-pointer"
          >
            <RefreshCw size={15} className={loading ? "animate-spin" : ""} />
            Refresh
          </button>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 p-4 flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search size={16} className="absolute left-3.5 top-3 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search reference, order ID, customer, or method..."
            className="w-full pl-10 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-600/20 focus:bg-white"
          />
        </div>
        <div className="flex items-center gap-1.5 bg-slate-100 p-1 rounded-xl">
          {(["all", "Payment", "Refund"] as const).map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setTypeFilter(tab)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
                typeFilter === tab
                  ? "bg-white text-slate-900 shadow-xs"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              {tab === "all" ? "All" : `${tab}s`}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-700 text-sm flex items-center justify-between">
          <span className="flex items-center gap-2">
            <AlertCircle size={16} />
            {error}
          </span>
          <button
            type="button"
            onClick={() => void loadData()}
            className="text-xs font-semibold underline cursor-pointer"
          >
            Retry
          </button>
        </div>
      )}

      <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-sm text-slate-500">
            Loading financial transactions...
          </div>
        ) : rows.length === 0 ? (
          <div className="p-10 text-center text-sm text-slate-500">
            No transactions recorded yet.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-500 uppercase">
                <tr>
                  <th className="px-5 py-3.5">Reference</th>
                  <th className="px-5 py-3.5">Type</th>
                  <th className="px-5 py-3.5">Order</th>
                  <th className="px-5 py-3.5">Party</th>
                  <th className="px-5 py-3.5">Method</th>
                  <th className="px-5 py-3.5 text-right">Amount</th>
                  <th className="px-5 py-3.5">Status</th>
                  <th className="px-5 py-3.5">Timestamp</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rows.map((row) => (
                  <tr key={row.ref} className="hover:bg-slate-50/70 transition">
                    <td className="px-5 py-3.5 font-mono text-xs font-semibold">
                      <Link
                        href={`/admin/transactions/${encodeURIComponent(row.ref)}`}
                        className="text-blue-600 hover:underline"
                      >
                        {row.ref}
                      </Link>
                    </td>
                    <td className="px-5 py-3.5">
                      <span
                        className={`inline-flex items-center gap-1 text-xs font-semibold ${
                          row.direction === "inflow"
                            ? "text-emerald-700"
                            : "text-rose-700"
                        }`}
                      >
                        {row.direction === "inflow" ? (
                          <ArrowDownLeft size={13} />
                        ) : (
                          <ArrowUpRight size={13} />
                        )}
                        {row.category}
                      </span>
                    </td>
                    <td className="px-5 py-3.5">
                      <Link
                        href={`/admin/orders/${row.orderId}`}
                        className="text-slate-700 hover:text-blue-600 font-medium"
                      >
                        #{row.orderId}
                      </Link>
                    </td>
                    <td className="px-5 py-3.5 text-slate-700">{row.party}</td>
                    <td className="px-5 py-3.5 text-slate-600">{row.method}</td>
                    <td
                      className={`px-5 py-3.5 text-right font-semibold ${
                        row.direction === "inflow"
                          ? "text-emerald-700"
                          : "text-rose-700"
                      }`}
                    >
                      {row.direction === "inflow" ? "+" : "-"}$
                      {row.amount.toFixed(2)} {row.currency}
                    </td>
                    <td className="px-5 py-3.5">
                      <span className="inline-flex px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-700 capitalize">
                        {row.status}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-xs text-slate-500 whitespace-nowrap">
                      {new Date(row.createdAt).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
