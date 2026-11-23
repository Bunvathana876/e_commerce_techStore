"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Heart,
  Minus,
  Plus,
  ShoppingBag,
  Tag,
  Trash2,
  Truck,
} from "lucide-react";
import { couponsApi, settingsApi } from "@/lib/api";
import {
  applyProductImageFallback,
  getEffectivePrice,
  resolveProductImage,
} from "@/lib/store-catalog";
import {
  getCartTotals,
  useShopStore,
  type StoreShippingRules,
} from "@/lib/store";

export default function CartPage() {
  const items = useShopStore((s) => s.items);
  const appliedCoupon = useShopStore((s) => s.appliedCoupon);
  const updateQuantity = useShopStore((s) => s.updateQuantity);
  const removeFromCart = useShopStore((s) => s.removeFromCart);
  const clearCart = useShopStore((s) => s.clearCart);
  const applyCouponCode = useShopStore((s) => s.applyCouponCode);
  const removeCoupon = useShopStore((s) => s.removeCoupon);
  const toggleWishlist = useShopStore((s) => s.toggleWishlist);
  const wishlist = useShopStore((s) => s.wishlist);
  const pushToast = useShopStore((s) => s.pushToast);

  const [promoCode, setPromoCode] = useState("");
  const [promoError, setPromoError] = useState<string | null>(null);
  const [applying, setApplying] = useState(false);
  const [availableCoupons, setAvailableCoupons] = useState<string[]>([]);
  const [shippingRules, setShippingRules] = useState<StoreShippingRules>({});

  useEffect(() => {
    couponsApi
      .available()
      .then((res) => {
        const codes = (res.data || [])
          .filter((c) => c.is_active)
          .map((c) => c.code);
        setAvailableCoupons(codes);
      })
      .catch(() => setAvailableCoupons([]));

    settingsApi
      .getPublic()
      .then((res) => {
        if (res.success && res.data) {
          const min = Number(res.data.free_shipping_min);
          const fee = Number(res.data.standard_shipping_fee);
          setShippingRules({
            freeShippingThreshold: Number.isFinite(min) ? min : undefined,
            standardShippingFee: Number.isFinite(fee) ? fee : undefined,
          });
        }
      })
      .catch(() => {});
  }, []);

  const totals = getCartTotals(items, appliedCoupon, shippingRules);

  const handleApplyPromo = async (codeOverride?: string) => {
    const code = (codeOverride ?? promoCode).trim();
    if (!code) return;
    setPromoError(null);
    setApplying(true);
    try {
      await applyCouponCode(code);
      setPromoCode("");
    } catch (err: unknown) {
      setPromoError(
        err instanceof Error ? err.message : "Invalid promo code."
      );
    } finally {
      setApplying(false);
    }
  };

  const handleMoveToWishlist = async (item: (typeof items)[0]) => {
    await toggleWishlist(item.product);
    await removeFromCart(item.key);
    pushToast({
      title: "Saved to Wishlist",
      description: `${item.product.name} moved to your wishlist.`,
      tone: "info",
    });
  };

  // ==========================================
  // EMPTY CART STATE
  // ==========================================
  if (items.length === 0) {
    return (
      <div className="bp-container max-w-2xl py-20 text-center sm:py-28">
        <div>
          <ShoppingBag size={40} aria-hidden="true" className="mx-auto text-line-strong" />
          <h1 className="mt-5 text-4xl font-bold text-ink sm:text-5xl">Your bag is empty</h1>
          <p className="mx-auto mt-3 max-w-md text-base leading-7 text-muted">
            Products you add from the shop will wait here until you check out.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Link
              href="/shop"
              className="bp-press inline-flex min-h-12 items-center gap-2 rounded-xl bg-ink px-6 text-[15px] font-semibold text-white hover:bg-brand"
            >
              Browse the shop <ArrowRight size={18} aria-hidden="true" />
            </Link>
            <Link
              href="/deals"
              className="bp-press inline-flex min-h-12 items-center gap-2 rounded-xl border border-line-strong bg-white px-6 text-[15px] font-semibold text-ink hover:border-ink"
            >
              See deals
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bp-container space-y-8 py-10 sm:py-14">
      {/* Header Row */}
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-line pb-6">
        <div>
          <Link
            href="/shop"
            className="inline-flex min-h-11 items-center gap-1.5 text-sm font-medium text-ink-soft hover:text-ink"
          >
            <ArrowLeft size={16} aria-hidden="true" /> Continue shopping
          </Link>
          <h1 className="mt-1 text-4xl font-bold text-ink sm:text-5xl">
            Your bag{" "}
            <span className="bp-price font-sans text-xl font-medium text-muted">
              {totals.totalItems} {totals.totalItems === 1 ? "item" : "items"}
            </span>
          </h1>
        </div>

        <button
          type="button"
          onClick={() => clearCart()}
          className="inline-flex min-h-11 items-center gap-1.5 rounded-xl px-3 text-sm font-medium text-muted transition-colors hover:bg-rose-50 hover:text-rose-700"
        >
          <Trash2 size={16} aria-hidden="true" /> Empty bag
        </button>
      </div>

      {/* Main Grid: Items + Sticky Summary */}
      <div className="grid grid-cols-1 items-start gap-10 lg:grid-cols-12 lg:gap-12">
        {/* Left: Cart Items (8 cols) */}
        <div className="space-y-6 lg:col-span-8">
          {/* Free Shipping Meter */}
          <div className="rounded-2xl bg-white p-5 ring-1 ring-line">
            <div className="mb-3 flex items-center justify-between gap-3 text-sm">
              {totals.amountToFreeShipping > 0 ? (
                <span className="flex items-center gap-2 text-ink-soft">
                  <Truck size={18} aria-hidden="true" className="shrink-0 text-ink" />
                  <span>
                    Add{" "}
                    <strong className="bp-price font-semibold text-ink">
                      ${totals.amountToFreeShipping.toFixed(2)}
                    </strong>{" "}
                    more for free delivery
                  </span>
                </span>
              ) : (
                <span className="flex items-center gap-2 font-medium text-emerald-700">
                  <CheckCircle2 size={18} aria-hidden="true" className="shrink-0" />
                  This order ships free
                </span>
              )}
              <span className="bp-price shrink-0 text-xs text-muted">
                ${totals.freeShippingThreshold}
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

          {/* Cart Item Cards */}
          <ul className="divide-y divide-line border-y border-line">
            {items.map((item) => {
              const unitPrice = getEffectivePrice(item.product);
              const isWishlisted = wishlist.some((w) => w.id === item.product.id);
              const outOfStock = item.product.stock <= 0;
              const lowStock = item.product.stock > 0 && item.product.stock <= 10;

              return (
                <li
                  key={item.key}
                  className="flex flex-col items-start gap-4 py-6 sm:flex-row sm:items-center sm:gap-6"
                >
                  {/* Thumbnail */}
                  <Link
                    href={`/product/${item.product.id}`}
                    tabIndex={-1}
                    aria-hidden="true"
                    className="flex h-24 w-24 shrink-0 items-center justify-center overflow-hidden rounded-2xl bg-white p-2 ring-1 ring-line sm:h-28 sm:w-28"
                  >
                    <img
                      src={resolveProductImage(item.product)}
                      alt=""
                      onError={applyProductImageFallback}
                      loading="lazy"
                      width={96}
                      height={96}
                      className="w-full h-full object-contain"
                    />
                  </Link>

                  {/* Details */}
                  <div className="flex-1 min-w-0">
                    <span className="text-xs text-muted">
                      {item.product.category?.name || "Technology"}
                    </span>
                    <Link
                      href={`/product/${item.product.id}`}
                      className="mt-0.5 line-clamp-2 block text-base font-semibold leading-snug text-ink hover:text-brand"
                    >
                      {item.product.name}
                    </Link>

                    {item.variant && (
                      <p className="mt-1 text-sm text-muted">
                        Option: <span className="text-ink">{item.variant}</span>
                      </p>
                    )}

                    <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
                      <span className="bp-price text-muted">
                        ${unitPrice.toFixed(2)} each
                      </span>
                      <span aria-hidden="true" className="text-line-strong">·</span>
                      <span
                        className={`font-medium ${
                          outOfStock
                            ? "flex items-center gap-1 text-rose-700"
                            : lowStock
                            ? "text-amber-700"
                            : "text-emerald-700"
                        }`}
                      >
                        {outOfStock ? (
                          <>
                            <AlertCircle size={14} aria-hidden="true" /> Out of stock
                          </>
                        ) : lowStock ? (
                          `Only ${item.product.stock} left`
                        ) : (
                          "In stock"
                        )}
                      </span>
                    </div>

                    {/* Secondary Actions */}
                    <div className="mt-2 flex items-center gap-1">
                      <button
                        type="button"
                        onClick={() => handleMoveToWishlist(item)}
                        aria-pressed={isWishlisted}
                        className={`-ml-2 inline-flex min-h-11 items-center gap-1.5 rounded-lg px-2 text-sm font-medium transition-colors ${
                          isWishlisted ? "text-rose-700" : "text-ink-soft hover:text-ink"
                        }`}
                      >
                        <Heart
                          size={16}
                          aria-hidden="true"
                          className={isWishlisted ? "fill-current" : ""}
                        />
                        <span>{isWishlisted ? "Saved" : "Save for later"}</span>
                      </button>

                      <button
                        type="button"
                        onClick={() => removeFromCart(item.key)}
                        aria-label={`Remove ${item.product.name} from bag`}
                        className="inline-flex min-h-11 items-center gap-1.5 rounded-lg px-2 text-sm font-medium text-ink-soft transition-colors hover:text-rose-700"
                      >
                        <Trash2 size={16} aria-hidden="true" />
                        <span>Remove</span>
                      </button>
                    </div>
                  </div>

                  {/* Stepper & Line Total */}
                  <div className="flex w-full items-center justify-between gap-3 sm:w-auto sm:flex-col-reverse sm:items-end">
                    <span className="bp-price text-lg font-bold text-ink">
                      ${(unitPrice * item.quantity).toFixed(2)}
                    </span>

                    {/* Stepper */}
                    <div className="inline-flex items-center rounded-xl border border-line-strong bg-white">
                      <button
                        type="button"
                        onClick={() => updateQuantity(item.key, item.quantity - 1)}
                        aria-label="Decrease quantity"
                        className="flex h-11 w-10 items-center justify-center text-ink"
                      >
                        <Minus size={15} aria-hidden="true" />
                      </button>
                      <span className="bp-price w-7 text-center text-sm font-semibold text-ink">
                        {item.quantity}
                      </span>
                      <button
                        type="button"
                        onClick={() => updateQuantity(item.key, item.quantity + 1)}
                        aria-label="Increase quantity"
                        disabled={item.quantity >= item.product.stock}
                        className="flex h-11 w-10 items-center justify-center text-ink disabled:opacity-30"
                      >
                        <Plus size={15} aria-hidden="true" />
                      </button>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>

        {/* Right: Sticky Order Summary (4 cols) */}
        <aside
          aria-labelledby="cart-summary"
          className="space-y-6 rounded-3xl bg-white p-6 ring-1 ring-line sm:p-7 lg:sticky lg:top-[calc(var(--header-h)+1.5rem)] lg:col-span-4"
        >
          <h2 id="cart-summary" className="text-2xl font-bold text-ink">
            Summary
          </h2>

          {/* Coupon Entry */}
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
              <div className="space-y-2.5">
                <div className="flex gap-2">
                  <label htmlFor="cart-promo" className="sr-only">
                    Promo code
                  </label>
                  <input
                    id="cart-promo"
                    type="text"
                    value={promoCode}
                    onChange={(e) => setPromoCode(e.target.value)}
                    placeholder="Promo code"
                    autoComplete="off"
                    aria-invalid={promoError ? true : undefined}
                    aria-describedby={promoError ? "cart-promo-error" : undefined}
                    className="min-h-11 min-w-0 flex-1 rounded-xl border border-line-strong bg-white px-3.5 text-base uppercase text-ink placeholder:normal-case placeholder:text-muted focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20 sm:text-sm"
                  />
                  <button
                    type="button"
                    disabled={applying || !promoCode.trim()}
                    onClick={() => handleApplyPromo()}
                    className="bp-press min-h-11 rounded-xl border border-line-strong bg-white px-4 text-sm font-semibold text-ink hover:border-ink disabled:opacity-40"
                  >
                    {applying ? "Checking…" : "Apply"}
                  </button>
                </div>

                {availableCoupons.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 items-center pt-1">
                    <span className="text-xs text-muted">Available codes:</span>
                    {availableCoupons.map((c) => (
                      <button
                        key={c}
                        type="button"
                        onClick={() => handleApplyPromo(c)}
                        className="min-h-8 rounded-md border border-dashed border-line-strong px-2 font-mono text-xs font-medium text-ink transition-colors hover:border-ink"
                      >
                        {c}
                      </button>
                    ))}
                  </div>
                )}

                {promoError && (
                  <p id="cart-promo-error" role="alert" className="text-sm text-rose-700">
                    {promoError}
                  </p>
                )}
              </div>
            )}
          </div>

          {/* Pricing Breakdown */}
          <dl className="bp-price space-y-3 border-t border-line pt-5 text-sm text-ink-soft">
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

            <div className="flex items-baseline justify-between border-t border-line pt-4 text-ink">
              <dt className="text-base font-semibold">Total</dt>
              <dd className="text-2xl font-bold">${totals.total.toFixed(2)}</dd>
            </div>
          </dl>

          <Link
            href="/checkout"
            className="bp-press flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-brand px-6 text-[15px] font-semibold text-white hover:bg-brand-hover"
          >
            Go to checkout
            <ArrowRight size={18} aria-hidden="true" />
          </Link>

          <p className="text-center text-xs leading-5 text-muted">
            Promo codes and totals are re-checked by the store when you place the order.
          </p>
        </aside>
      </div>
    </div>
  );
}
