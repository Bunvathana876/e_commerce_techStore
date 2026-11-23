"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Store,
  ShieldCheck,
  Package,
  ShoppingCart,
  AlertTriangle,
  ArrowRight,
  Clock,
  DollarSign,
  RefreshCw,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import { sellerApi, type ApiSellerDashboard } from "@/lib/api";
import { getAccessToken, isTokenExpired, logout } from "@/lib/auth";

export default function SellerDashboardPage() {
  const router = useRouter();
  const [dashboard, setDashboard] = useState<ApiSellerDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadDashboard = useCallback(async () => {
    const token = getAccessToken();
    if (!token || isTokenExpired(token)) {
      logout();
      router.replace(`/login?redirect=${encodeURIComponent("/seller")}&expired=true`);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const res = await sellerApi.getDashboard();
      if (res.success && res.data) {
        setDashboard(res.data);
      } else {
        setError(res.message || "Unable to load seller dashboard.");
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to fetch seller dashboard.");
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[340px] gap-3">
        <div className="w-9 h-9 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
        <p className="text-sm font-medium text-slate-500">Loading your store dashboard…</p>
      </div>
    );
  }

  if (error || !dashboard) {
    return (
      <div className="max-w-xl mx-auto py-16 text-center space-y-4">
        <div className="w-14 h-14 rounded-2xl bg-rose-50 text-rose-600 flex items-center justify-center mx-auto">
          <XCircle size={28} />
        </div>
        <h1 className="text-xl font-bold text-slate-900">Unable to load Seller Dashboard</h1>
        <p className="text-sm text-slate-500">{error || "Store data unavailable."}</p>
        <button
          type="button"
          onClick={() => void loadDashboard()}
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold transition"
        >
          <RefreshCw size={15} />
          Retry
        </button>
      </div>
    );
  }

  const pendingActionCount = dashboard.pending_orders + dashboard.processing_orders;

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-8">
      {/* Header Banner */}
      <div className="relative overflow-hidden rounded-3xl bg-slate-950 text-white p-6 sm:p-8 shadow-xl border border-white/10">
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2.5 max-w-2xl">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-600/30 border border-blue-500/40 text-blue-200 text-xs font-bold uppercase tracking-wider">
              <ShieldCheck size={14} className="text-emerald-400" />
              Store Status: {dashboard.store_status}
            </div>
            <h1 className="text-2xl sm:text-3xl font-black tracking-tight text-white">
              {dashboard.store_name}
            </h1>
            <p className="text-slate-300 text-sm leading-relaxed">
              Monitor live revenue, fulfill customer orders containing your products, and watch low-stock alerts across your catalog.
            </p>
            <div className="flex flex-wrap items-center gap-4 pt-1 text-xs text-slate-400">
              <span className="flex items-center gap-1.5 font-medium">
                <Store size={14} className="text-blue-400" />
                Rating {Number(dashboard.rating).toFixed(2)} ★
              </span>
              <span className="w-1 h-1 rounded-full bg-slate-700" />
              <span className="flex items-center gap-1.5 font-medium">
                <Clock size={14} className="text-emerald-400" />
                {pendingActionCount} order(s) awaiting fulfillment
              </span>
            </div>
          </div>

          <div className="shrink-0 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => void loadDashboard()}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-white text-xs font-bold transition"
            >
              <RefreshCw size={14} />
              Refresh
            </button>
            <Link
              href="/seller/orders"
              className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold transition shadow-lg shadow-blue-600/30"
            >
              <span>Manage Orders</span>
              <ArrowRight size={14} />
            </Link>
          </div>
        </div>
      </div>

      {/* KPI Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-2xl border border-slate-200/80 p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
              Gross Revenue
            </span>
            <DollarSign size={18} className="text-emerald-600" />
          </div>
          <p className="text-2xl font-black text-slate-900 mt-2">
            ${Number(dashboard.gross_revenue).toFixed(2)}
          </p>
          <p className="text-xs text-slate-500 mt-1">
            Non-cancelled sales for your items
          </p>
        </div>

        <div className="bg-white rounded-2xl border border-slate-200/80 p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
              Total Orders
            </span>
            <ShoppingCart size={18} className="text-blue-600" />
          </div>
          <p className="text-2xl font-black text-slate-900 mt-2">
            {dashboard.total_orders}
          </p>
          <p className="text-xs text-slate-500 mt-1">
            {dashboard.pending_orders} pending · {dashboard.shipped_orders} shipped · {dashboard.delivered_orders} delivered
          </p>
        </div>

        <div className="bg-white rounded-2xl border border-slate-200/80 p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
              Catalog Products
            </span>
            <Package size={18} className="text-indigo-600" />
          </div>
          <p className="text-2xl font-black text-slate-900 mt-2">
            {dashboard.total_products}
          </p>
          <p className="text-xs text-slate-500 mt-1">
            {dashboard.active_products} active on storefront
          </p>
        </div>

        <div className="bg-white rounded-2xl border border-slate-200/80 p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
              Stock Alerts
            </span>
            <AlertTriangle size={18} className="text-amber-500" />
          </div>
          <p className="text-2xl font-black text-slate-900 mt-2">
            {dashboard.low_stock_products_count + dashboard.out_of_stock_products_count}
          </p>
          <p className="text-xs text-slate-500 mt-1">
            {dashboard.low_stock_products_count} low stock · {dashboard.out_of_stock_products_count} out of stock
          </p>
        </div>
      </div>

      {/* Recent Orders + Low Stock Items */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-white rounded-2xl border border-slate-200/80 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
            <div>
              <h2 className="font-bold text-slate-900">Recent Store Orders</h2>
              <p className="text-xs text-slate-500">Latest orders containing products from your store</p>
            </div>
            <Link
              href="/seller/orders"
              className="text-xs font-bold text-blue-600 hover:underline flex items-center gap-1"
            >
              View all <ArrowRight size={13} />
            </Link>
          </div>

          {dashboard.recent_orders.length === 0 ? (
            <div className="p-10 text-center text-sm text-slate-500">
              No customer orders have been placed for your products yet.
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {dashboard.recent_orders.map((order) => (
                <div key={order.id} className="px-6 py-4 flex items-center justify-between gap-4 hover:bg-slate-50/70 transition">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-slate-900 text-sm">Order #{order.id}</span>
                      <span className="px-2 py-0.5 rounded-full text-[11px] font-bold uppercase bg-blue-50 text-blue-700">
                        {order.status}
                      </span>
                    </div>
                    <p className="text-xs text-slate-500 mt-0.5 truncate">
                      {order.user?.name || `Customer #${order.user_id}`} · {order.seller_items.length} store item(s)
                    </p>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="font-bold text-slate-900 text-sm">
                      ${Number(order.seller_subtotal).toFixed(2)}
                    </p>
                    <p className="text-[11px] text-slate-400">
                      {new Date(order.created_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
            <div>
              <h2 className="font-bold text-slate-900">Inventory Watch</h2>
              <p className="text-xs text-slate-500">Products needing replenishment</p>
            </div>
            <Link
              href="/seller/products"
              className="text-xs font-bold text-blue-600 hover:underline"
            >
              Catalog
            </Link>
          </div>

          {dashboard.low_stock_items.length === 0 ? (
            <div className="p-8 text-center space-y-2">
              <CheckCircle2 size={24} className="text-emerald-500 mx-auto" />
              <p className="text-sm font-semibold text-slate-700">All products healthy</p>
              <p className="text-xs text-slate-500">Every product has 10+ units in stock.</p>
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {dashboard.low_stock_items.map((item) => (
                <div key={item.id} className="px-5 py-3.5 flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-slate-900 truncate">{item.name}</p>
                    <p className="text-xs text-slate-500">${Number(item.price).toFixed(2)}</p>
                  </div>
                  <span
                    className={`px-2.5 py-1 rounded-full text-xs font-bold shrink-0 ${
                      item.stock <= 0
                        ? "bg-rose-50 text-rose-700"
                        : "bg-amber-50 text-amber-700"
                    }`}
                  >
                    {item.stock <= 0 ? "Out of Stock" : `${item.stock} left`}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
