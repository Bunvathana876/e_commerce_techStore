"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  Banknote,
  Check,
  CheckCircle2,
  Clock,
  CreditCard,
  Lock,
  PackageCheck,
  QrCode,
  ShieldCheck,
  Smartphone,
  Tag,
  Truck,
  UserCheck,
  type LucideIcon,
} from "lucide-react";
import {
  addressesApi,
  cartApi,
  couponsApi,
  ordersApi,
  type ApiAddress,
  type ApiCoupon,
  type ApiOrder,
} from "@/lib/api";
import { getCurrentUser, isLoggedIn } from "@/lib/auth";
import {
  CHECKOUT_PAYMENT_METHODS,
  clearDurableCheckoutKey,
  createCheckoutSubmissionLock,
  DEFAULT_CHECKOUT_PAYMENT_METHOD,
  executeCheckoutOrder,
  getOrCreateDurableCheckoutKey,
  getOrderPaymentPresentation,
} from "@/lib/checkout-security";
import { getEffectivePrice, resolveProductImage } from "@/lib/store-catalog";
import {
  getCartTotals,
  useShopStore,
} from "@/lib/store";

const PAYMENT_METHOD_ICONS: Record<string, LucideIcon> = {
  "Cash on Delivery": Banknote,
  "KHQR Scan & Pay": QrCode,
  "Credit / Debit Card": CreditCard,
  "Apple Pay": Smartphone,
};

