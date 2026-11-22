"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import PageHeader from "@/components/store/PageHeader";
import {
  AlertCircle,
  Compass,
  Filter,
  PackageOpen,
  RefreshCw,
} from "lucide-react";
import type { ApiCategory, ApiProduct } from "@/lib/api";
import {
  fetchStoreCategories,
  fetchStoreProducts,
} from "@/lib/store-catalog";
import ProductCard from "@/components/store/ProductCard";
import ProductSkeleton from "@/components/store/ProductSkeleton";

export default function NewArrivalsPage() {
  const [products, setProducts] = useState<ApiProduct[]>([]);
  const [categories, setCategories] = useState<ApiCategory[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [selectedCategory, setSelectedCategory] = useState<string>("All");
  const [onlyInStock, setOnlyInStock] = useState<boolean>(false);

  const loadArrivals = useCallback((param?: unknown) => {
    const isRetry =
      typeof param === "object" && param !== null && "isRetry" in param
        ? Boolean((param as { isRetry?: boolean }).isRetry)
        : false;
    setLoading(true);
    setLoadError(null);
    Promise.allSettled([
      fetchStoreProducts(),
      fetchStoreCategories(),
    ]).then(([prodRes, catRes]) => {
      const prodFailed =
        prodRes.status !== "fulfilled" ||
        (!prodRes.value.isLiveBackend && prodRes.value.products.length === 0);

      if (prodFailed && !isRetry && typeof window !== "undefined") {
        setTimeout(() => {
          loadArrivals({ isRetry: true });
        }, 2500);
        return;
      }

      if (prodRes.status === "fulfilled") {
        setProducts(prodRes.value.products);
        if (!prodRes.value.isLiveBackend && prodRes.value.products.length === 0) {
          setLoadError("We couldn't load the catalog. Please try again.");
        }
      } else {
        setProducts([]);
        setLoadError("We couldn't load the catalog. Please try again.");
      }

      if (catRes.status === "fulfilled") {
        setCategories(catRes.value);
      }
      setLoading(false);
    });
  }, []);

  useEffect(() => {
    loadArrivals();
  }, [loadArrivals]);

  // Sort strictly by verified backend creation timestamp (newest first), falling back to ID
  const newestProducts = useMemo(() => {
    return [...products].sort((a, b) => {
      const timeA = a.created_at ? new Date(a.created_at).getTime() : 0;
      const timeB = b.created_at ? new Date(b.created_at).getTime() : 0;
      if (timeB !== timeA) return timeB - timeA;
      return b.id - a.id;
    });
  }, [products]);

  // Filter newest products by selected category and stock
  const filteredArrivals = useMemo(() => {
    return newestProducts.filter((p) => {
      if (selectedCategory !== "All") {
        const matchesCategory =
          p.category?.name?.toLowerCase() === selectedCategory.toLowerCase() ||
          String(p.category_id) === selectedCategory;
        if (!matchesCategory) return false;
      }

      if (onlyInStock && p.stock <= 0) return false;

      return true;
    });
  }, [newestProducts, selectedCategory, onlyInStock]);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-12 space-y-10">
      <PageHeader
        eyebrow="New arrivals"
        title="Just added to the catalog"
        description="The most recent products in stock, newest first."
        meta={
          !loading ? (
            <span className="bp-price">
              {newestProducts.length} recent {newestProducts.length === 1 ? "product" : "products"}
            </span>
          ) : null
        }
      />

      {/* Filter Chips Bar */}
      <div className="bg-white rounded-2xl border border-slate-200/80 p-4 flex flex-wrap items-center justify-between gap-4 shadow-xs">
        {/* Category Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar py-0.5">
          <button
            type="button"
            onClick={() => setSelectedCategory("All")}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition cursor-pointer shrink-0 ${
              selectedCategory === "All"
                ? "bg-[#181818] text-white shadow-xs"
                : "bg-slate-50 text-slate-600 hover:bg-slate-100 border border-slate-200/60"
            }`}
          >
            All Arrivals
          </button>

          {categories.map((c) => {
            const active =
              selectedCategory.toLowerCase() === c.name.toLowerCase();
            return (
              <button
                key={c.id}
                type="button"
                onClick={() => setSelectedCategory(c.name)}
                className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition cursor-pointer shrink-0 ${
                  active
                    ? "bg-[#245BE7] text-white shadow-xs"
                    : "bg-slate-50 text-slate-600 hover:bg-slate-100 border border-slate-200/60"
                }`}
              >
                {c.name}
              </button>
            );
          })}
        </div>

        {/* Right: In-Stock Checkbox & Results Count */}
        <div className="flex items-center gap-4 ml-auto">
          <label className="flex items-center gap-2 text-xs font-bold text-slate-700 cursor-pointer">
            <input
              type="checkbox"
              checked={onlyInStock}
              onChange={(e) => setOnlyInStock(e.target.checked)}
              className="h-4 w-4 rounded border-slate-300 text-[#245BE7] focus:ring-[#245BE7] cursor-pointer"
            />
            <span>In Stock Only</span>
          </label>

          <span className="text-xs font-bold text-slate-400">
            {filteredArrivals.length} {filteredArrivals.length === 1 ? "item" : "items"}
          </span>
        </div>
      </div>

      {/* Product Grid */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {Array.from({ length: 8 }).map((_, i) => (
            <ProductSkeleton key={i} />
          ))}
        </div>
      ) : loadError && products.length === 0 ? (
        <div className="bg-white rounded-3xl border border-rose-200 p-12 text-center shadow-xs">
          <div className="w-12 h-12 rounded-full bg-rose-50 text-rose-600 flex items-center justify-center mx-auto mb-3">
            <AlertCircle size={24} />
          </div>
          <h2 className="text-lg font-semibold text-[#181818]">
            Unable to Load Products
          </h2>
          <p className="text-sm text-slate-500 mt-1 max-w-md mx-auto">
            {loadError}
          </p>
          <button
            type="button"
            onClick={loadArrivals}
            className="mt-5 px-6 py-2.5 rounded-xl bg-[#245BE7] hover:bg-blue-700 text-white text-xs font-semibold transition cursor-pointer shadow-sm inline-flex items-center gap-1.5"
          >
            <RefreshCw size={14} /> Retry
          </button>
        </div>
      ) : products.length === 0 ? (
        <div className="rounded-3xl border border-slate-200/80 bg-white p-12 text-center shadow-xs">
          <div className="w-12 h-12 rounded-2xl bg-blue-50 text-[#245BE7] flex items-center justify-center mx-auto mb-3">
            <PackageOpen size={22} />
          </div>
          <h3 className="text-lg font-semibold text-[#181818]">
            No Products Available
          </h3>
          <p className="text-xs sm:text-sm text-slate-500 mt-1 max-w-md mx-auto leading-relaxed">
            New products will appear here when they become available.
          </p>
        </div>
      ) : filteredArrivals.length === 0 ? (
        <div className="rounded-3xl border border-slate-200/80 bg-white p-12 text-center shadow-xs">
          <div className="w-12 h-12 rounded-2xl bg-blue-50 text-[#245BE7] flex items-center justify-center mx-auto mb-3">
            <Filter size={22} />
          </div>
          <h3 className="text-lg font-semibold text-[#181818]">
            No Items Found
          </h3>
          <p className="text-xs sm:text-sm text-slate-500 mt-1 max-w-md mx-auto leading-relaxed">
            No products match the selected category or stock criteria.
          </p>
          <button
            type="button"
            onClick={() => {
              setSelectedCategory("All");
              setOnlyInStock(false);
            }}
            className="mt-5 px-6 py-2.5 rounded-xl bg-[#181818] hover:bg-[#245BE7] text-white text-xs font-semibold transition cursor-pointer shadow-xs inline-flex items-center gap-2"
          >
            Reset Filters
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {filteredArrivals.map((product) => (
            <ProductCard key={product.id} product={product} />
          ))}
        </div>
      )}

      {/* Catalog Link Footer Banner */}
      <div className="rounded-3xl bg-slate-50 border border-slate-200/80 p-6 sm:p-8 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div>
          <h3 className="text-base font-semibold text-[#181818]">
            Looking for something older or specific?
          </h3>
          <p className="text-xs text-slate-500 mt-1">
            Explore our complete hardware catalog with multi-facet filters and custom price ranges.
          </p>
        </div>
        <Link
          href="/shop"
          className="px-6 py-3 rounded-2xl bg-[#181818] hover:bg-[#245BE7] text-white text-xs font-semibold transition shrink-0 inline-flex items-center gap-2 shadow-xs"
        >
          <Compass size={16} /> Open Shop Catalog
        </Link>
      </div>
    </div>
  );
}
