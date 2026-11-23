"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { AlertCircle, ArrowLeft, CheckCircle2, ClipboardList, Save } from "lucide-react";
import { suppliersApi, type ApiSupplier } from "@/lib/api";

export default function SupplierDetailPage() {
  const params = useParams<{ id: string }>();
  const supplierId = Number(params?.id);

  const [supplier, setSupplier] = useState<ApiSupplier | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedMsg, setSavedMsg] = useState<string | null>(null);

  const [form, setForm] = useState({
    code: "",
    name: "",
    contact_name: "",
    email: "",
    phone: "",
    address: "",
    city: "",
    country: "",
    tax_id: "",
    payment_terms: "Net 30",
    lead_time_days: 7,
    status: "Active",
    notes: "",
  });

  const loadSupplier = useCallback(async () => {
    if (!Number.isFinite(supplierId) || supplierId <= 0) return;
    setLoading(true);
    setError(null);
    try {
      const res = await suppliersApi.getById(supplierId);
      const s = res.data;
      setSupplier(s);
      setForm({
        code: s.code,
        name: s.name,
        contact_name: s.contact_name,
        email: s.email,
        phone: s.phone || "",
        address: s.address || "",
        city: s.city || "",
        country: s.country || "",
        tax_id: s.tax_id || "",
        payment_terms: s.payment_terms,
        lead_time_days: s.lead_time_days,
        status: s.status,
        notes: s.notes || "",
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load supplier.");
    } finally {
      setLoading(false);
    }
  }, [supplierId]);

  useEffect(() => {
    void loadSupplier();
  }, [loadSupplier]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setSavedMsg(null);
    try {
      const res = await suppliersApi.update(supplierId, {
        code: form.code.trim(),
        name: form.name.trim(),
        contact_name: form.contact_name.trim(),
        email: form.email.trim(),
        phone: form.phone.trim() || undefined,
        address: form.address.trim() || undefined,
        city: form.city.trim() || undefined,
        country: form.country.trim() || undefined,
        tax_id: form.tax_id.trim() || undefined,
        payment_terms: form.payment_terms,
        lead_time_days: Number(form.lead_time_days) || 0,
        status: form.status,
        notes: form.notes.trim() || undefined,
      });
      setSupplier(res.data);
      setSavedMsg("Supplier profile updated.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update supplier.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6 max-w-5xl">
      <Link
        href="/admin/suppliers"
        className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900"
      >
        <ArrowLeft size={16} />
        Back to Suppliers
      </Link>

      {loading ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-8 text-sm text-slate-500">
          Loading supplier details...
        </div>
      ) : error && !supplier ? (
        <div className="bg-rose-50 border border-rose-200 rounded-2xl p-6 text-rose-700 text-sm flex items-center gap-2">
          <AlertCircle size={18} />
          <span>{error}</span>
        </div>
      ) : supplier ? (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="bg-white rounded-2xl border border-slate-200 p-5">
              <p className="text-xs font-medium text-slate-500">Total Purchase Orders</p>
              <p className="text-2xl font-bold text-slate-900 mt-1">
                {supplier.purchase_orders_count}
              </p>
            </div>
            <div className="bg-white rounded-2xl border border-slate-200 p-5">
              <p className="text-xs font-medium text-slate-500">Open Purchase Orders</p>
              <p className="text-2xl font-bold text-amber-700 mt-1">
                {supplier.open_purchase_orders_count}
              </p>
            </div>
            <div className="bg-white rounded-2xl border border-slate-200 p-5">
              <p className="text-xs font-medium text-slate-500">Total Procured Amount</p>
              <p className="text-2xl font-bold text-slate-900 mt-1">
                ${Number(supplier.total_procured_amount || 0).toFixed(2)}
              </p>
            </div>
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 p-6">
            <div className="flex items-center justify-between border-b border-slate-100 pb-4 mb-5">
              <div>
                <h1 className="text-xl font-bold text-slate-900">{supplier.name}</h1>
                <p className="text-xs font-mono text-slate-500 mt-0.5">{supplier.code}</p>
              </div>
              <Link
                href="/admin/inventory"
                className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-slate-900 text-white rounded-xl text-xs font-semibold"
              >
                <ClipboardList size={14} />
                Create PO in Inventory
              </Link>
            </div>

            {savedMsg && (
              <div className="mb-4 p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center gap-2">
                <CheckCircle2 size={15} />
                {savedMsg}
              </div>
            )}

            {error && (
              <div className="mb-4 p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2">
                <AlertCircle size={15} />
                {error}
              </div>
            )}

            <form onSubmit={handleSave} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Supplier Name
                  </label>
                  <input
                    type="text"
                    required
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    className="w-full px-3.5 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Code
                  </label>
                  <input
                    type="text"
                    required
                    value={form.code}
                    onChange={(e) => setForm({ ...form, code: e.target.value })}
                    className="w-full px-3.5 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm font-mono"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Contact Name
                  </label>
                  <input
                    type="text"
                    required
                    value={form.contact_name}
                    onChange={(e) => setForm({ ...form, contact_name: e.target.value })}
                    className="w-full px-3.5 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Email
                  </label>
                  <input
                    type="email"
                    required
                    value={form.email}
                    onChange={(e) => setForm({ ...form, email: e.target.value })}
                    className="w-full px-3.5 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Phone
                  </label>
                  <input
                    type="text"
                    value={form.phone}
                    onChange={(e) => setForm({ ...form, phone: e.target.value })}
                    className="w-full px-3.5 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Payment Terms
                  </label>
                  <select
                    value={form.payment_terms}
                    onChange={(e) => setForm({ ...form, payment_terms: e.target.value })}
                    className="w-full px-3.5 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm"
                  >
                    <option value="Due on Receipt">Due on Receipt</option>
                    <option value="Net 15">Net 15</option>
                    <option value="Net 30">Net 30</option>
                    <option value="Net 60">Net 60</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Lead Time (Days)
                  </label>
                  <input
                    type="number"
                    min={0}
                    max={365}
                    value={form.lead_time_days}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        lead_time_days: parseInt(e.target.value, 10) || 0,
                      })
                    }
                    className="w-full px-3.5 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Status
                  </label>
                  <select
                    value={form.status}
                    onChange={(e) => setForm({ ...form, status: e.target.value })}
                    className="w-full px-3.5 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm"
                  >
                    <option value="Active">Active</option>
                    <option value="Inactive">Inactive</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Notes
                </label>
                <textarea
                  rows={2}
                  value={form.notes}
                  onChange={(e) => setForm({ ...form, notes: e.target.value })}
                  className="w-full px-3.5 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm"
                />
              </div>

              <div className="flex justify-end">
                <button
                  type="submit"
                  disabled={saving}
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold disabled:opacity-60 cursor-pointer"
                >
                  <Save size={15} />
                  {saving ? "Saving..." : "Save Changes"}
                </button>
              </div>
            </form>
          </div>

          {/* Purchase Order History */}
          <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-100">
              <h2 className="font-bold text-slate-900">Purchase Order History</h2>
            </div>
            {supplier.recent_purchase_orders.length === 0 ? (
              <div className="p-6 text-sm text-slate-500">
                No purchase orders created for this supplier yet.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-500 uppercase">
                    <tr>
                      <th className="px-5 py-3">PO Number</th>
                      <th className="px-5 py-3">Destination Warehouse</th>
                      <th className="px-5 py-3">Status</th>
                      <th className="px-5 py-3 text-right">Total Cost</th>
                      <th className="px-5 py-3">Created</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {supplier.recent_purchase_orders.map((po) => (
                      <tr key={po.id}>
                        <td className="px-5 py-3 font-mono text-xs font-semibold text-slate-900">
                          {po.po_number}
                        </td>
                        <td className="px-5 py-3 text-slate-700">
                          {po.warehouse_name || `Warehouse #${po.warehouse_id}`}
                        </td>
                        <td className="px-5 py-3 capitalize text-slate-700">
                          {po.status.replaceAll("_", " ")}
                        </td>
                        <td className="px-5 py-3 text-right font-semibold text-slate-900">
                          ${Number(po.total_cost).toFixed(2)}
                        </td>
                        <td className="px-5 py-3 text-xs text-slate-500">
                          {new Date(po.created_at).toLocaleDateString()}
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
