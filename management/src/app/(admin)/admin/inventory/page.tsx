"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  ArrowLeftRight,
  BookOpen,
  CheckCircle2,
  ClipboardList,
  Download,
  Package,
  Plus,
  RefreshCw,
  Search,
  Warehouse as WarehouseIcon,
} from "lucide-react";
import {
  inventoryApi,
  productsApi,
  reportsApi,
  suppliersApi,
  type ApiInventoryJournalEntry,
  type ApiInventoryLedgerTrialBalance,
  type ApiProduct,
  type ApiPurchaseOrder,
  type ApiSupplier,
  type ApiWarehouse,
  type ApiWarehouseStock,
  type ApiWarehouseTransfer,
} from "@/lib/api";

type InventoryTab = "stocks" | "warehouses" | "purchase_orders" | "transfers" | "ledger";

export default function InventoryPage() {
  const [activeTab, setActiveTab] = useState<InventoryTab>("stocks");
  const [warehouses, setWarehouses] = useState<ApiWarehouse[]>([]);
  const [stocks, setStocks] = useState<ApiWarehouseStock[]>([]);
  const [products, setProducts] = useState<ApiProduct[]>([]);
  const [suppliers, setSuppliers] = useState<ApiSupplier[]>([]);
  const [purchaseOrders, setPurchaseOrders] = useState<ApiPurchaseOrder[]>([]);
  const [transfers, setTransfers] = useState<ApiWarehouseTransfer[]>([]);
  const [ledgerEntries, setLedgerEntries] = useState<ApiInventoryJournalEntry[]>([]);
  const [trialBalance, setTrialBalance] = useState<ApiInventoryLedgerTrialBalance | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);

  const [warehouseFilter, setWarehouseFilter] = useState<string>("");
  const [ledgerTypeFilter, setLedgerTypeFilter] = useState<string>("");
  const [search, setSearch] = useState("");

  // Stock adjustment form
  const [adjForm, setAdjForm] = useState({
    product_id: "",
    warehouse_id: "",
    quantity_delta: "",
    unit_cost: "0.00",
    reason: "",
  });
  const [submittingAdj, setSubmittingAdj] = useState(false);

  // Warehouse form
  const [whForm, setWhForm] = useState({
    code: "",
    name: "",
    location: "",
    contact_name: "",
    contact_phone: "",
    is_default: false,
  });
  const [submittingWh, setSubmittingWh] = useState(false);

  // Purchase Order form
  const [poForm, setPoForm] = useState({
    supplier_id: "",
    warehouse_id: "",
    product_id: "",
    quantity_ordered: "10",
    unit_cost: "10.00",
    notes: "",
  });
  const [submittingPo, setSubmittingPo] = useState(false);

  // Transfer form
  const [transferForm, setTransferForm] = useState({
    source_warehouse_id: "",
    destination_warehouse_id: "",
    product_id: "",
    quantity: "1",
    notes: "",
  });
  const [submittingTransfer, setSubmittingTransfer] = useState(false);

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [whRes, stRes, prRes, supRes, poRes, trRes, ledRes] = await Promise.all([
        inventoryApi.getWarehouses(),
        inventoryApi.getStocks(
          warehouseFilter ? { warehouse_id: Number(warehouseFilter) } : undefined
        ),
        productsApi.list({ limit: 100 }),
        suppliersApi.getAll(),
        inventoryApi.getPurchaseOrders(),
        inventoryApi.getTransfers(),
        inventoryApi.getLedger({
          warehouse_id: warehouseFilter ? Number(warehouseFilter) : undefined,
          entry_type: ledgerTypeFilter || undefined,
          limit: 50,
        }),
      ]);

      const whList: ApiWarehouse[] = whRes.data || [];
      setWarehouses(whList);
      setStocks(stRes.data || []);
      setProducts(prRes.data?.items || []);
      setSuppliers(supRes.data || []);
      setPurchaseOrders(poRes.data || []);
      setTransfers(trRes.data || []);
      setLedgerEntries(ledRes.data?.entries || []);
      setTrialBalance(ledRes.data?.trial_balance || null);

      if (whList.length > 0 && !adjForm.warehouse_id) {
        const defWh = whList.find((w: ApiWarehouse) => w.is_default) || whList[0];
        setAdjForm((prev) => ({ ...prev, warehouse_id: String(defWh.id) }));
        setPoForm((prev) => ({ ...prev, warehouse_id: String(defWh.id) }));
        setTransferForm((prev) => ({ ...prev, source_warehouse_id: String(defWh.id) }));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load inventory data.");
    } finally {
      setLoading(false);
    }
  }, [adjForm.warehouse_id, ledgerTypeFilter, warehouseFilter]);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  const filteredStocks = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return stocks;
    return stocks.filter(
      (s) =>
        s.product_name.toLowerCase().includes(q) ||
        s.warehouse_name.toLowerCase().includes(q) ||
        s.warehouse_code.toLowerCase().includes(q)
    );
  }, [search, stocks]);

  const totalOnHand = useMemo(
    () => stocks.reduce((sum, s) => sum + Number(s.quantity || 0), 0),
    [stocks]
  );

  const handleAdjustmentSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const delta = parseInt(adjForm.quantity_delta, 10);
    if (!adjForm.product_id || Number.isNaN(delta) || delta === 0) {
      setError("Select a product and enter a non-zero quantity delta.");
      return;
    }
    setSubmittingAdj(true);
    setError(null);
    setFeedback(null);
    try {
      const res = await inventoryApi.createAdjustment({
        product_id: Number(adjForm.product_id),
        warehouse_id: adjForm.warehouse_id ? Number(adjForm.warehouse_id) : undefined,
        quantity_delta: delta,
        unit_cost: parseFloat(adjForm.unit_cost) || 0,
        reason: adjForm.reason.trim(),
      });
      setFeedback(`Posted double-entry adjustment ${res.data.entry_number}.`);
      setAdjForm((prev) => ({ ...prev, quantity_delta: "", reason: "" }));
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Stock adjustment failed.");
    } finally {
      setSubmittingAdj(false);
    }
  };

  const handleCreateWarehouse = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmittingWh(true);
    setError(null);
    setFeedback(null);
    try {
      const res = await inventoryApi.createWarehouse({
        code: whForm.code.trim().toUpperCase(),
        name: whForm.name.trim(),
        location: whForm.location.trim() || undefined,
        contact_name: whForm.contact_name.trim() || undefined,
        contact_phone: whForm.contact_phone.trim() || undefined,
        is_default: whForm.is_default,
      });
      setFeedback(`Created warehouse ${res.data.code} (${res.data.name}).`);
      setWhForm({
        code: "",
        name: "",
        location: "",
        contact_name: "",
        contact_phone: "",
        is_default: false,
      });
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create warehouse.");
    } finally {
      setSubmittingWh(false);
    }
  };

  const handleCreatePo = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmittingPo(true);
    setError(null);
    setFeedback(null);
    try {
      const res = await inventoryApi.createPurchaseOrder({
        supplier_id: Number(poForm.supplier_id),
        warehouse_id: Number(poForm.warehouse_id),
        notes: poForm.notes.trim() || undefined,
        items: [
          {
            product_id: Number(poForm.product_id),
            quantity_ordered: parseInt(poForm.quantity_ordered, 10) || 1,
            unit_cost: parseFloat(poForm.unit_cost) || 0,
          },
        ],
      });
      setFeedback(`Created Purchase Order ${res.data.po_number}.`);
      setPoForm((prev) => ({ ...prev, notes: "" }));
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create Purchase Order.");
    } finally {
      setSubmittingPo(false);
    }
  };

  const handlePoAction = async (
    poId: number,
    action: "order" | "receive" | "cancel"
  ) => {
    setError(null);
    setFeedback(null);
    try {
      if (action === "order") await inventoryApi.orderPurchaseOrder(poId);
      else if (action === "receive") await inventoryApi.receivePurchaseOrder(poId);
      else await inventoryApi.cancelPurchaseOrder(poId);
      setFeedback(`Purchase order #${poId} updated (${action}).`);
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : `Purchase order ${action} failed.`);
    }
  };

  const handleCreateTransfer = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmittingTransfer(true);
    setError(null);
    setFeedback(null);
    try {
      const res = await inventoryApi.createTransfer({
        source_warehouse_id: Number(transferForm.source_warehouse_id),
        destination_warehouse_id: Number(transferForm.destination_warehouse_id),
        notes: transferForm.notes.trim() || undefined,
        items: [
          {
            product_id: Number(transferForm.product_id),
            quantity: parseInt(transferForm.quantity, 10) || 1,
          },
        ],
      });
      setFeedback(`Created warehouse transfer ${res.data.transfer_number}.`);
      setTransferForm((prev) => ({ ...prev, notes: "" }));
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create warehouse transfer.");
    } finally {
      setSubmittingTransfer(false);
    }
  };

  const handleTransferAction = async (
    transferId: number,
    action: "dispatch" | "complete" | "cancel"
  ) => {
    setError(null);
    setFeedback(null);
    try {
      if (action === "dispatch") await inventoryApi.dispatchTransfer(transferId);
      else if (action === "complete") await inventoryApi.completeTransfer(transferId);
      else await inventoryApi.cancelTransfer(transferId);
      setFeedback(`Transfer #${transferId} updated (${action}).`);
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : `Transfer ${action} failed.`);
    }
  };

  const handleExportCsv = async () => {
    try {
      const csv = await reportsApi.downloadLedgerCsv("inventory");
      const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "inventory-ledger.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to export inventory ledger CSV.");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            Multi-Warehouse Inventory & Ledger
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Immutable double-entry inventory journal, Purchase Orders, and Warehouse Transfers
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => void handleExportCsv()}
            className="inline-flex items-center gap-2 px-3.5 py-2 bg-white border border-slate-200 rounded-xl text-sm font-medium text-slate-700 hover:bg-slate-50 cursor-pointer"
          >
            <Download size={15} />
            Export Ledger CSV
          </button>
          <button
            type="button"
            onClick={() => void loadAll()}
            className="inline-flex items-center gap-2 px-3.5 py-2 bg-slate-900 text-white rounded-xl text-sm font-medium hover:bg-slate-800 cursor-pointer"
          >
            <RefreshCw size={15} className={loading ? "animate-spin" : ""} />
            Refresh
          </button>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-2xl border border-slate-200 p-5">
          <p className="text-xs font-medium text-slate-500">Warehouses</p>
          <p className="text-2xl font-bold text-slate-900 mt-1">{warehouses.length}</p>
        </div>
        <div className="bg-white rounded-2xl border border-slate-200 p-5">
          <p className="text-xs font-medium text-slate-500">Total On-Hand Units</p>
          <p className="text-2xl font-bold text-slate-900 mt-1">{totalOnHand}</p>
        </div>
        <div className="bg-white rounded-2xl border border-slate-200 p-5">
          <p className="text-xs font-medium text-slate-500">Open Purchase Orders</p>
          <p className="text-2xl font-bold text-blue-600 mt-1">
            {
              purchaseOrders.filter((p) =>
                ["draft", "ordered", "partially_received"].includes(p.status)
              ).length
            }
          </p>
        </div>
        <div className="bg-white rounded-2xl border border-slate-200 p-5">
          <p className="text-xs font-medium text-slate-500">Ledger Trial Balance</p>
          <p className="text-lg font-bold mt-1 flex items-center gap-1.5">
            {trialBalance?.balanced ? (
              <span className="text-emerald-700 inline-flex items-center gap-1.5">
                <CheckCircle2 size={18} />
                Balanced ({trialBalance.total_debits} Dr / {trialBalance.total_credits} Cr)
              </span>
            ) : (
              <span className="text-rose-700">Check Trial Balance</span>
            )}
          </p>
        </div>
      </div>

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
            onClick={() => void loadAll()}
            className="text-xs font-semibold underline cursor-pointer"
          >
            Retry
          </button>
        </div>
      )}

      {/* Tabs */}
      <div className="flex flex-wrap gap-2 bg-white p-1.5 rounded-2xl border border-slate-200">
        {(
          [
            { id: "stocks", label: "Warehouse Stocks & Adjustments", icon: Package },
            { id: "warehouses", label: "Warehouses", icon: WarehouseIcon },
            { id: "purchase_orders", label: "Purchase Orders", icon: ClipboardList },
            { id: "transfers", label: "Warehouse Transfers", icon: ArrowLeftRight },
            { id: "ledger", label: "Double-Entry Ledger", icon: BookOpen },
          ] as const
        ).map((t) => {
          const Icon = t.icon;
          return (
            <button
              key={t.id}
              type="button"
              onClick={() => setActiveTab(t.id)}
              className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition cursor-pointer ${
                activeTab === t.id
                  ? "bg-blue-600 text-white"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              <Icon size={15} />
              {t.label}
            </button>
          );
        })}
      </div>

      {/* Tab 1: Stocks & Adjustments */}
      {activeTab === "stocks" && (
        <div className="space-y-6">
          <div className="bg-white rounded-2xl border border-slate-200 p-5">
            <h2 className="text-sm font-bold text-slate-900 mb-3">
              Post Warehouse Stock Adjustment (Creates Immutable Journal Entry)
            </h2>
            <form
              onSubmit={handleAdjustmentSubmit}
              className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-3"
            >
              <select
                required
                value={adjForm.warehouse_id}
                onChange={(e) => setAdjForm({ ...adjForm, warehouse_id: e.target.value })}
                className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm"
              >
                <option value="">Select Warehouse</option>
                {warehouses.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.code} — {w.name}
                  </option>
                ))}
              </select>
              <select
                required
                value={adjForm.product_id}
                onChange={(e) => setAdjForm({ ...adjForm, product_id: e.target.value })}
                className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm lg:col-span-2"
              >
                <option value="">Select Product</option>
                {products.map((p) => (
                  <option key={p.id} value={p.id}>
                    #{p.id} — {p.name} (Stock: {p.stock})
                  </option>
                ))}
              </select>
              <input
                type="number"
                required
                value={adjForm.quantity_delta}
                onChange={(e) => setAdjForm({ ...adjForm, quantity_delta: e.target.value })}
                placeholder="Delta (+10 / -2)"
                className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm"
              />
              <input
                type="text"
                required
                minLength={3}
                value={adjForm.reason}
                onChange={(e) => setAdjForm({ ...adjForm, reason: e.target.value })}
                placeholder="Audit reason (required)"
                className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm"
              />
              <button
                type="submit"
                disabled={submittingAdj}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-semibold disabled:opacity-50 cursor-pointer"
              >
                {submittingAdj ? "Posting..." : "Post Adjustment"}
              </button>
            </form>
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 p-4 flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Search size={16} className="absolute left-3.5 top-3 text-slate-400" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Filter by product or warehouse..."
                className="w-full pl-10 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm"
              />
            </div>
            <select
              value={warehouseFilter}
              onChange={(e) => setWarehouseFilter(e.target.value)}
              className="px-3.5 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm"
            >
              <option value="">All Warehouses</option>
              {warehouses.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.code} — {w.name}
                </option>
              ))}
            </select>
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
            {filteredStocks.length === 0 ? (
              <div className="p-8 text-center text-sm text-slate-500">
                No warehouse stock records found.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-500 uppercase">
                    <tr>
                      <th className="px-5 py-3.5">Warehouse</th>
                      <th className="px-5 py-3.5">Product</th>
                      <th className="px-5 py-3.5 text-right">On Hand</th>
                      <th className="px-5 py-3.5 text-right">Reserved</th>
                      <th className="px-5 py-3.5 text-right">Retail Value</th>
                      <th className="px-5 py-3.5 text-right">Ledger</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {filteredStocks.map((row) => (
                      <tr key={row.id} className="hover:bg-slate-50/70">
                        <td className="px-5 py-3.5">
                          <span className="font-mono text-xs font-semibold text-slate-900">
                            {row.warehouse_code}
                          </span>{" "}
                          <span className="text-slate-600">{row.warehouse_name}</span>
                        </td>
                        <td className="px-5 py-3.5 font-medium text-slate-900">
                          <Link
                            href={`/admin/inventory/${row.product_id}`}
                            className="text-blue-600 hover:underline"
                          >
                            {row.product_name}
                          </Link>
                        </td>
                        <td className="px-5 py-3.5 text-right font-bold text-slate-900">
                          {row.quantity}
                        </td>
                        <td className="px-5 py-3.5 text-right text-slate-600">
                          {row.reserved_quantity}
                        </td>
                        <td className="px-5 py-3.5 text-right font-medium text-slate-900">
                          ${(Number(row.product_price) * row.quantity).toFixed(2)}
                        </td>
                        <td className="px-5 py-3.5 text-right">
                          <Link
                            href={`/admin/inventory/${row.product_id}`}
                            className="text-xs font-semibold text-blue-600 hover:underline"
                          >
                            Product Audit →
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
      )}

      {/* Tab 2: Warehouses */}
      {activeTab === "warehouses" && (
        <div className="space-y-6">
          <div className="bg-white rounded-2xl border border-slate-200 p-5">
            <h2 className="text-sm font-bold text-slate-900 mb-3">Create Warehouse Location</h2>
            <form
              onSubmit={handleCreateWarehouse}
              className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-3"
            >
              <input
                type="text"
                required
                minLength={2}
                value={whForm.code}
                onChange={(e) => setWhForm({ ...whForm, code: e.target.value })}
                placeholder="Code (e.g. WH-EAST)"
                className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm font-mono"
              />
              <input
                type="text"
                required
                minLength={2}
                value={whForm.name}
                onChange={(e) => setWhForm({ ...whForm, name: e.target.value })}
                placeholder="Warehouse Name"
                className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm"
              />
              <input
                type="text"
                value={whForm.location}
                onChange={(e) => setWhForm({ ...whForm, location: e.target.value })}
                placeholder="City / Zone"
                className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm"
              />
              <input
                type="text"
                value={whForm.contact_name}
                onChange={(e) => setWhForm({ ...whForm, contact_name: e.target.value })}
                placeholder="Manager Name"
                className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm"
              />
              <label className="flex items-center gap-2 text-xs font-medium text-slate-700 px-2">
                <input
                  type="checkbox"
                  checked={whForm.is_default}
                  onChange={(e) => setWhForm({ ...whForm, is_default: e.target.checked })}
                />
                Default Fulfilment Hub
              </label>
              <button
                type="submit"
                disabled={submittingWh}
                className="inline-flex items-center justify-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-semibold cursor-pointer"
              >
                <Plus size={15} />
                {submittingWh ? "Creating..." : "Add Warehouse"}
              </button>
            </form>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {warehouses.map((w) => (
              <div key={w.id} className="bg-white rounded-2xl border border-slate-200 p-5 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-bold text-blue-700 bg-blue-50 px-2.5 py-0.5 rounded-full">
                    {w.code}
                  </span>
                  {w.is_default && (
                    <span className="text-[11px] font-semibold bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded-full">
                      Default
                    </span>
                  )}
                </div>
                <h3 className="font-bold text-slate-900">{w.name}</h3>
                <p className="text-xs text-slate-500">{w.location || "No location specified"}</p>
                <div className="pt-2 border-t border-slate-100 flex justify-between text-xs text-slate-600">
                  <span>{w.sku_count} SKUs</span>
                  <span className="font-bold text-slate-900">{w.total_units} units</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 3: Purchase Orders */}
      {activeTab === "purchase_orders" && (
        <div className="space-y-6">
          <div className="bg-white rounded-2xl border border-slate-200 p-5">
            <h2 className="text-sm font-bold text-slate-900 mb-3">
              Create Supplier Purchase Order
            </h2>
            <form
              onSubmit={handleCreatePo}
              className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-3"
            >
              <select
                required
                value={poForm.supplier_id}
                onChange={(e) => setPoForm({ ...poForm, supplier_id: e.target.value })}
                className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm"
              >
                <option value="">Select Supplier</option>
                {suppliers.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.code} — {s.name}
                  </option>
                ))}
              </select>
              <select
                required
                value={poForm.warehouse_id}
                onChange={(e) => setPoForm({ ...poForm, warehouse_id: e.target.value })}
                className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm"
              >
                <option value="">Destination Warehouse</option>
                {warehouses.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.code} — {w.name}
                  </option>
                ))}
              </select>
              <select
                required
                value={poForm.product_id}
                onChange={(e) => setPoForm({ ...poForm, product_id: e.target.value })}
                className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm"
              >
                <option value="">Select Product</option>
                {products.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
              <input
                type="number"
                required
                min={1}
                value={poForm.quantity_ordered}
                onChange={(e) => setPoForm({ ...poForm, quantity_ordered: e.target.value })}
                placeholder="Qty"
                className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm"
              />
              <input
                type="number"
                required
                min={0}
                step="0.01"
                value={poForm.unit_cost}
                onChange={(e) => setPoForm({ ...poForm, unit_cost: e.target.value })}
                placeholder="Unit Cost ($)"
                className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm"
              />
              <button
                type="submit"
                disabled={submittingPo}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-semibold cursor-pointer"
              >
                {submittingPo ? "Creating PO..." : "Create PO"}
              </button>
            </form>
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
            {purchaseOrders.length === 0 ? (
              <div className="p-8 text-center text-sm text-slate-500">
                No purchase orders created yet.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-500 uppercase">
                    <tr>
                      <th className="px-5 py-3.5">PO #</th>
                      <th className="px-5 py-3.5">Supplier</th>
                      <th className="px-5 py-3.5">Warehouse</th>
                      <th className="px-5 py-3.5">Items</th>
                      <th className="px-5 py-3.5 text-right">Total Cost</th>
                      <th className="px-5 py-3.5">Status</th>
                      <th className="px-5 py-3.5 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {purchaseOrders.map((po) => (
                      <tr key={po.id}>
                        <td className="px-5 py-3.5 font-mono text-xs font-semibold text-slate-900">
                          {po.po_number}
                        </td>
                        <td className="px-5 py-3.5 text-slate-800">
                          {po.supplier_name || `Supplier #${po.supplier_id}`}
                        </td>
                        <td className="px-5 py-3.5 text-slate-600">
                          {po.warehouse_name || `Warehouse #${po.warehouse_id}`}
                        </td>
                        <td className="px-5 py-3.5 text-xs text-slate-600">
                          {po.items.map((it) => `${it.product_name} (${it.quantity_received}/${it.quantity_ordered})`).join(", ")}
                        </td>
                        <td className="px-5 py-3.5 text-right font-semibold text-slate-900">
                          ${Number(po.total_cost).toFixed(2)}
                        </td>
                        <td className="px-5 py-3.5 capitalize text-slate-700">
                          {po.status.replaceAll("_", " ")}
                        </td>
                        <td className="px-5 py-3.5 text-right space-x-2 whitespace-nowrap">
                          {po.status === "draft" && (
                            <button
                              type="button"
                              onClick={() => void handlePoAction(po.id, "order")}
                              className="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 rounded-lg text-xs font-semibold text-slate-800 cursor-pointer"
                            >
                              Mark Ordered
                            </button>
                          )}
                          {["draft", "ordered", "partially_received"].includes(po.status) && (
                            <>
                              <button
                                type="button"
                                onClick={() => void handlePoAction(po.id, "receive")}
                                className="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 rounded-lg text-xs font-semibold text-white cursor-pointer"
                              >
                                Receive Stock
                              </button>
                              <button
                                type="button"
                                onClick={() => void handlePoAction(po.id, "cancel")}
                                className="px-2.5 py-1 bg-rose-50 hover:bg-rose-100 rounded-lg text-xs font-semibold text-rose-700 cursor-pointer"
                              >
                                Cancel
                              </button>
                            </>
                          )}
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

      {/* Tab 4: Transfers */}
      {activeTab === "transfers" && (
        <div className="space-y-6">
          <div className="bg-white rounded-2xl border border-slate-200 p-5">
            <h2 className="text-sm font-bold text-slate-900 mb-3">
              Create Inter-Warehouse Transfer
            </h2>
            <form
              onSubmit={handleCreateTransfer}
              className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3"
            >
              <select
                required
                value={transferForm.source_warehouse_id}
                onChange={(e) =>
                  setTransferForm({ ...transferForm, source_warehouse_id: e.target.value })
                }
                className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm"
              >
                <option value="">Source Warehouse</option>
                {warehouses.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.code} — {w.name}
                  </option>
                ))}
              </select>
              <select
                required
                value={transferForm.destination_warehouse_id}
                onChange={(e) =>
                  setTransferForm({
                    ...transferForm,
                    destination_warehouse_id: e.target.value,
                  })
                }
                className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm"
              >
                <option value="">Destination Warehouse</option>
                {warehouses.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.code} — {w.name}
                  </option>
                ))}
              </select>
              <select
                required
                value={transferForm.product_id}
                onChange={(e) =>
                  setTransferForm({ ...transferForm, product_id: e.target.value })
                }
                className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm"
              >
                <option value="">Select Product</option>
                {products.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
              <input
                type="number"
                required
                min={1}
                value={transferForm.quantity}
                onChange={(e) =>
                  setTransferForm({ ...transferForm, quantity: e.target.value })
                }
                placeholder="Qty"
                className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm"
              />
              <button
                type="submit"
                disabled={submittingTransfer}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-semibold cursor-pointer"
              >
                {submittingTransfer ? "Creating..." : "Create Transfer"}
              </button>
            </form>
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
            {transfers.length === 0 ? (
              <div className="p-8 text-center text-sm text-slate-500">
                No warehouse transfers recorded yet.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-500 uppercase">
                    <tr>
                      <th className="px-5 py-3.5">Transfer #</th>
                      <th className="px-5 py-3.5">Route</th>
                      <th className="px-5 py-3.5">Items</th>
                      <th className="px-5 py-3.5">Status</th>
                      <th className="px-5 py-3.5 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {transfers.map((tr) => (
                      <tr key={tr.id}>
                        <td className="px-5 py-3.5 font-mono text-xs font-semibold text-slate-900">
                          {tr.transfer_number}
                        </td>
                        <td className="px-5 py-3.5 text-slate-800">
                          {tr.source_warehouse_name || `#${tr.source_warehouse_id}`} →{" "}
                          {tr.destination_warehouse_name || `#${tr.destination_warehouse_id}`}
                        </td>
                        <td className="px-5 py-3.5 text-xs text-slate-600">
                          {tr.items.map((it) => `${it.product_name} × ${it.quantity}`).join(", ")}
                        </td>
                        <td className="px-5 py-3.5 capitalize text-slate-700">
                          {tr.status.replaceAll("_", " ")}
                        </td>
                        <td className="px-5 py-3.5 text-right space-x-2 whitespace-nowrap">
                          {tr.status === "draft" && (
                            <button
                              type="button"
                              onClick={() => void handleTransferAction(tr.id, "dispatch")}
                              className="px-2.5 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold cursor-pointer"
                            >
                              Dispatch
                            </button>
                          )}
                          {tr.status === "in_transit" && (
                            <button
                              type="button"
                              onClick={() => void handleTransferAction(tr.id, "complete")}
                              className="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold cursor-pointer"
                            >
                              Complete Receipt
                            </button>
                          )}
                          {(tr.status === "draft" || tr.status === "in_transit") && (
                            <button
                              type="button"
                              onClick={() => void handleTransferAction(tr.id, "cancel")}
                              className="px-2.5 py-1 bg-rose-50 hover:bg-rose-100 text-rose-700 rounded-lg text-xs font-semibold cursor-pointer"
                            >
                              Cancel
                            </button>
                          )}
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

      {/* Tab 5: Immutable Double-Entry Ledger */}
      {activeTab === "ledger" && (
        <div className="space-y-4">
          <div className="bg-white rounded-2xl border border-slate-200 p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="text-sm">
              <span className="font-semibold text-slate-900">Trial Balance:</span>{" "}
              <span className="text-slate-600">
                Debits = {trialBalance?.total_debits ?? 0} units | Credits ={" "}
                {trialBalance?.total_credits ?? 0} units | Entries ={" "}
                {trialBalance?.total_entries ?? 0}
              </span>
            </div>
            <select
              value={ledgerTypeFilter}
              onChange={(e) => setLedgerTypeFilter(e.target.value)}
              className="px-3.5 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm"
            >
              <option value="">All Entry Types</option>
              <option value="opening_balance">Opening Balance</option>
              <option value="adjustment">Adjustment</option>
              <option value="purchase_receipt">Purchase Receipt</option>
              <option value="transfer_out">Transfer Dispatch</option>
              <option value="transfer_in">Transfer Receipt</option>
              <option value="transfer_cancel">Transfer Cancel</option>
              <option value="order_sale">Order Sale</option>
              <option value="pos_sale">POS Sale</option>
              <option value="order_cancellation">Order Cancellation</option>
              <option value="refund_restock">Refund Restock</option>
            </select>
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
            {ledgerEntries.length === 0 ? (
              <div className="p-8 text-center text-sm text-slate-500">
                No double-entry inventory journal postings recorded yet.
              </div>
            ) : (
              <div className="divide-y divide-slate-100">
                {ledgerEntries.map((entry) => (
                  <div key={entry.id} className="p-5 space-y-3">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                      <div>
                        <span className="font-mono text-xs font-bold text-slate-900">
                          {entry.entry_number}
                        </span>
                        <span className="ml-2 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-blue-50 text-blue-700 capitalize">
                          {entry.entry_type.replaceAll("_", " ")}
                        </span>
                        {entry.reason && (
                          <p className="text-xs text-slate-600 mt-1">{entry.reason}</p>
                        )}
                      </div>
                      <span className="text-xs text-slate-500">
                        {new Date(entry.created_at).toLocaleString()}
                      </span>
                    </div>

                    <div className="overflow-x-auto">
                      <table className="w-full text-xs text-left bg-slate-50 rounded-xl">
                        <thead className="text-slate-500 uppercase border-b border-slate-200">
                          <tr>
                            <th className="px-3 py-2">Product</th>
                            <th className="px-3 py-2">Warehouse</th>
                            <th className="px-3 py-2">Account</th>
                            <th className="px-3 py-2 text-right">Debit</th>
                            <th className="px-3 py-2 text-right">Credit</th>
                            <th className="px-3 py-2 text-right">Balance After</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-200/70">
                          {entry.lines.map((line) => (
                            <tr key={line.id}>
                              <td className="px-3 py-2 font-medium text-slate-900">
                                {line.product_name}
                              </td>
                              <td className="px-3 py-2 text-slate-600">
                                {line.warehouse_name || "Offset Account"}
                              </td>
                              <td className="px-3 py-2 font-mono text-slate-700">
                                {line.account_type}
                              </td>
                              <td className="px-3 py-2 text-right font-semibold text-emerald-700">
                                {line.debit_qty || "-"}
                              </td>
                              <td className="px-3 py-2 text-right font-semibold text-rose-700">
                                {line.credit_qty || "-"}
                              </td>
                              <td className="px-3 py-2 text-right text-slate-700">
                                {line.balance_after ?? "-"}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
