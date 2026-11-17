"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import PageHeader from "@/components/store/PageHeader";
import {
  AlertCircle,
  Compass,
  Cpu,
} from "lucide-react";
import type { ApiCategory, ApiProduct } from "@/lib/api";
import {
  fetchStoreCategories,
  fetchStoreProducts,
} from "@/lib/store-catalog";
import CategoryFeatureCard from "@/components/store/promotions/CategoryFeatureCard";

export default function CategoriesPage() {
  const [categories, setCategories] = useState<ApiCategory[]>([]);
  const [products, setProducts] = useState<ApiProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const loadData = () => {
    setLoading(true);
    setLoadError(null);
    Promise.allSettled([
      fetchStoreCategories(),
      fetchStoreProducts(),
    ]).then(([catRes, prodRes]) => {
      let loadedCats: ApiCategory[] = [];
      let loadedProds: ApiProduct[] = [];

      if (catRes.status === "fulfilled") {
        loadedCats = catRes.value;
        setCategories(loadedCats);
      }
      if (prodRes.status === "fulfilled") {
        loadedProds = prodRes.value.products;
        setProducts(loadedProds);
      }

      const categoriesFailed =
        catRes.status === "rejected" || !catRes.value.isLiveBackend;
      if (categoriesFailed && loadedCats.length === 0) {
        setLoadError("We couldn't load the category directory. Please try again.");
      }
      setLoading(false);
    });
  };

  useEffect(() => {
    loadData();
  }, []);

  // Compute exact product counts per category from real product catalog
  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    products.forEach((p) => {
      const name = (p.category?.name || "").toLowerCase();
      counts[name] = (counts[name] || 0) + 1;
      if (p.category_id) {
        counts[String(p.category_id)] = (counts[String(p.category_id)] || 0) + 1;
      }
    });
    return counts;
  }, [products]);

  // Separate tech departments from secondary lifestyle departments
  const { techCategories, lifestyleCategories } = useMemo(() => {
    const tech: ApiCategory[] = [];
    const lifestyle: ApiCategory[] = [];

    categories.forEach((cat) => {
      const isTech = /electr|tech|audio|gadget|computer|laptop|access|monitor|phone|tablet|game|component/i.test(
        cat.name
      );
      if (isTech) {
        tech.push(cat);
      } else {
        lifestyle.push(cat);
      }
    });

    return { techCategories: tech, lifestyleCategories: lifestyle };
  }, [categories]);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-12 space-y-12">
      <PageHeader
        eyebrow="Categories"
        title="Every department in the store"
        description="Pick a department to see its products, prices and live stock."
        meta={
          !loading && categories.length > 0 ? (
            <span className="bp-price">
              {categories.length} departments · {products.length} products
            </span>
          ) : null
        }
      />

      {/* Loading Skeleton */}
      {loading ? (
        <div className="space-y-6">
          <div className="h-6 w-48 rounded-md bg-slate-200 animate-pulse" />
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                className="h-80 rounded-3xl bg-slate-100 animate-pulse border border-slate-200/80"
              />
            ))}
          </div>
        </div>
      ) : loadError && categories.length === 0 ? (
        /* Error State */
        <div className="bg-white rounded-3xl border border-rose-200 p-12 text-center shadow-xs">
          <div className="w-12 h-12 rounded-full bg-rose-50 text-rose-600 flex items-center justify-center mx-auto mb-3">
            <AlertCircle size={24} />
          </div>
          <h2 className="text-lg font-semibold text-[#181818]">
            Unable to Load Categories
          </h2>
          <p className="text-sm text-slate-500 mt-1 max-w-md mx-auto">
            {loadError}
          </p>
          <button
            type="button"
            onClick={loadData}
            className="mt-5 px-6 py-2.5 rounded-xl bg-[#245BE7] hover:bg-blue-700 text-white text-xs font-semibold transition cursor-pointer shadow-sm"
          >
            Retry
          </button>
        </div>
      ) : categories.length === 0 ? (
        /* Empty State */
        <div className="bg-white rounded-3xl border border-slate-200/80 p-12 text-center shadow-xs">
          <p className="text-lg font-semibold text-[#181818]">
            No Categories Available
          </p>
          <p className="text-sm text-slate-500 mt-1">
            There are currently no categories to display.
          </p>
        </div>
      ) : (
        <>
          {/* Section 1: Technology & Hardware Departments (Primary) */}
          {techCategories.length > 0 && (
            <section className="space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-2 border-b border-slate-200/80 pb-4">
                <div>
                  <span className="text-xs font-semibold uppercase tracking-wider text-[#245BE7] flex items-center gap-1.5">
                    <Cpu size={14} /> Core Technology
                  </span>
                  <h2 className="text-2xl sm:text-3xl font-semibold text-[#181818] mt-1 tracking-tight">
                    Technology &amp; Hardware
                  </h2>
                </div>
                <p className="text-xs text-slate-500">
                  Precision audio, smart wearables, and computing gear
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {techCategories.map((cat) => {
                  const count =
                    categoryCounts[cat.name.toLowerCase()] ??
                    categoryCounts[String(cat.id)] ??
                    0;

                  return (
                    <CategoryFeatureCard
                      key={cat.id}
                      category={cat}
                      productCount={count}
                      highlight={true}
                    />
                  );
                })}
              </div>
            </section>
          )}

          {/* Section 2: Curated Secondary Departments (Footwear, Apparel & Beauty) */}
          {lifestyleCategories.length > 0 && (
            <section className="space-y-6 pt-4">
              <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-2 border-b border-slate-200/80 pb-4">
                <div>
                  <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
                    Additional collections
                  </span>
                  <h2 className="text-2xl sm:text-3xl font-semibold text-[#181818] mt-1 tracking-tight">
                    Lifestyle, Footwear &amp; Apparel
                  </h2>
                </div>
                <p className="text-xs text-slate-500">
                  Curated lifestyle products from verified marketplace sellers
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {lifestyleCategories.map((cat) => {
                  const count =
                    categoryCounts[cat.name.toLowerCase()] ??
                    categoryCounts[String(cat.id)] ??
                    0;

                  return (
                    <CategoryFeatureCard
                      key={cat.id}
                      category={cat}
                      productCount={count}
                      highlight={false}
                    />
                  );
                })}
              </div>
            </section>
          )}

          {/* All Products Bottom Banner */}
          <div className="rounded-3xl bg-slate-50 border border-slate-200/80 p-6 sm:p-8 flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="text-center sm:text-left">
              <h3 className="text-lg font-semibold text-[#181818]">
                Looking for a specific model or component?
              </h3>
              <p className="text-xs sm:text-sm text-slate-500 mt-1">
                Browse our complete hardware catalog with live price and availability filters.
              </p>
            </div>
            <Link
              href="/shop"
              className="px-6 py-3 rounded-2xl bg-[#181818] hover:bg-[#245BE7] text-white text-xs font-semibold transition shrink-0 inline-flex items-center gap-2 shadow-sm"
            >
              <Compass size={16} /> Explore All Products
            </Link>
          </div>
        </>
      )}
    </div>
  );
}
