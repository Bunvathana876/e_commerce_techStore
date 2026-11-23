"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Download,
  RefreshCw,
  TrendingUp,
  Warehouse,
} from "lucide-react";
import {
  reportsApi,
  type ApiExecutiveReport,
  type ApiInventoryReport,
} from "@/lib/api";

export default function AdminReportsPage() {
  const [days, setDays] = useState(30);
  const [executive, setExecutive] = useState<ApiExecutiveReport | null>(null);
  const [inventory, setInventory] = useState<ApiInventoryReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadReports = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [execRes, invRes] = await Promise.all([
        reportsApi.getExecutive(days),
        reportsApi.getInventory(),
      ]);
      setExecutive(execRes.data);
      setInventory(invRes.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load reports.");
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    void loadReports();
  }, [loadReports]);

  const handleExport = async (ledger: "inventory" | "refunds") => {
    try {
      const csv = await reportsApi.downloadLedgerCsv(ledger);
      const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${ledger}-ledger.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to export ${ledger} CSV.`);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            Administrative Reports & Reconciliation
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Net revenue after settled refunds, payment mix, and multi-warehouse valuation
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="px-3.5 py-2 bg-white border border-slate-200 rounded-xl text-sm text-slate-700"
          >
            <option value={7}>Last 7 Days</option>
            <option value={30}>Last 30 Days</option>
            <option value={90}>Last 90 Days</option>
            <option value={365}>Last 365 Days</option>
          </select>
          <button
            type="button"
            onClick={() => void handleExport("inventory")}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-white border border-slate-200 rounded-xl text-xs font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer"
          >
            <Download size={14} />
            Inventory Ledger CSV
          </button>
          <button
            type="button"
            onClick={() => void handleExport("refunds")}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-white border border-slate-200 rounded-xl text-xs font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer"
          >
            <Download size={14} />
            Refund Ledger CSV
          </button>
          <button
            type="button"
            onClick={() => void loadReports()}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-slate-900 text-white rounded-xl text-xs font-semibold cursor-pointer"
          >
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
            Refresh
          </button>
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
            onClick={() => void loadReports()}
            className="text-xs font-semibold underline cursor-pointer"
          >
            Retry
          </button>
        </div>
      )}

      {loading && !executive ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-8 text-sm text-slate-500">
          Computing financial & inventory metrics...
        </div>
      ) : executive && inventory ? (
        <>
          {/* Financial Summary */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-white rounded-2xl border border-slate-200 p-5">
              <p className="text-xs font-medium text-slate-500">
                Gross Paid Revenue ({executive.days}d)
              </p>
              <p className="text-2xl font-bold text-slate-900 mt-1">
                ${Number(executive.gross_paid_revenue).toFixed(2)}
              </p>
              <p className="text-xs text-slate-500 mt-1">
                {executive.paid_orders_count} paid of {executive.total_orders} orders
              </p>
            </div>

            <div className="bg-white rounded-2xl border border-slate-200 p-5">
              <p className="text-xs font-medium text-slate-500">Settled Refunds</p>
              <p className="text-2xl font-bold text-rose-700 mt-1">
                -${Number(executive.settled_refunds_total).toFixed(2)}
              </p>
              <p className="text-xs text-amber-700 mt-1">
                Pending liability: ${Number(executive.pending_refund_liability).toFixed(2)}
              </p>
            </div>

            <div className="bg-white rounded-2xl border border-slate-200 p-5">
              <p className="text-xs font-medium text-slate-500">Net Revenue</p>
              <p className="text-2xl font-bold text-emerald-700 mt-1">
                ${Number(executive.net_revenue).toFixed(2)}
              </p>
              <p className="text-xs text-slate-500 mt-1">
                AOV: ${Number(executive.average_order_value).toFixed(2)}
              </p>
            </div>

            <div className="bg-white rounded-2xl border border-slate-200 p-5">
              <p className="text-xs font-medium text-slate-500">Inventory Valuation</p>
              <p className="text-2xl font-bold text-slate-900 mt-1">
                ${Number(inventory.total_retail_valuation).toFixed(2)}
              </p>
              <p className="text-xs text-slate-500 mt-1">
                {inventory.total_on_hand_units} units across {inventory.total_warehouses} warehouses
              </p>
            </div>
          </div>

          {/* Payment Method Mix + Inventory Ledger Check */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white rounded-2xl border border-slate-200 p-6">
              <div className="flex items-center gap-2 mb-4">
                <TrendingUp size={18} className="text-blue-600" />
                <h2 className="font-bold text-slate-900">Payment Method Breakdown</h2>
              </div>
              {executive.payment_method_breakdown.length === 0 ? (
                <p className="text-sm text-slate-500">No orders in selected period.</p>
              ) : (
                <div className="space-y-2.5">
                  {executive.payment_method_breakdown.map((pm) => (
                    <div
                      key={pm.payment_method}
                      className="flex items-center justify-between p-3 bg-slate-50 rounded-xl text-sm"
                    >
                      <div>
                        <span className="font-semibold text-slate-900">
                          {pm.payment_method}
                        </span>
                        <span className="text-xs text-slate-500 block">
                          {pm.orders_count} order{pm.orders_count === 1 ? "" : "s"}
                        </span>
                      </div>
                      <span className="font-bold text-slate-900">
                        ${Number(pm.gross_amount).toFixed(2)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="bg-white rounded-2xl border border-slate-200 p-6 space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Warehouse size={18} className="text-blue-600" />
                  <h2 className="font-bold text-slate-900">
                    Inventory Integrity & Procurement
                  </h2>
                </div>
                {inventory.ledger_balanced ? (
                  <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-full">
                    <CheckCircle2 size={14} />
                    Ledger Balanced
                  </span>
                ) : (
                  <span className="text-xs font-semibold text-rose-700">Ledger Mismatch</span>
                )}
              </div>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="p-3 bg-slate-50 rounded-xl">
                  <p className="text-xs text-slate-500">Committed PO Spend</p>
                  <p className="font-bold text-slate-900 mt-0.5">
                    ${Number(inventory.total_po_cost_committed).toFixed(2)}
                  </p>
                </div>
                <div className="p-3 bg-slate-50 rounded-xl">
                  <p className="text-xs text-slate-500">Open POs / In-Transit Transfers</p>
                  <p className="font-bold text-slate-900 mt-0.5">
                    {inventory.open_purchase_orders_count} POs /{" "}
                    {inventory.in_transit_transfers_count} Transfers
                  </p>
                </div>
                <div className="p-3 bg-slate-50 rounded-xl col-span-2">
                  <p className="text-xs text-slate-500">Double-Entry Quantity Totals</p>
                  <p className="font-bold text-slate-900 mt-0.5">
                    Total Debits: {inventory.ledger_total_debits} units | Total Credits:{" "}
                    {inventory.ledger_total_credits} units
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Warehouse Valuation Table */}
          <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-100">
              <h2 className="font-bold text-slate-900">Warehouse Valuation Breakdown</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-500 uppercase">
                  <tr>
                    <th className="px-5 py-3.5">Warehouse</th>
                    <th className="px-5 py-3.5 text-right">SKUs</th>
                    <th className="px-5 py-3.5 text-right">On-Hand Units</th>
                    <th className="px-5 py-3.5 text-right">Low Stock SKUs</th>
                    <th className="px-5 py-3.5 text-right">Out of Stock</th>
                    <th className="px-5 py-3.5 text-right">Retail Valuation</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {inventory.warehouses.map((w) => (
                    <tr key={w.warehouse_id}>
                      <td className="px-5 py-3.5">
                        <span className="font-mono text-xs font-semibold text-slate-900">
                          {w.warehouse_code}
                        </span>{" "}
                        {w.warehouse_name}
                      </td>
                      <td className="px-5 py-3.5 text-right">{w.sku_count}</td>
                      <td className="px-5 py-3.5 text-right font-semibold">{w.total_units}</td>
                      <td className="px-5 py-3.5 text-right text-amber-700">{w.low_stock_skus}</td>
                      <td className="px-5 py-3.5 text-right text-rose-700">
                        {w.out_of_stock_skus}
                      </td>
                      <td className="px-5 py-3.5 text-right font-bold text-slate-900">
                        ${Number(w.retail_valuation).toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Daily Trend */}
          <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-100">
              <h2 className="font-bold text-slate-900">Daily Revenue vs Refunds Trend</h2>
            </div>
            {executive.daily_trend.length === 0 ? (
              <div className="p-6 text-sm text-slate-500">
                No order activity in selected date range.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-500 uppercase">
                    <tr>
                      <th className="px-5 py-3">Date</th>
                      <th className="px-5 py-3 text-right">Orders</th>
                      <th className="px-5 py-3 text-right">Gross Paid Revenue</th>
                      <th className="px-5 py-3 text-right">Settled Refunds</th>
                      <th className="px-5 py-3 text-right">Net Revenue</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {executive.daily_trend.map((pt) => (
                      <tr key={pt.date}>
                        <td className="px-5 py-3 font-mono text-xs text-slate-800">{pt.date}</td>
                        <td className="px-5 py-3 text-right">{pt.orders_count}</td>
                        <td className="px-5 py-3 text-right font-medium">
                          ${Number(pt.gross_revenue).toFixed(2)}
                        </td>
                        <td className="px-5 py-3 text-right text-rose-700">
                          -${Number(pt.refunds_total).toFixed(2)}
                        </td>
                        <td className="px-5 py-3 text-right font-bold text-emerald-700">
                          ${Number(pt.net_revenue).toFixed(2)}
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
