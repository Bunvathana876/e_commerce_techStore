"use client";

import Link from "next/link";
import { Eye, Heart, Plus, Star } from "lucide-react";
import type { ApiProduct } from "@/lib/api";
import {
  applyProductImageFallback,
  getDiscountPercent,
  getEffectivePrice,
  getOriginalPrice,
  resolveProductImage,
} from "@/lib/store-catalog";
import { useShopStore } from "@/lib/store";

interface ProductCardProps {
  product: ApiProduct;
  layout?: "grid" | "list";
}

function StockLine({ stock, compact = false }: { stock: number; compact?: boolean }) {
  if (stock <= 0) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-500">
        Out of stock
      </span>
    );
  }
  if (stock <= 10) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-semibold text-amber-700 border border-amber-200/60">
        <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-amber-500" />
        {compact ? `Only ${stock} left` : `Only ${stock} left in stock`}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-semibold text-emerald-700 border border-emerald-200/60">
      <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
      In stock
    </span>
  );
}

export default function ProductCard({
  product,
  layout = "grid",
}: ProductCardProps) {
  const addToCart = useShopStore((state) => state.addToCart);
  const toggleWishlist = useShopStore((state) => state.toggleWishlist);
  const openQuickView = useShopStore((state) => state.openQuickView);
  const isWishlisted = useShopStore((state) =>
    state.wishlist.some((item) => item.id === product.id)
  );

  const effectivePrice = getEffectivePrice(product);
  const originalPrice = getOriginalPrice(product);
  const discountPercent = getDiscountPercent(product);
  const rating = Number(product.rating) || 0;
  const outOfStock = product.stock <= 0;
  const href = `/product/${product.id}`;

  const wishlistButton = (
    <button
      type="button"
      onClick={() => toggleWishlist(product)}
      aria-label={
        isWishlisted
          ? `Remove ${product.name} from wishlist`
          : `Save ${product.name} to wishlist`
      }
      aria-pressed={isWishlisted}
      className={`bp-press flex h-11 w-11 items-center justify-center rounded-xl border transition-all ${
        isWishlisted
          ? "border-rose-200 bg-rose-50 text-rose-600 shadow-xs"
          : "border-slate-200 bg-white/95 text-slate-600 hover:border-rose-300 hover:text-rose-600 shadow-xs"
      }`}
    >
      <Heart size={17} aria-hidden="true" className={isWishlisted ? "fill-current" : ""} />
    </button>
  );

  const priceBlock = (size: "sm" | "lg") => (
    <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
      <span
        className={`bp-price font-bold text-blue-600 ${size === "lg" ? "text-2xl" : "text-base sm:text-lg"}`}
      >
        ${effectivePrice.toFixed(2)}
      </span>
      {originalPrice && (
        <span className="bp-price text-sm text-slate-400 line-through">
          ${originalPrice.toFixed(2)}
        </span>
      )}
    </div>
  );

  // ==========================================
  // LIST VIEW LAYOUT
  // ==========================================
  if (layout === "list") {
    return (
      <article className="group relative flex flex-col gap-5 border-b border-line bg-transparent pb-6 sm:flex-row">
        <div className="relative aspect-square w-full shrink-0 overflow-hidden rounded-2xl border border-slate-200/80 bg-gradient-to-b from-slate-50 via-white to-slate-50/50 p-2 sm:h-48 sm:w-48 group-hover:border-blue-300 group-hover:shadow-md transition-all">
          <Link href={href} tabIndex={-1} aria-hidden="true" className="block h-full w-full">
            <img
              src={resolveProductImage(product)}
              alt=""
              onError={applyProductImageFallback}
              loading="lazy"
              width={480}
              height={480}
              className={`h-full w-full object-contain p-5 transition-transform duration-500 ease-out group-hover:scale-[1.03] ${
                outOfStock ? "opacity-50" : ""
              }`}
            />
          </Link>
          {discountPercent > 0 && (
            <span className="bp-sale-tag absolute left-3 top-3">−{discountPercent}%</span>
          )}
          <div className="absolute right-2 top-2">{wishlistButton}</div>
        </div>

        <div className="flex min-w-0 flex-1 flex-col justify-between">
          <div>
            <p className="flex flex-wrap items-center gap-x-2 text-xs font-medium text-muted">
              {product.category?.name && <span>{product.category.name}</span>}
              {product.seller?.name && (
                <>
                  <span aria-hidden="true">·</span>
                  <span className="truncate">{product.seller.name}</span>
                </>
              )}
              {rating > 0 && (
                <span className="ml-auto inline-flex items-center gap-1 font-semibold text-ink">
                  <Star size={12} aria-hidden="true" className="fill-amber-400 text-amber-400" />
                  {rating.toFixed(1)}
                  <span className="sr-only">out of 5</span>
                </span>
              )}
            </p>

            <h3 className="mt-1.5">
              <Link
                href={href}
                className="line-clamp-2 text-lg font-semibold leading-snug text-ink transition-colors hover:text-brand"
              >
                {product.name}
              </Link>
            </h3>

            {product.description && (
              <p className="mt-2 line-clamp-2 text-sm leading-6 text-muted">
                {product.description}
              </p>
            )}
          </div>

          <div className="mt-5 flex flex-col gap-4 border-t border-line pt-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              {priceBlock("lg")}
              <p className="mt-1 text-xs font-medium">
                <StockLine stock={product.stock} />
              </p>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => openQuickView(product)}
                className="bp-press inline-flex min-h-11 items-center justify-center gap-1.5 rounded-xl border border-line-strong bg-white px-4 text-sm font-semibold text-ink hover:border-ink"
              >
                <Eye size={16} aria-hidden="true" /> Quick view
              </button>
              <button
                type="button"
                disabled={outOfStock}
                onClick={() => addToCart(product, 1)}
                className="bp-press inline-flex min-h-11 items-center justify-center gap-1.5 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 px-5 text-sm font-semibold text-white shadow-sm hover:from-blue-700 hover:to-indigo-700 hover:shadow-md hover:shadow-blue-600/25 transition-all disabled:bg-slate-100 disabled:text-slate-400"
              >
                {outOfStock ? "Sold out" : "Add to bag"}
              </button>
            </div>
          </div>
        </div>
      </article>
    );
  }

  // ==========================================
  // GRID VIEW LAYOUT (DEFAULT)
  // ==========================================
  return (
    <article className="group relative flex h-full flex-col">
      {/* Image: modern rounded container with clean gradient surface and colorful hover border */}
      <div className="relative aspect-square w-full overflow-hidden rounded-2xl border border-slate-200/80 bg-gradient-to-b from-slate-50 via-white to-slate-50/50 p-2 transition-all duration-300 group-hover:border-blue-300 group-hover:shadow-lg group-hover:shadow-blue-500/10 group-has-[h3_a:focus-visible]:outline-2 group-has-[h3_a:focus-visible]:outline-brand">
        <Link href={href} tabIndex={-1} aria-hidden="true" className="block h-full w-full">
          <img
            src={resolveProductImage(product)}
            alt=""
            onError={applyProductImageFallback}
            loading="lazy"
            width={600}
            height={600}
            className={`h-full w-full object-contain p-6 transition-transform duration-500 ease-out group-hover:scale-[1.05] sm:p-8 ${
              outOfStock ? "opacity-50" : ""
            }`}
          />
        </Link>

        {discountPercent > 0 && !outOfStock && (
          <span className="bp-sale-tag pointer-events-none absolute left-3 top-3">
            −{discountPercent}%
          </span>
        )}
        {outOfStock && (
          <span className="pointer-events-none absolute left-3 top-3 rounded-full bg-slate-800 px-2.5 py-1 text-[11px] font-bold text-white shadow-xs">
            Sold out
          </span>
        )}

        <div className="absolute right-2 top-2 z-10 flex flex-col gap-2">
          {wishlistButton}
          <button
            type="button"
            onClick={() => openQuickView(product)}
            aria-label={`Quick view ${product.name}`}
            className="bp-press hidden h-11 w-11 items-center justify-center rounded-xl border border-slate-200 bg-white/95 text-slate-700 shadow-xs hover:border-blue-400 hover:text-blue-600 hover:shadow-sm md:flex md:translate-y-1 md:opacity-0 md:group-focus-within:translate-y-0 md:group-focus-within:opacity-100 md:group-hover:translate-y-0 md:group-hover:opacity-100 transition-all"
          >
            <Eye size={17} aria-hidden="true" />
          </button>
        </div>

        {/* Add to bag: icon button pinned to the image corner */}
        <button
          type="button"
          disabled={outOfStock}
          onClick={() => addToCart(product, 1)}
          aria-label={outOfStock ? `${product.name} is sold out` : `Add ${product.name} to bag`}
          className="bp-press absolute bottom-3 right-3 z-10 flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 text-white shadow-md shadow-blue-600/30 hover:from-blue-700 hover:to-indigo-700 hover:scale-105 transition-all disabled:hidden"
        >
          <Plus size={20} aria-hidden="true" />
        </button>
      </div>

      {/* Details: category, name, price — in that reading order */}
      <div className="flex flex-1 flex-col px-1 pt-4">
        <p className="flex items-center justify-between gap-2 text-xs font-semibold text-blue-600">
          <span className="truncate uppercase tracking-wide">{product.category?.name || ""}</span>
          {rating > 0 && (
            <span className="inline-flex shrink-0 items-center gap-1 font-bold text-slate-800">
              <Star size={12} aria-hidden="true" className="fill-amber-400 text-amber-400" />
              {rating.toFixed(1)}
              <span className="sr-only">out of 5</span>
            </span>
          )}
        </p>

        <h3 className="mt-1">
          <Link
            href={href}
            className="line-clamp-2 text-[15px] font-bold leading-snug text-slate-900 transition-colors after:absolute after:inset-0 after:content-[''] hover:text-blue-600 focus-visible:outline-none group-focus-within:text-blue-600"
          >
            {product.name}
          </Link>
        </h3>

        <div className="mt-auto pt-3">
          {priceBlock("sm")}
          <p className="mt-0.5 text-xs font-medium">
            <StockLine stock={product.stock} compact />
          </p>
        </div>
      </div>
    </article>
  );
}
