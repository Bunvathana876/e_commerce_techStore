"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  Bell,
  Check,
  CreditCard,
  Database,
  ExternalLink,
  Palette,
  RefreshCw,
  Save,
  ShieldCheck,
  Store,
  Truck,
  Upload,
} from "lucide-react";
import {
  settingsApi,
  uploadApi,
  type ApiInfrastructureStatus,
} from "@/lib/api";
import { API_BASE_URL, API_DOCS_URL } from "@/lib/config";

type Tab =
  | "general"
  | "appearance"
  | "shipping"
  | "payment"
  | "notifications"
  | "database";

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<Tab>("general");
  const [loading, setLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [infrastructure, setInfrastructure] = useState<ApiInfrastructureStatus | null>(null);
  const logoInputRef = useRef<HTMLInputElement | null>(null);

  const [general, setGeneral] = useState({
    storeName: "Blue Panda",
    storeEmail: "support@bluepanda.com",
    storePhone: "",
    storeAddress: "",
    storeLogoUrl: "",
    currency: "USD",
    language: "en",
    timezone: "Asia/Phnom_Penh",
  });

  const [appearance, setAppearance] = useState({
    theme: "light",
    primaryColor: "#245BE7",
    sidebarStyle: "default",
  });

  const [shipping, setShipping] = useState({
    freeShippingMin: "100.00",
    standardFee: "2.00",
    expressFee: "12.00",
    estimatedDays: "1-3",
  });

  const [payments, setPayments] = useState({
    enableCard: true,
    enableCod: true,
  });

  const [notifications, setNotifications] = useState({
    newOrder: true,
    lowStock: true,
    customerMessage: true,
    weeklyReport: false,
  });

  const loadSettings = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await settingsApi.get();
      if (res.success && res.data) {
        const s = res.data.settings;
        setGeneral({
          storeName: s.store_name || "Blue Panda",
          storeEmail: s.store_email || "support@bluepanda.com",
          storePhone: s.store_phone || "",
          storeAddress: s.store_address || "",
          storeLogoUrl: s.store_logo_url || "",
          currency: s.currency || "USD",
          language: s.language || "en",
          timezone: s.timezone || "Asia/Phnom_Penh",
        });
        setAppearance({
          theme: s.theme || "light",
          primaryColor: s.primary_color || "#245BE7",
          sidebarStyle: s.sidebar_style || "default",
        });
        setShipping({
          freeShippingMin: String(s.free_shipping_min ?? "100.00"),
          standardFee: String(s.standard_shipping_fee ?? "2.00"),
          expressFee: String(s.express_shipping_fee ?? "12.00"),
          estimatedDays: s.estimated_delivery_days || "1-3",
        });
        setPayments({
          enableCard: Boolean(s.enable_card_payment),
          enableCod: Boolean(s.enable_cod_payment),
        });
        setNotifications({
          newOrder: Boolean(s.notify_new_order),
          lowStock: Boolean(s.notify_low_stock),
          customerMessage: Boolean(s.notify_customer_message),
          weeklyReport: Boolean(s.notify_weekly_report),
        });
        setInfrastructure(res.data.infrastructure);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unable to load store settings.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadSettings();
  }, [loadSettings]);

  const handleSave = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setIsSaving(true);
    setSaved(false);
    setError(null);
    try {
      const res = await settingsApi.update({
        store_name: general.storeName.trim(),
        store_email: general.storeEmail.trim(),
        store_phone: general.storePhone.trim() || null,
        store_address: general.storeAddress.trim() || null,
        store_logo_url: general.storeLogoUrl.trim() || null,
        currency: general.currency,
        language: general.language,
        timezone: general.timezone,
        theme: appearance.theme,
        primary_color: appearance.primaryColor,
        sidebar_style: appearance.sidebarStyle,
        free_shipping_min: Number(shipping.freeShippingMin) || 0,
        standard_shipping_fee: Number(shipping.standardFee) || 0,
        express_shipping_fee: Number(shipping.expressFee) || 0,
        estimated_delivery_days: shipping.estimatedDays.trim() || "1-3",
        enable_card_payment: payments.enableCard,
        enable_cod_payment: payments.enableCod,
        notify_new_order: notifications.newOrder,
        notify_low_stock: notifications.lowStock,
        notify_customer_message: notifications.customerMessage,
        notify_weekly_report: notifications.weeklyReport,
      });
      if (res.success && res.data) {
        setInfrastructure(res.data.infrastructure);
        setSaved(true);
        setTimeout(() => setSaved(false), 3000);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to save store settings.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleLogoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingLogo(true);
    setError(null);
    try {
      const res = await uploadApi.uploadImage(file);
      if (res.success && res.data?.url) {
        setGeneral((prev) => ({ ...prev, storeLogoUrl: res.data.url }));
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Logo upload failed.");
    } finally {
      setUploadingLogo(false);
      e.target.value = "";
    }
  };

  const tabs = [
    { id: "general" as Tab, label: "General", icon: Store },
    { id: "appearance" as Tab, label: "Appearance", icon: Palette },
    { id: "shipping" as Tab, label: "Shipping", icon: Truck },
    { id: "payment" as Tab, label: "Payment", icon: CreditCard },
    { id: "notifications" as Tab, label: "Notifications", icon: Bell },
    { id: "database" as Tab, label: "Infrastructure & DB", icon: Database },
  ];

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto py-24 text-center space-y-3">
        <div className="w-9 h-9 border-4 border-[#7699F0] border-t-transparent rounded-full animate-spin mx-auto" />
        <p className="text-sm text-gray-500">Loading store settings from database…</p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSave} className="max-w-4xl mx-auto space-y-6 pb-10">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Store Settings</h1>
          <p className="text-sm text-gray-500 mt-1">
            Persisted storefront preferences, shipping rules, payment methods, and backend infrastructure status
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => void loadSettings()}
            className="inline-flex items-center gap-2 px-4 py-2.5 text-sm font-medium text-gray-700 bg-white border border-gray-200 rounded-xl hover:bg-gray-50 transition"
          >
            <RefreshCw size={15} />
            Reload
          </button>
          <button
            type="submit"
            disabled={isSaving}
            className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-semibold text-white bg-[#7699F0] rounded-xl hover:bg-blue-600 transition shadow-sm disabled:opacity-70"
          >
            {saved ? (
              <>
                <Check size={16} />
                Saved
              </>
            ) : (
              <>
                <Save size={16} />
                {isSaving ? "Saving…" : "Save Changes"}
              </>
            )}
          </button>
        </div>
      </div>

      {error && (
        <div
          role="alert"
          className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-800 text-sm flex items-center gap-2.5"
        >
          <AlertCircle size={18} className="shrink-0 text-rose-600" />
          <span>{error}</span>
        </div>
      )}

      {saved && (
        <div
          role="status"
          aria-live="polite"
          className="p-3.5 rounded-2xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm flex items-center gap-2"
        >
          <Check size={16} className="text-emerald-600" />
          <span>Store settings saved to PostgreSQL.</span>
        </div>
      )}

      {/* Tabs */}
      <div
        role="tablist"
        aria-label="Store settings sections"
        className="bg-white rounded-2xl border border-gray-100 shadow-sm p-1.5 flex flex-wrap gap-1"
      >
        {tabs.map((tab) => {
          const selected = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={selected}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium rounded-xl transition-all ${
                selected
                  ? "bg-[#7699F0] text-white shadow-sm"
                  : "text-gray-600 hover:bg-gray-50"
              }`}
            >
              <tab.icon size={16} aria-hidden="true" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* GENERAL */}
      {activeTab === "general" && (
        <div className="space-y-6">
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
            <h2 className="font-semibold text-gray-900 mb-4">Store Logo</h2>
            <div className="flex flex-wrap items-center gap-5">
              {general.storeLogoUrl ? (
                <img
                  src={general.storeLogoUrl}
                  alt={`${general.storeName} logo`}
                  className="w-20 h-20 rounded-2xl object-cover border border-gray-200"
                />
              ) : (
                <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-[#7699F0] to-blue-600 flex items-center justify-center text-white text-2xl font-bold shadow-sm">
                  {(general.storeName || "B").charAt(0).toUpperCase()}
                </div>
              )}
              <div className="space-y-2">
                <input
                  ref={logoInputRef}
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  onChange={handleLogoUpload}
                  className="hidden"
                  aria-label="Upload store logo image"
                />
                <button
                  type="button"
                  disabled={uploadingLogo}
                  onClick={() => logoInputRef.current?.click()}
                  className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-[#7699F0] bg-blue-50 rounded-xl hover:bg-blue-100 transition disabled:opacity-50"
                >
                  <Upload size={16} aria-hidden="true" />
                  {uploadingLogo ? "Uploading…" : "Upload Logo"}
                </button>
                <p className="text-xs text-gray-400">
                  PNG, JPG, or WebP · Uploaded via verified media storage ({infrastructure?.upload_storage_backend || "auto"})
                </p>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-5">
            <h2 className="font-semibold text-gray-900">Store Information</h2>

            <div>
              <label htmlFor="settings-store-name" className="block text-sm font-medium text-gray-700 mb-1.5">
                Store Name *
              </label>
              <input
                id="settings-store-name"
                name="store_name"
                type="text"
                required
                value={general.storeName}
                onChange={(e) => setGeneral({ ...general, storeName: e.target.value })}
                className="w-full px-4 py-2.5 text-sm bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#7699F0]"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
              <div>
                <label htmlFor="settings-store-email" className="block text-sm font-medium text-gray-700 mb-1.5">
                  Support Email *
                </label>
                <input
                  id="settings-store-email"
                  name="store_email"
                  type="email"
                  required
                  value={general.storeEmail}
                  onChange={(e) => setGeneral({ ...general, storeEmail: e.target.value })}
                  className="w-full px-4 py-2.5 text-sm bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#7699F0]"
                />
              </div>
              <div>
                <label htmlFor="settings-store-phone" className="block text-sm font-medium text-gray-700 mb-1.5">
                  Phone
                </label>
                <input
                  id="settings-store-phone"
                  name="store_phone"
                  type="tel"
                  value={general.storePhone}
                  onChange={(e) => setGeneral({ ...general, storePhone: e.target.value })}
                  className="w-full px-4 py-2.5 text-sm bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#7699F0]"
                />
              </div>
            </div>

            <div>
              <label htmlFor="settings-store-address" className="block text-sm font-medium text-gray-700 mb-1.5">
                Address
              </label>
              <input
                id="settings-store-address"
                name="store_address"
                type="text"
                value={general.storeAddress}
                onChange={(e) => setGeneral({ ...general, storeAddress: e.target.value })}
                className="w-full px-4 py-2.5 text-sm bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#7699F0]"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
              <div>
                <label htmlFor="settings-currency" className="block text-sm font-medium text-gray-700 mb-1.5">
                  Currency
                </label>
                <select
                  id="settings-currency"
                  name="currency"
                  value={general.currency}
                  onChange={(e) => setGeneral({ ...general, currency: e.target.value })}
                  className="w-full px-4 py-2.5 text-sm bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#7699F0]"
                >
                  <option value="USD">USD ($)</option>
                  <option value="KHR">KHR (៛)</option>
                  <option value="THB">THB (฿)</option>
                </select>
              </div>
              <div>
                <label htmlFor="settings-language" className="block text-sm font-medium text-gray-700 mb-1.5">
                  Language
                </label>
                <select
                  id="settings-language"
                  name="language"
                  value={general.language}
                  onChange={(e) => setGeneral({ ...general, language: e.target.value })}
                  className="w-full px-4 py-2.5 text-sm bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#7699F0]"
                >
                  <option value="en">English</option>
                  <option value="km">Khmer</option>
                  <option value="th">Thai</option>
                </select>
              </div>
              <div>
                <label htmlFor="settings-timezone" className="block text-sm font-medium text-gray-700 mb-1.5">
                  Timezone
                </label>
                <select
                  id="settings-timezone"
                  name="timezone"
                  value={general.timezone}
                  onChange={(e) => setGeneral({ ...general, timezone: e.target.value })}
                  className="w-full px-4 py-2.5 text-sm bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#7699F0]"
                >
                  <option value="Asia/Phnom_Penh">Phnom Penh (GMT+7)</option>
                  <option value="Asia/Bangkok">Bangkok (GMT+7)</option>
                  <option value="UTC">UTC</option>
                </select>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* APPEARANCE */}
      {activeTab === "appearance" && (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-6">
          <div>
            <h2 className="font-semibold text-gray-900">Appearance</h2>
            <p className="text-sm text-gray-500 mt-0.5">
              Customize portal appearance metadata saved with your store profile
            </p>
          </div>

          <fieldset>
            <legend className="block text-sm font-medium text-gray-700 mb-3">Theme</legend>
            <div className="grid grid-cols-3 gap-3">
              {[
                { id: "light", label: "Light", bg: "bg-white border-gray-200" },
                { id: "dark", label: "Dark", bg: "bg-gray-800 border-gray-700" },
                { id: "system", label: "System", bg: "bg-gradient-to-br from-white to-gray-800 border-gray-300" },
              ].map((theme) => (
                <button
                  key={theme.id}
                  type="button"
                  aria-pressed={appearance.theme === theme.id}
                  onClick={() => setAppearance({ ...appearance, theme: theme.id })}
                  className={`relative p-4 rounded-xl border-2 transition-all ${
                    appearance.theme === theme.id
                      ? "border-[#7699F0] ring-2 ring-[#7699F0]/20"
                      : "border-gray-200 hover:border-gray-300"
                  }`}
                >
                  <div className={`h-12 rounded-lg ${theme.bg} border mb-2`} />
                  <p className="text-sm font-medium text-gray-800">{theme.label}</p>
                </button>
              ))}
            </div>
          </fieldset>

          <div>
            <span className="block text-sm font-medium text-gray-700 mb-3">Primary Color</span>
            <div className="flex flex-wrap gap-3">
              {["#245BE7", "#7699F0", "#10B981", "#8B5CF6", "#F59E0B", "#EF4444"].map((color) => (
                <button
                  key={color}
                  type="button"
                  aria-label={`Select accent color ${color}`}
                  aria-pressed={appearance.primaryColor === color}
                  onClick={() => setAppearance({ ...appearance, primaryColor: color })}
                  className={`w-10 h-10 rounded-full transition-all ${
                    appearance.primaryColor === color
                      ? "ring-2 ring-offset-2 ring-gray-500 scale-110"
                      : "hover:scale-105"
                  }`}
                  style={{ backgroundColor: color }}
                />
              ))}
            </div>
          </div>
        </div>
      )}

      {/* SHIPPING */}
      {activeTab === "shipping" && (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-5">
          <div>
            <h2 className="font-semibold text-gray-900">Shipping Settings</h2>
            <p className="text-sm text-gray-500 mt-0.5">
              Persisted delivery thresholds and fees published to public store metadata
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            <div>
              <label htmlFor="settings-free-shipping" className="block text-sm font-medium text-gray-700 mb-1.5">
                Free Shipping Minimum ($)
              </label>
              <input
                id="settings-free-shipping"
                name="free_shipping_min"
                type="number"
                step="0.01"
                min="0"
                value={shipping.freeShippingMin}
                onChange={(e) => setShipping({ ...shipping, freeShippingMin: e.target.value })}
                className="w-full px-4 py-2.5 text-sm bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#7699F0]"
              />
            </div>

            <div>
              <label htmlFor="settings-delivery-days" className="block text-sm font-medium text-gray-700 mb-1.5">
                Estimated Delivery (days)
              </label>
              <input
                id="settings-delivery-days"
                name="estimated_delivery_days"
                type="text"
                value={shipping.estimatedDays}
                onChange={(e) => setShipping({ ...shipping, estimatedDays: e.target.value })}
                className="w-full px-4 py-2.5 text-sm bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#7699F0]"
              />
            </div>

            <div>
              <label htmlFor="settings-standard-fee" className="block text-sm font-medium text-gray-700 mb-1.5">
                Standard Shipping Fee ($)
              </label>
              <input
                id="settings-standard-fee"
                name="standard_shipping_fee"
                type="number"
                step="0.01"
                min="0"
                value={shipping.standardFee}
                onChange={(e) => setShipping({ ...shipping, standardFee: e.target.value })}
                className="w-full px-4 py-2.5 text-sm bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#7699F0]"
              />
            </div>

            <div>
              <label htmlFor="settings-express-fee" className="block text-sm font-medium text-gray-700 mb-1.5">
                Express Shipping Fee ($)
              </label>
              <input
                id="settings-express-fee"
                name="express_shipping_fee"
                type="number"
                step="0.01"
                min="0"
                value={shipping.expressFee}
                onChange={(e) => setShipping({ ...shipping, expressFee: e.target.value })}
                className="w-full px-4 py-2.5 text-sm bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#7699F0]"
              />
            </div>
          </div>
        </div>
      )}

      {/* PAYMENT */}
      {activeTab === "payment" && (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="px-6 py-5 border-b border-gray-100 flex items-center justify-between">
            <div>
              <h2 className="font-semibold text-gray-900">Supported Payment Methods</h2>
              <p className="text-sm text-gray-500 mt-0.5">
                Blue Panda supports verified Credit / Debit Card (Stripe) and Cash on Delivery
              </p>
            </div>
            <span
              className={`px-2.5 py-1 rounded-full text-xs font-semibold ${
                infrastructure?.card_gateway_configured
                  ? "bg-emerald-50 text-emerald-700"
                  : "bg-amber-50 text-amber-700"
              }`}
            >
              Stripe: {infrastructure?.card_gateway_configured ? "Configured" : "Needs Server Key"}
            </span>
          </div>

          <div className="divide-y divide-gray-100">
            <div className="flex items-center justify-between px-6 py-4">
              <div>
                <p className="text-sm font-semibold text-gray-900">Credit / Debit Card (Stripe)</p>
                <p className="text-xs text-gray-500">Online card capture via PaymentIntents & webhook verification</p>
              </div>
              <button
                type="button"
                role="switch"
                aria-checked={payments.enableCard}
                aria-label="Toggle Credit or Debit Card payment method"
                onClick={() => setPayments((p) => ({ ...p, enableCard: !p.enableCard }))}
                className={`relative w-11 h-6 rounded-full transition-colors ${
                  payments.enableCard ? "bg-[#7699F0]" : "bg-gray-200"
                }`}
              >
                <span
                  className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${
                    payments.enableCard ? "translate-x-5" : ""
                  }`}
                />
              </button>
            </div>

            <div className="flex items-center justify-between px-6 py-4">
              <div>
                <p className="text-sm font-semibold text-gray-900">Cash on Delivery (COD)</p>
                <p className="text-xs text-gray-500">Collect cash upon courier delivery and reconcile settlement</p>
              </div>
              <button
                type="button"
                role="switch"
                aria-checked={payments.enableCod}
                aria-label="Toggle Cash on Delivery payment method"
                onClick={() => setPayments((p) => ({ ...p, enableCod: !p.enableCod }))}
                className={`relative w-11 h-6 rounded-full transition-colors ${
                  payments.enableCod ? "bg-[#7699F0]" : "bg-gray-200"
                }`}
              >
                <span
                  className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${
                    payments.enableCod ? "translate-x-5" : ""
                  }`}
                />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* NOTIFICATIONS */}
      {activeTab === "notifications" && (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="px-6 py-5 border-b border-gray-100">
            <h2 className="font-semibold text-gray-900">Notification Preferences</h2>
            <p className="text-sm text-gray-500 mt-0.5">
              Saved alert rules for operations and store administration
            </p>
          </div>

          <div className="divide-y divide-gray-100">
            {[
              { key: "newOrder" as const, title: "New Orders", desc: "Notify administrators when customers place an order" },
              { key: "lowStock" as const, title: "Low Stock Alerts", desc: "Alert when warehouse SKU quantities fall below threshold" },
              { key: "customerMessage" as const, title: "Customer Messages", desc: "Notify on customer order notes and reviews" },
              { key: "weeklyReport" as const, title: "Weekly Report", desc: "Enable weekly revenue & ledger reconciliation summary" },
            ].map((item) => (
              <div key={item.key} className="flex items-center justify-between px-6 py-4">
                <div>
                  <p className="text-sm font-medium text-gray-900">{item.title}</p>
                  <p className="text-xs text-gray-400 mt-0.5">{item.desc}</p>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={notifications[item.key]}
                  aria-label={`Toggle ${item.title}`}
                  onClick={() =>
                    setNotifications({ ...notifications, [item.key]: !notifications[item.key] })
                  }
                  className={`relative w-11 h-6 rounded-full transition-colors ${
                    notifications[item.key] ? "bg-[#7699F0]" : "bg-gray-200"
                  }`}
                >
                  <span
                    className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${
                      notifications[item.key] ? "translate-x-5" : ""
                    }`}
                  />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* INFRASTRUCTURE & DB */}
      {activeTab === "database" && (
        <div className="space-y-6">
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-4">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-2xl bg-blue-50 text-[#7699F0] flex items-center justify-center">
                <Database size={24} />
              </div>
              <div>
                <h2 className="text-lg font-bold text-gray-900">Live Backend Infrastructure Status</h2>
                <p className="text-xs text-gray-500">
                  Real-time metadata inspected from FastAPI & connected database
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
              <div className="p-4 rounded-xl border border-gray-100 bg-gray-50/50 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-gray-500 uppercase">Database Engine</span>
                  <span
                    className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium ${
                      infrastructure?.database_connected
                        ? "bg-emerald-50 text-emerald-700"
                        : "bg-rose-50 text-rose-700"
                    }`}
                  >
                    {infrastructure?.database_connected ? "Connected" : "Disconnected"}
                  </span>
                </div>
                <p className="text-sm font-semibold text-gray-900 uppercase">
                  {infrastructure?.database_dialect || "postgresql"}
                </p>
                <p className="text-xs text-gray-500">
                  Media Storage: <strong>{infrastructure?.upload_storage_backend || "local"}</strong> · Email:{" "}
                  <strong>{infrastructure?.email_provider || "console"}</strong>
                </p>
              </div>

              <div className="p-4 rounded-xl border border-gray-100 bg-gray-50/50 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-gray-500 uppercase">FastAPI Backend API</span>
                  <a
                    href={API_DOCS_URL}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-xs font-semibold text-[#7699F0] hover:underline"
                  >
                    Swagger Docs <ExternalLink size={12} />
                  </a>
                </div>
                <p className="text-sm font-semibold text-gray-900">Blue Panda REST API</p>
                <p className="text-xs text-gray-400">
                  Base: <code className="text-gray-700 break-all">{API_BASE_URL}</code>
                </p>
              </div>

              <div className="sm:col-span-2 p-4 rounded-xl border border-gray-100 bg-gray-50/50 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-gray-500 uppercase">Live Database Schema</span>
                  <Link href="/admin/roles" className="text-xs font-semibold text-[#7699F0] hover:underline inline-flex items-center gap-1">
                    <ShieldCheck size={13} /> Inspect RBAC Roles
                  </Link>
                </div>
                <p className="text-sm font-semibold text-gray-900">
                  {infrastructure?.table_count ?? 0} Database Tables Active
                </p>
                <p className="text-xs text-gray-500 leading-relaxed">
                  {infrastructure?.table_names.join(", ") || "Unavailable"}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </form>
  );
}
