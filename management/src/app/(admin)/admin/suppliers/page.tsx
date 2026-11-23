"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  Building2,
  ClipboardList,
  Edit3,
  Plus,
  RefreshCw,
  Search,
  Trash2,
} from "lucide-react";
import { suppliersApi, type ApiSupplier } from "@/lib/api";

const STATUS_STYLE: Record<string, string> = {
  Active: "bg-emerald-50 text-emerald-700 border-emerald-200",
  Inactive: "bg-slate-100 text-slate-600 border-slate-200",
};

export default function SuppliersPage() {
  const [suppliers, setSuppliers] = useState<ApiSupplier[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const loadSuppliers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await suppliersApi.getAll({
        status: statusFilter || undefined,
        search: search.trim() || undefined,
      });
      setSuppliers(res.data || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load suppliers.");
    } finally {
      setLoading(false);
    }
  }, [search, statusFilter]);

  useEffect(() => {
    void loadSuppliers();
  }, [loadSuppliers]);

  const handleDelete = async (supplier: ApiSupplier) => {
    if (!window.confirm(`Delete supplier ${supplier.name} (${supplier.code})?`)) {
      return;
    }
    setDeletingId(supplier.id);
    setError(null);
    setFeedback(null);
    try {
      await suppliersApi.delete(supplier.id);
      setFeedback(`Deleted supplier ${supplier.name}.`);
      await loadSuppliers();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Cannot delete supplier while purchase orders remain attached."
      );
    } finally {
      setDeletingId(null);
    }
  };

  const activeCount = suppliers.filter((s) => s.status === "Active").length;
  const openPoCount = suppliers.reduce(
    (sum, s) => sum + Number(s.open_purchase_orders_count || 0),
    0
  );
  const totalProcured = suppliers.reduce(
    (sum, s) => sum + Number(s.total_procured_amount || 0),
    0
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Suppliers & Procurement</h1>
          <p className="text-sm text-slate-500 mt-1">
            Dedicated supplier directory linked directly to inventory Purchase Orders
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => void loadSuppliers()}
            className="inline-flex items-center gap-2 px-3.5 py-2 bg-white border border-slate-200 rounded-xl text-sm font-medium text-slate-700 hover:bg-slate-50 transition cursor-pointer"
          >
            <RefreshCw size={15} className={loading ? "animate-spin" : ""} />
            Refresh
          </button>
          <Link
            href="/admin/suppliers/create"
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-semibold transition"
          >
            <Plus size={16} />
            Add Supplier
          </Link>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-2xl border border-slate-200 p-5">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500">
            <span>Total Suppliers</span>
            <Building2 size={16} className="text-blue-600" />
          </div>
          <p className="text-2xl font-bold text-slate-900 mt-2">{suppliers.length}</p>
        </div>
        <div className="bg-white rounded-2xl border border-slate-200 p-5">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500">
            <span>Active Vendors</span>
            <Building2 size={16} className="text-emerald-600" />
          </div>
          <p className="text-2xl font-bold text-slate-900 mt-2">{activeCount}</p>
        </div>
        <div className="bg-white rounded-2xl border border-slate-200 p-5">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500">
            <span>Open Purchase Orders</span>
            <ClipboardList size={16} className="text-amber-600" />
          </div>
          <p className="text-2xl font-bold text-slate-900 mt-2">{openPoCount}</p>
        </div>
        <div className="bg-white rounded-2xl border border-slate-200 p-5">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500">
            <span>Total Procured Spend</span>
            <ClipboardList size={16} className="text-slate-600" />
          </div>
          <p className="text-2xl font-bold text-slate-900 mt-2">
            ${totalProcured.toFixed(2)}
          </p>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 p-4 flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search size={16} className="absolute left-3.5 top-3 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by supplier code, name, contact person, or email..."
            className="w-full pl-10 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-600/20 focus:bg-white"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3.5 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm text-slate-700"
        >
          <option value="">All Statuses</option>
          <option value="Active">Active</option>
          <option value="Inactive">Inactive</option>
        </select>
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
            onClick={() => void loadSuppliers()}
            className="text-xs font-semibold underline cursor-pointer"
          >
            Retry
          </button>
        </div>
      )}

      <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-sm text-slate-500">
            Loading suppliers...
          </div>
        ) : suppliers.length === 0 ? (
          <div className="p-10 text-center space-y-3">
            <p className="text-sm text-slate-500">
              No dedicated suppliers registered yet.
            </p>
            <Link
              href="/admin/suppliers/create"
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-blue-600 text-white rounded-xl text-xs font-semibold"
            >
              <Plus size={14} />
              Create First Supplier
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-500 uppercase">
                <tr>
                  <th className="px-5 py-3.5">Supplier</th>
                  <th className="px-5 py-3.5">Contact</th>
                  <th className="px-5 py-3.5">Terms & Lead Time</th>
                  <th className="px-5 py-3.5 text-center">POs (Open)</th>
                  <th className="px-5 py-3.5 text-right">Procured Spend</th>
                  <th className="px-5 py-3.5">Status</th>
                  <th className="px-5 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {suppliers.map((s) => (
                  <tr key={s.id} className="hover:bg-slate-50/70 transition">
                    <td className="px-5 py-3.5">
                      <div className="font-semibold text-slate-900">{s.name}</div>
                      <div className="text-xs font-mono text-slate-500">{s.code}</div>
                    </td>
                    <td className="px-5 py-3.5">
                      <div className="font-medium text-slate-800">{s.contact_name}</div>
                      <div className="text-xs text-slate-500">{s.email}</div>
                      {s.phone && (
                        <div className="text-xs text-slate-400">{s.phone}</div>
                      )}
                    </td>
                    <td className="px-5 py-3.5 text-slate-700">
                      <div className="font-medium">{s.payment_terms}</div>
                      <div className="text-xs text-slate-500">
                        Lead time: {s.lead_time_days} day{s.lead_time_days === 1 ? "" : "s"}
                      </div>
                    </td>
                    <td className="px-5 py-3.5 text-center text-slate-800 font-medium">
                      {s.purchase_orders_count}{" "}
                      <span className="text-xs text-amber-700">
                        ({s.open_purchase_orders_count} open)
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-right font-semibold text-slate-900">
                      ${Number(s.total_procured_amount || 0).toFixed(2)}
                    </td>
                    <td className="px-5 py-3.5">
                      <span
                        className={`inline-flex px-2.5 py-0.5 rounded-full text-xs font-semibold border ${
                          STATUS_STYLE[s.status] || "bg-slate-100 text-slate-700 border-slate-200"
                        }`}
                      >
                        {s.status}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      <div className="inline-flex items-center gap-2">
                        <Link
                          href={`/admin/suppliers/${s.id}`}
                          className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-medium"
                        >
                          <Edit3 size={13} />
                          Manage
                        </Link>
                        <button
                          type="button"
                          disabled={deletingId === s.id}
                          onClick={() => void handleDelete(s)}
                          className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-rose-50 hover:bg-rose-100 text-rose-700 text-xs font-medium disabled:opacity-50 cursor-pointer"
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
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
