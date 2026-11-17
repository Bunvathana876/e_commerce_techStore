"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  AlertCircle,
  ArrowRight,
  Bell,
  Check,
  Eye,
  EyeOff,
  Heart,
  KeyRound,
  LayoutDashboard,
  Lock,
  LogOut,
  Mail,
  MapPin,
  Package,
  Phone,
  Plus,
  ShieldCheck,
  ShoppingBag,
  Trash2,
  User,
} from "lucide-react";
import {
  addressesApi,
  authApi,
  notificationsApi,
  ordersApi,
  type ApiAddress,
  type ApiNotification,
  type ApiOrder,
  type ApiUser,
} from "@/lib/api";
import {
  getCurrentUser,
  isLoggedIn,
  logoutFromServer,
  saveAuthSession,
  getAccessToken,
} from "@/lib/auth";
import { useShopStore } from "@/lib/store";

function AccountHubContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const pushToast = useShopStore((s) => s.pushToast);
  const wishlistCount = useShopStore((s) => s.wishlist.length);
  const cartItemCount = useShopStore((s) =>
    s.items.reduce((sum, item) => sum + item.quantity, 0)
  );

  const [user, setUser] = useState<ApiUser | null>(null);
  const [orders, setOrders] = useState<ApiOrder[]>([]);
  const [activeTab, setActiveTab] = useState<
    "overview" | "profile" | "addresses" | "security" | "notifications"
  >("overview");

  // Profile fields
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [savingProfile, setSavingProfile] = useState(false);

  // Addresses
  const [addresses, setAddresses] = useState<ApiAddress[]>([]);
  const [addrName, setAddrName] = useState("");
  const [addrPhone, setAddrPhone] = useState("");
  const [addrLine, setAddrLine] = useState("");
  const [addrCity, setAddrCity] = useState("");
  const [addingAddress, setAddingAddress] = useState(false);

  // Password & Security
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showCurrentPw, setShowCurrentPw] = useState(false);
  const [showNewPw, setShowNewPw] = useState(false);
  const [showConfirmPw, setShowConfirmPw] = useState(false);
  const [savingPassword, setSavingPassword] = useState(false);
  const [securityError, setSecurityError] = useState<string | null>(null);

  // Notifications
  const [notifications, setNotifications] = useState<ApiNotification[]>([]);

  useEffect(() => {
    const tab = searchParams.get("tab");
    if (
      tab === "addresses" ||
      tab === "security" ||
      tab === "notifications" ||
      tab === "profile" ||
      tab === "overview"
    ) {
      setActiveTab(tab);
    }
  }, [searchParams]);

  useEffect(() => {
    if (!isLoggedIn()) return;
    const current = getCurrentUser();
    if (current) {
      setUser(current);
      setName(current.name || "");
      setPhone(current.phone || "");
      setAddrName(current.name || "");
      setAddrPhone(current.phone || "");
    }

    // Load actual user orders
    ordersApi
      .list()
      .then((res) => {
        if (res.data && Array.isArray(res.data)) {
          setOrders(res.data);
        }
      })
      .catch(() => {});

    // Load saved addresses
    addressesApi
      .list()
      .then((res) => {
        if (res.data) setAddresses(res.data);
      })
      .catch(() => {});

    // Load notifications
    notificationsApi
      .getAll({ limit: 20 })
      .then((res) => {
        if (res.data) setNotifications(res.data);
      })
      .catch(() => {});
  }, []);

  // Clear private account state immediately when auth state changes
  useEffect(() => {
    const handleAuthChange = () => {
      if (!isLoggedIn()) {
        setUser(null);
        setName("");
        setPhone("");
        setAddrName("");
        setAddrPhone("");
        setAddresses([]);
        setNotifications([]);
        setOrders([]);
      } else {
        const current = getCurrentUser();
        if (current) {
          setUser(current);
          setName(current.name || "");
          setPhone(current.phone || "");
          setAddrName(current.name || "");
          setAddrPhone(current.phone || "");
        }
      }
    };
    window.addEventListener("auth-changed", handleAuthChange);
    return () => window.removeEventListener("auth-changed", handleAuthChange);
  }, []);

  // ==========================================
  // UNAUTHENTICATED GUEST STATE
  // ==========================================
  if (!user) {
    return (
      <div className="min-h-[70vh] bg-[#F5F8FD]/60 flex items-center justify-center py-16 px-4">
        <div className="max-w-md w-full bg-white rounded-[2.5rem] border border-slate-200/80 p-8 sm:p-12 shadow-sm text-center space-y-6">
          <div className="w-20 h-20 rounded-3xl bg-blue-50 text-[#245BE7] flex items-center justify-center mx-auto shadow-inner border border-blue-100/60">
            <User size={36} />
          </div>

          <div>
            <h1 className="text-2xl sm:text-3xl font-semibold text-[#181818] tracking-tight">
              Sign In to Your Account
            </h1>
            <p className="text-sm text-slate-500 mt-2 leading-relaxed">
              Sign in to manage your saved shipping addresses, track hardware orders in real time, and curate your wishlist.
            </p>
          </div>

          <div className="flex flex-col sm:flex-row gap-3 pt-2">
            <Link
              href="/login?redirect=/account"
              className="flex-1 py-3.5 px-5 rounded-2xl bg-[#245BE7] hover:bg-blue-700 text-white text-xs font-semibold shadow-lg shadow-blue-600/20 transition active:scale-98 text-center"
            >
              Sign In
            </Link>
            <Link
              href="/register?redirect=/account"
              className="flex-1 py-3.5 px-5 rounded-2xl bg-slate-100 hover:bg-slate-200 text-[#181818] text-xs font-bold transition active:scale-98 text-center"
            >
              Create Account
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // Profile Save
  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingProfile(true);
    try {
      const res = await authApi.updateMe({ name: name.trim(), phone: phone.trim() });
      const token = getAccessToken();
      if (res.data && token) {
        saveAuthSession(token, res.data);
        setUser(res.data);
      }
      pushToast({
        title: "Profile Updated",
        description: "Your account details have been saved successfully.",
        tone: "success",
      });
    } catch (err: unknown) {
      pushToast({
        title: "Could not update profile",
        description: err instanceof Error ? err.message : "Please try again.",
        tone: "error",
      });
    } finally {
      setSavingProfile(false);
    }
  };

  const handleResetProfile = () => {
    if (user) {
      setName(user.name || "");
      setPhone(user.phone || "");
    }
  };

  // Address Management
  const handleCreateAddress = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!addrName.trim() || !addrLine.trim() || !addrCity.trim()) {
      pushToast({
        title: "Incomplete Address",
        description: "Please complete recipient name, address, and city.",
        tone: "error",
      });
      return;
    }

    setAddingAddress(true);
    try {
      const res = await addressesApi.create({
        full_name: addrName.trim(),
        phone: addrPhone.trim(),
        address_line: addrLine.trim(),
        city: addrCity.trim(),
        is_default: addresses.length === 0,
      });
      if (res.data) {
        setAddresses((prev) => [res.data, ...prev]);
        setAddrLine("");
        setAddrCity("");
        pushToast({
          title: "Address Saved",
          description: `${res.data.city} added to your delivery address book.`,
          tone: "success",
        });
      }
    } catch (err: unknown) {
      pushToast({
        title: "Could not save address",
        description: err instanceof Error ? err.message : "Backend unavailable.",
        tone: "error",
      });
    } finally {
      setAddingAddress(false);
    }
  };

  const handleDeleteAddress = async (id: number) => {
    try {
      await addressesApi.delete(id);
      setAddresses((prev) => prev.filter((a) => a.id !== id));
      pushToast({
        title: "Address Removed",
        description: "The address was deleted from your account.",
        tone: "info",
      });
    } catch {
      pushToast({
        title: "Could not delete address",
        description: "Please try again.",
        tone: "error",
      });
    }
  };

  // Password Security Change
  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setSecurityError(null);

    if (!currentPassword) {
      setSecurityError("Please enter your current password.");
      return;
    }

    if (newPassword.length < 6) {
      setSecurityError("New password must be at least 6 characters.");
      return;
    }

    if (newPassword !== confirmPassword) {
      setSecurityError("New passwords do not match. Please verify.");
      return;
    }

    setSavingPassword(true);
    try {
      await authApi.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      pushToast({
        title: "Password Changed",
        description: "Your password was updated. Please sign in with your new credentials.",
        tone: "success",
      });
      router.push("/login");
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message
          : "Password update failed. Check your current password.";
      setSecurityError(msg);
      pushToast({
        title: "Password update failed",
        description: msg,
        tone: "error",
      });
    } finally {
      setSavingPassword(false);
    }
  };

  const isStaff = user.role === "admin" || user.role === "seller";
  const staffDestination =
    user.role === "seller"
      ? `${process.env.NEXT_PUBLIC_MANAGEMENT_URL || "http://localhost:3001"}/seller`
      : `${process.env.NEXT_PUBLIC_MANAGEMENT_URL || "http://localhost:3001"}/admin/dashboard`;

  return (
    <div className="min-h-screen bg-[#F5F8FD]/60 pb-20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-8 sm:pt-10 space-y-8">
        {/* Page Editorial Header */}
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 pb-6 border-b border-slate-200/80">
          <div>
            <p className="bp-eyebrow">Account</p>
            <h1 className="mt-3 text-4xl font-bold text-ink sm:text-5xl">
              {user.name.split(" ")[0]}&apos;s account
            </h1>
            <p className="mt-4 max-w-xl text-base leading-7 text-muted">
              Your details, delivery addresses and sign-in options.
            </p>
          </div>

        </div>

        {/* Account Layout Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* Left Column: Sidebar & Profile Card */}
          <aside className="lg:col-span-4 bg-white rounded-[2.5rem] border border-slate-200/80 p-6 sm:p-7 shadow-xs space-y-6">
            {/* User Identity Card */}
            <div className="flex items-center gap-4 pb-6 border-b border-slate-100">
              <div aria-hidden="true"
                className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full bg-ink text-2xl font-semibold text-white">
                {user.name.charAt(0).toUpperCase()}
              </div>
              <div className="min-w-0 flex-1">
                <h2 className="text-base font-semibold text-[#181818] truncate">
                  {user.name}
                </h2>
                <p className="text-xs text-slate-500 truncate mt-0.5">{user.email}</p>
                <div className="flex items-center gap-2 mt-2">
                  <span className="px-2.5 py-0.5 rounded-full bg-blue-50 text-[#245BE7] text-[10px] font-semibold uppercase tracking-wider border border-blue-100">
                    {user.role}
                  </span>
                  <span className="text-[11px] font-semibold text-slate-400">
                    Member #{user.id}
                  </span>
                </div>
              </div>
            </div>

            {/* Navigation Tabs */}
            <nav className="space-y-1.5" aria-label="Account sections">
              {[
                { id: "overview" as const, label: "Account Overview", icon: LayoutDashboard },
                { id: "profile" as const, label: "Personal Information", icon: User },
                { id: "addresses" as const, label: "Shipping Addresses", icon: MapPin },
                { id: "notifications" as const, label: "Notifications", icon: Bell },
                { id: "security" as const, label: "Password & Security", icon: KeyRound },
              ].map((tab) => {
                const Icon = tab.icon;
                const active = activeTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => setActiveTab(tab.id)}
                    className={`w-full flex items-center justify-between px-4 py-3 rounded-2xl text-xs font-semibold transition cursor-pointer ${
                      active
                        ? "bg-[#245BE7] text-white shadow-md shadow-blue-600/20"
                        : "text-slate-700 hover:bg-slate-50 hover:text-[#245BE7]"
                    }`}
                  >
                    <span className="flex items-center gap-3">
                      <Icon size={16} />
                      {tab.label}
                    </span>
                    {tab.id === "notifications" && notifications.filter((n) => !n.read).length > 0 && (
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                        active ? "bg-white text-[#245BE7]" : "bg-blue-100 text-[#245BE7]"
                      }`}>
                        {notifications.filter((n) => !n.read).length}
                      </span>
                    )}
                  </button>
                );
              })}
            </nav>

            {/* Merchant / Staff Link if authorized */}
            {isStaff && (
              <div className="pt-2">
                <a
                  href={staffDestination}
                  className="bp-press flex min-h-12 w-full items-center justify-center gap-2 rounded-xl border border-line-strong bg-white px-4 text-sm font-semibold text-ink hover:border-ink"
                >
                  <LayoutDashboard size={15} />
                  Open merchant portal
                </a>
              </div>
            )}

            {/* Sign Out Action */}
            <div className="pt-4 border-t border-slate-100">
              <button
                type="button"
                onClick={() => {
                  void logoutFromServer();
                  router.push("/");
                }}
                className="w-full py-3 px-4 rounded-2xl border border-rose-200 text-rose-600 hover:bg-rose-50 text-xs font-semibold flex items-center justify-center gap-2 transition cursor-pointer"
              >
                <LogOut size={15} /> Sign Out of Blue Panda
              </button>
            </div>
          </aside>

          {/* Right Column: Active Content Panel */}
          <div className="lg:col-span-8 bg-white rounded-[2.5rem] border border-slate-200/80 p-6 sm:p-10 shadow-xs">
            {/* ========================================== */}
            {/* OVERVIEW TAB */}
            {/* ========================================== */}
            {activeTab === "overview" && (
              <div className="space-y-8">
                <div>
                  <h2 className="text-xl font-semibold text-[#181818] tracking-tight">
                    Welcome back, {user.name}
                  </h2>
                  <p className="text-xs sm:text-sm text-slate-500 mt-1">
                    Here is a quick overview of your current activity and store interactions.
                  </p>
                </div>

                {/* Quick-Stats 4-Grid */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {/* Orders Shortcut */}
                  <Link
                    href="/orders"
                    className="group p-5 rounded-3xl bg-blue-50/50 hover:bg-blue-50 border border-blue-100 transition space-y-2 block"
                  >
                    <div className="flex items-center justify-between">
                      <div className="w-10 h-10 rounded-xl bg-[#245BE7] text-white flex items-center justify-center">
                        <Package size={20} />
                      </div>
                      <span className="font-mono text-xl font-semibold text-[#181818]">
                        {orders.length}
                      </span>
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-[#181818] group-hover:text-[#245BE7] transition flex items-center gap-1">
                        My Orders <ArrowRight size={13} />
                      </p>
                      <p className="text-[11px] text-slate-500">
                        {orders.length > 0
                          ? `${orders.length} total orders recorded`
                          : "Track recent hardware shipments"}
                      </p>
                    </div>
                  </Link>

                  {/* Saved Wishlist Shortcut */}
                  <Link
                    href="/wishlist"
                    className="group p-5 rounded-3xl bg-rose-50/50 hover:bg-rose-50 border border-rose-100 transition space-y-2 block"
                  >
                    <div className="flex items-center justify-between">
                      <div className="w-10 h-10 rounded-xl bg-rose-500 text-white flex items-center justify-center">
                        <Heart size={20} />
                      </div>
                      <span className="font-mono text-xl font-semibold text-[#181818]">
                        {wishlistCount}
                      </span>
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-[#181818] group-hover:text-rose-600 transition flex items-center gap-1">
                        Saved Gear <ArrowRight size={13} />
                      </p>
                      <p className="text-[11px] text-slate-500">
                        {wishlistCount > 0
                          ? `${wishlistCount} saved items ready to buy`
                          : "Curate your workstation setup"}
                      </p>
                    </div>
                  </Link>

                  {/* Shopping Bag Shortcut */}
                  <Link
                    href="/cart"
                    className="group p-5 rounded-3xl bg-slate-50 hover:bg-slate-100/80 border border-slate-200/80 transition space-y-2 block"
                  >
                    <div className="flex items-center justify-between">
                      <div className="w-10 h-10 rounded-xl bg-[#181818] text-white flex items-center justify-center">
                        <ShoppingBag size={20} />
                      </div>
                      <span className="font-mono text-xl font-semibold text-[#181818]">
                        {cartItemCount}
                      </span>
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-[#181818] group-hover:text-[#245BE7] transition flex items-center gap-1">
                        Shopping Bag <ArrowRight size={13} />
                      </p>
                      <p className="text-[11px] text-slate-500">
                        {cartItemCount > 0
                          ? `${cartItemCount} items awaiting checkout`
                          : "Bag is currently empty"}
                      </p>
                    </div>
                  </Link>

                  {/* Addresses Shortcut */}
                  <button
                    type="button"
                    onClick={() => setActiveTab("addresses")}
                    className="text-left group p-5 rounded-3xl bg-emerald-50/50 hover:bg-emerald-50 border border-emerald-100 transition space-y-2 block w-full cursor-pointer"
                  >
                    <div className="flex items-center justify-between">
                      <div className="w-10 h-10 rounded-xl bg-emerald-600 text-white flex items-center justify-center">
                        <MapPin size={20} />
                      </div>
                      <span className="font-mono text-xl font-semibold text-[#181818]">
                        {addresses.length}
                      </span>
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-[#181818] group-hover:text-emerald-700 transition flex items-center gap-1">
                        Delivery Addresses <ArrowRight size={13} />
                      </p>
                      <p className="text-[11px] text-slate-500">
                        {addresses.length > 0
                          ? `${addresses.length} saved destinations`
                          : "Add a shipping destination"}
                      </p>
                    </div>
                  </button>
                </div>

                {/* Account Security Preview Card */}
                <div className="p-6 rounded-3xl bg-slate-50/80 border border-slate-200/80 space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-blue-100 text-[#245BE7] flex items-center justify-center">
                        <ShieldCheck size={20} />
                      </div>
                      <div>
                        <h3 className="text-xs font-semibold text-[#181818] uppercase tracking-wider">
                          Account Security Status
                        </h3>
                        <p className="text-xs text-slate-500">
                          Active Storefront Session with 256-Bit SSL Protection
                        </p>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => setActiveTab("security")}
                      className="px-4 py-2 rounded-xl border border-slate-200 hover:border-slate-300 bg-white text-xs font-semibold text-[#181818] transition cursor-pointer"
                    >
                      Update Password
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* ========================================== */}
            {/* PROFILE TAB */}
            {/* ========================================== */}
            {activeTab === "profile" && (
              <form onSubmit={handleSaveProfile} className="space-y-6 max-w-xl">
                <div>
                  <h2 className="text-xl font-semibold text-[#181818] tracking-tight">
                    Personal Information
                  </h2>
                  <p className="text-xs text-slate-500 mt-1">
                    Update your display name and contact phone number.
                  </p>
                </div>

                <div className="space-y-4">
                  <div>
                    <label
                      htmlFor="profile-name"
                      className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5"
                    >
                      Full Name *
                    </label>
                    <div className="relative">
                      <User
                        size={16}
                        className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400"
                      />
                      <input
                        id="profile-name"
                        type="text"
                        autoComplete="name"
                        required
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        className="w-full pl-10 pr-4 py-3 rounded-xl bg-slate-50 border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-[#245BE7] focus:bg-white transition"
                      />
                    </div>
                  </div>

                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <label
                        htmlFor="profile-email"
                        className="block text-xs font-semibold text-slate-700 uppercase tracking-wider"
                      >
                        Email Address
                      </label>
                      <span className="text-[11px] font-semibold text-slate-400 flex items-center gap-1">
                        <Lock size={11} /> Primary Account Identity
                      </span>
                    </div>
                    <div className="relative">
                      <Mail
                        size={16}
                        className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400"
                      />
                      <input
                        id="profile-email"
                        type="email"
                        disabled
                        value={user.email}
                        className="w-full pl-10 pr-4 py-3 rounded-xl bg-slate-100 border border-slate-200 text-sm text-slate-500 cursor-not-allowed"
                      />
                    </div>
                  </div>

                  <div>
                    <label
                      htmlFor="profile-phone"
                      className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5"
                    >
                      Mobile Phone (Courier Contact)
                    </label>
                    <div className="relative">
                      <Phone
                        size={16}
                        className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400"
                      />
                      <input
                        id="profile-phone"
                        type="tel"
                        autoComplete="tel"
                        value={phone}
                        onChange={(e) => setPhone(e.target.value)}
                        placeholder="+855 12 345 678"
                        className="w-full pl-10 pr-4 py-3 rounded-xl bg-slate-50 border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-[#245BE7] focus:bg-white transition"
                      />
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-3 pt-2">
                  <button
                    type="submit"
                    disabled={savingProfile}
                    className="px-6 py-3 rounded-2xl bg-[#245BE7] hover:bg-blue-700 text-white text-xs font-semibold shadow-md shadow-blue-600/20 transition cursor-pointer active:scale-98 disabled:opacity-50"
                  >
                    {savingProfile ? "Saving Details..." : "Save Profile Changes"}
                  </button>
                  <button
                    type="button"
                    onClick={handleResetProfile}
                    className="px-5 py-3 rounded-2xl border border-slate-200 hover:border-slate-300 text-slate-600 text-xs font-bold transition cursor-pointer"
                  >
                    Reset
                  </button>
                </div>
              </form>
            )}

            {/* ========================================== */}
            {/* ADDRESSES TAB */}
            {/* ========================================== */}
            {activeTab === "addresses" && (
              <div className="space-y-8">
                <div>
                  <h2 className="text-xl font-semibold text-[#181818] tracking-tight">
                    Saved Delivery Addresses
                  </h2>
                  <p className="text-xs text-slate-500 mt-1">
                    Manage destinations for fast, one-click standard courier delivery.
                  </p>
                </div>

                {addresses.length > 0 ? (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {addresses.map((addr) => (
                      <div
                        key={addr.id}
                        className="p-5 rounded-3xl border border-slate-200/80 bg-white shadow-xs flex flex-col justify-between space-y-3"
                      >
                        <div className="text-xs space-y-1.5">
                          <div className="flex items-center justify-between">
                            <span className="font-semibold text-[#181818] text-sm">
                              {addr.full_name}
                            </span>
                            {addr.is_default && (
                              <span className="px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-800 text-[10px] font-semibold uppercase tracking-wider border border-emerald-200">
                                Default
                              </span>
                            )}
                          </div>
                          <p className="text-slate-500 font-semibold">{addr.phone}</p>
                          <p className="text-slate-700 leading-relaxed">
                            {addr.address_line}, {addr.city} {addr.postal_code || ""}
                          </p>
                        </div>

                        <div className="pt-2 border-t border-slate-100 flex justify-end">
                          <button
                            type="button"
                            onClick={() => handleDeleteAddress(addr.id)}
                            aria-label={`Delete address for ${addr.full_name}`}
                            className="inline-flex items-center gap-1.5 text-xs font-bold text-slate-400 hover:text-rose-600 transition cursor-pointer"
                          >
                            <Trash2 size={13} />
                            Remove Address
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="p-8 rounded-3xl bg-slate-50 text-center space-y-2 border border-slate-200/60">
                    <MapPin size={28} className="text-slate-400 mx-auto" />
                    <p className="text-xs font-bold text-[#181818]">No Saved Addresses</p>
                    <p className="text-xs text-slate-500 max-w-sm mx-auto">
                      Add your home, office, or workshop delivery location below.
                    </p>
                  </div>
                )}

                {/* Add New Address Form */}
                <form
                  onSubmit={handleCreateAddress}
                  className="p-6 rounded-3xl bg-slate-50/80 border border-slate-200/80 space-y-4"
                >
                  <h3 className="text-xs font-semibold text-[#181818] uppercase tracking-wider flex items-center gap-2">
                    <Plus size={15} className="text-[#245BE7]" /> Add New Destination
                  </h3>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label
                        htmlFor="addr-name"
                        className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1"
                      >
                        Recipient Full Name *
                      </label>
                      <input
                        id="addr-name"
                        type="text"
                        autoComplete="name"
                        required
                        value={addrName}
                        onChange={(e) => setAddrName(e.target.value)}
                        placeholder="Alex Rivera"
                        className="w-full px-3.5 py-2.5 rounded-xl bg-white border border-slate-200 text-xs focus:outline-none focus:ring-2 focus:ring-[#245BE7]"
                      />
                    </div>

                    <div>
                      <label
                        htmlFor="addr-phone"
                        className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1"
                      >
                        Contact Phone *
                      </label>
                      <input
                        id="addr-phone"
                        type="tel"
                        autoComplete="tel"
                        required
                        value={addrPhone}
                        onChange={(e) => setAddrPhone(e.target.value)}
                        placeholder="+855 12 345 678"
                        className="w-full px-3.5 py-2.5 rounded-xl bg-white border border-slate-200 text-xs focus:outline-none focus:ring-2 focus:ring-[#245BE7]"
                      />
                    </div>

                    <div className="sm:col-span-2">
                      <label
                        htmlFor="addr-street"
                        className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1"
                      >
                        Street Address, Suite &amp; Building *
                      </label>
                      <textarea
                        id="addr-street"
                        rows={2}
                        autoComplete="street-address"
                        required
                        value={addrLine}
                        onChange={(e) => setAddrLine(e.target.value)}
                        placeholder="St 2004, House #14, Phnom Penh"
                        className="w-full px-3.5 py-2.5 rounded-xl bg-white border border-slate-200 text-xs focus:outline-none focus:ring-2 focus:ring-[#245BE7] resize-none"
                      />
                    </div>

                    <div>
                      <label
                        htmlFor="addr-city"
                        className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1"
                      >
                        City / Province *
                      </label>
                      <input
                        id="addr-city"
                        type="text"
                        autoComplete="address-level2"
                        required
                        value={addrCity}
                        onChange={(e) => setAddrCity(e.target.value)}
                        placeholder="Phnom Penh"
                        className="w-full px-3.5 py-2.5 rounded-xl bg-white border border-slate-200 text-xs focus:outline-none focus:ring-2 focus:ring-[#245BE7]"
                      />
                    </div>
                  </div>

                  <button
                    type="submit"
                    disabled={addingAddress}
                    className="px-6 py-3 rounded-2xl bg-[#181818] hover:bg-slate-800 text-white text-xs font-semibold transition cursor-pointer active:scale-98"
                  >
                    {addingAddress ? "Saving Destination..." : "Save Address to Book"}
                  </button>
                </form>
              </div>
            )}

            {/* ========================================== */}
            {/* NOTIFICATIONS TAB */}
            {/* ========================================== */}
            {activeTab === "notifications" && (
              <div className="space-y-6">
                <div className="flex items-center justify-between pb-4 border-b border-slate-100">
                  <div>
                    <h2 className="text-xl font-semibold text-[#181818] tracking-tight">
                      Notifications
                    </h2>
                    <p className="text-xs text-slate-500 mt-1">
                      System notices, shipment tracking updates, and account alerts.
                    </p>
                  </div>
                  {notifications.length > 0 && (
                    <button
                      type="button"
                      onClick={async () => {
                        await notificationsApi.markAllAsRead().catch(() => {});
                        setNotifications((prev) =>
                          prev.map((n) => ({ ...n, read: true }))
                        );
                        pushToast({
                          title: "All Caught Up",
                          description: "All notifications marked as read.",
                          tone: "info",
                        });
                      }}
                      className="text-xs font-bold text-[#245BE7] hover:underline inline-flex items-center gap-1 cursor-pointer"
                    >
                      <Check size={14} /> Mark all as read
                    </button>
                  )}
                </div>

                {notifications.length === 0 ? (
                  <div className="py-12 text-center space-y-2">
                    <Bell size={32} className="text-slate-300 mx-auto" />
                    <p className="text-xs font-bold text-[#181818]">No Notifications Yet</p>
                    <p className="text-xs text-slate-500 max-w-sm mx-auto">
                      When your order status updates or courier dispatches arrive, you will see them here.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {notifications.map((n) => (
                      <div
                        key={n.id}
                        className={`p-4 rounded-2xl border transition ${
                          n.read
                            ? "border-slate-100 bg-slate-50/50"
                            : "border-blue-200 bg-blue-50/40 ring-1 ring-blue-500/10"
                        }`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <p className="text-xs font-semibold text-[#181818]">{n.title}</p>
                          {!n.read && (
                            <span className="px-2 py-0.5 rounded-full bg-blue-100 text-[#245BE7] text-[9px] font-semibold uppercase">
                              New
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-slate-600 mt-1 leading-relaxed">
                          {n.message}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* ========================================== */}
            {/* SECURITY TAB */}
            {/* ========================================== */}
            {activeTab === "security" && (
              <form onSubmit={handleChangePassword} className="space-y-6 max-w-lg">
                <div>
                  <h2 className="text-xl font-semibold text-[#181818] tracking-tight">
                    Password &amp; Account Security
                  </h2>
                  <p className="text-xs text-slate-500 mt-1">
                    Update your account password. For security, changing your password invalidates active sessions.
                  </p>
                </div>

                {securityError && (
                  <div
                    role="alert"
                    aria-live="polite"
                    className="p-4 bg-rose-50 border border-rose-200 text-rose-800 text-xs font-bold rounded-2xl flex items-start gap-2.5"
                  >
                    <AlertCircle size={16} className="text-rose-600 shrink-0 mt-0.5" />
                    <span>{securityError}</span>
                  </div>
                )}

                <div className="space-y-4">
                  <div>
                    <label
                      htmlFor="sec-current"
                      className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5"
                    >
                      Current Password *
                    </label>
                    <div className="relative">
                      <Lock
                        size={16}
                        className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400"
                      />
                      <input
                        id="sec-current"
                        type={showCurrentPw ? "text" : "password"}
                        autoComplete="current-password"
                        required
                        value={currentPassword}
                        onChange={(e) => setCurrentPassword(e.target.value)}
                        className="w-full pl-10 pr-10 py-3 rounded-xl bg-slate-50 border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-[#245BE7] focus:bg-white transition"
                      />
                      <button
                        type="button"
                        onClick={() => setShowCurrentPw((v) => !v)}
                        aria-label={showCurrentPw ? "Hide password" : "Show password"}
                        className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 cursor-pointer p-1"
                      >
                        {showCurrentPw ? <EyeOff size={16} /> : <Eye size={16} />}
                      </button>
                    </div>
                  </div>

                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <label
                        htmlFor="sec-new"
                        className="block text-xs font-semibold text-slate-700 uppercase tracking-wider"
                      >
                        New Password *
                      </label>
                      <span className="text-[11px] font-semibold text-slate-400">
                        Min 6 characters
                      </span>
                    </div>
                    <div className="relative">
                      <Lock
                        size={16}
                        className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400"
                      />
                      <input
                        id="sec-new"
                        type={showNewPw ? "text" : "password"}
                        autoComplete="new-password"
                        minLength={6}
                        required
                        value={newPassword}
                        onChange={(e) => setNewPassword(e.target.value)}
                        className="w-full pl-10 pr-10 py-3 rounded-xl bg-slate-50 border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-[#245BE7] focus:bg-white transition"
                      />
                      <button
                        type="button"
                        onClick={() => setShowNewPw((v) => !v)}
                        aria-label={showNewPw ? "Hide password" : "Show password"}
                        className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 cursor-pointer p-1"
                      >
                        {showNewPw ? <EyeOff size={16} /> : <Eye size={16} />}
                      </button>
                    </div>
                  </div>

                  <div>
                    <label
                      htmlFor="sec-confirm"
                      className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5"
                    >
                      Confirm New Password *
                    </label>
                    <div className="relative">
                      <Lock
                        size={16}
                        className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400"
                      />
                      <input
                        id="sec-confirm"
                        type={showConfirmPw ? "text" : "password"}
                        autoComplete="new-password"
                        required
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        className="w-full pl-10 pr-10 py-3 rounded-xl bg-slate-50 border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-[#245BE7] focus:bg-white transition"
                      />
                      <button
                        type="button"
                        onClick={() => setShowConfirmPw((v) => !v)}
                        aria-label={showConfirmPw ? "Hide password" : "Show password"}
                        className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 cursor-pointer p-1"
                      >
                        {showConfirmPw ? <EyeOff size={16} /> : <Eye size={16} />}
                      </button>
                    </div>
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={savingPassword}
                  className="px-6 py-3.5 rounded-2xl bg-[#245BE7] hover:bg-blue-700 text-white text-xs font-semibold shadow-md shadow-blue-600/20 transition cursor-pointer active:scale-98 disabled:opacity-50"
                >
                  {savingPassword ? "Updating Password..." : "Confirm Password Update"}
                </button>
              </form>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function AccountPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-[70vh] flex items-center justify-center py-20 text-center">
          <div className="w-8 h-8 border-3 border-[#245BE7] border-t-transparent rounded-full animate-spin mx-auto" />
        </div>
      }
    >
      <AccountHubContent />
    </Suspense>
  );
}
