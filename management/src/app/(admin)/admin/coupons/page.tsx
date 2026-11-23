"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Edit3,
  Loader2,
  Plus,
  RefreshCw,
  Search,
  Tag,
  Trash2,
  X,
} from "lucide-react";
import {
  couponsApi,
  type ApiCoupon,
  type CouponCreatePayload,
  type CouponUpdatePayload,
} from "@/lib/api";

interface CouponFormState {
  code: string;
  description: string;
  discount_type: "percent" | "fixed";
  discount_value: string;
  min_order_amount: string;
  max_discount_amount: string;
  usage_limit: string;
  per_user_limit: string;
  expires_at: string;
  is_active: boolean;
}

const EMPTY_FORM: CouponFormState = {
  code: "",
  description: "",
  discount_type: "percent",
  discount_value: "10",
  min_order_amount: "0",
  max_discount_amount: "",
  usage_limit: "",
  per_user_limit: "",
  expires_at: "",
  is_active: true,
};

function setupDialogLightDismiss(
  dialog: HTMLDialogElement,
  onDismiss: () => void
): (() => void) | undefined {
  if ("closedBy" in HTMLDialogElement.prototype) return undefined;
  let pressedOutside = false;
  const isOutside = (e: PointerEvent) => {
    const r = dialog.getBoundingClientRect();
    return (
      e.clientX < r.left ||
      e.clientX > r.right ||
      e.clientY < r.top ||
      e.clientY > r.bottom
    );
  };
  const onDown = (e: PointerEvent) => {
    pressedOutside = isOutside(e);
  };
  const onUp = (e: PointerEvent) => {
    if (pressedOutside && isOutside(e)) onDismiss();
  };
  dialog.addEventListener("pointerdown", onDown);
  dialog.addEventListener("pointerup", onUp);
  return () => {
    dialog.removeEventListener("pointerdown", onDown);
    dialog.removeEventListener("pointerup", onUp);
  };
}