export default function CheckoutPage() {
  const items = useShopStore((s) => s.items);
  const appliedCoupon = useShopStore((s) => s.appliedCoupon);
  const clearCart = useShopStore((s) => s.clearCart);
  const applyCouponCode = useShopStore((s) => s.applyCouponCode);
  const removeCoupon = useShopStore((s) => s.removeCoupon);
  const pushToast = useShopStore((s) => s.pushToast);

  const submissionLockRef = useRef(createCheckoutSubmissionLock());
  const checkoutIdempotencyKeyRef = useRef<string | null>(null);

  const [savedAddresses, setSavedAddresses] = useState<ApiAddress[]>([]);
  const [selectedAddressId, setSelectedAddressId] = useState<number | "new">("new");
  const [availableCoupons, setAvailableCoupons] = useState<ApiCoupon[]>([]);

  // Semantic autofill-ready address form fields
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [streetAddress, setStreetAddress] = useState("");
  const [city, setCity] = useState("");
  const [postalCode, setPostalCode] = useState("");
  const [saveAddressForLater, setSaveAddressForLater] = useState(true);

  const [paymentMethod, setPaymentMethod] = useState(
    DEFAULT_CHECKOUT_PAYMENT_METHOD
  );
  const [promoInput, setPromoInput] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [couponLoading, setCouponLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [placedOrder, setPlacedOrder] = useState<ApiOrder | null>(null);

  const totals = getCartTotals(items, appliedCoupon);
  const authenticated = isLoggedIn();
  const currentUser = getCurrentUser();

  // Populate user data and fetch saved addresses / coupons
  useEffect(() => {
    if (currentUser) {
      setFullName(currentUser.name || "");
      setEmail(currentUser.email || "");
      setPhone(currentUser.phone || "");
    }

    if (authenticated) {
      addressesApi
        .list()
        .then((res) => {
          if (res.data && res.data.length > 0) {
            setSavedAddresses(res.data);
            const def = res.data.find((a) => a.is_default) || res.data[0];
            setSelectedAddressId(def.id);
          }
        })
        .catch(() => {});
    }

    // Fetch live backend promotional coupons for quick-fill chips
    couponsApi
      .available()
      .then((res) => {
        if (res.data && Array.isArray(res.data)) {
          setAvailableCoupons(res.data.filter((c) => c.is_active));
        }
      })
      .catch(() => {});
  }, [authenticated, currentUser]);

  const handleApplyCoupon = async (codeToApply?: string) => {
    const code = (codeToApply || promoInput).trim().toUpperCase();
    if (!code) return;

    setCouponLoading(true);
    setErrorMessage(null);
    try {
      await applyCouponCode(code);
      setPromoInput("");
      pushToast({
        title: "Coupon Applied",
        description: `Promo code ${code} has been successfully applied to your order.`,
        tone: "success",
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Invalid or expired promo code.";
      setErrorMessage(msg);
      pushToast({
        title: "Coupon Error",
        description: msg,
        tone: "error",
      });
    } finally {
      setCouponLoading(false);
    }
  };

  const selectedPaymentMeta = CHECKOUT_PAYMENT_METHODS.find((pm) => pm.id === paymentMethod);
  const isDemoPayment = selectedPaymentMeta?.isDemo ?? false;

  const handlePlaceOrder = async (e: React.FormEvent) => {
    e.preventDefault();
    if (items.length === 0 || submissionLockRef.current.isLocked()) return;

    if (!authenticated) {
      setErrorMessage(
        "Please sign in before placing your order. Guest checkout is not available on Blue Panda."
      );
      return;
    }

    if (isDemoPayment) {
      setErrorMessage(
        "Live payment gateway capture for this method is not integrated yet. Please select Cash on Delivery (COD) to place your order."
      );
      return;
    }

    setErrorMessage(null);
    setSubmitting(true);

    try {
      let resolvedAddressText = "";
      if (selectedAddressId !== "new") {
        const picked = savedAddresses.find((a) => a.id === selectedAddressId);
        if (picked) {
          resolvedAddressText = [
            picked.full_name,
            picked.phone,
            picked.address_line,
            picked.city,
            picked.postal_code,
          ]
            .filter(Boolean)
            .join(", ");
        }
      } else {
        resolvedAddressText = [
          fullName.trim(),
          phone.trim(),
          streetAddress.trim(),
          city.trim(),
          postalCode.trim(),
        ]
          .filter(Boolean)
          .join(", ");
      }

      if (!resolvedAddressText) {
        throw new Error("Please provide your delivery address.");
      }

      const checkoutItems = items.map((item) => ({
        productId: item.product.id,
        quantity: item.quantity,
      }));

      const durableKey = getOrCreateDurableCheckoutKey(checkoutItems);
      checkoutIdempotencyKeyRef.current = durableKey;

      const result = await executeCheckoutOrder({
        lock: submissionLockRef.current,
        isAuthenticated: true,
        items: checkoutItems,
        shippingAddress: resolvedAddressText,
        shippingAddressId:
          selectedAddressId !== "new" ? selectedAddressId : undefined,
        newAddressToSave:
          selectedAddressId === "new" && saveAddressForLater
            ? {
                full_name: fullName.trim(),
                phone: phone.trim(),
                address_line: streetAddress.trim(),
                city: city.trim(),
                postal_code: postalCode.trim() || undefined,
                is_default: savedAddresses.length === 0,
              }
            : undefined,
        paymentMethod,
        phone: phone.trim() || undefined,
        fullName: fullName.trim() || undefined,
        couponCode: appliedCoupon?.code || undefined,
        idempotencyKey: durableKey,
        deps: {
          createAddress: addressesApi.create,
          reconcileServerCart: cartApi.reconcile,
          createOrder: ordersApi.create,
          clearClientCart: clearCart,
        },
      });

      if (result.status === "duplicate_blocked") {
        return;
      }

      clearDurableCheckoutKey();
      checkoutIdempotencyKeyRef.current = null;
      setPlacedOrder(result.order);
      pushToast({
        title: `Order #${result.order.id} Confirmed!`,
        description: "Your tech order has been placed and queued for dispatch.",
        tone: "success",
      });
    } catch (err: unknown) {
      setErrorMessage(
        err instanceof Error
          ? err.message
          : "Could not complete your order. Please verify your details."
      );
    } finally {
      if (!submissionLockRef.current.isLocked()) {
        setSubmitting(false);
      }
    }
  };

  // ==========================================
  // PHASE 8: ORDER CONFIRMED CELEBRATION VIEW
  // ==========================================
  if (placedOrder) {
    const paymentMeta = getOrderPaymentPresentation(placedOrder);
    return (
      <div className="min-h-[75vh] bg-[#F5F8FD]/60 py-12 sm:py-16">
        <div className="max-w-3xl mx-auto px-4 sm:px-6">
          <div className="bg-white rounded-[2.5rem] border border-slate-200/80 p-8 sm:p-12 shadow-xl text-center space-y-8">
            {/* Header Success Badge */}
            <div className="w-22 h-22 rounded-3xl bg-emerald-500 text-white flex items-center justify-center mx-auto shadow-lg shadow-emerald-500/30">
              <PackageCheck size={44} />
            </div>

            <div>
              <div className="inline-flex items-center gap-1.5 px-3.5 py-1 rounded-full bg-emerald-50 border border-emerald-100 text-emerald-700 text-xs font-bold uppercase tracking-wider mb-2">
                <CheckCircle2 size={13} className="text-emerald-600" />
                Order Confirmed by Warehouse
              </div>
              <h1 className="text-3xl sm:text-4xl font-bold text-ink tracking-tight">
                Thank You for Your Order!
              </h1>
              <p className="text-sm text-slate-500 mt-2 max-w-md mx-auto leading-relaxed">
                Your order{" "}
                <strong className="text-ink font-bold">
                  #{placedOrder.id}
                </strong>{" "}
                is verified and our warehouse crew is preparing your items for courier dispatch.
              </p>
            </div>

            {/* Order Details Breakdown Box */}
            <div className="text-left p-6 sm:p-7 rounded-3xl bg-slate-50/80 border border-slate-200/80 space-y-4">
              <div className="flex flex-wrap justify-between items-center gap-2 pb-3 border-b border-slate-200/80">
                <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                  Order Reference
                </span>
                <span className="bp-price text-sm font-bold text-ink">
                  #{placedOrder.id}
                </span>
              </div>

              <div className="flex flex-wrap justify-between items-center gap-2 text-xs">
                <span className="text-slate-500 font-semibold">Processing Status</span>
                <span className="font-semibold px-2.5 py-0.5 rounded-full bg-blue-100 text-blue-800">
                  {paymentMeta.orderStatusLabel}
                </span>
              </div>

              <div className="flex flex-wrap justify-between items-center gap-2 text-xs">
                <span className="text-slate-500 font-semibold">Payment Method</span>
                <span className="font-bold text-slate-900">
                  {placedOrder.payment_method}
                </span>
              </div>

              <div className="flex flex-wrap justify-between items-center gap-2 text-xs">
                <span className="text-slate-500 font-semibold">Payment Status</span>
                <span
                  className={`font-bold px-2.5 py-0.5 rounded-full text-xs uppercase tracking-wide ${
                    paymentMeta.isPaid
                      ? "bg-emerald-100 text-emerald-800"
                      : "bg-amber-100 text-amber-800"
                  }`}
                >
                  {paymentMeta.paymentStatusLabel}
                </span>
              </div>

              <div className="flex flex-wrap justify-between items-start gap-2 text-xs pt-1">
                <span className="text-slate-500 font-semibold">Delivery Destination</span>
                <span className="font-bold text-slate-800 text-right max-w-sm leading-relaxed">
                  {placedOrder.shipping_address}
                </span>
              </div>

              {/* Items in this order */}
              <div className="pt-4 border-t border-slate-200 space-y-2">
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  Order Items ({placedOrder.items?.length || 0})
                </p>
                {placedOrder.items?.map((oi) => (
                  <div
                    key={oi.id}
                    className="flex justify-between items-center text-xs text-slate-700"
                  >
                    <span className="font-medium truncate max-w-xs">
                      {oi.product_name}{" "}
                      <span className="text-slate-400 font-normal">
                        × {oi.quantity}
                      </span>
                    </span>
                    <span className="font-bold font-mono">
                      ${Number(oi.subtotal).toFixed(2)}
                    </span>
                  </div>
                ))}
              </div>

              <div className="pt-3 border-t border-slate-200 flex justify-between items-center text-base font-bold text-ink">
                <span>{paymentMeta.totalLabel}</span>
                <span className="text-brand bp-price text-xl">
                  ${Number(placedOrder.total).toFixed(2)}
                </span>
              </div>
            </div>

            {/* Next Steps Timeline */}
            <div className="space-y-3 rounded-3xl bg-paper p-6 text-left ring-1 ring-line">
              <h3 className="text-sm font-semibold text-ink">What happens next</h3>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs text-slate-600">
                <div className="p-3 rounded-2xl bg-white/80 border border-slate-200/60">
                  <span className="font-bold text-ink block mb-1">
                    1. Warehouse Allocation
                  </span>
                  Physical inspection and anti-static packaging of your hardware.
                </div>
                <div className="p-3 rounded-2xl bg-white/80 border border-slate-200/60">
                  <span className="font-bold text-ink block mb-1">
                    2. Courier Handover
                  </span>
                  Standard dispatch in 1–3 business days with tracking updates.
                </div>
                <div className="p-3 rounded-2xl bg-white/80 border border-slate-200/60">
                  <span className="font-bold text-ink block mb-1">
                    3. Safe Delivery
                  </span>
                  Parcel inspection upon arrival; cash collected if COD selected.
                </div>
              </div>
            </div>

            {/* Action CTAs */}
            <div className="flex flex-wrap items-center justify-center gap-4 pt-2">
              <Link
                href="/orders"
                className="px-7 py-3.5 rounded-2xl bg-brand hover:bg-brand-hover text-white text-sm font-semibold inline-flex items-center gap-2 shadow-lg shadow-blue-600/20 transition active:scale-98"
              >
                Track Order in Account <ArrowRight size={16} />
              </Link>
              <Link
                href="/shop"
                className="px-6 py-3.5 rounded-2xl bg-slate-100 hover:bg-slate-200 text-slate-800 text-sm font-bold transition active:scale-98"
              >
                Continue Shopping
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ==========================================
  // EMPTY CART GUARD
  // ==========================================
  if (items.length === 0) {
    return (
      <div className="min-h-[60vh] bg-[#F5F8FD]/60 flex items-center justify-center py-16">
        <div className="max-w-md mx-auto px-4 text-center">
          <div className="bg-white rounded-[2.5rem] border border-slate-200/80 p-8 sm:p-12 shadow-sm">
            <div className="w-16 h-16 rounded-2xl bg-blue-50 text-brand flex items-center justify-center mx-auto mb-4">
              <Lock size={28} />
            </div>
            <h1 className="text-2xl font-bold text-ink">
              Your Shopping Bag is Empty
            </h1>
            <p className="text-sm text-slate-500 mt-2 leading-relaxed">
              Before proceeding to checkout, please add items to your shopping bag from our catalog.
            </p>
            <Link
              href="/shop"
              className="mt-6 inline-flex items-center gap-2 px-6 py-3 rounded-2xl bg-brand hover:bg-brand-hover text-white text-sm font-semibold transition shadow-md shadow-blue-600/20 active:scale-98"
            >
              Browse Shop Catalog <ArrowRight size={15} />
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // ==========================================
  // MAIN CHECKOUT FORM & FLOW
  // ==========================================
  return (
    <div className="pb-20">
      <div className="bp-container pt-8 sm:pt-10">
        {/* Navigation Breadcrumb & Stepper Header */}
        <div className="mb-8 space-y-4">
          <Link
            href="/cart"
            className="inline-flex min-h-11 items-center gap-1.5 text-sm font-medium text-ink-soft hover:text-ink"
          >
            <ArrowLeft size={16} aria-hidden="true" /> Back to bag
          </Link>

          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h1 className="text-4xl font-bold text-ink sm:text-5xl">Checkout</h1>
            </div>

            {/* Step outline: the three sections below, in order */}
            <ol aria-label="Checkout steps" className="flex items-center gap-2 text-sm text-muted">
              {["Delivery", "Shipping", "Payment"].map((step, index) => (
                <li key={step} className="flex items-center gap-2">
                  {index > 0 && <span aria-hidden="true" className="h-px w-5 bg-line-strong" />}
                  <span className="bp-price flex h-6 w-6 items-center justify-center rounded-full bg-ink text-xs font-semibold text-white">
                    {index + 1}
                  </span>
                  <span className="font-medium text-ink">{step}</span>
                </li>
              ))}
            </ol>
          </div>
        </div>

        {/* User Authentication Status Banner */}
        {authenticated ? (
          <div className="mb-8 flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-white p-4 text-sm ring-1 ring-line">
            <div className="flex items-center gap-2.5">
              <div aria-hidden="true" className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-paper text-ink">
                <UserCheck size={17} />
              </div>
              <div>
                <span className="font-semibold text-ink">
                  Signed in as {currentUser?.name || "Customer"}
                </span>
                <span className="ml-2 text-muted">
                  ({currentUser?.email || ""})
                </span>
                <p className="text-xs text-muted">
                  This order will appear under Orders in your account.
                </p>
              </div>
            </div>
            <Link
              href="/account"
              className="inline-flex min-h-11 items-center rounded-xl border border-line-strong px-4 text-sm font-medium text-ink transition-colors hover:border-ink"
            >
              Account details
            </Link>
          </div>
        ) : (
          <div className="mb-8 flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950 sm:p-5">
            <div className="flex items-start gap-3">
              <AlertCircle size={20} aria-hidden="true" className="mt-0.5 shrink-0 text-amber-700" />
              <div>
                <p className="font-semibold">Sign in to place your order</p>
                <p className="mt-0.5 text-amber-900/80">
                  Orders are linked to an account so you can track delivery and see receipts.
                </p>
              </div>
            </div>
            <Link
              href="/login?redirect=/checkout"
              className="bp-press inline-flex min-h-11 items-center rounded-xl bg-ink px-5 text-sm font-semibold text-white hover:bg-brand"
            >
              Sign in or create account
            </Link>
          </div>
        )}

        {/* Error message banner */}
        {errorMessage && (
          <div
            role="alert"
            aria-live="polite"
            className="mb-8 flex items-center gap-3 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm font-medium text-rose-900"
          >
            <AlertCircle size={18} aria-hidden="true" className="shrink-0 text-rose-700" />
            <span>{errorMessage}</span>
          </div>
        )}

        <form
          onSubmit={handlePlaceOrder}
          className="grid grid-cols-1 items-start gap-8 lg:grid-cols-12 lg:gap-12"
        >
          {/* Left Column: Form Steps */}
          <div className="space-y-6 lg:col-span-7">
            {/* STEP 1: DELIVERY ADDRESS & CONTACT */}
            <section className="rounded-3xl bg-white p-6 ring-1 ring-line sm:p-8 space-y-5">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line pb-4">
                <h2 className="flex items-center gap-3 text-xl font-bold text-ink">
                  <span className="bp-price flex h-7 w-7 items-center justify-center rounded-full bg-ink font-sans text-xs font-semibold text-white">
                    1
                  </span>
                  Delivery address
                </h2>
                {!authenticated && (
                  <Link
                    href="/login?redirect=/checkout"
                    className="text-sm font-medium text-brand underline-offset-4 hover:underline"
                  >
                    Have an account? Sign in
                  </Link>
                )}
              </div>

              {/* Saved Address Selector */}
              {savedAddresses.length > 0 && (
                <div className="space-y-3">
                  <p className="text-sm font-medium text-ink">
                    Saved addresses
                  </p>
                  <div className="space-y-2.5">
                    {savedAddresses.map((addr) => {
                      const isSelected = selectedAddressId === addr.id;
                      return (
                        <label
                          key={addr.id}
                          className={`flex items-start gap-3 p-4 rounded-2xl border cursor-pointer transition ${
                            isSelected
                              ? "border-brand bg-brand-soft ring-1 ring-brand"
                              : "border-line-strong bg-white hover:border-ink"
                          }`}
                        >
                          <input
                            type="radio"
                            name="saved-address"
                            checked={isSelected}
                            onChange={() => setSelectedAddressId(addr.id)}
                            className="mt-1 h-4 w-4 accent-brand"
                          />
                          <div className="text-xs flex-1">
                            <div className="flex items-center gap-2">
                              <span className="font-semibold text-ink">
                                {addr.full_name}
                              </span>
                              <span className="text-slate-400">•</span>
                              <span className="font-semibold text-slate-600">
                                {addr.phone}
                              </span>
                              {addr.is_default && (
                                <span className="px-2 py-0.5 rounded-full bg-blue-100 text-brand text-[11px] font-bold uppercase tracking-wider">
                                  Default
                                </span>
                              )}
                            </div>
                            <p className="text-slate-600 mt-1 leading-relaxed">
                              {addr.address_line}, {addr.city}{" "}
                              {addr.postal_code || ""}
                            </p>
                          </div>
                        </label>
                      );
                    })}

                    <label
                      className={`flex items-center gap-3 p-3.5 rounded-2xl border cursor-pointer text-xs font-bold transition ${
                        selectedAddressId === "new"
                          ? "border-brand bg-blue-50/40 text-brand ring-1 ring-[#245BE7]"
                          : "border-slate-200 text-slate-700 bg-white hover:border-slate-300"
                      }`}
                    >
                      <input
                        type="radio"
                        name="saved-address"
                        checked={selectedAddressId === "new"}
                        onChange={() => setSelectedAddressId("new")}
                        className="h-4 w-4 accent-brand"
                      />
                      <span>Ship to a new delivery address</span>
                    </label>
                  </div>
                </div>
              )}

              {/* New Address Input Form */}
              {(selectedAddressId === "new" || savedAddresses.length === 0) && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
                  <div className="sm:col-span-2">
                    <label
                      htmlFor="checkout-name"
                      className="mb-1.5 block text-sm font-medium text-ink"
                    >
                      Full Name *
                    </label>
                    <input
                      id="checkout-name"
                      name="name"
                      type="text"
                      autoComplete="name"
                      required
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      placeholder="Alex Rivera"
                      className="min-h-12 w-full rounded-xl border border-line-strong bg-white px-4 text-base text-ink placeholder:text-muted focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20 sm:text-sm"
                    />
                  </div>

                  <div>
                    <label
                      htmlFor="checkout-email"
                      className="mb-1.5 block text-sm font-medium text-ink"
                    >
                      Email Address (Receipt & Updates) *
                    </label>
                    <input
                      id="checkout-email"
                      name="email"
                      type="email"
                      autoComplete="email"
                      required
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="alex@example.com"
                      className="min-h-12 w-full rounded-xl border border-line-strong bg-white px-4 text-base text-ink placeholder:text-muted focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20 sm:text-sm"
                    />
                  </div>

                  <div>
                    <label
                      htmlFor="checkout-phone"
                      className="mb-1.5 block text-sm font-medium text-ink"
                    >
                      Mobile Phone (Courier Contact) *
                    </label>
                    <input
                      id="checkout-phone"
                      name="phone"
                      type="tel"
                      autoComplete="tel"
                      required
                      value={phone}
                      onChange={(e) => setPhone(e.target.value)}
                      placeholder="+855 12 345 678"
                      className="min-h-12 w-full rounded-xl border border-line-strong bg-white px-4 text-base text-ink placeholder:text-muted focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20 sm:text-sm"
                    />
                  </div>

                  <div className="sm:col-span-2">
                    <label
                      htmlFor="checkout-street"
                      className="mb-1.5 block text-sm font-medium text-ink"
                    >
                      Street Address, Building & Unit *
                    </label>
                    <textarea
                      id="checkout-street"
                      name="address"
                      rows={3}
                      autoComplete="street-address"
                      required
                      value={streetAddress}
                      onChange={(e) => setStreetAddress(e.target.value)}
                      placeholder="Street #, Building, Apartment/Suite, Landmark"
                      className="min-h-12 w-full rounded-xl border border-line-strong bg-white px-4 text-base text-ink placeholder:text-muted focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20 sm:text-sm resize-none"
                    />
                  </div>

                  <div>
                    <label
                      htmlFor="checkout-city"
                      className="mb-1.5 block text-sm font-medium text-ink"
                    >
                      City / Province *
                    </label>
                    <input
                      id="checkout-city"
                      name="city"
                      type="text"
                      autoComplete="address-level2"
                      required
                      value={city}
                      onChange={(e) => setCity(e.target.value)}
                      placeholder="Phnom Penh"
                      className="min-h-12 w-full rounded-xl border border-line-strong bg-white px-4 text-base text-ink placeholder:text-muted focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20 sm:text-sm"
                    />
                  </div>

                  <div>
                    <label
                      htmlFor="checkout-postal"
                      className="mb-1.5 block text-sm font-medium text-ink"
                    >
                      Postal Code (Optional)
                    </label>
                    <input
                      id="checkout-postal"
                      name="postal-code"
                      type="text"
                      autoComplete="postal-code"
                      value={postalCode}
                      onChange={(e) => setPostalCode(e.target.value)}
                      placeholder="12000"
                      className="min-h-12 w-full rounded-xl border border-line-strong bg-white px-4 text-base text-ink placeholder:text-muted focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20 sm:text-sm"
                    />
                  </div>

                  {authenticated && (
                    <label className="sm:col-span-2 flex items-center gap-2.5 text-xs font-bold text-slate-600 cursor-pointer pt-1">
                      <input
                        type="checkbox"
                        checked={saveAddressForLater}
                        onChange={(e) => setSaveAddressForLater(e.target.checked)}
                        className="h-5 w-5 rounded accent-brand"
                      />
                      Save this address to my account for faster checkout next time
                    </label>
                  )}
                </div>
              )}
            </section>

            {/* STEP 2: SHIPPING METHOD */}
            <section className="rounded-3xl bg-white p-6 ring-1 ring-line sm:p-8 space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line pb-4">
                <h2 className="flex items-center gap-3 text-xl font-bold text-ink">
                  <span className="bp-price flex h-7 w-7 items-center justify-center rounded-full bg-ink font-sans text-xs font-semibold text-white">
                    2
                  </span>
                  Shipping Service
                </h2>
                <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-500">
                  <Truck size={14} className="text-brand" />
                  Standard Tech Dispatch
                </div>
              </div>

              {/* Shipping Method Tile */}
              <div className="p-4 sm:p-5 rounded-2xl border-2 border-brand bg-blue-50/30 flex items-start justify-between gap-4">
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-xl bg-brand text-white flex items-center justify-center shrink-0">
                    <Truck size={20} />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-bold text-ink">
                        Standard Courier Delivery
                      </span>
                      {totals.shipping === 0 ? (
                        <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 text-[11px] font-bold uppercase tracking-wider">
                          Free Shipping
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded-full bg-blue-100 text-blue-800 text-[11px] font-bold uppercase tracking-wider">
                          Flat Rate
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-slate-500 mt-0.5">
                      1–3 business days standard courier dispatch with fragile electronics handling.
                    </p>
                    {totals.amountToFreeShipping > 0 ? (
                      <p className="text-xs font-bold text-brand mt-1.5">
                        Add ${totals.amountToFreeShipping.toFixed(2)} more to unlock FREE standard shipping.
                      </p>
                    ) : (
                      <p className="text-xs font-bold text-emerald-700 mt-1.5 flex items-center gap-1">
                        <Check size={12} /> Free shipping requirement satisfied ($100+ order).
                      </p>
                    )}
                  </div>
                </div>

                <div className="text-right shrink-0">
                  <span className="text-base font-bold text-ink">
                    {totals.shipping === 0 ? "FREE" : `$${totals.shipping.toFixed(2)}`}
                  </span>
                </div>
              </div>
            </section>

            {/* STEP 3: PAYMENT METHOD */}
            <section className="rounded-3xl bg-white p-6 ring-1 ring-line sm:p-8 space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line pb-4">
                <h2 className="flex items-center gap-3 text-xl font-bold text-ink">
                  <span className="bp-price flex h-7 w-7 items-center justify-center rounded-full bg-ink font-sans text-xs font-semibold text-white">
                    3
                  </span>
                  Payment Method
                </h2>
                <div className="flex items-center gap-1 text-xs font-bold text-slate-400">
                  <ShieldCheck size={14} className="text-emerald-600" />
                  Verified Gateways
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {CHECKOUT_PAYMENT_METHODS.map((pm) => {
                  const Icon = PAYMENT_METHOD_ICONS[pm.id] || CreditCard;
                  const active = paymentMethod === pm.id;
                  return (
                    <label
                      key={pm.id}
                      className={`flex items-start gap-3 p-4 rounded-2xl border cursor-pointer transition ${
                        active
                          ? "border-brand bg-blue-50/50 ring-2 ring-[#245BE7]/20"
                          : "border-line-strong bg-white hover:border-ink"
                      }`}
                    >
                      <input
                        type="radio"
                        name="payment-method"
                        checked={active}
                        onChange={() => setPaymentMethod(pm.id)}
                        className="mt-1 h-4 w-4 accent-brand"
                      />
                      <div className="flex-1 min-w-0">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <Icon size={16} className="text-brand shrink-0" />
                          <span className="text-xs font-bold text-ink">
                            {pm.title}
                          </span>
                          {pm.badge ? (
                            <span className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 text-[11px] font-bold uppercase tracking-wider">
                              {pm.badge}
                            </span>
                          ) : (
                            <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 text-[11px] font-bold uppercase tracking-wider">
                              ACTIVE
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-slate-500 mt-1 leading-snug">
                          {pm.subtitle}
                        </p>
                      </div>
                    </label>
                  );
                })}
              </div>

              {/* Informative notice for Sandbox / Demo methods */}
              {CHECKOUT_PAYMENT_METHODS.find((pm) => pm.id === paymentMethod)?.isDemo && (
                <div className="p-3.5 rounded-xl bg-amber-50/90 border border-amber-200 text-amber-900 text-xs flex items-start gap-2.5">
                  <Clock size={16} className="text-amber-600 shrink-0 mt-0.5" />
                  <p className="leading-relaxed">
                    <strong>Sandbox Preview Method:</strong> Live payment gateway capture is currently in demonstration mode. Your order will be placed with payment status{" "}
                    <strong className="underline">Pending Verification</strong>.
                  </p>
                </div>
              )}
            </section>
          </div>

          {/* Right Column: Order Review & Sticky Summary */}
          <aside className="space-y-6 rounded-3xl bg-white p-6 ring-1 ring-line sm:p-8 lg:sticky lg:top-[calc(var(--header-h)+1.5rem)] lg:col-span-5">
            <div className="flex items-center justify-between pb-4 border-b border-slate-100">
              <h2 className="text-lg font-bold text-ink">
                Order Summary
              </h2>
              <span className="px-2.5 py-1 rounded-full bg-blue-50 text-brand text-xs font-bold">
                {totals.totalItems} {totals.totalItems === 1 ? "item" : "items"}
              </span>
            </div>

            {/* Itemized Cart Items Scrollable List */}
            <div className="max-h-72 overflow-y-auto space-y-3 pr-1 divide-y divide-slate-100">
              {items.map((item) => {
                const unit = getEffectivePrice(item.product);
                return (
                  <div key={item.key} className="pt-3 first:pt-0 flex items-center gap-3">
                    <img
                      src={resolveProductImage(item.product)}
                      alt={item.product.name}
                      loading="lazy"
                      width={56}
                      height={56}
                      className="w-14 h-14 rounded-xl object-contain bg-slate-50 border border-slate-100 shrink-0 p-1"
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-bold text-ink truncate">
                        {item.product.name}
                      </p>
                      <p className="text-xs text-slate-400 mt-0.5">
                        Qty {item.quantity}
                        {item.variant ? ` • ${item.variant}` : ""}
                        <span className="ml-1 text-slate-500 font-medium">
                          (@ ${unit.toFixed(2)})
                        </span>
                      </p>
                    </div>
                    <span className="text-xs bp-price font-bold text-ink shrink-0">
                      ${(unit * item.quantity).toFixed(2)}
                    </span>
                  </div>
                );
              })}
            </div>

            {/* Promo Code Input & Dynamic Coupons */}
            <div className="pt-4 border-t border-slate-100 space-y-3">
              <label
                htmlFor="checkout-promo"
                className="block text-sm font-medium text-ink"
              >
                Promotional Voucher
              </label>

              {appliedCoupon ? (
                <div className="flex items-center justify-between p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-800">
                  <span className="font-bold flex items-center gap-1.5">
                    <Tag size={14} className="text-emerald-600" />
                    {appliedCoupon.code} (-${totals.discount.toFixed(2)})
                  </span>
                  <button
                    type="button"
                    onClick={removeCoupon}
                    className="font-bold text-emerald-700 hover:text-rose-600 hover:underline cursor-pointer transition text-xs"
                  >
                    Remove
                  </button>
                </div>
              ) : (
                <div className="flex gap-2">
                  <input
                    id="checkout-promo"
                    type="text"
                    value={promoInput}
                    onChange={(e) => setPromoInput(e.target.value)}
                    placeholder="Enter promo code"
                    className="flex-1 px-3.5 py-2.5 rounded-xl bg-slate-50 border border-slate-200 text-xs font-semibold uppercase tracking-wider focus:outline-none focus:ring-2 focus:ring-[#245BE7] focus:bg-white transition"
                  />
                  <button
                    type="button"
                    onClick={() => handleApplyCoupon()}
                    disabled={couponLoading || !promoInput.trim()}
                    className="px-5 py-2.5 rounded-xl bg-ink hover:bg-slate-800 disabled:opacity-50 text-white text-xs font-bold transition cursor-pointer active:scale-98"
                  >
                    {couponLoading ? "..." : "Apply"}
                  </button>
                </div>
              )}

              {/* Verified Active Promo Chips */}
              {!appliedCoupon && availableCoupons.length > 0 && (
                <div className="space-y-1.5 pt-1">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                    Active Store Vouchers
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {availableCoupons.map((c) => (
                      <button
                        key={c.code}
                        type="button"
                        onClick={() => handleApplyCoupon(c.code)}
                        className="px-2.5 py-1 rounded-lg bg-blue-50 hover:bg-blue-100 border border-blue-200 text-xs font-bold text-brand flex items-center gap-1 transition cursor-pointer active:scale-95"
                      >
                        <Tag size={10} />
                        {c.code}
                        <span className="text-slate-400 font-normal">
                          ({c.discount_type === "percentage" ? `${c.discount_value}%` : `$${c.discount_value}`})
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Pricing Breakdown */}
            <div className="space-y-2.5 text-xs text-slate-600 pt-4 border-t border-slate-100">
              <div className="flex justify-between">
                <span>Hardware Subtotal</span>
                <span className="bp-price font-bold text-slate-900">
                  ${totals.subtotal.toFixed(2)}
                </span>
              </div>

              {totals.discount > 0 && (
                <div className="flex justify-between text-emerald-600 font-bold">
                  <span className="flex items-center gap-1">
                    <Tag size={12} />
                    Promo Discount ({appliedCoupon?.code})
                  </span>
                  <span className="font-mono">
                    -${totals.discount.toFixed(2)}
                  </span>
                </div>
              )}

              <div className="flex justify-between">
                <span>Standard Delivery</span>
                <span className="bp-price font-bold text-slate-900">
                  {totals.shipping === 0 ? (
                    <span className="text-emerald-700 font-bold">FREE</span>
                  ) : (
                    `$${totals.shipping.toFixed(2)}`
                  )}
                </span>
              </div>

              <div className="flex justify-between items-center text-lg font-bold text-ink pt-4 border-t border-slate-200">
                <span>Total Due</span>
                <span className="bp-price text-2xl text-brand">
                  ${totals.total.toFixed(2)}
                </span>
              </div>
            </div>

            {/* Submit Order Action Button */}
            {!authenticated ? (
              <Link
                href="/login?redirect=/checkout"
                className="bp-press min-h-13 w-full px-6 rounded-xl bg-brand hover:bg-brand-hover text-white text-sm font-bold flex items-center justify-center gap-2 shadow-none transition text-center active:scale-98"
              >
                <Lock size={16} aria-hidden="true" />
                Sign in to place order · ${totals.total.toFixed(2)}
              </Link>
            ) : isDemoPayment ? (
              <div className="space-y-2">
                <button
                  type="button"
                  disabled
                  aria-disabled="true"
                  className="bp-press min-h-13 w-full px-6 rounded-xl bg-slate-100 border border-slate-200 text-slate-400 text-sm font-bold flex items-center justify-center gap-2 cursor-not-allowed shadow-none"
                >
                  <Lock size={16} aria-hidden="true" />
                  Online payment is not available yet
                </button>
                <p className="text-xs text-center text-amber-800 font-bold bg-amber-50 py-2 px-3 rounded-xl border border-amber-200">
                  Select <strong>Cash on Delivery (COD)</strong> above to proceed with your order.
                </p>
              </div>
            ) : (
              <button
                type="submit"
                disabled={submitting}
                className="bp-press min-h-13 w-full px-6 rounded-xl bg-brand hover:bg-brand-hover disabled:opacity-55 text-white text-sm font-bold flex items-center justify-center gap-2 shadow-none transition cursor-pointer active:scale-98"
              >
                <Lock size={16} aria-hidden="true" />
                {submitting
                  ? "Placing your order…"
                  : `Place order · $${totals.total.toFixed(2)}`}
              </button>
            )}

            {/* Buyer Trust Guarantees */}
            <div className="space-y-2 border-t border-line pt-4 text-sm text-muted">
              <p className="flex items-center gap-2">
                <Truck size={16} aria-hidden="true" className="shrink-0 text-ink" />
                <span>Courier delivery, usually 1–3 business days</span>
              </p>
              <p className="flex items-center gap-2">
                <ShieldCheck size={16} aria-hidden="true" className="shrink-0 text-ink" />
                <span>Prices, stock and promo codes are re-checked when you place the order</span>
              </p>
            </div>
          </aside>
        </form>
      </div>
    </div>
  );
}
