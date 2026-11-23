"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { AlertCircle, ArrowLeft, BookOpen, CheckCircle2, Warehouse } from "lucide-react";
import {
  inventoryApi,
  productsApi,
  type ApiInventoryJournalEntry,
  type ApiProduct,
  type ApiWarehouse,
  type ApiWarehouseStock,
} from "@/lib/api";

export default function ProductInventoryAuditPage() {
  const params = useParams<{ id: string }>();
  const productId = Number(params?.id);

  const [product, setProduct] = useState<ApiProduct | null>(null);
  const [warehouses, setWarehouses] = useState<ApiWarehouse[]>([]);
  const [stocks, setStocks] = useState<ApiWarehouseStock[]>([]);
  const [ledger, setLedger] = useState<ApiInventoryJournalEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);

  const [adjForm, setAdjForm] = useState({
    warehouse_id: "",
    quantity_delta: "",
    unit_cost: "0.00",
    reason: "",
  });
  const [submitting, setSubmitting] = useState(false);

  const loadData = useCallback(async () => {
    if (!Number.isFinite(productId) || productId <= 0) return;
    setLoading(true);
    setError(null);
    try {
      const [prodRes, whRes, stRes, ledRes] = await Promise.all([
        productsApi.get(productId),
        inventoryApi.getWarehouses(),
        inventoryApi.getProductStocks(productId),
        inventoryApi.getLedger({ product_id: productId, limit: 50 }),
      ]);
      setProduct(prodRes.data);
      const whList: ApiWarehouse[] = whRes.data || [];
      setWarehouses(whList);
      setStocks(stRes.data || []);
      setLedger(ledRes.data?.entries || []);
      if (whList.length > 0 && !adjForm.warehouse_id) {
        const defWh = whList.find((w: ApiWarehouse) => w.is_default) || whList[0];
        setAdjForm((prev) => ({ ...prev, warehouse_id: String(defWh.id) }));
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load product inventory."
      );
    } finally {
      setLoading(false);
    }
  }, [adjForm.warehouse_id, productId]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const handleAdjust = async (e: React.FormEvent) => {
    e.preventDefault();
    const delta = parseInt(adjForm.quantity_delta, 10);
    if (Number.isNaN(delta) || delta === 0) {
      setError("Enter a non-zero integer adjustment (+/-).");
      return;
    }
    setSubmitting(true);
    setError(null);
    setFeedback(null);
    try {
      const res = await inventoryApi.createAdjustment({
        product_id: productId,
        warehouse_id: adjForm.warehouse_id ? Number(adjForm.warehouse_id) : undefined,
        quantity_delta: delta,
        unit_cost: parseFloat(adjForm.unit_cost) || 0,
        reason: adjForm.reason.trim(),
      });
      setFeedback(`Posted adjustment ${res.data.entry_number} cleanly.`);
      setAdjForm((prev) => ({ ...prev, quantity_delta: "", reason: "" }));
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to post adjustment.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6 max-w-5xl">
      <Link
        href="/admin/inventory"
        className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900"
      >
        <ArrowLeft size={16} />
        Back to Multi-Warehouse Inventory
      </Link>

      {loading ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-8 text-sm text-slate-500">
          Loading SKU warehouse stocks & ledger...
        </div>
      ) : error && !product ? (
        <div className="bg-rose-50 border border-rose-200 rounded-2xl p-6 text-rose-700 text-sm flex items-center gap-2">
          <AlertCircle size={18} />
          <span>{error}</span>
        </div>
      ) : product ? (
        <>
          <div className="bg-white rounded-2xl border border-slate-200 p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <p className="text-xs font-semibold text-blue-600 uppercase">
                SKU #{product.id}
              </p>
              <h1 className="text-2xl font-bold text-slate-900 mt-0.5">{product.name}</h1>
              <p className="text-xs text-slate-500 mt-1">
                Sell price: ${Number(product.price).toFixed(2)} | Category:{" "}
                {product.category?.name || "Uncategorized"}
              </p>
            </div>
            <div className="text-right">
              <p className="text-xs text-slate-500">Aggregate On-Hand Stock</p>
              <p className="text-3xl font-bold text-slate-900">{product.stock}</p>
            </div>
          </div>

          {/* Per-Warehouse Breakdown */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {stocks.map((st) => (
              <div
                key={st.id}
                className="bg-white rounded-2xl border border-slate-200 p-5 space-y-1.5"
              >
                <div className="flex items-center gap-2 text-xs font-semibold text-blue-700">
                  <Warehouse size={14} />
                  <span>{st.warehouse_code}</span>
                </div>
                <p className="font-bold text-slate-900">{st.warehouse_name}</p>
                <div className="flex justify-between pt-2 text-sm">
                  <span className="text-slate-500">On Hand:</span>
                  <span className="font-bold text-slate-900">{st.quantity}</span>
                </div>
              </div>
            ))}
          </div>

          {/* Warehouse-Scoped Adjustment */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 space-y-4">
            <h2 className="font-bold text-slate-900">
              Record Immutable Stock Adjustment
            </h2>
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

            <form onSubmit={handleAdjust} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
              <select
                required
                value={adjForm.warehouse_id}
                onChange={(e) => setAdjForm({ ...adjForm, warehouse_id: e.target.value })}
                className="px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm"
              >
                {warehouses.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.code} — {w.name}
                  </option>
                ))}
              </select>
              <input
                type="number"
                required
                value={adjForm.quantity_delta}
                onChange={(e) => setAdjForm({ ...adjForm, quantity_delta: e.target.value })}
                placeholder="Delta (+5 or -3)"
                className="px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm"
              />
              <input
                type="number"
                step="0.01"
                min={0}
                value={adjForm.unit_cost}
                onChange={(e) => setAdjForm({ ...adjForm, unit_cost: e.target.value })}
                placeholder="Unit cost ($)"
                className="px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm"
              />
              <input
                type="text"
                required
                minLength={3}
                value={adjForm.reason}
                onChange={(e) => setAdjForm({ ...adjForm, reason: e.target.value })}
                placeholder="Cycle count / shrinkage reason"
                className="px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm"
              />
              <button
                type="submit"
                disabled={submitting}
                className="px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-semibold cursor-pointer disabled:opacity-60"
              >
                {submitting ? "Posting..." : "Post Adjustment"}
              </button>
            </form>
          </div>

          {/* SKU Ledger History */}
          <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center gap-2">
              <BookOpen size={17} className="text-blue-600" />
              <h2 className="font-bold text-slate-900">SKU Journal History</h2>
            </div>
            {ledger.length === 0 ? (
              <div className="p-6 text-sm text-slate-500">
                No ledger entries recorded for this SKU yet.
              </div>
            ) : (
              <div className="divide-y divide-slate-100">
                {ledger.map((entry) => (
                  <div key={entry.id} className="p-5 space-y-2">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-mono font-bold text-slate-900">
                        {entry.entry_number} — {entry.entry_type}
                      </span>
                      <span className="text-slate-500">
                        {new Date(entry.created_at).toLocaleString()}
                      </span>
                    </div>
                    {entry.reason && (
                      <p className="text-xs text-slate-600">{entry.reason}</p>
                    )}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1">
                      {entry.lines.map((line) => (
                        <div
                          key={line.id}
                          className="p-2.5 rounded-xl bg-slate-50 border border-slate-200/70 text-xs flex items-center justify-between"
                        >
                          <div>
                            <span className="font-mono text-slate-800">{line.account_type}</span>
                            <span className="block text-[11px] text-slate-500">
                              {line.warehouse_name || "Offset Account"}
                            </span>
                          </div>
                          <div className="text-right font-semibold">
                            {line.debit_qty > 0 && (
                              <span className="text-emerald-700">Dr {line.debit_qty}</span>
                            )}
                            {line.credit_qty > 0 && (
                              <span className="text-rose-700">Cr {line.credit_qty}</span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      ) : null}
    </div>
  );
}