export default function AdminCouponsPage() {
  const [coupons, setCoupons] = useState<ApiCoupon[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<{
    tone: "success" | "error";
    text: string;
  } | null>(null);

  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "inactive">("all");
  const [typeFilter, setTypeFilter] = useState<"all" | "percent" | "fixed">("all");

  const [editingCoupon, setEditingCoupon] = useState<ApiCoupon | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [formState, setFormState] = useState<CouponFormState>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [deletingCoupon, setDeletingCoupon] = useState<ApiCoupon | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [togglingId, setTogglingId] = useState<number | null>(null);
  const [referenceNowMs, setReferenceNowMs] = useState<number>(() => Date.now());

  const formDialogRef = useRef<HTMLDialogElement | null>(null);
  const deleteDialogRef = useRef<HTMLDialogElement | null>(null);

  const loadCoupons = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    setReferenceNowMs(Date.now());
    try {
      const res = await couponsApi.list();
      if (res.success && Array.isArray(res.data)) {
        setCoupons(res.data);
      } else {
        throw new Error(res.message || "Unable to fetch promotional coupons.");
      }
    } catch (err: unknown) {
      setLoadError(
        err instanceof Error ? err.message : "Failed to load coupons from server."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadCoupons();
  }, [loadCoupons]);

  useEffect(() => {
    const dialog = formDialogRef.current;
    if (!dialog || !formOpen) return;
    if (!dialog.open) dialog.showModal();
    return setupDialogLightDismiss(dialog, () => dialog.close());
  }, [formOpen]);

  useEffect(() => {
    const dialog = deleteDialogRef.current;
    if (!dialog || !deletingCoupon) return;
    if (!dialog.open) dialog.showModal();
    return setupDialogLightDismiss(dialog, () => dialog.close());
  }, [deletingCoupon]);

  const openCreateModal = () => {
    setEditingCoupon(null);
    setFormState(EMPTY_FORM);
    setFormError(null);
    setFormOpen(true);
  };

  const openEditModal = (coupon: ApiCoupon) => {
    setEditingCoupon(coupon);
    setFormState({
      code: coupon.code,
      description: coupon.description || "",
      discount_type: coupon.discount_type === "fixed" ? "fixed" : "percent",
      discount_value: String(coupon.discount_value),
      min_order_amount: String(coupon.min_order_amount ?? 0),
      max_discount_amount:
        coupon.max_discount_amount != null ? String(coupon.max_discount_amount) : "",
      usage_limit: coupon.usage_limit != null ? String(coupon.usage_limit) : "",
      per_user_limit:
        coupon.per_user_limit != null ? String(coupon.per_user_limit) : "",
      expires_at: coupon.expires_at ? coupon.expires_at.slice(0, 10) : "",
      is_active: coupon.is_active,
    });
    setFormError(null);
    setFormOpen(true);
  };

  const closeFormModal = () => {
    if (formDialogRef.current?.open) {
      formDialogRef.current.close();
    } else {
      setFormOpen(false);
    }
  };

  const closeDeleteModal = () => {
    if (deleteDialogRef.current?.open) {
      deleteDialogRef.current.close();
    } else {
      setDeletingCoupon(null);
    }
  };

  const handleSaveCoupon = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    const trimmedCode = formState.code.trim().toUpperCase();
    const discountValue = Number(formState.discount_value);
    const minOrder = Number(formState.min_order_amount || "0");
    const maxDiscount = formState.max_discount_amount.trim()
      ? Number(formState.max_discount_amount)
      : null;
    const usageLimit = formState.usage_limit.trim()
      ? Number(formState.usage_limit)
      : null;
    const perUserLimit = formState.per_user_limit.trim()
      ? Number(formState.per_user_limit)
      : null;

    if (!editingCoupon && trimmedCode.length < 2) {
      setFormError("Coupon code must be at least 2 characters.");
      return;
    }
    if (!Number.isFinite(discountValue) || discountValue <= 0) {
      setFormError("Discount value must be greater than 0.");
      return;
    }
    if (formState.discount_type === "percent" && discountValue > 100) {
      setFormError("Percentage discount cannot exceed 100%.");
      return;
    }
    if (!Number.isFinite(minOrder) || minOrder < 0) {
      setFormError("Minimum order amount must be 0 or greater.");
      return;
    }

    const expiresIso = formState.expires_at.trim()
      ? `${formState.expires_at.trim()}T23:59:59Z`
      : null;

    setSaving(true);
    try {
      if (editingCoupon) {
        const updatePayload: CouponUpdatePayload = {
          description: formState.description.trim() || null,
          discount_type: formState.discount_type,
          discount_value: discountValue,
          min_order_amount: minOrder,
          max_discount_amount: maxDiscount,
          usage_limit: usageLimit,
          per_user_limit: perUserLimit,
          expires_at: expiresIso,
          is_active: formState.is_active,
        };
        const res = await couponsApi.update(editingCoupon.id, updatePayload);
        if (!res.success) {
          throw new Error(res.message || "Failed to update coupon.");
        }
        setStatusMessage({
          tone: "success",
          text: `Coupon ${editingCoupon.code} updated.`,
        });
      } else {
        const createPayload: CouponCreatePayload = {
          code: trimmedCode,
          description: formState.description.trim() || undefined,
          discount_type: formState.discount_type,
          discount_value: discountValue,
          min_order_amount: minOrder,
          max_discount_amount: maxDiscount,
          usage_limit: usageLimit,
          per_user_limit: perUserLimit,
          expires_at: expiresIso,
          is_active: formState.is_active,
        };
        const res = await couponsApi.create(createPayload);
        if (!res.success) {
          throw new Error(res.message || "Failed to create coupon.");
        }
        setStatusMessage({
          tone: "success",
          text: `Coupon ${trimmedCode} created.`,
        });
      }
      closeFormModal();
      await loadCoupons();
    } catch (err: unknown) {
      setFormError(
        err instanceof Error ? err.message : "Could not save promo coupon."
      );
    } finally {
      setSaving(false);
    }
  };

  const handleToggleActive = async (coupon: ApiCoupon) => {
    setTogglingId(coupon.id);
    setStatusMessage(null);
    try {
      const res = await couponsApi.update(coupon.id, {
        is_active: !coupon.is_active,
      });
      if (!res.success) {
        throw new Error(res.message || "Failed to update status.");
      }
      setCoupons((prev) =>
        prev.map((c) =>
          c.id === coupon.id ? { ...c, is_active: !coupon.is_active } : c
        )
      );
      setStatusMessage({
        tone: "success",
        text: `Coupon ${coupon.code} is now ${!coupon.is_active ? "active" : "inactive"}.`,
      });
    } catch (err: unknown) {
      setStatusMessage({
        tone: "error",
        text: err instanceof Error ? err.message : "Unable to update coupon status.",
      });
    } finally {
      setTogglingId(null);
    }
  };

  const handleConfirmDelete = async () => {
    if (!deletingCoupon) return;
    setDeleting(true);
    try {
      const res = await couponsApi.delete(deletingCoupon.id);
      if (!res.success) {
        throw new Error(res.message || "Failed to delete coupon.");
      }
      setStatusMessage({
        tone: "success",
        text: `Coupon ${deletingCoupon.code} deleted.`,
      });
      closeDeleteModal();
      await loadCoupons();
    } catch (err: unknown) {
      setStatusMessage({
        tone: "error",
        text: err instanceof Error ? err.message : "Unable to delete coupon.",
      });
      closeDeleteModal();
    } finally {
      setDeleting(false);
    }
  };

  const filteredCoupons = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return coupons.filter((c) => {
      if (statusFilter === "active" && !c.is_active) return false;
      if (statusFilter === "inactive" && c.is_active) return false;
      if (typeFilter !== "all" && c.discount_type !== typeFilter) return false;
      if (
        q &&
        !c.code.toLowerCase().includes(q) &&
        !(c.description || "").toLowerCase().includes(q)
      ) {
        return false;
      }
      return true;
    });
  }, [coupons, searchQuery, statusFilter, typeFilter]);

  const kpis = useMemo(() => {
    const sevenDaysMs = 7 * 24 * 60 * 60 * 1000;
    const activeCount = coupons.filter((c) => c.is_active).length;
    const totalRedemptions = coupons.reduce(
      (sum, c) => sum + (Number(c.used_count) || 0),
      0
    );
    const expiringSoon = coupons.filter((c) => {
      if (!c.expires_at || !c.is_active) return false;
      const diff = new Date(c.expires_at).getTime() - referenceNowMs;
      return diff >= 0 && diff <= sevenDaysMs;
    }).length;
    return { total: coupons.length, activeCount, totalRedemptions, expiringSoon };
  }, [coupons, referenceNowMs]);

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Coupons &amp; Promos</h1>
          <p className="text-sm text-slate-500 mt-1">
            Create discount vouchers, configure per-customer usage limits, and manage campaign status.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            type="button"
            onClick={() => void loadCoupons()}
            disabled={loading}
            className="inline-flex items-center gap-1.5 px-3.5 py-2.5 rounded-xl border border-slate-200 bg-white text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            <RefreshCw size={15} className={loading ? "animate-spin" : ""} aria-hidden="true" />
            Refresh
          </button>
          <button
            type="button"
            onClick={openCreateModal}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold shadow-sm cursor-pointer"
          >
            <Plus size={16} aria-hidden="true" />
            Create Coupon
          </button>
        </div>
      </div>

      {statusMessage && (
        <div
          role={statusMessage.tone === "error" ? "alert" : "status"}
          className={`flex items-center justify-between gap-3 rounded-2xl border px-4 py-3 text-sm font-medium ${
            statusMessage.tone === "error"
              ? "border-rose-200 bg-rose-50 text-rose-800"
              : "border-emerald-200 bg-emerald-50 text-emerald-800"
          }`}
        >
          <span className="flex items-center gap-2">
            {statusMessage.tone === "error" ? (
              <AlertCircle size={16} aria-hidden="true" />
            ) : (
              <CheckCircle2 size={16} aria-hidden="true" />
            )}
            {statusMessage.text}
          </span>
          <button
            type="button"
            aria-label="Dismiss status notice"
            onClick={() => setStatusMessage(null)}
            className="p-1 rounded-lg hover:bg-black/5"
          >
            <X size={15} aria-hidden="true" />
          </button>
        </div>
      )}

      {/* KPI Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="rounded-2xl bg-white border border-slate-100 p-5 shadow-xs">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Total Coupons
          </p>
          <p className="text-2xl font-bold text-slate-900 mt-2">{kpis.total}</p>
        </div>
        <div className="rounded-2xl bg-white border border-slate-100 p-5 shadow-xs">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Active Campaigns
          </p>
          <p className="text-2xl font-bold text-emerald-600 mt-2">{kpis.activeCount}</p>
        </div>
        <div className="rounded-2xl bg-white border border-slate-100 p-5 shadow-xs">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Total Redemptions
          </p>
          <p className="text-2xl font-bold text-blue-600 mt-2">{kpis.totalRedemptions}</p>
        </div>
        <div className="rounded-2xl bg-white border border-slate-100 p-5 shadow-xs">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Expiring in 7 Days
          </p>
          <p className="text-2xl font-bold text-amber-600 mt-2">{kpis.expiringSoon}</p>
        </div>
      </div>

      {/* Filters */}
      <search className="rounded-2xl bg-white border border-slate-100 p-4 flex flex-col sm:flex-row gap-3 items-stretch sm:items-center justify-between shadow-xs">
        <div className="relative flex-1 max-w-md">
          <label htmlFor="coupon-search" className="sr-only">
            Search coupons
          </label>
          <Search
            size={16}
            aria-hidden="true"
            className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400"
          />
          <input
            id="coupon-search"
            type="search"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by code or description…"
            className="w-full pl-10 pr-4 py-2 rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div className="flex flex-wrap gap-2.5">
          <label htmlFor="coupon-status-filter" className="sr-only">
            Filter by status
          </label>
          <select
            id="coupon-status-filter"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as typeof statusFilter)}
            className="px-3 py-2 rounded-xl border border-slate-200 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="all">All Statuses</option>
            <option value="active">Active Only</option>
            <option value="inactive">Inactive Only</option>
          </select>

          <label htmlFor="coupon-type-filter" className="sr-only">
            Filter by discount type
          </label>
          <select
            id="coupon-type-filter"
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value as typeof typeFilter)}
            className="px-3 py-2 rounded-xl border border-slate-200 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="all">All Discount Types</option>
            <option value="percent">Percentage (%)</option>
            <option value="fixed">Fixed Amount ($)</option>
          </select>
        </div>
      </search>

      {/* Main Content */}
      {loading ? (
        <div className="rounded-2xl bg-white border border-slate-100 py-20 flex flex-col items-center justify-center text-blue-600">
          <Loader2 size={32} className="animate-spin mb-3" aria-hidden="true" />
          <p className="text-sm text-slate-600 font-medium">Loading coupons from PostgreSQL…</p>
        </div>
      ) : loadError ? (
        <div
          role="alert"
          className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-center space-y-3"
        >
          <p className="text-sm font-semibold text-rose-800">{loadError}</p>
          <button
            type="button"
            onClick={() => void loadCoupons()}
            className="px-4 py-2 rounded-xl bg-white border border-rose-200 text-sm font-semibold text-rose-700 hover:bg-rose-100"
          >
            Retry
          </button>
        </div>
      ) : filteredCoupons.length === 0 ? (
        <div className="rounded-2xl bg-white border border-slate-100 py-16 text-center space-y-3">
          <Tag size={32} className="mx-auto text-slate-300" aria-hidden="true" />
          <p className="text-sm font-semibold text-slate-700">
            No matching promo coupons found
          </p>
          <p className="text-xs text-slate-500">
            Adjust your filters or create a new promotional voucher.
          </p>
        </div>
      ) : (
        <div className="rounded-2xl bg-white border border-slate-100 shadow-xs overflow-hidden">
          <div
            tabIndex={0}
            role="region"
            aria-labelledby="coupons-table-caption"
            className="bp-table-wrapper"
          >
            <table className="text-left text-sm">
              <caption id="coupons-table-caption" className="sr-only">
                Promotional coupons directory
              </caption>
              <thead className="border-b border-slate-100 text-xs font-semibold uppercase tracking-wider text-slate-500">
                <tr>
                  <th scope="col" className="px-5 py-3.5">Code</th>
                  <th scope="col" className="px-5 py-3.5">Discount</th>
                  <th scope="col" className="px-5 py-3.5">Min Spend / Cap</th>
                  <th scope="col" className="px-5 py-3.5">Usage Limits</th>
                  <th scope="col" className="px-5 py-3.5">Expires</th>
                  <th scope="col" className="px-5 py-3.5">Status</th>
                  <th scope="col" className="px-5 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredCoupons.map((c) => {
                  const isPercent = c.discount_type === "percent";
                  return (
                    <tr key={c.id} className="hover:bg-slate-50/70 transition-colors">
                      <th scope="row" className="px-5 py-4 font-semibold text-slate-900">
                        <div>
                          <span className="font-mono text-sm font-bold text-blue-600">
                            {c.code}
                          </span>
                          {c.description && (
                            <p className="text-xs font-normal text-slate-500 mt-0.5 line-clamp-1">
                              {c.description}
                            </p>
                          )}
                        </div>
                      </th>
                      <td data-label="Discount" className="px-5 py-4 font-semibold text-slate-800 whitespace-nowrap">
                        {isPercent
                          ? `${Number(c.discount_value)}% off`
                          : `$${Number(c.discount_value).toFixed(2)} off`}
                      </td>
                      <td data-label="Min Spend / Cap" className="px-5 py-4 text-xs text-slate-600 whitespace-nowrap">
                        Min ${Number(c.min_order_amount || 0).toFixed(2)}
                        {c.max_discount_amount != null
                          ? ` • Max $${Number(c.max_discount_amount).toFixed(2)}`
                          : ""}
                      </td>
                      <td data-label="Usage Limits" className="px-5 py-4 text-xs text-slate-600 whitespace-nowrap">
                        <span>
                          Used {c.used_count ?? 0}
                          {c.usage_limit != null ? ` / ${c.usage_limit}` : " / ∞"}
                        </span>
                        {c.per_user_limit != null && (
                          <span className="block text-slate-400">
                            {c.per_user_limit} per customer
                          </span>
                        )}
                      </td>
                      <td data-label="Expires" className="px-5 py-4 text-xs text-slate-600 whitespace-nowrap">
                        {c.expires_at
                          ? new Date(c.expires_at).toLocaleDateString()
                          : "No expiry"}
                      </td>
                      <td data-label="Status" className="px-5 py-4 whitespace-nowrap">
                        <button
                          type="button"
                          role="switch"
                          aria-checked={c.is_active}
                          aria-label={`Toggle ${c.code} active status`}
                          disabled={togglingId === c.id}
                          onClick={() => void handleToggleActive(c)}
                          className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold transition cursor-pointer ${
                            c.is_active
                              ? "bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                              : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                          }`}
                        >
                          {c.is_active ? "Active" : "Inactive"}
                        </button>
                      </td>
                      <td data-label="Actions" className="px-5 py-4 text-right whitespace-nowrap">
                        <div className="inline-flex items-center gap-1.5">
                          <button
                            type="button"
                            onClick={() => openEditModal(c)}
                            aria-label={`Edit ${c.code}`}
                            className="p-2 rounded-lg text-slate-500 hover:text-blue-600 hover:bg-blue-50 transition"
                          >
                            <Edit3 size={15} aria-hidden="true" />
                          </button>
                          <button
                            type="button"
                            onClick={() => setDeletingCoupon(c)}
                            aria-label={`Delete ${c.code}`}
                            className="p-2 rounded-lg text-slate-500 hover:text-rose-600 hover:bg-rose-50 transition"
                          >
                            <Trash2 size={15} aria-hidden="true" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Create / Edit Coupon Native Dialog */}
      {formOpen && (
        <dialog
          ref={formDialogRef}
          aria-labelledby="coupon-dialog-title"
          onClose={() => {
            if (formDialogRef.current) formDialogRef.current.returnValue = "";
            setFormOpen(false);
          }}
          {...({ closedby: "any" } as Record<string, unknown>)}
          className="m-auto w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-0 shadow-2xl overflow-hidden max-h-[90vh] open:flex flex-col"
        >
          <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between shrink-0">
            <h2 id="coupon-dialog-title" className="text-lg font-bold text-slate-900">
              {editingCoupon ? `Edit Coupon ${editingCoupon.code}` : "Create Promo Coupon"}
            </h2>
            <button
              type="button"
              onClick={closeFormModal}
              aria-label="Close coupon dialog"
              className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100"
            >
              <X size={18} aria-hidden="true" />
            </button>
          </div>

          <form onSubmit={handleSaveCoupon} className="p-6 overflow-y-auto space-y-4">
            {formError && (
              <div
                role="alert"
                className="rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-2.5 text-xs font-semibold text-rose-800"
              >
                {formError}
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label htmlFor="coupon-code" className="block text-xs font-semibold text-slate-700 mb-1">
                  Promo Code
                </label>
                <input
                  id="coupon-code"
                  name="code"
                  type="text"
                  autoFocus={!editingCoupon}
                  disabled={Boolean(editingCoupon)}
                  required
                  value={formState.code}
                  onChange={(e) =>
                    setFormState((s) => ({ ...s, code: e.target.value.toUpperCase() }))
                  }
                  placeholder="WELCOME10"
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm uppercase font-mono disabled:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label htmlFor="coupon-type" className="block text-xs font-semibold text-slate-700 mb-1">
                  Discount Type
                </label>
                <select
                  id="coupon-type"
                  name="discount_type"
                  value={formState.discount_type}
                  onChange={(e) =>
                    setFormState((s) => ({
                      ...s,
                      discount_type: e.target.value === "fixed" ? "fixed" : "percent",
                    }))
                  }
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="percent">Percentage (%)</option>
                  <option value="fixed">Fixed Amount ($)</option>
                </select>
              </div>
            </div>

            <div>
              <label htmlFor="coupon-description" className="block text-xs font-semibold text-slate-700 mb-1">
                Description
              </label>
              <input
                id="coupon-description"
                name="description"
                type="text"
                autoFocus={Boolean(editingCoupon)}
                value={formState.description}
                onChange={(e) => setFormState((s) => ({ ...s, description: e.target.value }))}
                placeholder="10% welcome discount for new customers"
                className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label htmlFor="coupon-value" className="block text-xs font-semibold text-slate-700 mb-1">
                  {formState.discount_type === "percent" ? "Percent (%)" : "Amount ($)"}
                </label>
                <input
                  id="coupon-value"
                  name="discount_value"
                  type="number"
                  step="0.01"
                  min="0.01"
                  max={formState.discount_type === "percent" ? "100" : undefined}
                  required
                  value={formState.discount_value}
                  onChange={(e) => setFormState((s) => ({ ...s, discount_value: e.target.value }))}
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label htmlFor="coupon-min" className="block text-xs font-semibold text-slate-700 mb-1">
                  Min Spend ($)
                </label>
                <input
                  id="coupon-min"
                  name="min_order_amount"
                  type="number"
                  step="0.01"
                  min="0"
                  value={formState.min_order_amount}
                  onChange={(e) => setFormState((s) => ({ ...s, min_order_amount: e.target.value }))}
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label htmlFor="coupon-max" className="block text-xs font-semibold text-slate-700 mb-1">
                  Max Cap ($)
                </label>
                <input
                  id="coupon-max"
                  name="max_discount_amount"
                  type="number"
                  step="0.01"
                  min="0"
                  value={formState.max_discount_amount}
                  onChange={(e) => setFormState((s) => ({ ...s, max_discount_amount: e.target.value }))}
                  placeholder="Optional"
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label htmlFor="coupon-usage-limit" className="block text-xs font-semibold text-slate-700 mb-1">
                  Global Limit
                </label>
                <input
                  id="coupon-usage-limit"
                  name="usage_limit"
                  type="number"
                  min="1"
                  value={formState.usage_limit}
                  onChange={(e) => setFormState((s) => ({ ...s, usage_limit: e.target.value }))}
                  placeholder="Unlimited"
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label htmlFor="coupon-per-user-limit" className="block text-xs font-semibold text-slate-700 mb-1">
                  Per Customer
                </label>
                <input
                  id="coupon-per-user-limit"
                  name="per_user_limit"
                  type="number"
                  min="1"
                  value={formState.per_user_limit}
                  onChange={(e) => setFormState((s) => ({ ...s, per_user_limit: e.target.value }))}
                  placeholder="Unlimited"
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label htmlFor="coupon-expires" className="block text-xs font-semibold text-slate-700 mb-1">
                  Expiry Date
                </label>
                <input
                  id="coupon-expires"
                  name="expires_at"
                  type="date"
                  value={formState.expires_at}
                  onChange={(e) => setFormState((s) => ({ ...s, expires_at: e.target.value }))}
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            <label className="flex items-center gap-2.5 text-sm font-medium text-slate-700 pt-1 cursor-pointer">
              <input
                type="checkbox"
                checked={formState.is_active}
                onChange={(e) => setFormState((s) => ({ ...s, is_active: e.target.checked }))}
                className="h-4 w-4 accent-blue-600 rounded"
              />
              Coupon is active for customer checkout
            </label>

            <div className="pt-4 border-t border-slate-100 flex items-center justify-end gap-2.5">
              <button
                type="button"
                onClick={closeFormModal}
                className="px-4 py-2 rounded-xl border border-slate-200 text-sm font-semibold text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={saving}
                className="px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-semibold"
              >
                {saving ? "Saving…" : editingCoupon ? "Save Changes" : "Create Coupon"}
              </button>
            </div>
          </form>
        </dialog>
      )}

      {/* Delete Confirmation Native Dialog */}
      {deletingCoupon && (
        <dialog
          ref={deleteDialogRef}
          aria-labelledby="delete-coupon-title"
          onClose={() => {
            if (deleteDialogRef.current) deleteDialogRef.current.returnValue = "";
            setDeletingCoupon(null);
          }}
          {...({ closedby: "any" } as Record<string, unknown>)}
          className="m-auto w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl space-y-4"
        >
          <h2 id="delete-coupon-title" className="text-lg font-bold text-slate-900">
            Delete coupon {deletingCoupon.code}?
          </h2>
          <p className="text-sm text-slate-600">
            Customers will no longer be able to redeem this promotional voucher. This action cannot be undone.
          </p>
          <div className="flex items-center justify-end gap-2.5 pt-2">
            <button
              type="button"
              autoFocus
              onClick={closeDeleteModal}
              className="px-4 py-2 rounded-xl border border-slate-200 text-sm font-semibold text-slate-700 hover:bg-slate-50"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={deleting}
              onClick={() => void handleConfirmDelete()}
              className="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-700 disabled:opacity-50 text-white text-sm font-semibold"
            >
              {deleting ? "Deleting…" : "Delete Coupon"}
            </button>
          </div>
        </dialog>
      )}
    </div>
  );
}
