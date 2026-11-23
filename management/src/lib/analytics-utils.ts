import type { ApiOrder } from "./api";

export type AnalyticsDateRange = "7days" | "30days" | "90days" | "all";

export const ANALYTICS_RANGE_DAYS: Record<AnalyticsDateRange, number | null> = {
  "7days": 7,
  "30days": 30,
  "90days": 90,
  all: null,
};

export interface AnalyticsTopProduct {
  productId: number | null;
  productName: string;
  unitsSold: number;
  revenue: number;
}

export interface AnalyticsPeriodSummary {
  filteredOrders: ApiOrder[];
  activeOrders: ApiOrder[];
  cancelledCount: number;
  grossRevenue: number;
  totalOrders: number;
  avgOrderValue: number;
  topProducts: AnalyticsTopProduct[];
}

export function filterOrdersByRange(
  orders: ApiOrder[],
  dateRange: AnalyticsDateRange,
  nowMs: number = Date.now()
): ApiOrder[] {
  const days = ANALYTICS_RANGE_DAYS[dateRange];
  if (days == null) return orders;
  const cutoffMs = nowMs - days * 24 * 60 * 60 * 1000;
  return orders.filter((order) => {
    const ts = new Date(order.created_at).getTime();
    return Number.isFinite(ts) && ts >= cutoffMs && ts <= nowMs + 60_000;
  });
}

export function summarizeAnalyticsPeriod(
  orders: ApiOrder[],
  dateRange: AnalyticsDateRange,
  nowMs: number = Date.now()
): AnalyticsPeriodSummary {
  const filteredOrders = filterOrdersByRange(orders, dateRange, nowMs);
  const activeOrders = filteredOrders.filter(
    (o) => (o.status || "").toLowerCase() !== "cancelled"
  );
  const cancelledCount = filteredOrders.length - activeOrders.length;
  const grossRevenue = activeOrders.reduce(
    (sum, o) => sum + (Number(o.total) || 0),
    0
  );
  const totalOrders = filteredOrders.length;
  const avgOrderValue = activeOrders.length > 0 ? grossRevenue / activeOrders.length : 0;

  const productMap = new Map<string, AnalyticsTopProduct>();
  for (const order of activeOrders) {
    for (const item of order.items || []) {
      const key = item.product_id ? `id:${item.product_id}` : `name:${item.product_name}`;
      const existing = productMap.get(key);
      const qty = Number(item.quantity) || 0;
      const lineRevenue = Number(item.subtotal) || 0;
      if (existing) {
        existing.unitsSold += qty;
        existing.revenue += lineRevenue;
      } else {
        productMap.set(key, {
          productId: item.product_id ?? null,
          productName: item.product_name,
          unitsSold: qty,
          revenue: lineRevenue,
        });
      }
    }
  }

  const topProducts = Array.from(productMap.values())
    .sort((a, b) => b.revenue - a.revenue || b.unitsSold - a.unitsSold)
    .slice(0, 6);

  return {
    filteredOrders,
    activeOrders,
    cancelledCount,
    grossRevenue,
    totalOrders,
    avgOrderValue,
    topProducts,
  };
}
