"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  Clock,
  ExternalLink,
  MapPin,
  Package,
  Printer,
  RefreshCw,
  Search,
  ShieldCheck,
  ShoppingBag,
  Truck,
  X,
  XCircle,
} from "lucide-react";
import { ordersApi, type ApiOrder, type ApiProduct } from "@/lib/api";
import { isLoggedIn } from "@/lib/auth";
import { getOrderPaymentPresentation } from "@/lib/checkout-security";
import {
  applyProductImageFallback,
  fetchStoreProducts,
  NEUTRAL_PRODUCT_PLACEHOLDER,
  resolveProductImage,
} from "@/lib/store-catalog";
import { useShopStore } from "@/lib/store";

const TRACKING_STEPS = ["pending", "processing", "shipped", "delivered"];

function getStepIndex(status: string): number {
  const normalized = status.toLowerCase();
  if (normalized === "confirmed" || normalized === "preparing") return 1;
  const idx = TRACKING_STEPS.indexOf(normalized);
  return idx === -1 ? 0 : idx;
}

export default function OrdersPage() {
  const addToCart = useShopStore((s) => s.addToCart);
  const pushToast = useShopStore((s) => s.pushToast);

  const [serverOrders, setServerOrders] = useState<ApiOrder[]>([]);
  const [productCatalog, setProductCatalog] = useState<ApiProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedOrder, setSelectedOrder] = useState<ApiOrder | null>(null);
  const [reorderingId, setReorderingId] = useState<number | null>(null);

  const authenticated = isLoggedIn();

  const loadOrders = useCallback(async () => {
    if (!authenticated) {
      setServerOrders([]);
      setLoading(false);
      return;
    }

    setLoading(true);
    setLoadError(null);
    try {
      const [ordersRes, catalogRes] = await Promise.all([
        ordersApi.list(),
        fetchStoreProducts().catch(() => ({ products: [] as ApiProduct[] })),
      ]);

      if (ordersRes.success === false || !Array.isArray(ordersRes.data)) {
        throw new Error(ordersRes.message || "Unable to load your orders.");
      }

      const confirmedOnly = ordersRes.data.filter(
        (o) => Number.isInteger(Number(o.id)) && Number(o.id) > 0
      );
      setServerOrders(confirmedOnly);
      if (catalogRes?.products) {
        setProductCatalog(catalogRes.products);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "";
      setLoadError(
        msg.includes("Failed to fetch") ||
          msg.includes("NetworkError") ||
          msg.includes("Load failed")
          ? "Unable to reach the server to load your orders. Please check your internet connection."
          : msg || "Unable to load your order history right now."
      );
    } finally {
      setLoading(false);
    }
  }, [authenticated]);

  useEffect(() => {
    loadOrders();
  }, [loadOrders]);

  // Escape key handler for details modal
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && selectedOrder) {
        setSelectedOrder(null);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [selectedOrder]);

  // Lock body scroll when modal is open
  useEffect(() => {
    if (!selectedOrder) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [selectedOrder]);

  // Compute status counts for filters
  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = {
      all: serverOrders.length,
      pending: 0,
      processing: 0,
      shipped: 0,
      delivered: 0,
      cancelled: 0,
    };
    for (const o of serverOrders) {
      const s = o.status.toLowerCase();
      if (s === "pending") counts.pending += 1;
      else if (s === "processing" || s === "preparing" || s === "confirmed")
        counts.processing += 1;
      else if (s === "shipped") counts.shipped += 1;
      else if (s === "delivered") counts.delivered += 1;
      else if (s === "cancelled") counts.cancelled += 1;
    }
    return counts;
  }, [serverOrders]);

  // Filter & Search Orders
  const filteredOrders = useMemo(() => {
    let list = [...serverOrders].sort(
      (a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    );

    if (statusFilter !== "all") {
      list = list.filter((o) => {
        const s = o.status.toLowerCase();
        if (statusFilter === "processing") {
          return s === "processing" || s === "preparing" || s === "confirmed";
        }
        return s === statusFilter;
      });
    }

    if (searchQuery.trim()) {
      const q = searchQuery.trim().toLowerCase().replace(/^#/, "");
      list = list.filter((o) => {
        const idMatch = String(o.id).includes(q);
        const itemMatch = o.items.some((item) =>
          item.product_name.toLowerCase().includes(q)
        );
        return idMatch || itemMatch;
      });
    }

    return list;
  }, [serverOrders, statusFilter, searchQuery]);

  // Helper to find catalog image for an order item
  const getItemImage = (productId?: number | null, productName?: string) => {
    if (productId) {
      const matched = productCatalog.find((p) => p.id === productId);
      if (matched) return resolveProductImage(matched);
    }
    if (productName) {
      const matched = productCatalog.find((p) =>
        productName.toLowerCase().includes(p.name.toLowerCase())
      );
      if (matched) return resolveProductImage(matched);
    }
    return NEUTRAL_PRODUCT_PLACEHOLDER;
  };

  // Reorder all products from an order
  const handleReorder = async (order: ApiOrder) => {
    setReorderingId(order.id);
    try {
      let addedCount = 0;
      for (const oi of order.items) {
        const found =
          productCatalog.find((p) => p.id === oi.product_id) ||
          productCatalog.find((p) =>
            oi.product_name.toLowerCase().includes(p.name.toLowerCase())
          );
        if (found && (found.stock ?? 0) > 0) {
          await addToCart(found, Math.min(oi.quantity, found.stock), undefined, false);
          addedCount += 1;
        }
      }

      if (addedCount > 0) {
        pushToast({
          title: "Added to Shopping Bag",
          description: `Added ${addedCount} products from Order #${order.id} into your cart.`,
          tone: "success",
        });
        useShopStore.getState().openCart();
      } else {
        pushToast({
          title: "Items Currently Unavailable",
          description: "None of the products from this order are currently in stock.",
          tone: "error",
        });
      }
    } finally {
      setReorderingId(null);
    }
  };

  // Printable receipt handler
  const handlePrintReceipt = () => {
    window.print();
  };

  // ==========================================
  // UNAUTHENTICATED GUEST STATE
  // ==========================================
  if (!authenticated) {
    return (
      <div className="min-h-[70vh] bg-[#F5F8FD]/60 flex items-center justify-center py-16 px-4">
        <div className="max-w-md w-full bg-white rounded-[2.5rem] border border-slate-200/80 p-8 sm:p-12 shadow-sm text-center space-y-6">
          <div className="w-20 h-20 rounded-3xl bg-blue-50 text-[#245BE7] flex items-center justify-center mx-auto shadow-inner border border-blue-100/60">
            <Package size={36} />
          </div>

          <div>
            <h1 className="text-3xl font-bold text-ink sm:text-4xl">
              Sign in to see your orders
            </h1>
            <p className="mt-3 text-base leading-7 text-muted">
              Your order history, delivery status and receipts live in your account.
            </p>
          </div>

          <div className="flex flex-col sm:flex-row gap-3 pt-2">
            <Link
              href="/login?redirect=/orders"
              className="bp-press flex min-h-12 flex-1 items-center justify-center rounded-xl bg-ink px-5 text-[15px] font-semibold text-white hover:bg-brand"
            >
              Sign in
            </Link>
            <Link
              href="/register?redirect=/orders"
              className="bp-press flex min-h-12 flex-1 items-center justify-center rounded-xl border border-line-strong bg-white px-5 text-[15px] font-semibold text-ink hover:border-ink"
            >
              Create account
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="pb-20">
      <div className="bp-container max-w-5xl space-y-8 pt-10 sm:pt-14">
        {/* Page Editorial Header */}
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 pb-6 border-b border-slate-200/80">
          <div>
            <p className="bp-eyebrow">Orders</p>
            <h1 className="mt-3 text-4xl font-bold text-ink sm:text-5xl">
              Your orders{" "}
              <span className="bp-price font-sans text-xl font-medium text-muted">
                {serverOrders.length} {serverOrders.length === 1 ? "order" : "orders"}
              </span>
            </h1>
            <p className="text-sm text-slate-500 mt-1 max-w-xl">
              Monitor live courier dispatch, verify itemized purchase receipts, and manage repeat hardware orders.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={loadOrders}
              disabled={loading}
              className="px-4 py-2.5 rounded-2xl border border-slate-200 bg-white hover:bg-slate-50 text-xs font-semibold text-slate-700 inline-flex items-center gap-2 shadow-xs transition cursor-pointer active:scale-98"
            >
              <RefreshCw size={14} className={loading ? "animate-spin text-[#245BE7]" : ""} />
              Refresh
            </button>
          </div>
        </div>

        {/* Filter and Search Bar Controls */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4">
          {/* Status Tabs with Counts */}
          <div className="flex items-center gap-2 overflow-x-auto no-scrollbar pb-1 sm:pb-0">
            {[
              { id: "all", label: "All Orders", count: statusCounts.all },
              { id: "pending", label: "Pending", count: statusCounts.pending },
              { id: "processing", label: "Processing", count: statusCounts.processing },
              { id: "shipped", label: "Dispatched", count: statusCounts.shipped },
              { id: "delivered", label: "Delivered", count: statusCounts.delivered },
              { id: "cancelled", label: "Cancelled", count: statusCounts.cancelled },
            ]
              .filter((f) => f.id === "all" || f.count > 0)
              .map((f) => (
                <button
                  key={f.id}
                  type="button"
                  onClick={() => setStatusFilter(f.id)}
                  className={`px-4 py-2.5 rounded-2xl text-xs font-semibold transition shrink-0 cursor-pointer flex items-center gap-2 ${
                    statusFilter === f.id
                      ? "bg-[#245BE7] text-white shadow-md shadow-blue-600/20"
                      : "bg-white border border-slate-200/90 text-slate-700 hover:border-blue-200 hover:bg-slate-50"
                  }`}
                >
                  <span>{f.label}</span>
                  <span
                    className={`px-1.5 py-0.5 rounded-full text-[10px] font-mono ${
                      statusFilter === f.id
                        ? "bg-white/20 text-white"
                        : "bg-slate-100 text-slate-500"
                    }`}
                  >
                    {f.count}
                  </span>
                </button>
              ))}
          </div>

          {/* Search Box */}
          <div className="relative min-w-[240px] sm:w-72">
            <Search
              size={15}
              className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400"
            />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by order # or item..."
              className="w-full pl-9 pr-4 py-2.5 rounded-2xl bg-white border border-slate-200 text-xs font-semibold text-[#181818] placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-[#245BE7] shadow-xs"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery("")}
                aria-label="Clear search"
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 p-0.5"
              >
                <X size={13} />
              </button>
            )}
          </div>
        </div>

        {/* Load Error Alert */}
        {loadError && (
          <div
            role="alert"
            className="p-4 sm:p-5 rounded-3xl bg-rose-50 border border-rose-200 text-rose-800 text-sm font-bold flex flex-wrap items-center justify-between gap-4"
          >
            <div className="flex items-center gap-2.5">
              <AlertCircle size={18} className="text-rose-600 shrink-0" />
              <span>{loadError}</span>
            </div>
            <button
              type="button"
              onClick={loadOrders}
              disabled={loading}
              className="px-4 py-1.5 rounded-xl bg-white border border-rose-300 hover:bg-rose-100 text-xs font-semibold text-rose-800 transition cursor-pointer"
            >
              Try Again
            </button>
          </div>
        )}

        {/* ========================================== */}
        {/* LOADING SKELETONS */}
        {/* ========================================== */}
        {loading && serverOrders.length === 0 ? (
          <div className="space-y-6">
            {[1, 2, 3].map((n) => (
              <div
                key={n}
                className="bg-white rounded-[2.5rem] border border-slate-200/80 p-6 sm:p-8 shadow-xs animate-pulse space-y-6"
              >
                <div className="flex justify-between items-center pb-4 border-b border-slate-100">
                  <div className="space-y-2">
                    <div className="h-5 w-40 bg-slate-200 rounded-lg" />
                    <div className="h-3 w-64 bg-slate-100 rounded-lg" />
                  </div>
                  <div className="h-7 w-24 bg-slate-200 rounded-xl" />
                </div>
                <div className="grid grid-cols-4 gap-2">
                  {[1, 2, 3, 4].map((s) => (
                    <div key={s} className="h-16 bg-slate-100 rounded-2xl" />
                  ))}
                </div>
                <div className="space-y-3">
                  <div className="h-4 w-3/4 bg-slate-100 rounded-lg" />
                  <div className="h-4 w-1/2 bg-slate-100 rounded-lg" />
                </div>
              </div>
            ))}
          </div>
        ) : filteredOrders.length === 0 ? (
          /* ========================================== */
          /* EMPTY STATE (Phase 3 Requested Copy) */
          /* ========================================== */
          <div className="bg-white rounded-[2.5rem] border border-slate-200/80 p-12 sm:p-16 text-center shadow-xs max-w-xl mx-auto space-y-6">
            <div className="w-20 h-20 rounded-3xl bg-blue-50 text-[#245BE7] flex items-center justify-center mx-auto shadow-inner border border-blue-100/60">
              <Package size={36} />
            </div>

            <div>
              <h2 className="text-2xl sm:text-3xl font-semibold text-[#181818] tracking-tight">
                {serverOrders.length === 0
                  ? "Your tech journey starts here."
                  : "No matching orders found."}
              </h2>
              <p className="text-sm text-slate-500 mt-2 leading-relaxed">
                {serverOrders.length === 0
                  ? "Explore the latest gear and find something you'll love."
                  : "Try clearing your search query or selecting a different status filter."}
              </p>
            </div>

            <div className="pt-2 flex flex-wrap justify-center gap-3">
              {serverOrders.length === 0 ? (
                <Link
                  href="/shop"
                  className="px-7 py-3.5 rounded-2xl bg-[#245BE7] hover:bg-blue-700 text-white text-xs font-semibold shadow-lg shadow-blue-600/20 transition active:scale-98 inline-flex items-center gap-2"
                >
                  Explore Products <ArrowRight size={15} />
                </Link>
              ) : (
                <button
                  type="button"
                  onClick={() => {
                    setStatusFilter("all");
                    setSearchQuery("");
                  }}
                  className="px-6 py-3 rounded-2xl bg-slate-900 hover:bg-[#245BE7] text-white text-xs font-semibold transition cursor-pointer"
                >
                  Clear Filters &amp; Search
                </button>
              )}
            </div>
          </div>
        ) : (
          /* ========================================== */
          /* ORDER CARDS LIST */
          /* ========================================== */
          <div className="space-y-6">
            {filteredOrders.map((order) => {
              const cancelled = order.status.toLowerCase() === "cancelled";
              const activeStep = getStepIndex(order.status);
              const paymentMeta = getOrderPaymentPresentation(order);

              return (
                <article
                  key={order.id}
                  className="bg-white rounded-[2.5rem] border border-slate-200/80 p-6 sm:p-8 shadow-xs hover:border-blue-200/80 transition space-y-6"
                >
                  {/* Order Top Header */}
                  <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-100">
                    <div>
                      <div className="flex flex-wrap items-center gap-2.5">
                        <h2 className="text-lg font-semibold text-[#181818]">
                          Order #{order.id}
                        </h2>

                        {/* Separate Order Status Badge */}
                        <span
                          className={`px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wider inline-flex items-center gap-1.5 ${
                            cancelled
                              ? "bg-rose-50 text-rose-700 border border-rose-200"
                              : order.status.toLowerCase() === "delivered"
                              ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
                              : order.status.toLowerCase() === "shipped"
                              ? "border border-sky bg-brand-soft text-blue-800"
                              : "bg-blue-50 text-[#245BE7] border border-blue-200"
                          }`}
                        >
                          {order.status.toLowerCase() === "delivered" && (
                            <CheckCircle2 size={12} />
                          )}
                          {order.status.toLowerCase() === "shipped" && (
                            <Truck size={12} />
                          )}
                          {cancelled && <XCircle size={12} />}
                          Status: {paymentMeta.orderStatusLabel}
                        </span>

                        {/* Separate Payment Status Badge */}
                        <span
                          className={`px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wider border ${
                            paymentMeta.isPaid
                              ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                              : "bg-amber-50 text-amber-800 border-amber-200"
                          }`}
                        >
                          Payment: {paymentMeta.paymentStatusLabel}
                        </span>
                      </div>

                      <p className="text-xs text-slate-400 mt-1.5 flex flex-wrap items-center gap-2">
                        <span className="flex items-center gap-1">
                          <Clock size={12} />
                          {new Date(order.created_at).toLocaleDateString(undefined, {
                            year: "numeric",
                            month: "short",
                            day: "numeric",
                          })}
                        </span>
                        <span>•</span>
                        <span>{order.payment_method}</span>
                      </p>
                    </div>

                    <div className="text-right">
                      <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 block">
                        {paymentMeta.totalLabel}
                      </span>
                      <span className="text-2xl font-semibold font-mono text-[#245BE7]">
                        ${Number(order.total).toFixed(2)}
                      </span>
                    </div>
                  </div>

                  {/* Confirmed Status Tracking Progress */}
                  {cancelled ? (
                    <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-800 text-xs font-bold flex items-center gap-2.5">
                      <XCircle size={16} className="text-rose-600 shrink-0" />
                      <span>This order was cancelled by the store administrator.</span>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <div className="grid grid-cols-4 gap-2">
                        {[
                          { label: "Order Placed", icon: ShoppingBag },
                          { label: "Preparing", icon: Package },
                          { label: "Dispatched", icon: Truck },
                          { label: "Delivered", icon: CheckCircle2 },
                        ].map((step, idx) => {
                          const Icon = step.icon;
                          const done = idx <= activeStep;
                          const isCurrent = idx === activeStep;
                          return (
                            <div
                              key={step.label}
                              className={`p-3 rounded-2xl border text-center transition ${
                                done
                                  ? isCurrent
                                    ? "border-[#245BE7] bg-blue-50/80 text-[#245BE7] ring-2 ring-[#245BE7]/20 font-semibold"
                                    : "border-blue-200 bg-blue-50/50 text-[#245BE7] font-bold"
                                  : "border-slate-100 bg-slate-50 text-slate-400"
                              }`}
                            >
                              <Icon size={18} className="mx-auto mb-1 shrink-0" />
                              <span className="text-[11px] block truncate">
                                {step.label}
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* Line Items List with Thumbnails */}
                  <div className="space-y-3 divide-y divide-slate-100">
                    {order.items.map((item) => {
                      const img = getItemImage(item.product_id, item.product_name);
                      return (
                        <div
                          key={item.id}
                          className="pt-3 first:pt-0 flex items-center justify-between gap-4"
                        >
                          <div className="flex items-center gap-3 min-w-0">
                            <img
                              src={img}
                              alt={item.product_name}
                              onError={applyProductImageFallback}
                              loading="lazy"
                              width={48}
                              height={48}
                              className="w-12 h-12 rounded-xl object-contain bg-slate-50 border border-slate-100 p-1 shrink-0"
                            />
                            <div className="min-w-0">
                              <p className="text-xs font-semibold text-[#181818] truncate">
                                {item.product_name}
                              </p>
                              <p className="text-[11px] text-slate-400">
                                Qty: {item.quantity} × ${Number(item.price).toFixed(2)}
                              </p>
                            </div>
                          </div>

                          <span className="text-xs font-semibold font-mono text-[#181818] shrink-0">
                            ${Number(item.subtotal).toFixed(2)}
                          </span>
                        </div>
                      );
                    })}
                  </div>

                  {/* Footer Destination & Actions */}
                  <div className="pt-4 border-t border-slate-100 flex flex-wrap items-center justify-between gap-4">
                    <p className="text-xs text-slate-500 flex items-center gap-1.5 max-w-md">
                      <MapPin size={14} className="text-[#245BE7] shrink-0" />
                      <span className="truncate">{order.shipping_address}</span>
                    </p>

                    <div className="flex items-center gap-2.5">
                      <button
                        type="button"
                        onClick={() => setSelectedOrder(order)}
                        className="px-4 py-2 rounded-xl border border-slate-200 hover:border-slate-300 bg-white text-xs font-bold text-slate-700 inline-flex items-center gap-1.5 transition cursor-pointer active:scale-98"
                      >
                        <ExternalLink size={13} />
                        View Details &amp; Receipt
                      </button>

                      <button
                        type="button"
                        onClick={() => handleReorder(order)}
                        disabled={reorderingId === order.id}
                        className="px-4 py-2 rounded-xl bg-[#181818] hover:bg-[#245BE7] disabled:opacity-50 text-white text-xs font-semibold inline-flex items-center gap-1.5 transition cursor-pointer active:scale-98"
                      >
                        <ShoppingBag size={13} />
                        {reorderingId === order.id ? "Adding..." : "Buy Again"}
                      </button>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </div>

      {/* ========================================== */}
      {/* ORDER DETAILS & PRINTABLE RECEIPT MODAL */}
      {/* ========================================== */}
      {selectedOrder && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="order-details-title"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/50 backdrop-blur-xs animate-fadeIn"
        >
          {/* Backdrop dismiss */}
          <button
            type="button"
            aria-label="Close dialog"
            onClick={() => setSelectedOrder(null)}
            className="absolute inset-0 cursor-default"
          />

          <div className="relative w-full max-w-2xl bg-white rounded-[2.5rem] border border-slate-200 shadow-2xl overflow-hidden max-h-[90vh] flex flex-col z-10">
            {/* Modal Header */}
            <div className="px-6 sm:px-8 py-5 border-b border-slate-100 flex items-center justify-between">
              <div>
                <span className="text-[10px] font-semibold uppercase tracking-wider text-[#245BE7]">
                  Official Purchase Receipt
                </span>
                <h3
                  id="order-details-title"
                  className="text-lg font-semibold text-[#181818]"
                >
                  Order #{selectedOrder.id}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setSelectedOrder(null)}
                aria-label="Close details"
                className="w-9 h-9 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-600 flex items-center justify-center transition cursor-pointer"
              >
                <X size={18} />
              </button>
            </div>

            {/* Modal Scrollable Body */}
            <div className="p-6 sm:p-8 overflow-y-auto space-y-6">
              {/* Receipt Metadata Box */}
              <div className="p-5 rounded-2xl bg-slate-50 border border-slate-100 space-y-3 text-xs">
                <div className="flex justify-between items-center">
                  <span className="text-slate-500 font-semibold">Order Date</span>
                  <span className="font-bold text-[#181818]">
                    {new Date(selectedOrder.created_at).toLocaleString(undefined, {
                      dateStyle: "medium",
                      timeStyle: "short",
                    })}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-500 font-semibold">Order Status</span>
                  <span className="font-bold text-[#245BE7]">
                    {getOrderPaymentPresentation(selectedOrder).orderStatusLabel}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-500 font-semibold">Payment Method</span>
                  <span className="font-bold text-[#181818]">
                    {selectedOrder.payment_method}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-500 font-semibold">Payment Status</span>
                  <span className="font-bold text-emerald-700">
                    {getOrderPaymentPresentation(selectedOrder).paymentStatusLabel}
                  </span>
                </div>
                <div className="flex justify-between items-start pt-1 border-t border-slate-200/80">
                  <span className="text-slate-500 font-semibold">Delivery Address</span>
                  <span className="font-bold text-[#181818] text-right max-w-xs leading-relaxed">
                    {selectedOrder.shipping_address}
                  </span>
                </div>
              </div>

              {/* Items in this Order */}
              <div className="space-y-3">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Itemized Hardware ({selectedOrder.items.length})
                </h4>
                <div className="space-y-2.5 divide-y divide-slate-100">
                  {selectedOrder.items.map((item) => (
                    <div
                      key={item.id}
                      className="pt-2.5 first:pt-0 flex items-center justify-between text-xs"
                    >
                      <div>
                        <p className="font-semibold text-[#181818]">{item.product_name}</p>
                        <p className="text-[11px] text-slate-400">
                          {item.quantity} × ${Number(item.price).toFixed(2)}
                        </p>
                      </div>
                      <span className="font-mono font-bold text-[#181818]">
                        ${Number(item.subtotal).toFixed(2)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Financial Calculation Breakdown */}
              <div className="p-5 rounded-2xl bg-blue-50/40 border border-blue-100/60 space-y-2 text-xs text-slate-700">
                <div className="flex justify-between">
                  <span>Hardware Subtotal</span>
                  <span className="font-mono font-bold">
                    ${Number(selectedOrder.subtotal).toFixed(2)}
                  </span>
                </div>
                {Number(selectedOrder.discount_amount) > 0 && (
                  <div className="flex justify-between text-emerald-700 font-bold">
                    <span>
                      Promo Savings{" "}
                      {selectedOrder.coupon_code ? `(${selectedOrder.coupon_code})` : ""}
                    </span>
                    <span className="font-mono">
                      -${Number(selectedOrder.discount_amount).toFixed(2)}
                    </span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span>Standard Courier Shipping</span>
                  <span className="font-mono font-bold">
                    {Number(selectedOrder.shipping_fee) === 0
                      ? "FREE"
                      : `$${Number(selectedOrder.shipping_fee).toFixed(2)}`}
                  </span>
                </div>
                <div className="pt-2 border-t border-blue-200/80 flex justify-between items-center text-sm font-semibold text-[#181818]">
                  <span>Total Amount</span>
                  <span className="font-mono text-lg text-[#245BE7]">
                    ${Number(selectedOrder.total).toFixed(2)}
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-2 text-[11px] text-slate-400">
                <ShieldCheck size={14} className="text-emerald-600" />
                Verified authentic order registered in Blue Panda backend.
              </div>
            </div>

            {/* Modal Footer Actions */}
            <div className="px-6 sm:px-8 py-4 border-t border-slate-100 bg-slate-50/50 flex flex-wrap items-center justify-between gap-3">
              <button
                type="button"
                onClick={handlePrintReceipt}
                className="px-4 py-2.5 rounded-xl border border-slate-200 bg-white hover:bg-slate-100 text-xs font-semibold text-slate-700 inline-flex items-center gap-2 transition cursor-pointer"
              >
                <Printer size={14} />
                Print Receipt
              </button>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => {
                    handleReorder(selectedOrder);
                    setSelectedOrder(null);
                  }}
                  className="px-5 py-2.5 rounded-xl bg-[#245BE7] hover:bg-blue-700 text-white text-xs font-semibold inline-flex items-center gap-1.5 transition cursor-pointer"
                >
                  <ShoppingBag size={14} />
                  Reorder All
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
