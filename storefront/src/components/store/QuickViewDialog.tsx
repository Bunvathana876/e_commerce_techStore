"use client";

import { useEffect, useId, useRef, useState } from "react";
import Link from "next/link";
import {
  ArrowRight,
  Check,
  Heart,
  Minus,
  Plus,
  ShoppingBag,
  Star,
  X,
  AlertCircle,
} from "lucide-react";
import {
  applyProductImageFallback,
  getDiscountPercent,
  getEffectivePrice,
  getOriginalPrice,
  resolveProductImage,
} from "@/lib/store-catalog";
import { useShopStore } from "@/lib/store";

export default function QuickViewDialog() {
  const product = useShopStore((s) => s.quickViewProduct);
  const closeQuickView = useShopStore((s) => s.closeQuickView);
  const addToCart = useShopStore((s) => s.addToCart);
  const toggleWishlist = useShopStore((s) => s.toggleWishlist);
  const wishlist = useShopStore((s) => s.wishlist);

  const dialogRef = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const [quantity, setQuantity] = useState(1);

  useEffect(() => {
    setQuantity(1);
  }, [product?.id]);

  // Open / close native modal dialog in top layer
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    if (product) {
      if (!dialog.open) {
        dialog.showModal();
      }
    } else if (dialog.open) {
      dialog.close();
    }
  }, [product]);

  // Light-dismiss backdrop click & Escape handling
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    const handleClose = () => {
      closeQuickView();
    };
    dialog.addEventListener("close", handleClose);

    let handleBackdropClick: ((event: MouseEvent) => void) | null = null;
    if (!("closedBy" in HTMLDialogElement.prototype)) {
      handleBackdropClick = (event: MouseEvent) => {
        if (event.target !== dialog) return;
        const rect = dialog.getBoundingClientRect();
        const isDialogContent =
          rect.top <= event.clientY &&
          event.clientY <= rect.top + rect.height &&
          rect.left <= event.clientX &&
          event.clientX <= rect.left + rect.width;
        if (isDialogContent) return;
        dialog.close();
      };
      dialog.addEventListener("click", handleBackdropClick);
    }

    return () => {
      dialog.removeEventListener("close", handleClose);
      if (handleBackdropClick) {
        dialog.removeEventListener("click", handleBackdropClick);
      }
    };
  }, [closeQuickView]);

  const isWishlisted = product
    ? wishlist.some((w) => w.id === product.id)
    : false;

  if (!product) return null;

  const effectivePrice = getEffectivePrice(product);
  const originalPrice = getOriginalPrice(product);
  const discountPercent = getDiscountPercent(product);
  const rating = Number(product.rating) || 0;
  const outOfStock = product.stock <= 0;
  const lowStock = product.stock > 0 && product.stock <= 10;

  return (
    <dialog
      ref={dialogRef}
      {...({ closedby: "any" } as any)}
      aria-labelledby={titleId}
      className="m-auto w-[calc(100%-1.5rem)] max-w-4xl overflow-hidden rounded-4xl bg-white p-0 text-ink shadow-2xl sm:w-[calc(100%-3rem)]"
    >
      <div className="grid max-h-[90dvh] grid-cols-1 overflow-y-auto md:max-h-[82dvh] md:grid-cols-12 md:overflow-hidden">
        {/* Image */}
        <div className="relative flex min-h-[260px] items-center justify-center bg-paper p-8 md:col-span-6 md:min-h-full">
          <img
            src={resolveProductImage(product)}
            alt={product.name}
            onError={applyProductImageFallback}
            width={600}
            height={600}
            className="max-h-64 w-auto object-contain sm:max-h-96"
          />
          {discountPercent > 0 && (
            <span className="bp-sale-tag absolute left-5 top-5 text-xs">−{discountPercent}%</span>
          )}
        </div>

        {/* Details */}
        <div className="flex flex-col justify-between overflow-y-auto p-6 sm:p-8 md:col-span-6">
          <div>
            <div className="flex items-start justify-between gap-4">
              <p className="flex flex-wrap items-center gap-x-2 pt-2 text-sm text-muted">
                <span>{product.category?.name || "Tech"}</span>
                {product.seller?.name && (
                  <>
                    <span aria-hidden="true">·</span>
                    <span>{product.seller.name}</span>
                  </>
                )}
              </p>
              <button
                type="button"
                onClick={() => dialogRef.current?.close()}
                aria-label="Close preview"
                className="-mr-2 -mt-1 flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-ink-soft transition-colors hover:bg-surface-subtle hover:text-ink"
              >
                <X size={20} aria-hidden="true" />
              </button>
            </div>

            <h2
              id={titleId}
              className="mt-2 text-2xl font-bold leading-tight text-ink sm:text-3xl"
            >
              {product.name}
            </h2>

            {rating > 0 && (
              <p className="mt-2 inline-flex items-center gap-1 text-sm text-ink">
                <Star size={14} aria-hidden="true" className="fill-amber-400 text-amber-400" />
                <span className="font-semibold">{rating.toFixed(1)}</span>
                <span className="sr-only">out of 5</span>
              </p>
            )}

            <div className="mt-6 flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <span className="bp-price text-3xl font-bold text-ink">
                ${effectivePrice.toFixed(2)}
              </span>
              {originalPrice && (
                <span className="bp-price text-base text-muted line-through">
                  ${originalPrice.toFixed(2)}
                </span>
              )}
            </div>
            <p
              className={`mt-2 flex items-center gap-1.5 text-sm font-medium ${
                outOfStock ? "text-muted" : lowStock ? "text-amber-700" : "text-emerald-700"
              }`}
            >
              {outOfStock ? (
                <>
                  <AlertCircle size={15} aria-hidden="true" /> Out of stock
                </>
              ) : lowStock ? (
                <>
                  <AlertCircle size={15} aria-hidden="true" /> Only {product.stock} left in stock
                </>
              ) : (
                <>
                  <Check size={15} aria-hidden="true" /> In stock
                </>
              )}
            </p>

            {product.description && (
              <p className="mt-5 line-clamp-4 text-[15px] leading-7 text-ink-soft">
                {product.description}
              </p>
            )}
          </div>

          <div className="mt-8 space-y-4 border-t border-line pt-6">
            <div className="flex items-center gap-3">
              <div className="inline-flex shrink-0 items-center rounded-xl border border-line-strong">
                <button
                  type="button"
                  onClick={() => setQuantity((q) => Math.max(1, q - 1))}
                  aria-label="Decrease quantity"
                  disabled={outOfStock || quantity <= 1}
                  className="flex h-12 w-10 items-center justify-center text-ink disabled:opacity-30"
                >
                  <Minus size={15} aria-hidden="true" />
                </button>
                <span
                  aria-live="polite"
                  aria-label={`Quantity ${quantity}`}
                  className="bp-price w-7 text-center text-base font-semibold"
                >
                  {quantity}
                </span>
                <button
                  type="button"
                  onClick={() =>
                    setQuantity((q) => Math.min(Math.max(1, product.stock), q + 1))
                  }
                  aria-label="Increase quantity"
                  disabled={outOfStock || quantity >= product.stock}
                  className="flex h-12 w-10 items-center justify-center text-ink disabled:opacity-30"
                >
                  <Plus size={15} aria-hidden="true" />
                </button>
              </div>

              <button
                type="button"
                disabled={outOfStock}
                onClick={() => {
                  addToCart(product, quantity, undefined, true);
                  dialogRef.current?.close();
                }}
                className="bp-press inline-flex min-h-12 flex-1 items-center justify-center gap-2 rounded-xl bg-ink px-5 text-[15px] font-semibold text-white hover:bg-brand disabled:bg-surface-subtle disabled:text-muted"
              >
                <ShoppingBag size={18} aria-hidden="true" />
                {outOfStock ? "Sold out" : "Add to bag"}
              </button>

              <button
                type="button"
                onClick={() => toggleWishlist(product)}
                aria-pressed={isWishlisted}
                aria-label={
                  isWishlisted
                    ? `Remove ${product.name} from wishlist`
                    : `Save ${product.name} to wishlist`
                }
                className={`bp-press flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-line-strong ${
                  isWishlisted ? "text-rose-600" : "text-ink-soft hover:border-ink hover:text-ink"
                }`}
              >
                <Heart size={19} aria-hidden="true" className={isWishlisted ? "fill-current" : ""} />
              </button>
            </div>

            <Link
              href={`/product/${product.id}`}
              onClick={() => dialogRef.current?.close()}
              className="group inline-flex min-h-11 items-center gap-1.5 text-sm font-semibold text-ink"
            >
              <span className="bp-link">Full details and reviews</span>
              <ArrowRight
                size={15}
                aria-hidden="true"
                className="transition-transform group-hover:translate-x-0.5"
              />
            </Link>
          </div>
        </div>
      </div>
    </dialog>
  );
}
