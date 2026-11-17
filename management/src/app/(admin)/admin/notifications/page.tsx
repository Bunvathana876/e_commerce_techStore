"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  Bell,
  ShoppingCart,
  Package,
  Star,
  AlertTriangle,
  Check,
  CheckCheck,
  Trash2,
  Users,
  CreditCard,
  RefreshCw,
  Settings,
  X,
  Clock,
  Filter,
  BellOff,
  Info,
  Sparkles,
} from "lucide-react";
import { statsApi, ordersApi, reviewsApi, notificationsApi } from "@/lib/api";
import type { ApiOrder, ApiReview, DashboardStats, ApiNotification } from "@/lib/api";
import {
  AUTH_KEY, TOKEN_KEY, USER_KEY,
  getAccessToken, getCurrentUserId, getSessionEpoch,
} from "@/lib/auth";
import {
  loadAdminFeed,
  isSameAdminNotificationSession,
  mutatePersonalAdminFeed,
  mutatePersonalAdminNotification,
} from "@/lib/admin-notification-feed";

// ─── Types ─────────────────────────────────────────────────────────────────

type NotificationType =
  | "order"
  | "delivery"
  | "promo"
  | "stock"
  | "review"
  | "payment"
  | "user"
  | "system";

interface Notification {
  id: string;
  type: NotificationType;
  title: string;
  message: string;
  time: string;
  timestamp: number;
  read: boolean;
  link?: string;
  source: "live" | "system";
  scope: "personal" | "shared" | "summary";
  recipientId: number | null;
}

// ─── Helpers ────────────────────────────────────────────────────────────────

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days === 1) return "Yesterday";
  return `${days} days ago`;
}

