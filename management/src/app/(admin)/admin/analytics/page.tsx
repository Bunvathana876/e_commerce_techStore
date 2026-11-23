"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import Link from "next/link";
import {
  AlertCircle,
  TrendingUp,
  Calendar,
  Loader2,
  Package,
  RefreshCw,
  ShoppingCart,
  DollarSign,
} from "lucide-react";
import { ordersApi, productsApi, ApiOrder, ApiProduct } from "@/lib/api";
import {
  summarizeAnalyticsPeriod,
  type AnalyticsDateRange,
} from "@/lib/analytics-utils";

const RANGE_LABELS: Record<AnalyticsDateRange, string> = {
  "7days": "Last 7 days",
  "30days": "Last 30 days",
  "90days": "Last 90 days",
  all: "All time",
};

export default function AnalyticsPage() {
  const [dateRange, setDateRange] = useState<AnalyticsDateRange>("30days");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [orders, setOrders] = useState<ApiOrder[]>([]);
  const [products, setProducts] = useState<ApiProduct[]>([]);

  const loadAnalytics = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const [ordersRes, productsRes] = await Promise.all([
        ordersApi.list(),
        productsApi.list(),
      ]);

      if (!ordersRes.success || !Array.isArray(ordersRes.data)) {
        throw new Error(ordersRes.message || "Unable to load order analytics.");
      }
      setOrders(ordersRes.data);
      if (productsRes.success && productsRes.data) {
        setProducts(productsRes.data.items);
      }
    } catch (err: unknown) {
      setLoadError(
        err instanceof Error ? err.message : "Failed to load analytics from server."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadAnalytics();
  }, [loadAnalytics]);

  const period = useMemo(
    () => summarizeAnalyticsPeriod(orders, dateRange),
    [orders, dateRange]
  );

  return (
    <div className="space-y-6 pb-10">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Store Analytics</h1>
          <p className="text-sm text-gray-500 mt-1">
            Order conversion and revenue breakdown ({RANGE_LABELS[dateRange]})
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <div className="relative">
            <Calendar
              size={16}
              aria-hidden="true"
              className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
            />
            <label htmlFor="analytics-date-range" className="sr-only">
              Select analytics date range
            </label>
            <select
              id="analytics-date-range"
              value={dateRange}
              onChange={(e) => setDateRange(e.target.value as AnalyticsDateRange)}
              className="pl-9 pr-8 py-2.5 text-sm bg-white border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#7699F0] appearance-none"
            >
              <option value="7days">Last 7 days</option>
              <option value="30days">Last 30 days</option>
              <option value="90days">Last 90 days</option>
              <option value="all">All time</option>
            </select>
          </div>

          <button
            type="button"
            onClick={() => void loadAnalytics()}
            disabled={loading}
            aria-label="Refresh analytics"
            className="p-2.5 rounded-xl bg-white border border-gray-200 text-gray-600 hover:bg-gray-50 disabled:opacity-50"
          >
            <RefreshCw size={16} className={loading ? "animate-spin" : ""} aria-hidden="true" />
          </button>
        </div>
      </div>

      {loading ? (
        <div className="py-24 flex flex-col items-center justify-center text-[#7699F0]">
          <Loader2 size={36} className="animate-spin mb-3" aria-hidden="true" />
          <p className="text-sm font-medium text-gray-600">
            Calculating analytics from PostgreSQL...
          </p>
        </div>
      ) : loadError ? (
        <div role="alert" className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-center space-y-3">
          <AlertCircle size={24} className="mx-auto text-rose-600" aria-hidden="true" />
          <p className="text-sm font-semibold text-rose-800">{loadError}</p>
          <button
            type="button"
            onClick={() => void loadAnalytics()}
            className="px-4 py-2 rounded-xl bg-white border border-rose-200 text-sm font-semibold text-rose-700 hover:bg-rose-100"
          >
            Retry
          </button>
        </div>
      ) : (
        <>
          {/* KPI Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-white rounded-2xl border border-gray-100 p-5 shadow-sm">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-500">Gross Sales</span>
                <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
                  <DollarSign size={20} aria-hidden="true" />
                </div>
              </div>
              <p className="text-2xl font-bold text-gray-900 mt-2">
                ${period.grossRevenue.toFixed(2)}
              </p>
              <p className="text-xs text-emerald-600 font-medium mt-1">
                {period.activeOrders.length} active orders ({RANGE_LABELS[dateRange]})
              </p>
            </div>

            <div className="bg-white rounded-2xl border border-gray-100 p-5 shadow-sm">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-500">Total Orders</span>
                <div className="w-10 h-10 rounded-xl bg-blue-50 text-[#7699F0] flex items-center justify-center">
                  <ShoppingCart size={20} aria-hidden="true" />
                </div>
              </div>
              <p className="text-2xl font-bold text-gray-900 mt-2">{period.totalOrders}</p>
              <p className="text-xs text-blue-600 font-medium mt-1">
                {period.cancelledCount} cancelled in period
              </p>
            </div>

            <div className="bg-white rounded-2xl border border-gray-100 p-5 shadow-sm">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-500">Avg. Order Value</span>
                <div className="w-10 h-10 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center">
                  <TrendingUp size={20} aria-hidden="true" />
                </div>
              </div>
              <p className="text-2xl font-bold text-gray-900 mt-2">
                ${period.avgOrderValue.toFixed(2)}
              </p>
              <p className="text-xs text-purple-600 font-medium mt-1">
                Per non-cancelled order
              </p>
            </div>

            <div className="bg-white rounded-2xl border border-gray-100 p-5 shadow-sm">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-500">Catalog Size</span>
                <div className="w-10 h-10 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center">
                  <Package size={20} aria-hidden="true" />
                </div>
              </div>
              <p className="text-2xl font-bold text-gray-900 mt-2">
                {products.length} Items
              </p>
              <p className="text-xs text-amber-600 font-medium mt-1">Active catalog inventory</p>
            </div>
          </div>

          {/* Breakdown & Top Selling Items */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Top Selling Products in Period */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="font-semibold text-gray-900">
                  Top Selling Products ({RANGE_LABELS[dateRange]})
                </h2>
                <Link
                  href="/admin/products"
                  className="text-xs font-semibold text-[#7699F0] hover:underline"
                >
                  View All Products →
                </Link>
              </div>

              {period.topProducts.length === 0 ? (
                <p className="text-sm text-gray-500 py-8 text-center">
                  No non-cancelled product sales recorded in this date window.
                </p>
              ) : (
                <div className="divide-y divide-gray-100">
                  {period.topProducts.map((item) => (
                    <div
                      key={`${item.productId ?? "x"}-${item.productName}`}
                      className="py-3 flex items-center justify-between"
                    >
                      <div>
                        <p className="text-sm font-semibold text-gray-900">{item.productName}</p>
                        <p className="text-xs text-gray-400">{item.unitsSold} units sold</p>
                      </div>
                      <span className="font-semibold text-gray-900 text-sm">
                        ${item.revenue.toFixed(2)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Order Fulfillment Status Breakdown */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-4">
              <h2 className="font-semibold text-gray-900">
                Order Fulfillment Distribution ({RANGE_LABELS[dateRange]})
              </h2>
              <div className="space-y-3 pt-2">
                {[
                  {
                    status: "Delivered",
                    count: period.filteredOrders.filter((o) => o.status === "delivered").length,
                    color: "bg-emerald-500",
                  },
                  {
                    status: "Shipped",
                    count: period.filteredOrders.filter((o) => o.status === "shipped").length,
                    color: "bg-blue-500",
                  },
                  {
                    status: "Processing",
                    count: period.filteredOrders.filter((o) => o.status === "processing").length,
                    color: "bg-indigo-500",
                  },
                  {
                    status: "Pending",
                    count: period.filteredOrders.filter((o) => o.status === "pending").length,
                    color: "bg-amber-500",
                  },
                  {
                    status: "Cancelled",
                    count: period.cancelledCount,
                    color: "bg-red-500",
                  },
                ].map((item) => {
                  const percent =
                    period.totalOrders > 0
                      ? ((item.count / period.totalOrders) * 100).toFixed(1)
                      : "0";
                  return (
                    <div key={item.status} className="space-y-1">
                      <div className="flex justify-between text-xs font-medium">
                        <span className="text-gray-700">{item.status}</span>
                        <span className="text-gray-500">
                          {item.count} orders ({percent}%)
                        </span>
                      </div>
                      <div className="h-2 w-full bg-gray-100 rounded-full overflow-hidden">
                        <div
                          className={`h-full ${item.color} rounded-full transition-all`}
                          style={{ width: `${percent}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
