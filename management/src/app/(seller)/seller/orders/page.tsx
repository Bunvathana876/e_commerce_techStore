"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  MapPin,
  Package,
  RefreshCw,
  Search,
  ShieldAlert,
  ShoppingCart,
  Truck,
  X,
} from "lucide-react";
import {
  ordersApi,
  sellerApi,
  type ApiOrderTracking,
  type ApiSellerOrder,
} from "@/lib/api";
import { getAccessToken, isTokenExpired, logout } from "@/lib/auth";

const STATUS_FILTERS = [
  { label: "All Orders", value: "all" },
  { label: "Pending", value: "pending" },
  { label: "Processing", value: "processing" },
  { label: "Shipped", value: "shipped" },
  { label: "Delivered", value: "delivered" },
  { label: "Cancelled", value: "cancelled" },
];

export default function SellerOrdersPage() {
  const router = useRouter();
  const [orders, setOrders] = useState<ApiSellerOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const [statusFilter, setStatusFilter] = useState("all");
  const [searchInput, setSearchInput] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);

  const [updatingOrderId, setUpdatingOrderId] = useState<number | null>(null);

  // Tracking drawer state
  const [trackingOrder, setTrackingOrder] = useState<ApiSellerOrder | null>(null);
  const [trackingData, setTrackingData] = useState<ApiOrderTracking | null>(null);
  const [trackingLoading, setTrackingLoading] = useState(false);
  const [trackingSaving, setTrackingSaving] = useState(false);
  const [carrier, setCarrier] = useState("Blue Panda Express");
  const [trackingNumber, setTrackingNumber] = useState("");
  const [trackingUrl, setTrackingUrl] = useState("");
  const [shipmentStatus, setShipmentStatus] = useState("in_transit");
  const [location, setLocation] = useState("");
  const [eventDescription, setEventDescription] = useState("");

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3500);
  };

  const loadOrders = useCallback(async () => {
    const token = getAccessToken();
    if (!token || isTokenExpired(token)) {
      logout();
      router.replace(`/login?redirect=${encodeURIComponent("/seller/orders")}&expired=true`);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const res = await sellerApi.getOrders({
        page,
        limit: 10,
        status: statusFilter,
        search: searchQuery || undefined,
      });
      if (res.success && res.data) {
        setOrders(res.data.items);
        setTotal(res.data.total);
        setTotalPages(res.data.total_pages);
      } else {
        setError(res.message || "Failed to load orders.");
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load seller orders.");
    } finally {
      setLoading(false);
    }
  }, [page, router, searchQuery, statusFilter]);

  useEffect(() => {
    void loadOrders();
  }, [loadOrders]);

  const handleAdvanceStatus = async (order: ApiSellerOrder, nextStatus: "processing" | "shipped") => {
    setUpdatingOrderId(order.id);
    setError(null);
    try {
      await sellerApi.updateOrderStatus(order.id, { status: nextStatus });
      showToast(`Order #${order.id} marked as ${nextStatus}.`);
      await loadOrders();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unable to update order status.");
    } finally {
      setUpdatingOrderId(null);
    }
  };

  const openTrackingModal = async (order: ApiSellerOrder) => {
    setTrackingOrder(order);
    setTrackingLoading(true);
    try {
      const res = await ordersApi.getTracking(order.id);
      if (res.success && res.data) {
        setTrackingData(res.data);
        setCarrier(res.data.shipment?.carrier || "Blue Panda Express");
        setTrackingNumber(res.data.shipment?.tracking_number || "");
        setTrackingUrl(res.data.shipment?.tracking_url || "");
        setShipmentStatus(res.data.shipment?.status || "in_transit");
        setLocation("");
        setEventDescription("");
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unable to load tracking info.");
    } finally {
      setTrackingLoading(false);
    }
  };

  const handleSaveTracking = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!trackingOrder) return;
    setTrackingSaving(true);
    try {
      const res = await sellerApi.updateOrderTracking(trackingOrder.id, {
        carrier: carrier.trim(),
        tracking_number: trackingNumber.trim() || null,
        tracking_url: trackingUrl.trim() || null,
        status: shipmentStatus,
        location: location.trim() || null,
        event_description: eventDescription.trim() || null,
      });
      if (res.success && res.data) {
        setTrackingData(res.data);
        showToast(`Tracking updated for Order #${trackingOrder.id}.`);
        await loadOrders();
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unable to update tracking.");
    } finally {
      setTrackingSaving(false);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-10">
      {toast && (
        <div
          role="status"
          aria-live="polite"
          className="fixed bottom-6 right-6 z-50 bg-slate-900 text-white px-4 py-3 rounded-xl shadow-xl flex items-center gap-2.5 text-sm font-medium"
        >
          <CheckCircle2 size={18} className="text-emerald-400" />
          <span>{toast}</span>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Store Orders & Fulfillment</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Track orders containing your products, advance shipping status, and attach real carrier tracking numbers.
          </p>
        </div>

        <button
          type="button"
          onClick={() => void loadOrders()}
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white border border-slate-200 text-slate-700 text-xs font-bold hover:bg-slate-50 transition self-start"
        >
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      {/* Filters & Search */}
      <div className="bg-white rounded-2xl border border-slate-200/80 p-4 shadow-sm space-y-4">
        <div className="flex flex-wrap gap-2">
          {STATUS_FILTERS.map((f) => (
            <button
              key={f.value}
              type="button"
              onClick={() => {
                setStatusFilter(f.value);
                setPage(1);
              }}
              className={`px-3.5 py-2 rounded-xl text-xs font-bold transition ${
                statusFilter === f.value
                  ? "bg-blue-600 text-white shadow-sm"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            setSearchQuery(searchInput.trim());
            setPage(1);
          }}
          className="flex gap-2"
        >
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="search"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search by Order ID (#102), product name, buyer name, or address..."
              aria-label="Search seller orders"
              className="w-full pl-10 pr-4 py-2.5 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <button
            type="submit"
            className="px-5 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold transition"
          >
            Search
          </button>
        </form>
      </div>

      {error && (
        <div
          role="alert"
          className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-800 text-sm flex items-center gap-2.5"
        >
          <ShieldAlert size={18} className="shrink-0 text-rose-600" />
          <span>{error}</span>
        </div>
      )}

      {/* Orders List */}
      {loading ? (
        <div className="py-20 text-center">
          <div className="w-9 h-9 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-sm text-slate-500">Loading store orders…</p>
        </div>
      ) : orders.length === 0 ? (
        <div className="bg-white rounded-2xl border border-slate-200/80 p-12 text-center space-y-3">
          <ShoppingCart size={32} className="text-slate-300 mx-auto" />
          <h2 className="text-lg font-bold text-slate-900">No matching orders found</h2>
          <p className="text-sm text-slate-500">
            Orders containing your store&apos;s products will appear here as customers check out.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {orders.map((order) => {
            const st = order.status.toLowerCase();
            return (
              <div
                key={order.id}
                className="bg-white rounded-2xl border border-slate-200/80 shadow-sm p-5 sm:p-6 space-y-4"
              >
                <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-100 pb-4">
                  <div className="space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-base font-extrabold text-slate-900">
                        Order #{order.id}
                      </span>
                      <span className="px-2.5 py-0.5 rounded-full text-xs font-bold uppercase bg-blue-50 text-blue-700">
                        {order.status}
                      </span>
                      <span className="px-2.5 py-0.5 rounded-full text-xs font-bold uppercase bg-slate-100 text-slate-700">
                        {order.payment_method} · {order.payment_status}
                      </span>
                    </div>
                    <p className="text-xs text-slate-500 flex items-center gap-1.5">
                      <MapPin size={12} />
                      {order.user?.name || `Customer #${order.user_id}`} — {order.shipping_address}
                    </p>
                  </div>

                  <div className="text-right">
                    <p className="text-xs font-semibold text-slate-400">Your Store Subtotal</p>
                    <p className="text-lg font-black text-slate-900">
                      ${Number(order.seller_subtotal).toFixed(2)}
                    </p>
                    {order.shipment?.tracking_number && (
                      <p className="text-xs font-mono text-blue-600 mt-0.5">
                        {order.shipment.carrier}: {order.shipment.tracking_number}
                      </p>
                    )}
                  </div>
                </div>

                {/* Seller-owned items */}
                <div className="space-y-2">
                  {order.seller_items.map((item) => (
                    <div
                      key={item.id}
                      className="flex items-center justify-between text-sm bg-slate-50 rounded-xl px-3.5 py-2.5"
                    >
                      <div className="flex items-center gap-2.5 min-w-0">
                        <Package size={15} className="text-blue-600 shrink-0" />
                        <span className="font-semibold text-slate-800 truncate">{item.product_name}</span>
                        <span className="text-xs text-slate-500">× {item.quantity}</span>
                      </div>
                      <span className="font-bold text-slate-900">${Number(item.subtotal).toFixed(2)}</span>
                    </div>
                  ))}
                </div>

                {/* Fulfillment Actions */}
                <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                  {!order.can_update_status ? (
                    <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 px-3 py-1.5 rounded-lg">
                      Fulfillment actions are restricted because this order spans multiple sellers or your store is inactive.
                    </p>
                  ) : (
                    <div className="flex flex-wrap items-center gap-2">
                      {st === "pending" && (
                        <button
                          type="button"
                          disabled={updatingOrderId === order.id}
                          onClick={() => void handleAdvanceStatus(order, "processing")}
                          className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-xs font-bold transition"
                        >
                          {updatingOrderId === order.id ? "Updating…" : "Mark Processing"}
                        </button>
                      )}
                      {st === "processing" && (
                        <button
                          type="button"
                          disabled={updatingOrderId === order.id}
                          onClick={() => void handleAdvanceStatus(order, "shipped")}
                          className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-bold transition"
                        >
                          {updatingOrderId === order.id ? "Updating…" : "Mark Shipped"}
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => void openTrackingModal(order)}
                        className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-bold transition"
                      >
                        <Truck size={14} />
                        {order.shipment ? "Update Tracking" : "Add Tracking"}
                      </button>
                    </div>
                  )}

                  <span className="text-xs text-slate-400">
                    Placed {new Date(order.created_at).toLocaleString()}
                  </span>
                </div>
              </div>
            );
          })}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between pt-2">
              <p className="text-xs text-slate-500">
                Showing page {page} of {totalPages} ({total} total)
              </p>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className="p-2 rounded-xl border border-slate-200 bg-white disabled:opacity-40 hover:bg-slate-50"
                  aria-label="Previous orders page"
                >
                  <ChevronLeft size={16} />
                </button>
                <button
                  type="button"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  className="p-2 rounded-xl border border-slate-200 bg-white disabled:opacity-40 hover:bg-slate-50"
                  aria-label="Next orders page"
                >
                  <ChevronRight size={16} />
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tracking Editor Modal */}
      {trackingOrder && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="seller-tracking-modal-title"
          className="fixed inset-0 z-50 bg-slate-950/50 backdrop-blur-xs flex items-center justify-center p-4"
        >
          <div className="bg-white rounded-3xl max-w-lg w-full p-6 shadow-2xl space-y-5 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <h2 id="seller-tracking-modal-title" className="text-lg font-bold text-slate-900">
                  Shipment Tracking · Order #{trackingOrder.id}
                </h2>
                <p className="text-xs text-slate-500">
                  Customer visible courier & milestone updates
                </p>
              </div>
              <button
                type="button"
                onClick={() => setTrackingOrder(null)}
                aria-label="Close tracking modal"
                className="p-2 rounded-xl hover:bg-slate-100 text-slate-500"
              >
                <X size={18} />
              </button>
            </div>

            {trackingLoading ? (
              <div className="py-8 text-center text-sm text-slate-500">Loading shipment timeline…</div>
            ) : (
              <form onSubmit={handleSaveTracking} className="space-y-4">
                <div>
                  <label htmlFor="seller-track-carrier" className="block text-xs font-bold text-slate-700 mb-1">
                    Carrier *
                  </label>
                  <input
                    id="seller-track-carrier"
                    name="carrier"
                    type="text"
                    required
                    value={carrier}
                    onChange={(e) => setCarrier(e.target.value)}
                    className="w-full px-3.5 py-2.5 text-sm rounded-xl border border-slate-200 bg-slate-50"
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label htmlFor="seller-track-number" className="block text-xs font-bold text-slate-700 mb-1">
                      Tracking Number
                    </label>
                    <input
                      id="seller-track-number"
                      name="tracking_number"
                      type="text"
                      value={trackingNumber}
                      onChange={(e) => setTrackingNumber(e.target.value)}
                      placeholder="e.g. JT-88990011"
                      className="w-full px-3.5 py-2.5 text-sm rounded-xl border border-slate-200 bg-slate-50"
                    />
                  </div>
                  <div>
                    <label htmlFor="seller-track-status" className="block text-xs font-bold text-slate-700 mb-1">
                      Shipment Status *
                    </label>
                    <select
                      id="seller-track-status"
                      name="status"
                      value={shipmentStatus}
                      onChange={(e) => setShipmentStatus(e.target.value)}
                      className="w-full px-3.5 py-2.5 text-sm rounded-xl border border-slate-200 bg-slate-50"
                    >
                      <option value="label_created">Label Created</option>
                      <option value="picked_up">Picked Up</option>
                      <option value="in_transit">In Transit</option>
                      <option value="out_for_delivery">Out for Delivery</option>
                      <option value="delivered">Delivered</option>
                      <option value="exception">Exception</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label htmlFor="seller-track-url" className="block text-xs font-bold text-slate-700 mb-1">
                    Carrier Tracking URL
                  </label>
                  <input
                    id="seller-track-url"
                    name="tracking_url"
                    type="url"
                    value={trackingUrl}
                    onChange={(e) => setTrackingUrl(e.target.value)}
                    placeholder="https://..."
                    className="w-full px-3.5 py-2.5 text-sm rounded-xl border border-slate-200 bg-slate-50"
                  />
                </div>

                <div>
                  <label htmlFor="seller-track-location" className="block text-xs font-bold text-slate-700 mb-1">
                    Checkpoint Location
                  </label>
                  <input
                    id="seller-track-location"
                    name="location"
                    type="text"
                    value={location}
                    onChange={(e) => setLocation(e.target.value)}
                    placeholder="Phnom Penh Hub"
                    className="w-full px-3.5 py-2.5 text-sm rounded-xl border border-slate-200 bg-slate-50"
                  />
                </div>

                <div>
                  <label htmlFor="seller-track-desc" className="block text-xs font-bold text-slate-700 mb-1">
                    Update Note
                  </label>
                  <textarea
                    id="seller-track-desc"
                    name="event_description"
                    rows={2}
                    value={eventDescription}
                    onChange={(e) => setEventDescription(e.target.value)}
                    placeholder="Optional checkpoint note for customer..."
                    className="w-full px-3.5 py-2.5 text-sm rounded-xl border border-slate-200 bg-slate-50"
                  />
                </div>

                {trackingData && trackingData.events.length > 0 && (
                  <div className="pt-2 border-t border-slate-100 space-y-2">
                    <p className="text-xs font-bold uppercase tracking-wider text-slate-400">
                      Tracking History
                    </p>
                    <ul className="space-y-1.5 text-xs text-slate-600 max-h-36 overflow-y-auto">
                      {trackingData.events.map((ev, idx) => (
                        <li key={ev.id ?? idx} className="flex justify-between gap-2 bg-slate-50 rounded-lg px-3 py-1.5">
                          <span className="font-semibold text-slate-800">{ev.title}</span>
                          <span className="text-slate-400 shrink-0">
                            {new Date(ev.occurred_at).toLocaleDateString()}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="flex gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => setTrackingOrder(null)}
                    className="flex-1 py-2.5 rounded-xl border border-slate-200 text-slate-700 text-sm font-bold hover:bg-slate-50"
                  >
                    Close
                  </button>
                  <button
                    type="submit"
                    disabled={trackingSaving}
                    className="flex-1 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-bold"
                  >
                    {trackingSaving ? "Saving…" : "Save Tracking"}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
