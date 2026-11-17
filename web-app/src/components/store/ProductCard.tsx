"use client";

import Link from "next/link";
import {
  Eye,
  Heart,
  ShoppingBag,
  Sparkles,
  Star,
  Store,
} from "lucide-react";
import type { ApiProduct } from "@/lib/api";
import {
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

export default function ProductCard({
  product,
  layout = "grid",
}: ProductCardProps) {
  const addToCart = useShopStore((s) => s.addToCart);
  const toggleWishlist = useShopStore((s) => s.toggleWishlist);
  const openQuickView = useShopStore((s) => s.openQuickView);
  const isWishlisted = useShopStore((s) =>
    s.wishlist.some((w) => w.id === product.id)
  );

  const effectivePrice = getEffectivePrice(product);
  const originalPrice = getOriginalPrice(product);
  const discountPercent = getDiscountPercent(product);
  const rating = Number(product.rating) || 4.8;
  const outOfStock = product.stock <= 0;
  const lowStock = product.stock > 0 && product.stock <= 12;

  if (layout === "list") {
    return (
      <article className="group bg-white rounded-3xl border border-slate-200/80 hover:border-blue-300 shadow-xs hover:shadow-xl hover:shadow-blue-950/5 transition-all duration-300 p-4 sm:p-5 flex flex-col sm:flex-row gap-5">
        <div className="relative w-full sm:w-52 h-52 rounded-2xl overflow-hidden bg-slate-100 shrink-0">
          <Link href={`/product/${product.id}`} className="block w-full h-full">
            <img
              src={resolveProductImage(product)}
              alt={product.name}
              loading="lazy"
              width={400}
              height={400}
              className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
            />
          </Link>
          {discountPercent > 0 && (
            <span className="absolute top-3 left-3 px-2.5 py-1 rounded-full bg-rose-500 text-white text-xs font-bold shadow-sm">
              -{discountPercent}%
            </span>
          )}
          <button
            type="button"
            onClick={() => toggleWishlist(product)}
            aria-label={isWishlisted ? "Remove from wishlist" : "Save to wishlist"}
            className={`absolute top-3 right-3 w-9 h-9 rounded-full flex items-center justify-center backdrop-blur-md transition-all cursor-pointer ${
              isWishlisted
                ? "bg-rose-500 text-white shadow-md"
                : "bg-white/90 text-slate-700 hover:bg-white hover:text-rose-500"
            }`}
          >
            <Heart size={16} className={isWishlisted ? "fill-current" : ""} />
          </button>
        </div>

        <div className="flex-1 flex flex-col justify-between min-w-0">
          <div>
            <div className="flex flex-wrap items-center gap-2 mb-2">
              {product.category?.name && (
                <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-blue-50 text-blue-700">
                  {product.category.name}
                </span>
              )}
              {product.seller?.name && (
                <span className="inline-flex items-center gap-1 text-xs text-slate-500">
                  <Store size={12} className="text-blue-600" />
                  {product.seller.name}
                </span>
              )}
              <span className="inline-flex items-center gap-1 text-xs font-semibold text-amber-600 ml-auto">
                <Star size={13} className="fill-amber-400 text-amber-400" />
                {rating.toFixed(1)}
              </span>
            </div>

            <Link
              href={`/product/${product.id}`}
              className="text-lg font-bold text-slate-900 hover:text-blue-600 transition-colors line-clamp-1"
            >
              {product.name}
            </Link>
            <p className="text-sm text-slate-500 mt-1.5 line-clamp-2 leading-relaxed">
              {product.description ||
                "Authentic quality guaranteed with fast tracked delivery and 30-day hassle-free returns."}
            </p>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-4 pt-4 mt-4 border-t border-slate-100">
            <div className="flex items-baseline gap-2.5">
              <span className="text-2xl font-extrabold text-slate-900">
                ${effectivePrice.toFixed(2)}
              </span>
              {originalPrice && (
                <span className="text-sm text-slate-400 line-through font-medium">
                  ${originalPrice.toFixed(2)}
                </span>
              )}
              {lowStock && (
                <span className="text-xs font-semibold text-amber-600 bg-amber-50 px-2 py-0.5 rounded-full">
                  Only {product.stock} left
                </span>
              )}
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => openQuickView(product)}
                className="px-3.5 py-2.5 rounded-xl border border-slate-200 text-slate-700 hover:border-blue-300 hover:text-blue-600 text-xs font-semibold inline-flex items-center gap-1.5 transition cursor-pointer"
              >
                <Eye size={15} />
                Quick View
              </button>
              <button
                type="button"
                disabled={outOfStock}
                onClick={() => addToCart(product, 1)}
                className="px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 disabled:bg-slate-200 disabled:text-slate-400 text-white text-xs font-bold inline-flex items-center gap-2 shadow-sm shadow-blue-600/20 transition cursor-pointer"
              >
                <ShoppingBag size={15} />
                {outOfStock ? "Sold Out" : "Add to Bag"}
              </button>
            </div>
          </div>
        </div>
      </article>
    );
  }

  return (
    <article className="group relative bg-white rounded-3xl border border-slate-200/80 hover:border-blue-300/90 shadow-[0_8px_30px_rgba(15,23,42,0.04)] hover:shadow-[0_18px_45px_rgba(37,99,235,0.10)] transition-all duration-300 flex flex-col overflow-hidden">
      {/* Image Container */}
      <div className="relative aspect-square overflow-hidden bg-slate-100">
        <Link href={`/product/${product.id}`} className="block w-full h-full">
          <img
            src={resolveProductImage(product)}
            alt={product.name}
            loading="lazy"
            width={500}
            height={500}
            className="w-full h-full object-cover group-hover:scale-108 transition-transform duration-500 ease-out"
          />
        </Link>

        {/* Top Left Badges */}
        <div className="absolute top-3 left-3 flex flex-col gap-1.5 pointer-events-none">
          {discountPercent > 0 && (
            <span className="px-2.5 py-1 rounded-full bg-rose-500 text-white text-[11px] font-extrabold tracking-wide shadow-sm">
              -{discountPercent}% OFF
            </span>
          )}
          {rating >= 4.85 && !outOfStock && (
            <span className="px-2.5 py-1 rounded-full bg-slate-900/85 backdrop-blur-md text-amber-300 text-[11px] font-bold inline-flex items-center gap-1">
              <Sparkles size={11} />
              Top Pick
            </span>
          )}
          {outOfStock && (
            <span className="px-2.5 py-1 rounded-full bg-slate-900/90 text-white text-[11px] font-bold">
              Out of Stock
            </span>
          )}
        </div>

        {/* Top Right Actions */}
        <div className="absolute top-3 right-3 flex flex-col gap-2">
          <button
            type="button"
            onClick={() => toggleWishlist(product)}
            aria-label={isWishlisted ? "Remove from wishlist" : "Save to wishlist"}
            className={`w-9 h-9 rounded-full flex items-center justify-center backdrop-blur-md transition-all shadow-sm cursor-pointer ${
              isWishlisted
                ? "bg-rose-500 text-white scale-105"
                : "bg-white/90 text-slate-700 hover:bg-white hover:text-rose-500"
            }`}
          >
            <Heart size={16} className={isWishlisted ? "fill-current" : ""} />
          </button>

          <button
            type="button"
            onClick={() => openQuickView(product)}
            aria-label={`Quick view ${product.name}`}
            className="w-9 h-9 rounded-full bg-white/90 text-slate-700 hover:bg-white hover:text-blue-600 flex items-center justify-center backdrop-blur-md shadow-sm opacity-100 sm:opacity-0 sm:translate-x-2 sm:group-hover:opacity-100 sm:group-hover:translate-x-0 transition-all duration-200 cursor-pointer"
          >
            <Eye size={16} />
          </button>
        </div>

      </div>

      {/* Content */}
      <div className="p-4 flex-1 flex flex-col justify-between">
        <div>
          <div className="flex items-center justify-between gap-2 text-xs mb-1.5">
            <span className="font-semibold text-blue-600 truncate">
              {product.category?.name || "Featured"}
            </span>
            <span className="inline-flex items-center gap-1 font-bold text-slate-700 shrink-0">
              <Star size={12} className="fill-amber-400 text-amber-400" />
              {rating.toFixed(1)}
            </span>
          </div>

          <Link
            href={`/product/${product.id}`}
            className="font-bold text-slate-900 group-hover:text-blue-600 transition-colors line-clamp-2 text-sm sm:text-[15px] leading-snug"
          >
            {product.name}
          </Link>

          {product.seller?.name && (
            <p className="mt-1 text-[11px] text-slate-400 flex items-center gap-1 truncate">
              <Store size={11} className="shrink-0" />
              <span className="truncate">{product.seller.name}</span>
            </p>
          )}
        </div>

        <div className="mt-4 pt-3 border-t border-slate-100 flex items-end justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-baseline gap-2">
              <span className="text-lg font-extrabold text-slate-900">
                ${effectivePrice.toFixed(2)}
              </span>
              {originalPrice && (
                <span className="text-xs text-slate-400 line-through font-medium">
                  ${originalPrice.toFixed(2)}
                </span>
              )}
            </div>
            {lowStock && (
              <p className="text-[11px] font-semibold text-amber-600 mt-0.5">
                Only {product.stock} left
              </p>
            )}
          </div>
          <button
            type="button"
            disabled={outOfStock}
            onClick={() => addToCart(product, 1)}
            className="h-10 px-3.5 rounded-xl bg-slate-950 hover:bg-blue-600 disabled:bg-slate-100 disabled:text-slate-400 text-white text-xs font-extrabold inline-flex items-center justify-center gap-1.5 shadow-sm transition-colors cursor-pointer disabled:cursor-not-allowed shrink-0"
          >
            <ShoppingBag size={14} />
            <span>{outOfStock ? "Sold out" : "Add"}</span>
          </button>
        </div>
      </div>
    </article>
  );
}
