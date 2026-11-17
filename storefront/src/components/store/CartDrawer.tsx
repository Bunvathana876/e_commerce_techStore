"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowRight,
  CheckCircle2,
  Minus,
  Plus,
  ShoppingBag,
  Tag,
  Trash2,
  Truck,
  X,
} from "lucide-react";
import { couponsApi } from "@/lib/api";
import {
  applyProductImageFallback,
  getEffectivePrice,
  resolveProductImage,
} from "@/lib/store-catalog";
import {
  FREE_SHIPPING_THRESHOLD,
  getCartTotals,
  useShopStore,
} from "@/lib/store";

export default function CartDrawer() {
  const isOpen = useShopStore((s) => s.isCartOpen);
  const closeCart = useShopStore((s) => s.closeCart);
  const items = useShopStore((s) => s.items);
  const appliedCoupon = useShopStore((s) => s.appliedCoupon);
  const updateQuantity = useShopStore((s) => s.updateQuantity);
  const removeFromCart = useShopStore((s) => s.removeFromCart);
  const applyCouponCode = useShopStore((s) => s.applyCouponCode);
  const removeCoupon = useShopStore((s) => s.removeCoupon);

  const [promoInput, setPromoInput] = useState("");
  const [promoError, setPromoError] = useState<string | null>(null);
  const [applyingPromo, setApplyingPromo] = useState(false);
  const [availableCoupons, setAvailableCoupons] = useState<string[]>([]);

  // Keyboard Escape dismissal & body scroll lock
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeCart();
    };
    window.addEventListener("keydown", handleKeyDown);
    document.body.style.overflow = "hidden";

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
    };
  }, [isOpen, closeCart]);

  useEffect(() => {
    if (!isOpen) return;
    couponsApi
      .available()
      .then((res) => {
        const codes = (res.data || [])
          .filter((c) => c.is_active)
          .map((c) => c.code);
        setAvailableCoupons(codes);
      })
      .catch(() => setAvailableCoupons([]));
  }, [isOpen]);

  const totals = getCartTotals(items, appliedCoupon);

  const handleApplyPromo = async (codeToApply?: string) => {
    const code = (codeToApply ?? promoInput).trim();
    if (!code) return;
    setPromoError(null);
    setApplyingPromo(true);
    try {
      await applyCouponCode(code);
      setPromoInput("");
    } catch (err: unknown) {
      setPromoError(
        err instanceof Error ? err.message : "Invalid promo code."
      );
    } finally {
      setApplyingPromo(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Shopping Bag"
      className="fixed inset-0 z-50 flex justify-end"
    >
      {/* Backdrop */}
      <div
        onClick={closeCart}
        aria-hidden="true"
        className="fixed inset-0 animate-fade-in bg-ink/50"
      />

      {/* Drawer Panel */}
      <aside className="relative z-10 flex h-full max-h-dvh w-full max-w-md animate-drawer-in flex-col justify-between overflow-hidden bg-white shadow-2xl">
        {/* Header */}
        <div className="border-b border-line px-5 pb-5 pt-4">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-bold text-ink">
              Your bag{" "}
              <span className="bp-price font-sans text-base font-medium text-muted">
                ({totals.totalItems})
              </span>
            </h2>

            <button
              type="button"
              onClick={closeCart}
              aria-label="Close shopping bag"
              className="-mr-2 flex h-11 w-11 items-center justify-center rounded-full text-ink-soft transition-colors hover:bg-surface-subtle hover:text-ink"
            >
              <X size={20} aria-hidden="true" />
            </button>
          </div>

          {/* Free Shipping Progress */}
          {items.length > 0 && (
            <div className="mt-4">
              <div className="mb-2 flex items-center justify-between text-sm">
                {totals.amountToFreeShipping > 0 ? (
                  <span className="flex items-center gap-1.5 text-ink-soft">
                    <Truck size={16} aria-hidden="true" className="shrink-0" />
                    <span>
                      <strong className="bp-price font-semibold text-ink">
                        ${totals.amountToFreeShipping.toFixed(2)}
                      </strong>{" "}
                      away from free delivery
                    </span>
                  </span>
                ) : (
                  <span className="flex items-center gap-1.5 font-medium text-emerald-700">
                    <CheckCircle2 size={16} aria-hidden="true" className="shrink-0" />
                    Free delivery on this order
                  </span>
                )}
                <span className="bp-price text-xs text-muted">
                  ${FREE_SHIPPING_THRESHOLD}
                </span>
              </div>
              <div
                role="progressbar"
                aria-label="Progress to free delivery"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={totals.freeShippingProgress}
                className="h-1.5 overflow-hidden rounded-full bg-surface-subtle"
              >
                <div
                  className={`h-full rounded-full transition-[width] duration-500 ease-out ${
                    totals.amountToFreeShipping === 0
                      ? "bg-emerald-500"
                      : "bg-brand"
                  }`}
                  style={{ width: `${totals.freeShippingProgress}%` }}
                />
              </div>
            </div>
          )}
        </div>

        {/* Scrollable Cart Items */}
        <div className="flex-1 overflow-y-auto px-5">
          {items.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center py-12">
              <ShoppingBag size={36} aria-hidden="true" className="text-line-strong" />
              <h3 className="mt-4 text-lg font-semibold text-ink">Your bag is empty</h3>
              <p className="mt-1.5 max-w-xs text-sm leading-6 text-muted">
                Add something from the shop and it will show up here.
              </p>
              <Link
                href="/shop"
                onClick={closeCart}
                className="bp-press mt-6 inline-flex min-h-11 items-center gap-2 rounded-xl bg-ink px-5 text-sm font-semibold text-white hover:bg-brand"
              >
                Browse the shop <ArrowRight size={16} aria-hidden="true" />
              </Link>
            </div>
          ) : (
            items.map((item) => {
              const unitPrice = getEffectivePrice(item.product);

              return (
                <div
                  key={item.key}
                  className="flex gap-4 border-b border-line py-5 last:border-b-0"
                >
                  {/* Thumbnail */}
                  <Link
                    href={`/product/${item.product.id}`}
                    onClick={closeCart}
                    tabIndex={-1}
                    aria-hidden="true"
                    className="flex h-20 w-20 shrink-0 items-center justify-center overflow-hidden rounded-xl bg-paper p-2"
                  >
                    <img
                      src={resolveProductImage(item.product)}
                      alt=""
                      onError={applyProductImageFallback}
                      fetchPriority="low"
                      loading="lazy"
                      width={80}
                      height={80}
                      className="w-full h-full object-contain"
                    />
                  </Link>

                  {/* Info */}
                  <div className="flex-1 min-w-0 flex flex-col justify-between">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <Link
                          href={`/product/${item.product.id}`}
                          onClick={closeCart}
                          className="line-clamp-2 text-sm font-semibold leading-snug text-ink hover:text-brand"
                        >
                          {item.product.name}
                        </Link>
                        {item.variant && (
                          <p className="mt-0.5 text-xs text-muted">
                            {item.variant}
                          </p>
                        )}
                      </div>

                      <button
                        type="button"
                        onClick={() => removeFromCart(item.key)}
                        aria-label={`Remove ${item.product.name}`}
                        className="-mr-2 -mt-2 flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-muted transition-colors hover:text-rose-700"
                      >
                        <Trash2 size={16} aria-hidden="true" />
                      </button>
                    </div>

                    {/* Stepper + Price */}
                    <div className="mt-2 flex items-center justify-between">
                      <div className="inline-flex items-center rounded-lg border border-line-strong">
                        <button
                          type="button"
                          onClick={() => updateQuantity(item.key, item.quantity - 1)}
                          aria-label="Decrease quantity"
                          className="flex h-9 w-9 items-center justify-center text-ink"
                        >
                          <Minus size={14} aria-hidden="true" />
                        </button>
                        <span className="bp-price w-6 text-center text-sm font-semibold text-ink">
                          {item.quantity}
                        </span>
                        <button
                          type="button"
                          onClick={() => updateQuantity(item.key, item.quantity + 1)}
                          aria-label="Increase quantity"
                          disabled={item.quantity >= item.product.stock}
                          className="flex h-9 w-9 items-center justify-center text-ink disabled:opacity-30"
                        >
                          <Plus size={14} aria-hidden="true" />
                        </button>
                      </div>

                      <span className="bp-price text-sm font-semibold text-ink">
                        ${(unitPrice * item.quantity).toFixed(2)}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Sticky Footer */}
        {items.length > 0 && (
          <div className="space-y-4 border-t border-line bg-paper p-5 pb-[max(1.25rem,env(safe-area-inset-bottom))]">
            {/* Promo Voucher Box */}
            <div>
              {appliedCoupon ? (
                <div className="flex min-h-11 items-center justify-between rounded-xl border border-emerald-200 bg-emerald-50 px-3.5 text-sm text-emerald-900">
                  <span className="bp-price flex items-center gap-1.5 font-semibold">
                    <Tag size={15} aria-hidden="true" />
                    Code {appliedCoupon.code} (-${totals.discount.toFixed(2)})
                  </span>
                  <button
                    type="button"
                    onClick={removeCoupon}
                    className="min-h-11 px-1 font-medium text-emerald-800 underline-offset-4 hover:underline"
                  >
                    Remove
                  </button>
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="flex gap-2">
                    <label htmlFor="drawer-promo" className="sr-only">
                      Promo code
                    </label>
                    <input
                      id="drawer-promo"
                      type="text"
                      value={promoInput}
                      onChange={(e) => setPromoInput(e.target.value)}
                      placeholder="Promo code"
                      autoComplete="off"
                      aria-invalid={promoError ? true : undefined}
                      aria-describedby={promoError ? "drawer-promo-error" : undefined}
                      className="min-h-11 min-w-0 flex-1 rounded-xl border border-line-strong bg-white px-3 text-base uppercase text-ink placeholder:normal-case placeholder:text-muted focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20 sm:text-sm"
                    />
                    <button
                      type="button"
                      disabled={applyingPromo || !promoInput.trim()}
                      onClick={() => handleApplyPromo()}
                      className="bp-press min-h-11 rounded-xl border border-line-strong bg-white px-4 text-sm font-semibold text-ink hover:border-ink disabled:opacity-40"
                    >
                      {applyingPromo ? "Checking…" : "Apply"}
                    </button>
                  </div>
                  {availableCoupons.length > 0 && (
                    <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar pt-0.5">
                      <span className="shrink-0 text-xs text-muted">Try:</span>
                      {availableCoupons.map((code) => (
                        <button
                          key={code}
                          type="button"
                          onClick={() => handleApplyPromo(code)}
                          className="min-h-8 shrink-0 rounded-md border border-dashed border-line-strong px-2 font-mono text-xs font-medium text-ink transition-colors hover:border-ink"
                        >
                          {code}
                        </button>
                      ))}
                    </div>
                  )}
                  {promoError && (
                    <p id="drawer-promo-error" role="alert" className="text-sm text-rose-700">
                      {promoError}
                    </p>
                  )}
                </div>
              )}
            </div>

            {/* Totals Breakdown */}
            <dl className="bp-price space-y-2 text-sm text-ink-soft">
              <div className="flex justify-between">
                <dt>Subtotal</dt>
                <dd className="text-ink">${totals.subtotal.toFixed(2)}</dd>
              </div>
              {totals.discount > 0 && (
                <div className="flex justify-between text-emerald-700">
                  <dt>Promo discount</dt>
                  <dd>−${totals.discount.toFixed(2)}</dd>
                </div>
              )}
              <div className="flex justify-between">
                <dt>Delivery</dt>
                <dd className="text-ink">
                  {totals.shipping === 0 ? "Free" : `$${totals.shipping.toFixed(2)}`}
                </dd>
              </div>
              <div className="flex justify-between border-t border-line pt-3 text-base font-semibold text-ink">
                <dt>Total</dt>
                <dd className="text-lg font-bold">${totals.total.toFixed(2)}</dd>
              </div>
            </dl>

            {/* CTA Buttons */}
            <div className="grid grid-cols-1 gap-1">
              <Link
                href="/checkout"
                onClick={closeCart}
                className="bp-press flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-brand px-5 text-[15px] font-semibold text-white hover:bg-brand-hover"
              >
                Go to checkout
                <ArrowRight size={18} aria-hidden="true" />
              </Link>
              <Link
                href="/cart"
                onClick={closeCart}
                className="flex min-h-11 w-full items-center justify-center text-sm font-medium text-ink-soft hover:text-ink"
              >
                <span className="bp-link">View full bag</span>
              </Link>
            </div>
          </div>
        )}
      </aside>
    </div>
  );
}
