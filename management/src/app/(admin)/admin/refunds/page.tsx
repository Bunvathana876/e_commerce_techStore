"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  BookOpen,
  CheckCircle2,
  Download,
  Plus,
  RefreshCw,
  RotateCcw,
  Search,
} from "lucide-react";
import {
  inventoryApi,
  ordersApi,
  refundsApi,
  reportsApi,
  type ApiOrder,
  type ApiRefund,
  type ApiRefundLedgerEntry,
  type ApiRefundLedgerTrialBalance,
  type ApiWarehouse,
} from "@/lib/api";

const STATUS_BADGE: Record<string, string> = {
  requested: "bg-amber-50 text-amber-700 border-amber-200",
  approved: "bg-blue-50 text-blue-700 border-blue-200",
  processed: "bg-emerald-50 text-emerald-700 border-emerald-200",
  rejected: "bg-rose-50 text-rose-700 border-rose-200",
};

export default function RefundsPage() {
  const [tab, setTab] = useState<"refunds" | "ledger">("refunds");
  const [refunds, setRefunds] = useState<ApiRefund[]>([]);
  const [orders, setOrders] = useState<ApiOrder[]>([]);
  const [warehouses, setWarehouses] = useState<ApiWarehouse[]>([]);
  const [ledgerEntries, setLedgerEntries] = useState<ApiRefundLedgerEntry[]>([]);
  const [trialBalance, setTrialBalance] = useState<ApiRefundLedgerTrialBalance | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  const [showCreateForm, setShowCreateForm] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createForm, setCreateForm] = useState({
    order_id: "",
    amount: "",
    refund_method: "Credit / Debit Card",
    reason: "",
    restock_items: true,
    warehouse_id: "",
    notes: "",
  });

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [refRes, ordRes, whRes, ledRes] = await Promise.all([
        refundsApi.getAll({
          status: statusFilter || undefined,
          search: search.trim() || undefined,
        }),
        ordersApi.listAll(),
        inventoryApi.getWarehouses(),
        refundsApi.getLedger({ limit: 50 }),
      ]);
      setRefunds(refRes.data || []);
      setOrders(ordRes.data || []);
      const whList: ApiWarehouse[] = whRes.data || [];
      setWarehouses(whList);
      setLedgerEntries(ledRes.data?.entries || []);
      setTrialBalance(ledRes.data?.trial_balance || null);

      if (whList.length > 0 && !createForm.warehouse_id) {
        const defWh = whList.find((w: ApiWarehouse) => w.is_default) || whList[0];
        setCreateForm((prev) => ({ ...prev, warehouse_id: String(defWh.id) }));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load refunds.");
    } finally {
      setLoading(false);
    }
  }, [createForm.warehouse_id, search, statusFilter]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const handleCreateRefund = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    setError(null);
    setFeedback(null);
    try {
      const res = await refundsApi.create({
        order_id: Number(createForm.order_id),
        amount: createForm.amount ? parseFloat(createForm.amount) : undefined,
        refund_method: createForm.refund_method,
        reason: createForm.reason.trim(),
        restock_items: createForm.restock_items,
        warehouse_id: createForm.warehouse_id
          ? Number(createForm.warehouse_id)
          : undefined,
        notes: createForm.notes.trim() || undefined,
      });
      setFeedback(`Created refund request ${res.data.refund_number}.`);
      setShowCreateForm(false);
      setCreateForm((prev) => ({
        ...prev,
        order_id: "",
        amount: "",
        reason: "",
        notes: "",
      }));
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create refund request.");
    } finally {
      setCreating(false);
    }
  };

  const handleWorkflow = async (
    refund: ApiRefund,
    action: "approve" | "process" | "reject"
  ) => {
    setError(null);
    setFeedback(null);
    try {
      if (action === "approve") {
        await refundsApi.approve(refund.refund_number);
        setFeedback(`Approved ${refund.refund_number} & accrued liability in ledger.`);
      } else if (action === "process") {
        await refundsApi.process(refund.refund_number);
        setFeedback(`Processed settlement for ${refund.refund_number}.`);
      } else {
        const reason = window.prompt("Reason for rejecting this refund:", "Ineligible for refund");
        if (!reason || reason.trim().length < 3) return;
        await refundsApi.reject(refund.refund_number, { reason: reason.trim() });
        setFeedback(`Rejected ${refund.refund_number}.`);
      }
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : `Refund ${action} failed.`);
    }
  };

  const handleExportCsv = async () => {
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
      setError(err instanceof Error ? err.message : "Failed to export refund ledger CSV.");
    }
  };

  const settledTotal = refunds
    .filter((r) => r.status === "processed")
    .reduce((sum, r) => sum + Number(r.amount || 0), 0);

  const liabilityTotal = refunds
    .filter((r) => r.status === "requested" || r.status === "approved")
    .reduce((sum, r) => sum + Number(r.amount || 0), 0);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            Refunds & Double-Entry Accounting Ledger
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Dedicated refund approvals, inventory restocking, and immutable GL postings (4100 / 2100 / 1010 / 1020)
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => void handleExportCsv()}
            className="inline-flex items-center gap-2 px-3.5 py-2 bg-white border border-slate-200 rounded-xl text-sm font-medium text-slate-700 hover:bg-slate-50 cursor-pointer"
          >
            <Download size={15} />
            Export GL CSV
          </button>
          <button
            type="button"
            onClick={() => setShowCreateForm((v) => !v)}
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-semibold cursor-pointer"
          >
            <Plus size={16} />
            New Refund Request
          </button>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-2xl border border-slate-200 p-5">
          <p className="text-xs font-medium text-slate-500">Total Refund Records</p>
          <p className="text-2xl font-bold text-slate-900 mt-1">{refunds.length}</p>
        </div>
        <div className="bg-white rounded-2xl border border-slate-200 p-5">
          <p className="text-xs font-medium text-slate-500">Pending Liability</p>
          <p className="text-2xl font-bold text-amber-700 mt-1">${liabilityTotal.toFixed(2)}</p>
        </div>
        <div className="bg-white rounded-2xl border border-slate-200 p-5">
          <p className="text-xs font-medium text-slate-500">Settled Refunds</p>
          <p className="text-2xl font-bold text-emerald-700 mt-1">${settledTotal.toFixed(2)}</p>
        </div>
        <div className="bg-white rounded-2xl border border-slate-200 p-5">
          <p className="text-xs font-medium text-slate-500">GL Trial Balance</p>
          <p className="text-sm font-bold mt-2">
            {trialBalance?.balanced ? (
              <span className="text-emerald-700 inline-flex items-center gap-1.5">
                <CheckCircle2 size={16} />
                Balanced (${Number(trialBalance.total_debits).toFixed(2)})
              </span>
            ) : (
              <span className="text-rose-700">Check Ledger</span>
            )}
          </p>
        </div>
      </div>

      {showCreateForm && (
        <div className="bg-white rounded-2xl border border-slate-200 p-6">
          <h2 className="text-sm font-bold text-slate-900 mb-4">Record Refund Request</h2>
          <form onSubmit={handleCreateRefund} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Order *</label>
              <select
                required
                value={createForm.order_id}
                onChange={(e) => setCreateForm({ ...createForm, order_id: e.target.value })}
                className="w-full px-3.5 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm"
              >
                <option value="">Select Order</option>
                {orders.map((o) => (
                  <option key={o.id} value={o.id}>
                    Order #{o.id} — ${Number(o.total).toFixed(2)} ({o.status}/{o.payment_status})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Amount (blank = full remaining balance)
              </label>
              <input
                type="number"
                step="0.01"
                min="0.01"
                value={createForm.amount}
                onChange={(e) => setCreateForm({ ...createForm, amount: e.target.value })}
                placeholder="Full order total"
                className="w-full px-3.5 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Refund Method
              </label>
              <select
                value={createForm.refund_method}
                onChange={(e) => setCreateForm({ ...createForm, refund_method: e.target.value })}
                className="w-full px-3.5 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm"
              >
                <option value="Credit / Debit Card">Credit / Debit Card</option>
                <option value="Cash on Delivery">Cash on Delivery</option>
                <option value="Cash">Cash</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Reason *
              </label>
              <input
                type="text"
                required
                minLength={3}
                value={createForm.reason}
                onChange={(e) => setCreateForm({ ...createForm, reason: e.target.value })}
                placeholder="Customer return / defective item"
                className="w-full px-3.5 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Restock Warehouse
              </label>
              <select
                value={createForm.warehouse_id}
                onChange={(e) => setCreateForm({ ...createForm, warehouse_id: e.target.value })}
                disabled={!createForm.restock_items}
                className="w-full px-3.5 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm disabled:opacity-50"
              >
                {warehouses.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.code} — {w.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-end justify-between gap-3">
              <label className="flex items-center gap-2 text-xs font-medium text-slate-700 py-2">
                <input
                  type="checkbox"
                  checked={createForm.restock_items}
                  onChange={(e) =>
                    setCreateForm({ ...createForm, restock_items: e.target.checked })
                  }
                />
                Restock items on settle
              </label>
              <button
                type="submit"
                disabled={creating}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-semibold cursor-pointer"
              >
                {creating ? "Creating..." : "Create Refund"}
              </button>
            </div>
          </form>
        </div>
      )}

      {feedback && (
        <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm">
          {feedback}
        </div>
      )}

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

      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex gap-2 bg-white p-1.5 rounded-2xl border border-slate-200">
          <button
            type="button"
            onClick={() => setTab("refunds")}
            className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold cursor-pointer ${
              tab === "refunds" ? "bg-blue-600 text-white" : "text-slate-600"
            }`}
          >
            <RotateCcw size={15} />
            Refund Requests
          </button>
          <button
            type="button"
            onClick={() => setTab("ledger")}
            className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold cursor-pointer ${
              tab === "ledger" ? "bg-blue-600 text-white" : "text-slate-600"
            }`}
          >
            <BookOpen size={15} />
            General Ledger ({ledgerEntries.length})
          </button>
        </div>

        <button
          type="button"
          onClick={() => void loadData()}
          className="inline-flex items-center gap-2 px-3.5 py-2 bg-white border border-slate-200 rounded-xl text-sm text-slate-700 hover:bg-slate-50 cursor-pointer"
        >
          <RefreshCw size={15} className={loading ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      {tab === "refunds" ? (
        <div className="space-y-4">
          <div className="bg-white rounded-2xl border border-slate-200 p-4 flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Search size={16} className="absolute left-3.5 top-3 text-slate-400" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search refund #, customer, or order ID..."
                className="w-full pl-10 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm"
              />
            </div>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3.5 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm"
            >
              <option value="">All Statuses</option>
              <option value="requested">Requested</option>
              <option value="approved">Approved</option>
              <option value="processed">Processed</option>
              <option value="rejected">Rejected</option>
            </select>
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
            {refunds.length === 0 ? (
              <div className="p-10 text-center text-sm text-slate-500">
                No refund requests recorded.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-500 uppercase">
                    <tr>
                      <th className="px-5 py-3.5">Refund #</th>
                      <th className="px-5 py-3.5">Order</th>
                      <th className="px-5 py-3.5">Customer</th>
                      <th className="px-5 py-3.5">Method</th>
                      <th className="px-5 py-3.5 text-right">Amount</th>
                      <th className="px-5 py-3.5">Status</th>
                      <th className="px-5 py-3.5 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {refunds.map((r) => (
                      <tr key={r.id} className="hover:bg-slate-50/70">
                        <td className="px-5 py-3.5 font-mono text-xs font-semibold">
                          <Link
                            href={`/admin/refunds/${encodeURIComponent(r.refund_number)}`}
                            className="text-blue-600 hover:underline"
                          >
                            {r.refund_number}
                          </Link>
                        </td>
                        <td className="px-5 py-3.5">
                          <Link
                            href={`/admin/orders/${r.order_id}`}
                            className="font-semibold text-slate-800 hover:text-blue-600"
                          >
                            #{r.order_id}
                          </Link>
                        </td>
                        <td className="px-5 py-3.5 text-slate-700">
                          <div>{r.customer_name || "Customer"}</div>
                          <div className="text-xs text-slate-400 truncate max-w-[180px]">
                            {r.reason}
                          </div>
                        </td>
                        <td className="px-5 py-3.5 text-slate-600">{r.refund_method}</td>
                        <td className="px-5 py-3.5 text-right font-semibold text-slate-900">
                          ${Number(r.amount).toFixed(2)}
                        </td>
                        <td className="px-5 py-3.5">
                          <span
                            className={`inline-flex px-2.5 py-0.5 rounded-full text-xs font-semibold border capitalize ${
                              STATUS_BADGE[r.status] || "bg-slate-100 text-slate-700 border-slate-200"
                            }`}
                          >
                            {r.status}
                          </span>
                        </td>
                        <td className="px-5 py-3.5 text-right space-x-2 whitespace-nowrap">
                          {r.status === "requested" && (
                            <button
                              type="button"
                              onClick={() => void handleWorkflow(r, "approve")}
                              className="px-2.5 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold cursor-pointer"
                            >
                              Approve
                            </button>
                          )}
                          {r.status === "approved" && (
                            <button
                              type="button"
                              onClick={() => void handleWorkflow(r, "process")}
                              className="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold cursor-pointer"
                            >
                              Settle Refund
                            </button>
                          )}
                          {(r.status === "requested" || r.status === "approved") && (
                            <button
                              type="button"
                              onClick={() => void handleWorkflow(r, "reject")}
                              className="px-2.5 py-1 bg-rose-50 hover:bg-rose-100 text-rose-700 rounded-lg text-xs font-semibold cursor-pointer"
                            >
                              Reject
                            </button>
                          )}
                          <Link
                            href={`/admin/refunds/${encodeURIComponent(r.refund_number)}`}
                            className="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-medium"
                          >
                            Audit
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
      ) : (
        <div className="space-y-4">
          {trialBalance && trialBalance.accounts.length > 0 && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {trialBalance.accounts.map((acc) => (
                <div
                  key={acc.account_code}
                  className="bg-white rounded-2xl border border-slate-200 p-4"
                >
                  <p className="text-xs font-mono font-bold text-blue-700">
                    {acc.account_code}
                  </p>
                  <p className="text-sm font-semibold text-slate-900 mt-0.5">
                    {acc.account_name}
                  </p>
                  <div className="mt-2 flex justify-between text-xs text-slate-600">
                    <span>Dr ${Number(acc.total_debits).toFixed(2)}</span>
                    <span>Cr ${Number(acc.total_credits).toFixed(2)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
            {ledgerEntries.length === 0 ? (
              <div className="p-8 text-center text-sm text-slate-500">
                No refund ledger journal postings recorded yet.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left">
                  <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 uppercase font-semibold">
                    <tr>
                      <th className="px-4 py-3">Journal Ref</th>
                      <th className="px-4 py-3">Account</th>
                      <th className="px-4 py-3">Entry Type</th>
                      <th className="px-4 py-3 text-right">Debit</th>
                      <th className="px-4 py-3 text-right">Credit</th>
                      <th className="px-4 py-3">Memo</th>
                      <th className="px-4 py-3">Date</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {ledgerEntries.map((entry) => (
                      <tr key={entry.id}>
                        <td className="px-4 py-3 font-mono font-semibold text-slate-900">
                          {entry.journal_ref}
                        </td>
                        <td className="px-4 py-3">
                          <span className="font-mono font-semibold text-blue-700">
                            {entry.account_code}
                          </span>{" "}
                          <span className="text-slate-600">{entry.account_name}</span>
                        </td>
                        <td className="px-4 py-3 capitalize text-slate-700">
                          {entry.entry_type.replaceAll("_", " ")}
                        </td>
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
        </div>
      )}
    </div>
  );
}
