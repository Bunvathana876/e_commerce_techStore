"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import PageHeader from "@/components/store/PageHeader";
import {
  AlertCircle,
  ArrowRight,
  Check,
  Copy,
  Percent,
  RefreshCw,
  Tag,
} from "lucide-react";
import type { ApiCoupon, ApiProduct } from "@/lib/api";
import {
  fetchStoreCoupons,
  fetchStoreProducts,
  getDiscountPercent,
} from "@/lib/store-catalog";
import { useShopStore } from "@/lib/store";
import ProductCard from "@/components/store/ProductCard";
import EmptyDealsState from "@/components/store/promotions/EmptyDealsState";

export default function DealsPage() {
  const pushToast = useShopStore((s) => s.pushToast);
  const applyCouponCode = useShopStore((s) => s.applyCouponCode);
  const appliedCoupon = useShopStore((s) => s.appliedCoupon);
  const cartItems = useShopStore((s) => s.items);

  const [products, setProducts] = useState<ApiProduct[]>([]);
  const [coupons, setCoupons] = useState<ApiCoupon[]>([]);
  const [loading, setLoading] = useState(true);
  const [productsError, setProductsError] = useState<string | null>(null);
  const [couponsError, setCouponsError] = useState<string | null>(null);
  const [copiedCode, setCopiedCode] = useState<string | null>(null);
  const retryRef = useRef<((param?: unknown) => void) | null>(null);

  const loadDealsData = useCallback((param?: unknown) => {
    const isRetry =
      typeof param === "object" && param !== null && "isRetry" in param
        ? Boolean((param as { isRetry?: boolean }).isRetry)
        : false;
    setLoading(true);
    setProductsError(null);
    setCouponsError(null);
    Promise.allSettled([
      fetchStoreProducts(),
      fetchStoreCoupons(),
    ]).then(([prodRes, coupRes]) => {
      const prodFailed =
        prodRes.status !== "fulfilled" ||
        (!prodRes.value.isLiveBackend && prodRes.value.products.length === 0);

      if (prodFailed && !isRetry && typeof window !== "undefined") {
        setTimeout(() => {
          retryRef.current?.({ isRetry: true });
        }, 2500);
        return;
      }

      if (prodRes.status === "fulfilled") {
        setProducts(prodRes.value.products);
        if (!prodRes.value.isLiveBackend && prodRes.value.products.length === 0) {
          setProductsError("We couldn't load the catalog. Please try again.");
        }
      } else {
        setProducts([]);
        setProductsError("We couldn't load the catalog. Please try again.");
      }

      if (coupRes.status === "fulfilled") {
        setCoupons(coupRes.value);
        if (!coupRes.value.isLiveBackend && coupRes.value.length === 0) {
          setCouponsError("We couldn't load active promotional coupons. Please try again.");
        }
      } else {
        setCoupons([]);
        setCouponsError("We couldn't load active promotional coupons. Please try again.");
      }
      setLoading(false);
    });
  }, []);

  useEffect(() => {
    retryRef.current = loadDealsData;
  }, [loadDealsData]);

  useEffect(() => {
    loadDealsData();
  }, [loadDealsData]);

  const discountedProducts = useMemo(() => {
    return products
      .filter((p) => getDiscountPercent(p) > 0)
      .sort((a, b) => getDiscountPercent(b) - getDiscountPercent(a));
  }, [products]);

  const handleCopyCode = (code: string) => {
    navigator.clipboard?.writeText(code);
    setCopiedCode(code);
    pushToast({
      title: `Promo Code ${code} Copied`,
      description: "Code copied to clipboard. Apply it in your Shopping Bag or at Checkout.",
      tone: "success",
    });
    window.setTimeout(() => setCopiedCode(null), 2500);
  };

  const handleApplyCoupon = async (code: string) => {
    await applyCouponCode(code);
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-12 space-y-12">
      <PageHeader
        eyebrow="Deals"
        title="This week's price cuts"
        description="Marked-down products from the live catalog, plus promo codes you can apply in your bag or at checkout."
        meta={
          !loading ? (
            <span className="bp-price">
              {discountedProducts.length} {discountedProducts.length === 1 ? "product" : "products"} on sale ·{" "}
              {coupons.length} active {coupons.length === 1 ? "code" : "codes"}
            </span>
          ) : null
        }
      />

      {/* Official Coupons Section */}
      <section className="space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-2 border-b border-slate-200/80 pb-4">
          <div>
            <span className="text-xs font-semibold uppercase tracking-wider text-[#245BE7] flex items-center gap-1.5">
              <Tag size={14} /> Official Store Promos
            </span>
            <h2 className="text-2xl sm:text-3xl font-semibold text-[#181818] mt-1 tracking-tight">
              Available Promo Coupons
            </h2>
          </div>
          <p className="text-xs text-slate-500">
            Apply at checkout or inside your shopping bag. Server-validated per order.
          </p>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div
                key={i}
                className="h-44 rounded-3xl bg-slate-100 animate-pulse border border-slate-200/80"
              />
            ))}
          </div>
        ) : coupons.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {coupons.map((c) => {
              const minAmount = Number(c.min_order_amount) || 0;
              const isCurrentApplied = appliedCoupon?.code === c.code;

              return (
                <div
                  key={c.id}
                  className="p-5 rounded-3xl bg-white border border-slate-200/90 hover:border-blue-300 shadow-xs hover:shadow-xl hover:shadow-blue-600/5 transition-all flex flex-col justify-between gap-4"
                >
                  <div>
                    {/* Discount Pill */}
                    <div className="flex items-center justify-between">
                      <span className="px-3 py-1 rounded-full bg-blue-50 text-[#245BE7] text-xs font-semibold border border-blue-200/80">
                        {c.discount_type === "percent"
                          ? `${Number(c.discount_value)}% OFF`
                          : `$${Number(c.discount_value)} OFF`}
                      </span>
                      {c.max_discount_amount && (
                        <span className="text-[10px] font-bold text-slate-400">
                          Up to ${Number(c.max_discount_amount)}
                        </span>
                      )}
                    </div>

                    {/* Description */}
                    <h3 className="text-sm font-bold text-[#181818] mt-3 leading-snug">
                      {c.description || "Official store promotional discount"}
                    </h3>

                    {/* Threshold requirements */}
                    <p className="text-xs text-slate-500 mt-1 font-medium">
                      {minAmount > 0
                        ? `Valid on orders $${minAmount.toFixed(0)}+`
                        : "No minimum purchase required"}
                    </p>
                  </div>

                  {/* Code Box & Actions */}
                  <div className="pt-3 border-t border-slate-100 flex items-center justify-between gap-2">
                    <code className="text-xs font-semibold bg-slate-100 text-[#181818] px-2.5 py-1.5 rounded-xl tracking-wider">
                      {c.code}
                    </code>

                    <div className="flex items-center gap-1.5">
                      {cartItems.length > 0 && !isCurrentApplied && (
                        <button
                          type="button"
                          onClick={() => handleApplyCoupon(c.code)}
                          title="Apply directly to current shopping bag"
                          className="px-2.5 py-1.5 rounded-xl border border-blue-200 text-[#245BE7] hover:bg-blue-50 text-xs font-bold transition cursor-pointer"
                        >
                          Apply
                        </button>
                      )}

                      <button
                        type="button"
                        onClick={() => handleCopyCode(c.code)}
                        aria-label={`Copy coupon code ${c.code}`}
                        className={`px-3 py-1.5 rounded-xl text-xs font-bold inline-flex items-center gap-1.5 transition cursor-pointer active:scale-95 ${
                          isCurrentApplied
                            ? "bg-emerald-600 text-white"
                            : copiedCode === c.code
                            ? "bg-blue-600 text-white"
                            : "bg-[#181818] hover:bg-[#245BE7] text-white"
                        }`}
                      >
                        {isCurrentApplied ? (
                          <>
                            <Check size={13} /> Active
                          </>
                        ) : copiedCode === c.code ? (
                          <>
                            <Check size={13} /> Copied
                          </>
                        ) : (
                          <>
                            <Copy size={13} /> Copy
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : couponsError && coupons.length === 0 ? (
          <div className="rounded-3xl border border-rose-200 bg-white p-6 text-center sm:text-left flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="flex items-start gap-3">
              <AlertCircle size={20} className="text-rose-500 shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-bold text-[#181818]">
                  Unable to Load Promotions
                </p>
                <p className="text-xs text-slate-500 mt-0.5">
                  {couponsError}
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={loadDealsData}
              className="px-4 py-2 rounded-xl bg-[#245BE7] hover:bg-blue-700 text-white text-xs font-bold inline-flex items-center justify-center gap-1.5 shrink-0 transition shadow-xs cursor-pointer"
            >
              <RefreshCw size={13} /> Retry
            </button>
          </div>
        ) : (
          <div className="rounded-3xl border border-slate-200/80 bg-slate-50 p-6 text-center sm:text-left flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <p className="text-sm font-bold text-slate-800">
                No active promotional codes at this moment
              </p>
              <p className="text-xs text-slate-500 mt-0.5">
                Eligible discounts are automatically computed at checkout. Check back for upcoming seasonal campaigns.
              </p>
            </div>
            <Link
              href="/shop"
              className="px-4 py-2 rounded-xl bg-[#245BE7] hover:bg-blue-700 text-white text-xs font-bold inline-flex items-center justify-center gap-1.5 shrink-0 transition shadow-xs"
            >
              Browse Catalog <ArrowRight size={13} />
            </Link>
          </div>
        )}
      </section>

      {/* Discounted Hardware Products Grid */}
      <section className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-2 border-b border-slate-200/80 pb-4">
          <div>
            <span className="text-xs font-semibold uppercase tracking-wider text-[#245BE7] flex items-center gap-1.5">
              <Percent size={14} /> Price Drops
            </span>
            <h2 className="text-2xl sm:text-3xl font-semibold text-[#181818] mt-1 tracking-tight">
              Discounted Hardware
            </h2>
          </div>
          <p className="text-xs text-slate-500">
            Real prices calculated directly from active store markdown inventory
          </p>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5">
            {Array.from({ length: 4 }).map((_, i) => (
              <div
                key={i}
                className="h-80 rounded-3xl bg-slate-100 animate-pulse border border-slate-200/80"
              />
            ))}
          </div>
        ) : discountedProducts.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5">
            {discountedProducts.map((p) => (
              <ProductCard key={p.id} product={p} />
            ))}
          </div>
        ) : productsError ? (
          <div className="bg-white rounded-3xl border border-rose-200 p-12 text-center shadow-xs">
            <div className="w-12 h-12 rounded-full bg-rose-50 text-rose-600 flex items-center justify-center mx-auto mb-3">
              <AlertCircle size={24} />
            </div>
            <h3 className="text-lg font-semibold text-[#181818]">
              Unable to Load Products
            </h3>
            <p className="text-sm text-slate-500 mt-1 max-w-md mx-auto">
              {productsError}
            </p>
            <button
              type="button"
              onClick={loadDealsData}
              className="mt-5 px-6 py-2.5 rounded-xl bg-[#245BE7] hover:bg-blue-700 text-white text-xs font-semibold transition cursor-pointer shadow-sm inline-flex items-center gap-1.5"
            >
              <RefreshCw size={14} /> Retry
            </button>
          </div>
        ) : (
          <EmptyDealsState
            title="No Markdown Discounts Currently Active"
            description="All items in the store are currently offered at standard verified pricing. Check out our latest arrivals and catalog gear."
            ctaText="Explore Full Catalog"
            ctaHref="/shop"
          />
        )}
      </section>
    </div>
  );
}
