"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Bell,
  Check,
  ChevronDown,
  Copy,
  Heart,
  LayoutDashboard,
  LogOut,
  Menu,
  Package,
  Search,
  ShoppingBag,
  Store,
  Truck,
  User,
  X,
} from "lucide-react";
import {
  notificationsApi,
  type ApiNotification,
  type ApiUser,
} from "@/lib/api";
import { getCurrentUser, isLoggedIn, logout } from "@/lib/auth";
import { getCartTotals, useShopStore } from "@/lib/store";

const NAV_LINKS = [
  { href: "/shop", label: "Shop" },
  { href: "/categories", label: "Categories" },
  { href: "/deals", label: "Deals", badge: "SALE" },
  { href: "/stores", label: "Stores" },
];

export default function StoreNavbar() {
  const pathname = usePathname();
  const router = useRouter();

  const items = useShopStore((s) => s.items);
  const appliedCoupon = useShopStore((s) => s.appliedCoupon);
  const wishlist = useShopStore((s) => s.wishlist);
  const openCart = useShopStore((s) => s.openCart);
  const openSearch = useShopStore((s) => s.openSearch);
  const pushToast = useShopStore((s) => s.pushToast);
  const syncCartFromBackend = useShopStore((s) => s.syncCartFromBackend);
  const syncWishlistFromBackend = useShopStore(
    (s) => s.syncWishlistFromBackend
  );

  const [mounted, setMounted] = useState(false);
  const [user, setUser] = useState<ApiUser | null>(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [copiedCode, setCopiedCode] = useState(false);
  const [notifications, setNotifications] = useState<ApiNotification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);

  const userMenuRef = useRef<HTMLDivElement>(null);
  const notifMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMounted(true);
    const refreshAuth = () => {
      if (isLoggedIn()) {
        const current = getCurrentUser();
        setUser(current);
        syncCartFromBackend();
        syncWishlistFromBackend();
      } else {
        setUser(null);
        setNotifications([]);
        setUnreadCount(0);
      }
    };
    refreshAuth();
    window.addEventListener("auth-changed", refreshAuth);
    return () => window.removeEventListener("auth-changed", refreshAuth);
  }, [syncCartFromBackend, syncWishlistFromBackend]);

  // Load notifications if logged in
  useEffect(() => {
    if (!user) {
      setNotifications([]);
      setUnreadCount(0);
      return;
    }
    notificationsApi
      .getAll({ limit: 5 })
      .then((res) => {
        if (res.data) setNotifications(res.data);
        if (typeof res.unread_count === "number") {
          setUnreadCount(res.unread_count);
        } else if (res.data) {
          setUnreadCount(res.data.filter((n) => !n.read).length);
        }
      })
      .catch(() => {});
  }, [user]);

  // Outside click handler for dropdowns
  useEffect(() => {
    const handleOutside = (e: MouseEvent) => {
      if (
        userMenuRef.current &&
        !userMenuRef.current.contains(e.target as Node)
      ) {
        setUserMenuOpen(false);
      }
      if (
        notifMenuRef.current &&
        !notifMenuRef.current.contains(e.target as Node)
      ) {
        setNotifOpen(false);
      }
    };
    document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, []);

  const totals = getCartTotals(items, appliedCoupon);
  const cartCount = mounted ? totals.totalItems : 0;
  const wishlistCount = mounted ? wishlist.length : 0;

  const handleCopyPromo = () => {
    navigator.clipboard?.writeText("WELCOME10");
    setCopiedCode(true);
    pushToast({
      title: "Code WELCOME10 Copied!",
      description: "Use it at checkout for 10% OFF your order.",
      tone: "info",
    });
    window.setTimeout(() => setCopiedCode(false), 2200);
  };

  const handleLogout = () => {
    logout();
    setUserMenuOpen(false);
    pushToast({
      title: "Signed out",
      description: "See you again soon at Blue Panda!",
      tone: "info",
    });
    router.push("/");
  };

  const isStaff = user?.role === "admin" || user?.role === "seller";

  return (
    <>
      {/* Top Announcement Bar */}
      <div className="bg-slate-950 text-white text-xs">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 min-h-9 py-2 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-slate-200 font-medium">
            <Truck size={14} className="text-blue-400 shrink-0" />
            <span>Free delivery over $100</span>
            <span className="hidden sm:inline text-slate-600">•</span>
            <span className="hidden sm:inline">30-day returns</span>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={handleCopyPromo}
              className="hidden sm:inline-flex items-center gap-1.5 text-blue-300 hover:text-white font-bold transition cursor-pointer"
            >
              <span>WELCOME10</span>
              {copiedCode ? <Check size={12} /> : <Copy size={12} />}
            </button>
            {isStaff && (
              <Link
                href="/admin/dashboard"
                className="hidden sm:inline-flex items-center gap-1 text-blue-300 hover:text-white font-semibold transition"
              >
                <LayoutDashboard size={12} />
                Merchant Admin
              </Link>
            )}
          </div>
        </div>
      </div>

      {/* Main Sticky Glass Header */}
      <header className="sticky top-0 z-40 bg-white/92 backdrop-blur-xl border-b border-slate-200/70 shadow-[0_1px_0_rgba(15,23,42,0.02)]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-17 flex items-center justify-between gap-2 sm:gap-3">
          {/* Brand Logo */}
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setMobileMenuOpen((v) => !v)}
              aria-label="Toggle navigation menu"
              className="lg:hidden w-10 h-10 rounded-xl border border-slate-200 flex items-center justify-center text-slate-700 hover:bg-slate-50 cursor-pointer"
            >
              {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
            </button>

            <Link href="/" className="flex items-center gap-2.5 group">
              <img
                src="/images/logo_panda_blue.png"
                alt="Blue Panda Logo"
                width={42}
                height={42}
                className="w-10.5 h-10.5 rounded-2xl object-cover shadow-md shadow-blue-600/20 group-hover:scale-105 transition-transform"
              />
              <div className="hidden sm:block">
                <span className="text-lg font-extrabold tracking-tight text-slate-900 block leading-none">
                  Blue<span className="text-blue-600">Panda</span>
                </span>
                <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400 block mt-0.5">
                  Official Store
                </span>
              </div>
            </Link>
          </div>

          {/* Desktop Navigation */}
          <nav className="hidden lg:flex items-center gap-1">
            {NAV_LINKS.map((link) => {
              const active = pathname.startsWith(link.href);
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`px-3.5 py-2 rounded-xl text-sm font-bold transition-all inline-flex items-center gap-1.5 ${
                    active
                      ? "bg-slate-950 text-white shadow-sm"
                      : "text-slate-600 hover:text-slate-950 hover:bg-slate-100"
                  }`}
                >
                  {link.label}
                  {link.badge && (
                    <span className="px-1.5 py-0.5 rounded-md bg-rose-500 text-white text-[9px] font-extrabold leading-none">
                      {link.badge}
                    </span>
                  )}
                </Link>
              );
            })}
          </nav>

          {/* Right Actions */}
          <div className="flex items-center gap-2">
            {/* Search Pill */}
            <button
              type="button"
              onClick={openSearch}
              className="hidden md:flex items-center gap-2.5 pl-3.5 pr-2.5 py-2 rounded-2xl bg-slate-100 hover:bg-slate-200/70 text-slate-500 text-xs font-medium transition w-48 xl:w-60 justify-between cursor-pointer"
            >
              <span className="inline-flex items-center gap-2 truncate">
                <Search size={15} className="text-slate-400 shrink-0" />
                Search products
              </span>
              <kbd className="px-1.5 py-0.5 text-[10px] font-bold bg-white text-slate-500 rounded-md border border-slate-200">
                ⌘K
              </kbd>
            </button>

            <button
              type="button"
              onClick={openSearch}
              aria-label="Search store"
              className="md:hidden w-10 h-10 rounded-xl hover:bg-slate-100 flex items-center justify-center text-slate-700 cursor-pointer"
            >
              <Search size={19} />
            </button>

            {/* Wishlist */}
            <Link
              href="/wishlist"
              aria-label="Wishlist"
              className="relative w-10 h-10 rounded-xl hover:bg-slate-100 hidden sm:flex items-center justify-center text-slate-700 transition"
            >
              <Heart size={19} />
              {wishlistCount > 0 && (
                <span className="absolute top-1 right-1 min-w-4.5 h-4.5 px-1 rounded-full bg-rose-500 text-white text-[10px] font-extrabold flex items-center justify-center">
                  {wishlistCount}
                </span>
              )}
            </Link>

            {/* Notifications (when logged in) */}
            {mounted && user && (
              <div className="relative" ref={notifMenuRef}>
                <button
                  type="button"
                  onClick={() => setNotifOpen((v) => !v)}
                  aria-label="Notifications"
                  className="relative w-10 h-10 rounded-xl hover:bg-slate-100 flex items-center justify-center text-slate-700 transition cursor-pointer"
                >
                  <Bell size={19} />
                  {unreadCount > 0 && (
                    <span className="absolute top-1 right-1 min-w-4.5 h-4.5 px-1 rounded-full bg-blue-600 text-white text-[10px] font-extrabold flex items-center justify-center">
                      {unreadCount > 9 ? "9+" : unreadCount}
                    </span>
                  )}
                </button>

                {notifOpen && (
                  <div className="absolute right-0 mt-2 w-80 rounded-2xl bg-white shadow-2xl border border-slate-200 py-2 z-50">
                    <div className="px-4 py-2 border-b border-slate-100 flex items-center justify-between">
                      <span className="text-xs font-extrabold text-slate-900">
                        Updates & Alerts
                      </span>
                      <Link
                        href="/account?tab=notifications"
                        onClick={() => setNotifOpen(false)}
                        className="text-xs font-bold text-blue-600 hover:underline"
                      >
                        View all
                      </Link>
                    </div>
                    <div className="max-h-72 overflow-y-auto divide-y divide-slate-50">
                      {notifications.length === 0 ? (
                        <p className="p-6 text-center text-xs text-slate-400">
                          You&apos;re all caught up!
                        </p>
                      ) : (
                        notifications.map((n) => (
                          <Link
                            key={n.id}
                            href={n.link || "/orders"}
                            onClick={() => setNotifOpen(false)}
                            className="block px-4 py-3 hover:bg-slate-50 transition"
                          >
                            <p className="text-xs font-bold text-slate-900 line-clamp-1">
                              {n.title}
                            </p>
                            <p className="text-xs text-slate-500 line-clamp-2 mt-0.5">
                              {n.message}
                            </p>
                          </Link>
                        ))
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Shopping Bag Pill */}
            <button
              type="button"
              onClick={openCart}
              className="h-10 px-3.5 rounded-2xl bg-slate-900 hover:bg-blue-600 text-white text-xs font-bold inline-flex items-center gap-2 shadow-sm transition-colors cursor-pointer"
            >
              <ShoppingBag size={16} />
              {mounted && cartCount > 0 ? (
                <>
                  <span className="hidden sm:inline">
                    ${totals.subtotal.toFixed(2)}
                  </span>
                  <span className="px-1.5 py-0.5 rounded-full bg-blue-500 text-white text-[10px] font-extrabold">
                    {cartCount}
                  </span>
                </>
              ) : (
                <span className="hidden sm:inline">Bag</span>
              )}
            </button>

            {/* User Profile / Sign In */}
            {mounted && user ? (
              <div className="relative" ref={userMenuRef}>
                <button
                  type="button"
                  onClick={() => setUserMenuOpen((v) => !v)}
                  className="h-10 pl-2 pr-2.5 rounded-2xl border border-slate-200 hover:border-slate-300 bg-white flex items-center gap-2 transition cursor-pointer"
                >
                  <div className="w-7 h-7 rounded-xl bg-blue-600 text-white text-xs font-extrabold flex items-center justify-center">
                    {user.name?.charAt(0).toUpperCase() || "U"}
                  </div>
                  <span className="hidden xl:block text-xs font-bold text-slate-800 max-w-24 truncate">
                    {user.name.split(" ")[0]}
                  </span>
                  <ChevronDown size={14} className="text-slate-400" />
                </button>

                {userMenuOpen && (
                  <div className="absolute right-0 mt-2 w-60 rounded-2xl bg-white shadow-2xl border border-slate-200 py-2 z-50">
                    <div className="px-4 py-2.5 border-b border-slate-100">
                      <p className="text-sm font-extrabold text-slate-900 truncate">
                        {user.name}
                      </p>
                      <p className="text-xs text-slate-400 truncate">
                        {user.email}
                      </p>
                    </div>
                    <div className="py-1">
                      <Link
                        href="/account"
                        onClick={() => setUserMenuOpen(false)}
                        className="flex items-center gap-2.5 px-4 py-2 text-xs font-bold text-slate-700 hover:bg-slate-50"
                      >
                        <User size={15} className="text-blue-600" />
                        My Account & Addresses
                      </Link>
                      <Link
                        href="/orders"
                        onClick={() => setUserMenuOpen(false)}
                        className="flex items-center gap-2.5 px-4 py-2 text-xs font-bold text-slate-700 hover:bg-slate-50"
                      >
                        <Package size={15} className="text-blue-600" />
                        My Orders & Receipts
                      </Link>
                      <Link
                        href="/wishlist"
                        onClick={() => setUserMenuOpen(false)}
                        className="flex items-center gap-2.5 px-4 py-2 text-xs font-bold text-slate-700 hover:bg-slate-50"
                      >
                        <Heart size={15} className="text-rose-500" />
                        Saved Wishlist
                      </Link>
                      {isStaff && (
                        <Link
                          href="/admin/dashboard"
                          onClick={() => setUserMenuOpen(false)}
                          className="flex items-center gap-2.5 px-4 py-2 text-xs font-bold text-indigo-700 bg-indigo-50/60 hover:bg-indigo-50"
                        >
                          <LayoutDashboard size={15} />
                          Switch to Admin Portal
                        </Link>
                      )}
                    </div>
                    <div className="pt-1 border-t border-slate-100">
                      <button
                        type="button"
                        onClick={handleLogout}
                        className="w-full flex items-center gap-2.5 px-4 py-2 text-xs font-bold text-rose-600 hover:bg-rose-50 cursor-pointer"
                      >
                        <LogOut size={15} />
                        Sign Out
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <Link
                href="/login"
                aria-label="Sign in"
                className="h-10 px-2.5 sm:px-4 rounded-xl sm:rounded-2xl border border-slate-200 hover:border-blue-600 hover:text-blue-600 text-slate-800 text-xs font-bold inline-flex items-center gap-1.5 transition"
              >
                <User size={15} />
                <span className="hidden sm:inline">Sign In</span>
              </Link>
            )}
          </div>
        </div>

        {/* Mobile Slide-Down Navigation */}
        {mobileMenuOpen && (
          <div className="lg:hidden border-t border-slate-100 bg-white px-4 py-4 space-y-1.5">
            {NAV_LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setMobileMenuOpen(false)}
                className="flex items-center justify-between px-3.5 py-2.5 rounded-xl text-sm font-bold text-slate-700 hover:bg-blue-50 hover:text-blue-600"
              >
                <span>{link.label}</span>
                {link.badge && (
                  <span className="px-2 py-0.5 rounded-md bg-rose-500 text-white text-[10px] font-extrabold">
                    {link.badge}
                  </span>
                )}
              </Link>
            ))}
            <div className="pt-2 mt-2 border-t border-slate-100 flex items-center gap-2">
              <Link
                href="/wishlist"
                onClick={() => setMobileMenuOpen(false)}
                className="flex-1 py-2.5 text-center rounded-xl bg-rose-50 text-xs font-bold text-rose-700"
              >
                Wishlist
              </Link>
              <Link
                href="/orders"
                onClick={() => setMobileMenuOpen(false)}
                className="flex-1 py-2.5 text-center rounded-xl bg-slate-100 text-xs font-bold text-slate-800"
              >
                Track Order
              </Link>
            </div>
            <div className="flex items-center gap-2">
              <Link
                href="/account"
                onClick={() => setMobileMenuOpen(false)}
                className="flex-1 py-2.5 text-center rounded-xl bg-slate-100 text-xs font-bold text-slate-800"
              >
                My Account
              </Link>
              <Link
                href="/admin/dashboard"
                onClick={() => setMobileMenuOpen(false)}
                className="flex-1 py-2.5 text-center rounded-xl bg-blue-50 text-xs font-bold text-blue-700 inline-flex items-center justify-center gap-1"
              >
                <Store size={13} /> Admin / POS
              </Link>
            </div>
          </div>
        )}
      </header>
    </>
  );
}