function isSameDay(ts: number, referenceTs: number): boolean {
  const a = new Date(ts);
  const b = new Date(referenceTs);
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

// ─── Icon helpers ────────────────────────────────────────────────────────────

const TYPE_META: Record<
  NotificationType,
  { icon: React.ReactNode; bg: string; dot: string; label: string }
> = {
  order: {
    icon: <ShoppingCart size={18} className="text-blue-600" />,
    bg: "bg-blue-50",
    dot: "bg-blue-500",
    label: "Orders",
  },
  delivery: {
    icon: <Package size={18} className="text-emerald-600" />,
    bg: "bg-emerald-50",
    dot: "bg-emerald-500",
    label: "Delivery",
  },
  promo: {
    icon: <Sparkles size={18} className="text-purple-600" />,
    bg: "bg-purple-50",
    dot: "bg-purple-500",
    label: "Promo",
  },
  stock: {
    icon: <AlertTriangle size={18} className="text-amber-600" />,
    bg: "bg-amber-50",
    dot: "bg-amber-500",
    label: "Stock",
  },
  review: {
    icon: <Star size={18} className="text-violet-600" />,
    bg: "bg-violet-50",
    dot: "bg-violet-500",
    label: "Reviews",
  },
  payment: {
    icon: <CreditCard size={18} className="text-emerald-600" />,
    bg: "bg-emerald-50",
    dot: "bg-emerald-500",
    label: "Payments",
  },
  user: {
    icon: <Users size={18} className="text-sky-600" />,
    bg: "bg-sky-50",
    dot: "bg-sky-500",
    label: "Users",
  },
  system: {
    icon: <Bell size={18} className="text-gray-500" />,
    bg: "bg-gray-50",
    dot: "bg-gray-400",
    label: "System",
  },
};

const FILTER_TABS = [
  "All",
  "Unread",
  "Orders",
  "Stock",
  "Reviews",
  "Payments",
  "System",
] as const;

// ─── Component ───────────────────────────────────────────────────────────────

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [filter, setFilter] = useState<string>("All");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<string | null>(null);

  // Settings stored in localStorage
  const [settings, setSettings] = useState({
    orders: true,
    stock: true,
    reviews: true,
    payments: true,
    users: true,
    system: true,
  });
  const [todayTs] = useState(() => Date.now());

  // ── Load settings from localStorage ──────────────────────────────────────
  useEffect(() => {
    try {
      const saved = localStorage.getItem("notif_settings");
      if (saved) setSettings(JSON.parse(saved));
    } catch {}
  }, []);

  const saveSettings = (next: typeof settings) => {
    setSettings(next);
    localStorage.setItem("notif_settings", JSON.stringify(next));
  };

  // ── Build notifications from live API data ────────────────────────────────
  const buildNotifications = useCallback(
    (
      orders: ApiOrder[],
      reviews: ApiReview[],
      liveStats: DashboardStats | null
    ): Notification[] => {
      const list: Notification[] = [];

      // --- Pending orders → "order" notifications
      if (settings.orders) {
        orders
          .filter((o) => o.status === "pending")
          .slice(0, 5)
          .forEach((o) => {
            const customerName = o.user?.name ?? `User #${o.user_id}`;
            const total = parseFloat(String(o.total)).toFixed(2);
            list.push({
              id: `order-${o.id}`,
              type: "order",
              title: "New Order Received",
              message: `Order #${o.id} from ${customerName} — $${total}`,
              time: timeAgo(o.created_at),
              timestamp: new Date(o.created_at).getTime(),
              read: false,
              link: `/admin/orders/${o.id}`,
              source: "live",
              scope: "summary",
              recipientId: null,
            });
          });

        // Processing orders
        orders
          .filter((o) => o.status === "processing")
          .slice(0, 3)
          .forEach((o) => {
            list.push({
              id: `order-proc-${o.id}`,
              type: "order",
              title: "Order Processing",
              message: `Order #${o.id} is being prepared for shipment`,
              time: timeAgo(o.updated_at),
              timestamp: new Date(o.updated_at).getTime(),
              read: true,
              link: `/admin/orders/${o.id}`,
              source: "live",
              scope: "summary",
              recipientId: null,
            });
          });
      }

      // --- Pending reviews → "review" notifications
      if (settings.reviews) {
        reviews
          .filter((r) => r.status === "pending")
          .slice(0, 5)
          .forEach((r) => {
            const reviewer = r.user?.name ?? "A customer";
            const product = r.product?.name ?? "a product";
            const stars = "★".repeat(r.rating) + "☆".repeat(5 - r.rating);
            list.push({
              id: `review-${r.id}`,
              type: "review",
              title: "New Review Pending Approval",
              message: `${reviewer} left ${stars} on "${product}"`,
              time: timeAgo(r.created_at),
              timestamp: new Date(r.created_at).getTime(),
              read: false,
              link: `/admin/reviews/${r.id}`,
              source: "live",
              scope: "summary",
              recipientId: null,
            });
          });
      }

      // --- Low stock → "stock" notifications
      if (settings.stock && liveStats) {
        if (liveStats.out_of_stock_count > 0) {
          list.push({
            id: "stock-oos",
            type: "stock",
            title: "Products Out of Stock",
            message: `${liveStats.out_of_stock_count} product${liveStats.out_of_stock_count > 1 ? "s are" : " is"} out of stock`,
            time: "Now",
            timestamp: Date.now() - 60000,
            read: false,
            link: "/admin/products",
            source: "live",
            scope: "summary",
            recipientId: null,
          });
        }
        if (liveStats.low_stock_count > 0) {
          list.push({
            id: "stock-low",
            type: "stock",
            title: "Low Stock Alert",
            message: `${liveStats.low_stock_count} product${liveStats.low_stock_count > 1 ? "s have" : " has"} low inventory`,
            time: "Now",
            timestamp: Date.now() - 120000,
            read: liveStats.out_of_stock_count === 0,
            link: "/admin/products",
            source: "live",
            scope: "summary",
            recipientId: null,
          });
        }
      }

      // --- Revenue milestone → "payment" (system-generated, always)
      if (settings.payments && liveStats && liveStats.total_revenue > 0) {
        list.push({
          id: "revenue-summary",
          type: "payment",
          title: "Revenue Summary",
          message: `Total revenue reached $${liveStats.total_revenue.toFixed(2)} across ${liveStats.total_orders} orders`,
          time: "Today",
          timestamp: Date.now() - 3600000,
          read: true,
          link: "/admin/dashboard",
          source: "system",
          scope: "summary",
          recipientId: null,
        });
      }

      // --- System / reports
      if (settings.system && liveStats) {
        list.push({
          id: "sys-report",
          type: "system",
          title: "Store Overview Ready",
          message: `${liveStats?.total_products ?? 0} products, ${liveStats?.total_users ?? 0} customers, ${liveStats?.pending_orders_count ?? 0} orders pending`,
          time: "Today",
          timestamp: Date.now() - 7200000,
          read: true,
          link: "/admin/dashboard",
          source: "system",
          scope: "summary",
          recipientId: null,
        });
      }

      // Sort by timestamp desc
      return list.sort((a, b) => b.timestamp - a.timestamp);
    },
    [settings]
  );

  // ── Fetch live data ───────────────────────────────────────────────────────
  const fetchData = useCallback(
    async (silent = false) => {
      const session = {
        epoch: getSessionEpoch(), token: getAccessToken(), userId: getCurrentUserId(),
      };
      const isSameSession = () => isSameAdminNotificationSession(session, {
        epoch: getSessionEpoch(), token: getAccessToken(), userId: getCurrentUserId(),
      });
      if (!silent) setLoading(true);
      else setRefreshing(true);

      try {
        const [ordersRes, reviewsRes, statsRes, dbNotifsRes] = await Promise.allSettled([
          ordersApi.listAll(),
          reviewsApi.list({ status: "pending" }),
          statsApi.getOverview(),
          loadAdminFeed(
            () => notificationsApi.getAll({ limit: 50 }),
            session.userId ?? -1
          ),
        ]);
        if (!isSameSession()) return false;

        const orders =
          ordersRes.status === "fulfilled"
            ? (ordersRes.value.data as ApiOrder[]) ?? []
            : [];
        const reviews =
          reviewsRes.status === "fulfilled"
            ? (reviewsRes.value.data as ApiReview[]) ?? []
            : [];
        const liveStats =
          statsRes.status === "fulfilled"
            ? (statsRes.value.data as DashboardStats)
            : null;

        setStats(liveStats);

        const feed = dbNotifsRes.status === "fulfilled" ? dbNotifsRes.value : null;
        let finalNotifications: Notification[] = [];
        if (feed?.status === "ready") {
          finalNotifications = feed.notifications.map((n: ApiNotification) => ({
            id: String(n.id),
            type: (n.type as NotificationType) || "system",
            title: n.title,
            message: n.message,
            time: timeAgo(n.created_at),
            timestamp: new Date(n.created_at).getTime(),
            read: n.user_id === null || n.read,
            link: n.link || undefined,
            source: "live" as const,
            scope: n.user_id === null ? "shared" : "personal",
            recipientId: n.user_id,
          }));
          setErrorMessage(null);
        } else {
          // Live activity summaries remain visible but cannot mutate persisted notices.
          finalNotifications = buildNotifications(orders, reviews, liveStats).map(
            (n) => ({ ...n, read: true })
          );
          setErrorMessage(feed?.error ?? "Could not load notifications.");
          setSuccessMessage(null);
        }

        finalNotifications.sort((a, b) => b.timestamp - a.timestamp);
        setNotifications(finalNotifications);
        return feed?.status === "ready";
      } catch (error) {
        if (isSameSession()) {
          setNotifications([]);
          setErrorMessage(error instanceof Error ? error.message : "Could not load notifications.");
          setSuccessMessage(null);
        }
        return false;
      } finally {
        if (isSameSession()) {
          setLoading(false);
          setRefreshing(false);
        }
      }
    },
    [buildNotifications]
  );

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    const clearPrivateFeed = () => {
      setNotifications([]);
      setStats(null);
      setPendingAction(null);
      setSuccessMessage(null);
      setErrorMessage(null);
      setLoading(true);
      if (getAccessToken()) void fetchData();
    };
    const onStorage = (event: StorageEvent) => {
      if (event.key === AUTH_KEY || event.key === TOKEN_KEY || event.key === USER_KEY) {
        clearPrivateFeed();
      }
    };
    window.addEventListener("auth-changed", clearPrivateFeed);
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener("auth-changed", clearPrivateFeed);
      window.removeEventListener("storage", onStorage);
    };
  }, [fetchData]);

  // Refresh every 60s
  useEffect(() => {
    const t = setInterval(() => fetchData(true), 60000);
    return () => clearInterval(t);
  }, [fetchData]);

  // ── Actions ───────────────────────────────────────────────────────────────

  const refreshAfterMutation = async () => {
    if (!(await fetchData(true))) {
      throw new Error("Update saved, but the notification feed could not be refreshed.");
    }
  };

  const runAction = async (key: string, mutate: () => Promise<void>, success: string): Promise<boolean> => {
    if (pendingAction) return false;
    const session = {
      epoch: getSessionEpoch(), token: getAccessToken(), userId: getCurrentUserId(),
    };
    const isSameSession = () => isSameAdminNotificationSession(session, {
      epoch: getSessionEpoch(), token: getAccessToken(), userId: getCurrentUserId(),
    });
    setPendingAction(key);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      await mutate();
      if (isSameSession()) {
        setSuccessMessage(success);
        return true;
      }
      return false;
    } catch (error) {
      if (isSameSession()) {
        setErrorMessage(error instanceof Error ? error.message : "Notification action failed.");
      }
      return false;
    } finally {
      if (isSameSession()) setPendingAction(null);
    }
  };

  const markAsRead = (id: string): Promise<boolean> => {
    const notification = notifications.find((item) => item.id === id);
    if (!notification || notification.scope !== "personal") return Promise.resolve(false);
    return runAction(`read-${id}`, () => mutatePersonalAdminNotification(
      { user_id: notification.recipientId }, getCurrentUserId() ?? -1,
      () => notificationsApi.markAsRead(Number(id)), refreshAfterMutation
    ), "Notification marked as read.");
  };

  const markAllAsRead = () => {
    void runAction("read-all", () => mutatePersonalAdminFeed(
      () => notificationsApi.markAllAsRead(), refreshAfterMutation
    ), "Personal notifications marked as read.");
  };

  const deleteNotification = (id: string) => {
    const notification = notifications.find((item) => item.id === id);
    if (!notification || notification.scope !== "personal") return;
    void runAction(`delete-${id}`, () => mutatePersonalAdminNotification(
      { user_id: notification.recipientId }, getCurrentUserId() ?? -1,
      () => notificationsApi.delete(Number(id)), refreshAfterMutation
    ), "Notification deleted.");
  };

  const clearAll = () => {
    void runAction("clear-all", () => mutatePersonalAdminFeed(
      () => notificationsApi.clearAll(), refreshAfterMutation
    ), "Personal notifications cleared.");
  };

  // ── Filter logic ──────────────────────────────────────────────────────────

  const filtered = notifications.filter((n) => {
    if (filter === "Unread") return !n.read;
    if (filter === "Orders") return n.type === "order" || n.type === "delivery";
    if (filter === "Stock") return n.type === "stock";
    if (filter === "Reviews") return n.type === "review";
    if (filter === "Payments") return n.type === "payment";
    if (filter === "System")
      return n.type === "system" || n.type === "user" || n.type === "promo";
    return true;
  });

  const unreadCount = notifications.filter((n) => n.scope === "personal" && !n.read).length;
  const personalCount = notifications.filter((n) => n.scope === "personal").length;
  const todayItems = filtered.filter((n) => isSameDay(n.timestamp, todayTs));
  const earlierItems = filtered.filter(
    (n) => !isSameDay(n.timestamp, todayTs)
  );

  // ── Render ────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="max-w-3xl mx-auto space-y-4">
        <div className="h-10 bg-gray-100 rounded-xl animate-pulse w-48" />
        <div className="h-24 bg-gray-100 rounded-2xl animate-pulse" />
        <div className="h-14 bg-gray-100 rounded-2xl animate-pulse" />
        {[...Array(4)].map((_, i) => (
          <div
            key={i}
            className="h-24 bg-gray-100 rounded-2xl animate-pulse"
          />
        ))}
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto space-y-5">
      {/* ── Header ─────────────────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-gray-900">Notifications</h1>
            {unreadCount > 0 && (
              <span className="px-2.5 py-0.5 text-xs font-bold bg-[#7699F0] text-white rounded-full animate-pulse">
                {unreadCount} new
              </span>
            )}
          </div>
          <p className="text-sm text-gray-500 mt-1">
            {errorMessage
              ? "Saved notifications are unavailable. Retry to see the current feed."
              : unreadCount > 0
              ? `${unreadCount} unread notification${unreadCount > 1 ? "s" : ""} — stay on top of your store`
              : "No unread personal notifications."}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => fetchData(true)}
            disabled={refreshing || pendingAction !== null}
            className="p-2 rounded-xl text-gray-500 hover:bg-gray-100 transition"
            title="Refresh"
          >
            <RefreshCw
              size={16}
              className={refreshing ? "animate-spin" : ""}
            />
          </button>
          <button
            onClick={() => setShowSettings(!showSettings)}
            className={`p-2 rounded-xl transition ${showSettings ? "bg-[#7699F0] text-white" : "text-gray-500 hover:bg-gray-100"}`}
            title="Notification settings"
          >
            <Settings size={16} />
          </button>
          {unreadCount > 0 && (
            <button
              onClick={markAllAsRead}
              disabled={pendingAction !== null}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-[#7699F0] bg-blue-50 rounded-xl hover:bg-blue-100 transition"
            >
              <CheckCheck size={15} />
              Mark all read
            </button>
          )}
          {personalCount > 0 && (
            <button
              onClick={clearAll}
              disabled={pendingAction !== null}
              className="inline-flex items-center gap-2 px-3 py-2 text-sm font-medium text-red-500 bg-red-50 rounded-xl hover:bg-red-100 transition"
            >
              <Trash2 size={15} />
              Clear personal
            </button>
          )}
        </div>
      </div>

      {errorMessage && (
        <div role="alert" className="flex items-center justify-between gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <span>{errorMessage} {notifications.some((n) => n.scope === "summary") && "Showing read-only live activity summaries."}</span>
          <button onClick={() => fetchData(true)} disabled={refreshing} className="font-semibold underline underline-offset-2">
            Retry
          </button>
        </div>
      )}
      {successMessage && !errorMessage && (
        <p role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          {successMessage}
        </p>
      )}
      {notifications.some((n) => n.scope === "shared") && (
        <p className="text-xs text-gray-500">Shared notices are read-only because read and delete state is global.</p>
      )}

      {/* ── Settings Panel ─────────────────────────────────────────────── */}
      {showSettings && (
        <div className="bg-white border border-gray-200 rounded-2xl p-5 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Settings size={16} className="text-gray-500" />
              <span className="font-semibold text-gray-800">
                Notification Preferences
              </span>
            </div>
            <button
              onClick={() => setShowSettings(false)}
              className="p-1 text-gray-400 hover:text-gray-600 transition"
            >
              <X size={16} />
            </button>
          </div>
          <p className="text-xs text-gray-500 mb-4">
            Choose which notifications appear on this page. Changes take effect
            on next refresh.
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {(
              Object.entries(settings) as [keyof typeof settings, boolean][]
            ).map(([key, val]) => {
              const meta =
                TYPE_META[key as NotificationType] ??
                TYPE_META.system;
              return (
                <label
                  key={key}
                  className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition select-none ${
                    val
                      ? "border-[#7699F0]/40 bg-blue-50/40"
                      : "border-gray-100 bg-gray-50"
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={val}
                    onChange={() =>
                      saveSettings({ ...settings, [key]: !val })
                    }
                    className="accent-[#7699F0] w-4 h-4 cursor-pointer"
                  />
                  <div
                    className={`w-7 h-7 rounded-lg flex items-center justify-center ${meta.bg}`}
                  >
                    {meta.icon}
                  </div>
                  <span className="text-sm font-medium capitalize text-gray-700">
                    {meta.label}
                  </span>
                </label>
              );
            })}
          </div>
        </div>
      )}

      {/* ── KPI Summary Bar ─────────────────────────────────────────────── */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            {
              label: "Pending Orders",
              value: stats.pending_orders_count ?? 0,
              icon: <ShoppingCart size={15} className="text-blue-600" />,
              bg: "bg-blue-50",
              alert: (stats.pending_orders_count ?? 0) > 0,
            },
            {
              label: "Pending Reviews",
              value: 0,
              icon: <Star size={15} className="text-violet-600" />,
              bg: "bg-violet-50",
              alert: false,
              override:
                notifications.filter(
                  (n) => n.type === "review" && !n.read
                ).length,
            },
            {
              label: "Low Stock",
              value: stats.low_stock_count,
              icon: <Package size={15} className="text-amber-600" />,
              bg: "bg-amber-50",
              alert: stats.low_stock_count > 0,
            },
            {
              label: "Unread",
              value: unreadCount,
              icon: <Bell size={15} className="text-[#7699F0]" />,
              bg: "bg-blue-50",
              alert: unreadCount > 0,
            },
          ].map((kpi) => (
            <div
              key={kpi.label}
              className="bg-white border border-gray-100 rounded-2xl p-4 shadow-sm"
            >
              <div className="flex items-center justify-between mb-2">
                <div
                  className={`w-8 h-8 rounded-lg flex items-center justify-center ${kpi.bg}`}
                >
                  {kpi.icon}
                </div>
                {kpi.alert && (
                  <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                )}
              </div>
              <p className="text-2xl font-bold text-gray-900">
                {kpi.override ?? kpi.value}
              </p>
              <p className="text-xs text-gray-500 mt-0.5">{kpi.label}</p>
            </div>
          ))}
        </div>
      )}

      {/* ── Filter Tabs ──────────────────────────────────────────────────── */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-3">
        <div className="flex items-center gap-2 mb-1">
          <Filter size={13} className="text-gray-400" />
          <span className="text-xs text-gray-400 font-medium">Filter by</span>
        </div>
        <div className="flex flex-wrap gap-2">
          {FILTER_TABS.map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3.5 py-1.5 text-xs font-medium rounded-lg transition-all ${
                filter === f
                  ? "bg-[#7699F0] text-white shadow-sm"
                  : "bg-gray-50 text-gray-600 hover:bg-gray-100"
              }`}
            >
              {f}
              {f === "Unread" && unreadCount > 0 && (
                <span className="ml-1.5 px-1.5 py-0.5 text-[10px] bg-white/30 rounded-full">
                  {unreadCount}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* ── Notification Groups ──────────────────────────────────────────── */}
      {filtered.length === 0 ? (
        <EmptyState filter={filter} />
      ) : (
        <div className="space-y-5">
          {todayItems.length > 0 && (
            <NotifGroup
              label="Today"
              items={todayItems}
              onRead={markAsRead}
              onDelete={deleteNotification}
              busy={pendingAction !== null}
            />
          )}
          {earlierItems.length > 0 && (
            <NotifGroup
              label="Earlier"
              items={earlierItems}
              onRead={markAsRead}
              onDelete={deleteNotification}
              busy={pendingAction !== null}
            />
          )}
        </div>
      )}

      {/* ── Footer info ──────────────────────────────────────────────────── */}
      {filtered.length > 0 && (
        <div className="flex items-center justify-center gap-2 text-xs text-gray-400 py-2">
          <Info size={12} />
          <span>
            Notifications refresh every 60 seconds.
          </span>
        </div>
      )}
    </div>
  );
}

// ─── Sub-components ──────────────────────────────────────────────────────────

function NotifGroup({
  label,
  items,
  onRead,
  onDelete,
  busy,
}: {
  label: string;
  items: Notification[];
  onRead: (id: string) => Promise<boolean>;
  onDelete: (id: string) => void;
  busy: boolean;
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-gray-500 uppercase tracking-wide">
          <Clock size={11} />
          {label}
        </div>
        <div className="flex-1 h-px bg-gray-100" />
        <span className="text-xs text-gray-400">{items.length}</span>
      </div>

      {items.map((n) => (
        <NotifCard key={n.id} notif={n} onRead={onRead} onDelete={onDelete} busy={busy} />
      ))}
    </div>
  );
}

function NotifCard({
  notif,
  onRead,
  onDelete,
  busy,
}: {
  notif: Notification;
  onRead: (id: string) => Promise<boolean>;
  onDelete: (id: string) => void;
  busy: boolean;
}) {
  const router = useRouter();
  const meta =
    (TYPE_META as Record<string, typeof TYPE_META.system>)[notif.type] ??
    TYPE_META.system;

  const handleCardClick = async () => {
    if (busy && notif.scope === "personal") return;
    if (notif.scope === "personal" && !notif.read) {
      if (!(await onRead(notif.id))) return;
    }
    if (notif.link) {
      let target = notif.link;
      if (target.startsWith("/orders")) {
        target = `/admin${target}`;
      }
      router.push(target);
    }
  };

  return (
    <div
      onClick={() => { void handleCardClick(); }}
      className={`group relative bg-white rounded-2xl border shadow-sm p-4 transition-all hover:shadow-md cursor-pointer ${
        notif.read
          ? "border-gray-100 hover:border-gray-200"
          : "border-[#7699F0]/25 bg-blue-50/20 hover:border-[#7699F0]/40"
      }`}
    >
      {/* Unread indicator strip */}
      {!notif.read && (
        <div className="absolute left-0 top-3 bottom-3 w-1 bg-[#7699F0] rounded-full" />
      )}

      <div className="flex items-start gap-4 pl-1">
        {/* Icon */}
        <div
          className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${meta.bg}`}
        >
          {meta.icon}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <p
                  className={`text-sm leading-snug ${
                    notif.read
                      ? "font-medium text-gray-800"
                      : "font-semibold text-gray-900"
                  }`}
                >
                  {notif.title}
                </p>
                {!notif.read && (
                  <span
                    className={`inline-block w-2 h-2 rounded-full flex-shrink-0 ${meta.dot}`}
                  />
                )}
                {/* Type badge */}
                <span className="px-1.5 py-0.5 text-[10px] font-medium rounded-md bg-gray-100 text-gray-500">
                  {meta.label}
                </span>
                {notif.scope === "shared" && (
                  <span className="px-1.5 py-0.5 text-[10px] font-medium rounded-md bg-slate-100 text-slate-600">
                    Shared
                  </span>
                )}
              </div>
              <p className="text-sm text-gray-500 mt-0.5 leading-relaxed truncate">
                {notif.message}
              </p>
              <p className="text-xs text-gray-400 mt-1.5 flex items-center gap-1">
                <Clock size={10} />
                {notif.time}
              </p>
            </div>

            {notif.scope === "personal" && <button
              onClick={(e) => {
                e.stopPropagation();
                onDelete(notif.id);
              }}
              disabled={busy}
              className="p-1.5 rounded-lg text-gray-300 hover:text-red-500 hover:bg-red-50 transition opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 flex-shrink-0"
              title="Remove"
            >
              <X size={14} />
            </button>}
          </div>

          {/* Actions row */}
          <div className="flex items-center gap-3 mt-3 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity">
            {notif.link && (
              <span className="text-xs font-medium text-[#7699F0] inline-flex items-center gap-1">
                View details →
              </span>
            )}
            {notif.scope !== "personal" && (
              <span className="ml-auto text-xs text-gray-400">
                {notif.scope === "shared" ? "Shared · read-only" : "Live summary"}
              </span>
            )}
            {notif.scope === "personal" && <div className="flex items-center gap-1 ml-auto">
              {!notif.read && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    void onRead(notif.id);
                  }}
                  disabled={busy}
                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium text-emerald-600 bg-emerald-50 hover:bg-emerald-100 transition"
                  title="Mark as read"
                >
                  <Check size={12} />
                  Mark read
                </button>
              )}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(notif.id);
                }}
                disabled={busy}
                className="p-1.5 rounded-lg text-gray-400 hover:text-red-600 hover:bg-red-50 transition"
                title="Delete"
              >
                <Trash2 size={13} />
              </button>
            </div>}
          </div>
        </div>
      </div>
    </div>
  );
}

function EmptyState({ filter }: { filter: string }) {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 py-20 text-center shadow-sm">
      <div className="w-16 h-16 rounded-2xl bg-gray-50 flex items-center justify-center mx-auto mb-4">
        <BellOff className="text-gray-300" size={30} />
      </div>
      <p className="text-gray-700 font-semibold">
        {filter === "All" ? "No notifications" : `No ${filter.toLowerCase()} notifications`}
      </p>
      <p className="text-sm text-gray-400 mt-1">
        {filter === "Unread"
          ? "You're all caught up — great work! 🎉"
          : "Nothing here for this filter."}
      </p>
    </div>
  );
}
