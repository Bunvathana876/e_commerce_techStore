"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { usePathname, useRouter } from "next/navigation";
import {
  Bell,
  ChevronDown,
  Heart,
  LayoutDashboard,
  LogOut,
  Menu,
  Package,
  Search,
  ShoppingBag,
  Store,
  User,
  X,
} from "lucide-react";
import {
  notificationsApi,
  type ApiNotification,
  type ApiUser,
} from "@/lib/api";
import { getCurrentUser, isLoggedIn, logoutFromServer } from "@/lib/auth";
import { getCartTotals, useShopStore } from "@/lib/store";

const NAV_LINKS = [
  { href: "/shop", label: "Shop" },
  { href: "/categories", label: "Categories" },
  { href: "/new-arrivals", label: "New Arrivals" },
  { href: "/deals", label: "Deals" },
];

export default function StoreNavbar() {
  const pathname = usePathname();
  const router = useRouter();
  const items = useShopStore((state) => state.items);
  const appliedCoupon = useShopStore((state) => state.appliedCoupon);
  const wishlist = useShopStore((state) => state.wishlist);
  const openCart = useShopStore((state) => state.openCart);
  const openSearch = useShopStore((state) => state.openSearch);
  const pushToast = useShopStore((state) => state.pushToast);
  const syncCartFromBackend = useShopStore((state) => state.syncCartFromBackend);
  const syncWishlistFromBackend = useShopStore(
    (state) => state.syncWishlistFromBackend
  );

  const [mounted, setMounted] = useState(false);
  const [user, setUser] = useState<ApiUser | null>(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [notificationMenuOpen, setNotificationMenuOpen] = useState(false);
  const [notifications, setNotifications] = useState<ApiNotification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);

  const userMenuRef = useRef<HTMLDivElement>(null);
  const notificationMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMounted(true);
    const refreshAuth = () => {
      if (isLoggedIn()) {
        const current = getCurrentUser();
        setUser(current);
        void syncCartFromBackend();
        void syncWishlistFromBackend();
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

  useEffect(() => {
    if (!user) return;

    notificationsApi
      .getAll({ limit: 5 })
      .then((response) => {
        const list = response.data ?? [];
        setNotifications(list);
        setUnreadCount(
          typeof response.unread_count === "number"
            ? response.unread_count
            : list.filter((notification) => !notification.read).length
        );
      })
      .catch(() => {
        setNotifications([]);
        setUnreadCount(0);
      });
  }, [user]);

  useEffect(() => {
    const handleOutsideClick = (event: MouseEvent) => {
      if (
        userMenuRef.current &&
        !userMenuRef.current.contains(event.target as Node)
      ) {
        setUserMenuOpen(false);
      }
      if (
        notificationMenuRef.current &&
        !notificationMenuRef.current.contains(event.target as Node)
      ) {
        setNotificationMenuOpen(false);
      }
    };
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMobileMenuOpen(false);
        setUserMenuOpen(false);
        setNotificationMenuOpen(false);
      }
    };

    document.addEventListener("mousedown", handleOutsideClick);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleOutsideClick);
      document.removeEventListener("keydown", handleEscape);
    };
  }, []);

  useEffect(() => {
    setMobileMenuOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!mobileMenuOpen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [mobileMenuOpen]);

  const totals = getCartTotals(items, appliedCoupon);
  const cartCount = mounted ? totals.totalItems : 0;
  const wishlistCount = mounted ? wishlist.length : 0;
  const isStaff = user?.role === "admin" || user?.role === "seller";
  const managementUrl =
    process.env.NEXT_PUBLIC_MANAGEMENT_URL || "http://localhost:3001";
  const staffDestination =
    user?.role === "seller"
      ? `${managementUrl}/seller`
      : `${managementUrl}/admin/dashboard`;

  const handleLogout = () => {
    void logoutFromServer();
    setUserMenuOpen(false);
    pushToast({
      title: "Signed out",
      description: "You are signed out on this browser.",
      tone: "info",
    });
    router.push("/");
  };

  const isActiveLink = (href: string) => {
    const baseHref = href.split("?")[0];
    return pathname === baseHref || pathname.startsWith(`${baseHref}/`);
  };

  return (
    <>
      <header className="sticky top-0 z-40 border-b border-line bg-paper/95 backdrop-blur supports-[backdrop-filter]:bg-paper/90">
        <div className="bp-container">
          <div className="flex h-(--header-h) items-center justify-between gap-3 sm:gap-4">
            {/* Mobile menu trigger */}
            <button
              type="button"
              onClick={() => setMobileMenuOpen((open) => !open)}
              aria-label={mobileMenuOpen ? "Close navigation" : "Open navigation"}
              aria-expanded={mobileMenuOpen}
              aria-controls="mobile-store-navigation"
              className="-ml-2 flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-ink transition-colors hover:bg-surface-subtle lg:hidden"
            >
              {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
            </button>

            {/* LEFT: Logo & Wordmark */}
            <Link
              href="/"
              className="group flex shrink-0 items-center gap-2.5"
              aria-label="Blue Panda Tech Store home"
            >
              <Image
                src="/images/logo_panda_blue.png"
                loading="eager"
                alt=""
                width={36}
                height={36}
                className="h-9 w-9 object-contain"
              />
              <span className="font-display hidden text-xl font-semibold tracking-tight text-ink min-[400px]:inline">
                Blue Panda
              </span>
            </Link>

            {/* CENTER: Navigation Links */}
            <nav
              aria-label="Store primary navigation"
              className="hidden items-center gap-8 lg:flex"
            >
              {NAV_LINKS.map((link) => {
                const active = isActiveLink(link.href);
                return (
                  <Link
                    key={link.href}
                    href={link.href}
                    aria-current={active ? "page" : undefined}
                    className={`relative inline-flex h-(--header-h) items-center text-sm font-medium transition-colors after:absolute after:inset-x-0 after:bottom-0 after:h-0.5 after:origin-left after:bg-ink after:transition-transform after:duration-200 ${
                      active
                        ? "text-ink after:scale-x-100"
                        : "text-ink-soft after:scale-x-0 hover:text-ink hover:after:scale-x-100"
                    }`}
                  >
                    {link.label}
                  </Link>
                );
              })}
            </nav>

            {/* RIGHT: Search, Wishlist, Account, Cart */}
            <div className="flex items-center gap-2 sm:gap-3">
              {/* Search Pill launcher */}
              <button
                type="button"
                onClick={openSearch}
                aria-label="Search products"
                className="group relative flex h-11 w-11 items-center justify-center gap-2 text-left text-sm text-muted transition-colors hover:text-ink sm:w-36 sm:justify-start sm:px-2 md:w-40"
              >
                <Search size={18} aria-hidden="true" className="shrink-0 text-ink sm:text-muted" />
                <span className="hidden truncate sm:inline">Search</span>
                <kbd className="ml-auto hidden rounded border border-line bg-white px-1.5 py-0.5 font-sans text-[11px] font-medium text-muted md:inline-block">
                  ⌘K
                </kbd>
              </button>

              {/* Wishlist Icon */}
              <Link
                href="/wishlist"
                aria-label={`Favorites${wishlistCount ? `, ${wishlistCount} items` : ""}`}
                className="relative hidden h-11 w-11 items-center justify-center rounded-xl text-ink transition-colors hover:bg-surface-subtle sm:flex"
              >
                <Heart size={20} aria-hidden="true" />
                {wishlistCount > 0 && (
                  <span className="absolute right-1 top-1 flex h-4.5 min-w-4.5 items-center justify-center rounded-full bg-ink px-1 text-[10px] font-bold text-white ring-2 ring-white">
                    {wishlistCount > 99 ? "99+" : wishlistCount}
                  </span>
                )}
              </Link>

              {/* Notifications (Logged in users) */}
              {mounted && user && (
                <div className="relative hidden md:block" ref={notificationMenuRef}>
                  <button
                    type="button"
                    onClick={() => setNotificationMenuOpen((open) => !open)}
                    aria-label={`Notifications${unreadCount ? `, ${unreadCount} unread` : ""}`}
                    aria-expanded={notificationMenuOpen}
                    aria-controls="store-notification-menu"
                    className="relative flex h-11 w-11 items-center justify-center rounded-xl text-ink transition-colors hover:bg-surface-subtle"
                  >
                    <Bell size={20} aria-hidden="true" />
                    {unreadCount > 0 && (
                      <span className="absolute right-1 top-1 flex h-4.5 min-w-4.5 items-center justify-center rounded-full bg-brand px-1 text-[10px] font-bold text-white ring-2 ring-white">
                        {unreadCount > 9 ? "9+" : unreadCount}
                      </span>
                    )}
                  </button>

                  {notificationMenuOpen && (
                    <div
                      id="store-notification-menu"
                      className="absolute right-0 mt-2 w-80 overflow-hidden rounded-2xl border border-line bg-white shadow-xl"
                    >
                      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
                        <span className="text-sm font-semibold text-slate-950">
                          Notifications
                        </span>
                        <Link
                          href="/account?tab=notifications"
                          onClick={() => setNotificationMenuOpen(false)}
                          className="text-xs font-semibold text-blue-700 hover:underline"
                        >
                          View all
                        </Link>
                      </div>
                      <div className="max-h-72 overflow-y-auto divide-y divide-slate-100">
                        {notifications.length === 0 ? (
                          <p className="p-6 text-center text-sm text-slate-500">
                            No new notifications.
                          </p>
                        ) : (
                          notifications.map((notification) => (
                            <Link
                              key={notification.id}
                              href={notification.link || "/orders"}
                              onClick={() => setNotificationMenuOpen(false)}
                              className="block px-4 py-3 transition-colors hover:bg-slate-50"
                            >
                              <p className="line-clamp-1 text-sm font-semibold text-slate-900">
                                {notification.title}
                              </p>
                              <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">
                                {notification.message}
                              </p>
                            </Link>
                          ))
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Account Dropdown or Sign In */}
              {mounted && user ? (
                <div className="relative" ref={userMenuRef}>
                  <button
                    type="button"
                    onClick={() => setUserMenuOpen((open) => !open)}
                    aria-label="Open account menu"
                    aria-expanded={userMenuOpen}
                    aria-controls="store-account-menu"
                    className="flex h-11 items-center gap-2 rounded-xl px-2 transition-colors hover:bg-surface-subtle"
                  >
                    <span className="flex h-7 w-7 items-center justify-center rounded-full bg-ink text-xs font-semibold text-white">
                      {user.name?.charAt(0).toUpperCase() || "U"}
                    </span>
                    <span className="hidden max-w-20 truncate text-xs font-semibold text-slate-800 xl:block">
                      {user.name.split(" ")[0]}
                    </span>
                    <ChevronDown size={13} className="hidden text-slate-400 sm:block" />
                  </button>

                  {userMenuOpen && (
                    <div
                      id="store-account-menu"
                      className="absolute right-0 mt-2 w-60 overflow-hidden rounded-2xl border border-line bg-white shadow-xl"
                    >
                      <div className="border-b border-slate-100 px-4 py-3">
                        <p className="truncate text-sm font-semibold text-slate-950">
                          {user.name}
                        </p>
                        <p className="mt-0.5 truncate text-xs text-slate-500">
                          {user.email}
                        </p>
                      </div>
                      <div className="p-2">
                        {[
                          { href: "/account", label: "My account", icon: User },
                          { href: "/orders", label: "My orders", icon: Package },
                          { href: "/wishlist", label: "Favorites", icon: Heart },
                        ].map((item) => {
                          const Icon = item.icon;
                          return (
                            <Link
                              key={item.href}
                              href={item.href}
                              onClick={() => setUserMenuOpen(false)}
                              className="flex min-h-11 items-center gap-2.5 rounded-xl px-3 text-sm font-medium text-ink hover:bg-surface-subtle"
                            >
                              <Icon size={16} /> {item.label}
                            </Link>
                          );
                        })}
                        {isStaff && (
                          <a
                            href={staffDestination}
                            onClick={() => setUserMenuOpen(false)}
                            className="flex min-h-11 items-center gap-2.5 rounded-xl px-3 text-sm font-medium text-ink hover:bg-surface-subtle"
                          >
                            <LayoutDashboard size={16} /> Management portal
                          </a>
                        )}
                      </div>
                      <div className="border-t border-slate-100 p-2">
                        <button
                          type="button"
                          onClick={handleLogout}
                          className="flex min-h-11 w-full items-center gap-2.5 rounded-xl px-3 text-sm font-medium text-rose-700 hover:bg-rose-50"
                        >
                          <LogOut size={16} /> Sign out
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <Link
                  href="/login"
                  aria-label="Sign in"
                  className="flex h-11 min-w-11 items-center justify-center gap-1.5 rounded-xl px-2 text-sm font-medium text-ink transition-colors hover:bg-surface-subtle sm:px-3"
                >
                  <User size={20} aria-hidden="true" />
                  <span className="hidden xl:inline">Sign in</span>
                </Link>
              )}

              {/* Cart Button */}
              <button
                type="button"
                onClick={openCart}
                aria-label={`Open shopping cart${cartCount ? `, ${cartCount} items` : ""}`}
                className="bp-press relative inline-flex h-11 min-w-11 items-center justify-center gap-2 border border-ink px-3 text-sm font-medium text-ink hover:bg-ink hover:text-white sm:px-4"
              >
                <ShoppingBag size={18} aria-hidden="true" />
                <span className="hidden sm:inline">Bag</span>
                {cartCount > 0 && (
                  <span className="bp-price flex h-5 min-w-5 items-center justify-center rounded-full bg-brand px-1 text-[11px] font-bold text-white">
                    {cartCount > 99 ? "99+" : cartCount}
                  </span>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Mobile Navigation Drawer */}
        {mobileMenuOpen && (
          <div className="absolute inset-x-0 top-full z-50 h-dvh animate-fade-in bg-ink/40 lg:hidden">
            <button
              type="button"
              aria-label="Close navigation"
              onClick={() => setMobileMenuOpen(false)}
              className="absolute inset-0"
            />
            <nav
              id="mobile-store-navigation"
              aria-label="Mobile store navigation"
              className="relative max-h-[calc(100dvh-var(--header-h)-2.25rem)] overflow-y-auto border-t border-line bg-white px-4 py-5 shadow-xl"
            >
              <div className="space-y-4">
                {/* Mobile Search Button */}
                <button
                  type="button"
                  onClick={() => {
                    setMobileMenuOpen(false);
                    openSearch();
                  }}
                  className="flex min-h-12 w-full items-center justify-between rounded-xl border border-line bg-paper px-4 text-sm text-muted transition-colors hover:border-line-strong"
                >
                  <span className="flex items-center gap-2">
                    <Search size={18} aria-hidden="true" />
                    <span>Search products</span>
                  </span>
                </button>

                {/* Primary Nav Links */}
                <div>
                  {NAV_LINKS.map((link) => {
                    const active = isActiveLink(link.href);
                    return (
                      <Link
                        key={link.href}
                        href={link.href}
                        aria-current={active ? "page" : undefined}
                        onClick={() => setMobileMenuOpen(false)}
                        className={`font-display flex min-h-14 items-center justify-between border-b border-line px-1 text-2xl font-semibold ${
                          active ? "text-brand" : "text-ink"
                        }`}
                      >
                        {link.label}
                        <ChevronDown size={18} aria-hidden="true" className="-rotate-90 text-muted" />
                      </Link>
                    );
                  })}
                </div>

                <div className="my-2" />

                {/* Bag & Saved Shortcuts */}
                <div className="space-y-1">
                  <Link
                    href="/wishlist"
                    onClick={() => setMobileMenuOpen(false)}
                    className="flex min-h-12 items-center justify-between rounded-xl px-1 text-[15px] font-medium text-ink"
                  >
                    <span className="flex items-center gap-3">
                      <Heart size={20} aria-hidden="true" className="text-muted" />
                      Wishlist
                    </span>
                    {wishlistCount > 0 && (
                      <span className="bp-price rounded-full bg-surface-subtle px-2 py-0.5 text-xs font-semibold text-ink">
                        {wishlistCount}
                      </span>
                    )}
                  </Link>

                  <button
                    type="button"
                    onClick={() => {
                      setMobileMenuOpen(false);
                      openCart();
                    }}
                    className="flex min-h-12 w-full items-center justify-between rounded-xl px-1 text-left text-[15px] font-medium text-ink"
                  >
                    <span className="flex items-center gap-3">
                      <ShoppingBag size={20} aria-hidden="true" className="text-muted" />
                      Shopping bag
                    </span>
                    {cartCount > 0 && (
                      <span className="bp-price rounded-full bg-ink px-2 py-0.5 text-xs font-semibold text-white">
                        {cartCount}
                      </span>
                    )}
                  </button>
                </div>

                <div className="my-2" />

                {/* Account Section */}
                {user ? (
                  <div className="space-y-3 rounded-2xl border border-line bg-paper p-4">
                    <div className="flex items-center gap-3">
                      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-ink text-sm font-semibold text-white">
                        {user.name?.charAt(0).toUpperCase() || "U"}
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-semibold text-ink">
                          {user.name}
                        </p>
                        <p className="truncate text-xs text-muted">
                          {user.email}
                        </p>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2 pt-1">
                      <Link
                        href="/account"
                        onClick={() => setMobileMenuOpen(false)}
                        className="flex min-h-11 items-center justify-center rounded-xl border border-line bg-white px-3 text-sm font-semibold text-ink"
                      >
                        Account
                      </Link>
                      <button
                        type="button"
                        onClick={handleLogout}
                        className="flex min-h-11 items-center justify-center rounded-xl border border-rose-200 bg-white px-3 text-sm font-semibold text-rose-700"
                      >
                        Sign Out
                      </button>
                    </div>

                    {isStaff && (
                      <a
                        href={staffDestination}
                        className="flex min-h-11 w-full items-center justify-center gap-2 rounded-xl border border-line bg-white px-3 text-sm font-medium text-ink"
                      >
                        <Store size={15} /> Management portal
                      </a>
                    )}
                  </div>
                ) : (
                  <div className="grid grid-cols-2 gap-2 pt-2">
                    <Link
                      href="/login"
                      onClick={() => setMobileMenuOpen(false)}
                      className="flex min-h-12 items-center justify-center rounded-xl bg-ink px-4 text-sm font-semibold text-white"
                    >
                      Sign in
                    </Link>
                    <Link
                      href="/register"
                      onClick={() => setMobileMenuOpen(false)}
                      className="flex min-h-12 items-center justify-center rounded-xl border border-line-strong px-4 text-sm font-semibold text-ink"
                    >
                      Create account
                    </Link>
                  </div>
                )}
              </div>
            </nav>
          </div>
        )}
      </header>
    </>
  );
}
