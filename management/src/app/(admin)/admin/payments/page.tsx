"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  Banknote,
  CheckCircle2,
  Clock,
  CreditCard,
  Eye,
  RefreshCw,
  Search,
  ShieldCheck,
} from "lucide-react";
import {
  paymentsApi,
  type ApiPaymentConfig,
  type ApiPaymentTransaction,
} from "@/lib/api";

const STATUS_BADGE: Record<string, string> = {
  captured: "bg-emerald-50 text-emerald-700 border-emerald-200",
  succeeded: "bg-emerald-50 text-emerald-700 border-emerald-200",
  paid: "bg-emerald-50 text-emerald-700 border-emerald-200",
  pending: "bg-amber-50 text-amber-700 border-amber-200",
  requires_action: "bg-amber-50 text-amber-700 border-amber-200",
  failed: "bg-rose-50 text-rose-700 border-rose-200",
  refunded: "bg-slate-100 text-slate-700 border-slate-200",
  partially_refunded: "bg-slate-100 text-slate-700 border-slate-200",
};

export default function PaymentsPage() {
  const [transactions, setTransactions] = useState<ApiPaymentTransaction[]>([]);
  const [config, setConfig] = useState<ApiPaymentConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [methodFilter, setMethodFilter] = useState("");

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [cfgRes, listRes] = await Promise.all([
        paymentsApi.getConfig(),
        paymentsApi.getAll({
          status: statusFilter || undefined,
          method: methodFilter || undefined,
          search: search.trim() || undefined,
        }),
      ]);
      setConfig(cfgRes.data);
      setTransactions(listRes.data || []);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to load payment transactions."
      );
    } finally {
      setLoading(false);
    }
  }, [methodFilter, search, statusFilter]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const isSettledStatus = (status: string) =>
    ["captured", "succeeded", "paid"].includes((status || "").toLowerCase());

  const succeededVolume = transactions
    .filter((t) => isSettledStatus(t.status))
    .reduce((sum, t) => sum + Number(t.amount || 0), 0);

  const pendingVolume = transactions
    .filter((t) => ["pending", "requires_action"].includes((t.status || "").toLowerCase()))
    .reduce((sum, t) => sum + Number(t.amount || 0), 0);

  const cardVolume = transactions
    .filter((t) => t.payment_method.toLowerCase().includes("card") && isSettledStatus(t.status))
    .reduce((sum, t) => sum + Number(t.amount || 0), 0);

  const codVolume = transactions
    .filter((t) => t.payment_method.toLowerCase().includes("delivery") && isSettledStatus(t.status))
    .reduce((sum, t) => sum + Number(t.amount || 0), 0);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Digital Payments</h1>
          <p className="text-sm text-slate-500 mt-1">
            Authoritative card gateway & Cash on Delivery payment ledger
          </p>
        </div>
        <button
          type="button"
          onClick={() => void loadData()}
          className="inline-flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 rounded-xl text-sm font-medium text-slate-700 hover:bg-slate-50 transition cursor-pointer"
        >
          <RefreshCw size={15} className={loading ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      {config && (
        <div
          className={`rounded-2xl border p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${
            config.card_gateway_configured
              ? "bg-emerald-50/70 border-emerald-200 text-emerald-900"
              : "bg-amber-50/80 border-amber-200 text-amber-900"
          }`}
        >
          <div className="flex items-start gap-3">
            <ShieldCheck size={20} className="shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold">
                {config.card_gateway_configured
                  ? `Stripe Card Gateway Active (${config.currency})`
                  : "Stripe Card Gateway Not Configured"}
              </p>
              <p className="text-xs opacity-80 mt-0.5">
                Enabled payment methods: {config.supported_methods.join(", ")}.
                {!config.card_gateway_configured &&
                  " Set STRIPE_SECRET_KEY to process live online Credit / Debit Card payments."}
              </p>
            </div>
          </div>
          <Link
            href="/admin/settings"
            className="text-xs font-semibold underline shrink-0"
          >
            Payment Settings
          </Link>
        </div>
      )}

      {/* KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-2xl border border-slate-200 p-5">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500">
            <span>Settled Payments</span>
            <CheckCircle2 size={16} className="text-emerald-600" />
          </div>
          <p className="text-2xl font-bold text-slate-900 mt-2">
            ${succeededVolume.toFixed(2)}
          </p>
        </div>

        <div className="bg-white rounded-2xl border border-slate-200 p-5">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500">
            <span>Pending Authorization / COD</span>
            <Clock size={16} className="text-amber-600" />
          </div>
          <p className="text-2xl font-bold text-slate-900 mt-2">
            ${pendingVolume.toFixed(2)}
          </p>
        </div>

        <div className="bg-white rounded-2xl border border-slate-200 p-5">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500">
            <span>Credit / Debit Card Settled</span>
            <CreditCard size={16} className="text-blue-600" />
          </div>
          <p className="text-2xl font-bold text-slate-900 mt-2">
            ${cardVolume.toFixed(2)}
          </p>
        </div>

        <div className="bg-white rounded-2xl border border-slate-200 p-5">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500">
            <span>Cash on Delivery Settled</span>
            <Banknote size={16} className="text-slate-600" />
          </div>
          <p className="text-2xl font-bold text-slate-900 mt-2">
            ${codVolume.toFixed(2)}
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-2xl border border-slate-200 p-4 flex flex-col md:flex-row gap-3">
        <div className="relative flex-1">
          <Search size={16} className="absolute left-3.5 top-3 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by transaction ref, customer, email, or order ID..."
            className="w-full pl-10 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-600/20 focus:bg-white"
          />
        </div>
        <select
          value={methodFilter}
          onChange={(e) => setMethodFilter(e.target.value)}
          className="px-3.5 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm text-slate-700"
        >
          <option value="">All Payment Methods</option>
          <option value="Credit / Debit Card">Credit / Debit Card</option>
          <option value="Cash on Delivery">Cash on Delivery</option>
          <option value="Cash">POS Cash</option>
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3.5 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm text-slate-700"
        >
          <option value="">All Statuses</option>
          <option value="captured">Captured</option>
          <option value="pending">Pending</option>
          <option value="requires_action">Requires Action</option>
          <option value="failed">Failed</option>
          <option value="refunded">Refunded</option>
        </select>
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

      {/* Table */}
      <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-sm text-slate-500">
            Loading payment transactions...
          </div>
        ) : transactions.length === 0 ? (
          <div className="p-10 text-center text-sm text-slate-500">
            No payment transactions found matching your filters.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-500 uppercase">
                <tr>
                  <th className="px-5 py-3.5">Transaction Ref</th>
                  <th className="px-5 py-3.5">Order</th>
                  <th className="px-5 py-3.5">Customer</th>
                  <th className="px-5 py-3.5">Method</th>
                  <th className="px-5 py-3.5">Provider</th>
                  <th className="px-5 py-3.5 text-right">Amount</th>
                  <th className="px-5 py-3.5">Status</th>
                  <th className="px-5 py-3.5">Date</th>
                  <th className="px-5 py-3.5 text-right">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {transactions.map((tx) => (
                  <tr key={tx.id} className="hover:bg-slate-50/70 transition">
                    <td className="px-5 py-3.5 font-mono text-xs font-semibold text-slate-900">
                      {tx.transaction_ref}
                    </td>
                    <td className="px-5 py-3.5">
                      <Link
                        href={`/admin/orders/${tx.order_id}`}
                        className="font-semibold text-blue-600 hover:underline"
                      >
                        #{tx.order_id}
                      </Link>
                    </td>
                    <td className="px-5 py-3.5">
                      <div className="font-medium text-slate-900">
                        {tx.customer_name || "Guest / Walk-in"}
                      </div>
                      {tx.customer_email && (
                        <div className="text-xs text-slate-500">{tx.customer_email}</div>
                      )}
                    </td>
                    <td className="px-5 py-3.5 text-slate-700">
                      <div>{tx.payment_method}</div>
                      {tx.card_last4 && (
                        <div className="text-xs text-slate-500">
                          {tx.card_brand || "Card"} •••• {tx.card_last4}
                        </div>
                      )}
                    </td>
                    <td className="px-5 py-3.5 text-xs uppercase font-medium text-slate-600">
                      {tx.provider}
                    </td>
                    <td className="px-5 py-3.5 text-right font-semibold text-slate-900">
                      ${Number(tx.amount).toFixed(2)} {tx.currency}
                    </td>
                    <td className="px-5 py-3.5">
                      <span
                        className={`inline-flex px-2.5 py-0.5 rounded-full text-xs font-semibold border capitalize ${
                          STATUS_BADGE[tx.status] || "bg-slate-100 text-slate-700 border-slate-200"
                        }`}
                      >
                        {tx.status}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-xs text-slate-500 whitespace-nowrap">
                      {new Date(tx.created_at).toLocaleString()}
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      <Link
                        href={`/admin/payments/${encodeURIComponent(tx.transaction_ref)}`}
                        className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-medium"
                      >
                        <Eye size={13} />
                        View
                      </Link>
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
