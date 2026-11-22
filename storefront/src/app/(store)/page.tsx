"use client";

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import Link from "next/link";
import {
  ArrowRight,
  FilterX,
  Grid2X2,
  PackageOpen,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  Truck,
  Zap,
} from "lucide-react";
import {
  API_BASE_URL,
  categoriesApi,
  productsApi,
  type ApiCategory,
  type ApiProduct,
} from "@/lib/api";
import {
  getDiscountPercent,
  getEffectivePrice,
  resolveProductImage,
} from "@/lib/store-catalog";
import CategoryCard from "@/components/store/CategoryCard";
import FilterToolbar from "@/components/store/FilterToolbar";
import { PrimaryButton } from "@/components/store/PrimaryButton";
import ProductGrid from "@/components/store/ProductGrid";
import PromoHero from "@/components/store/PromoHero";

const BACKEND_ORIGIN = API_BASE_URL.replace(/\/api\/?$/, "");

function resolveCategoryImage(image?: string | null): string | null {
  const value = image?.trim();
  if (!value) return null;
  if (value.startsWith("http://") || value.startsWith("https://")) return value;
  if (value.startsWith("/uploads") || value.startsWith("uploads/")) {
    return `${BACKEND_ORIGIN}${value.startsWith("/") ? value : `/${value}`}`;
  }
  if (value.startsWith("/")) return value;
  return null;
}

function SectionHeader({
  id,
  eyebrow,
  title,
  href,
  action,
  tone = "light",
}: {
  id: string;
  eyebrow: string;
  title: string;
  href?: string;
  action?: string;
  tone?: "light" | "dark";
}) {
  const dark = tone === "dark";
  return (
    <div className="mb-8 flex flex-col gap-3 sm:mb-10 sm:flex-row sm:items-end sm:justify-between sm:gap-6">
      <div>
        <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-bold uppercase tracking-wider ${
          dark ? "bg-sky/20 text-sky border border-sky/30" : "bg-blue-50 text-blue-700 border border-blue-200/70"
        }`}>
          {eyebrow}
        </span>
        <h2
          id={id}
          className={`mt-3 text-3xl font-bold leading-[1.1] sm:text-4xl tracking-tight ${
            dark ? "text-white" : "text-slate-900"
          }`}
        >
          {title}
        </h2>
      </div>
      {href && action && (
        <Link
          href={href}
          className={`group inline-flex min-h-11 shrink-0 items-center gap-1.5 text-sm font-semibold transition-colors ${
            dark ? "text-white" : "text-blue-600 hover:text-blue-700"
          }`}
        >
          <span className="bp-link">{action}</span>
          <ArrowRight
            size={16}
            aria-hidden="true"
            className="transition-transform duration-200 group-hover:translate-x-1"
          />
        </Link>
      )}
    </div>
  );
}

function StatePanel({
  icon,
  title,
  description,
  tone = "neutral",
  action,
}: {
  icon: ReactNode;
  title: string;
  description: string;
  tone?: "neutral" | "error";
  action?: ReactNode;
}) {
  return (
    <div
      role={tone === "error" ? "alert" : undefined}
      className={`rounded-3xl border px-6 py-14 text-center ${
        tone === "error" ? "border-rose-200 bg-rose-50/40" : "border-dashed border-line-strong bg-white"
      }`}
    >
      <span
        aria-hidden="true"
        className={`mx-auto flex justify-center ${tone === "error" ? "text-rose-500" : "text-muted"}`}
      >
        {icon}
      </span>
      <h3 className="mt-4 text-base font-semibold text-ink">{title}</h3>
      <p className="mx-auto mt-1.5 max-w-sm text-sm leading-6 text-muted">{description}</p>
      {action && <div className="mt-6 flex justify-center">{action}</div>}
    </div>
  );
}

export default function StoreHomePage() {
  const [products, setProducts] = useState<ApiProduct[]>([]);
  const [categories, setCategories] = useState<ApiCategory[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [productsError, setProductsError] = useState<boolean>(false);
  const [categoriesError, setCategoriesError] = useState<boolean>(false);

  // Discovery / Filter toolbar state
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [priceRange, setPriceRange] = useState<string>("all");
  const [minRating, setMinRating] = useState<number>(0);
  const [inStockOnly, setInStockOnly] = useState<boolean>(false);
  const [sortBy, setSortBy] = useState<string>("featured");

  const loadHomepage = useCallback(async (param?: unknown) => {
    const isRetry =
      typeof param === "object" && param !== null && "isRetry" in param
        ? Boolean((param as { isRetry?: boolean }).isRetry)
        : false;
    setIsLoading(true);
    setLoadError(null);
    setProductsError(false);
    setCategoriesError(false);

    const [productResult, categoryResult] = await Promise.allSettled([
      productsApi.list({ limit: 40 }),
      categoriesApi.list(true),
    ]);
    let requestFailed = false;

    if (
      productResult.status === "fulfilled" &&
      productResult.value.success !== false &&
      Array.isArray(productResult.value.data?.items)
    ) {
      setProducts(
        productResult.value.data.items.filter(
          (product) => product.is_active !== false
        )
      );
    } else {
      setProducts([]);
      setProductsError(true);
      requestFailed = true;
    }

    if (
      categoryResult.status === "fulfilled" &&
      categoryResult.value.success !== false &&
      Array.isArray(categoryResult.value.data)
    ) {
      setCategories(categoryResult.value.data);
    } else {
      setCategories([]);
      setCategoriesError(true);
      requestFailed = true;
    }

    if (requestFailed && !isRetry && typeof window !== "undefined") {
      setTimeout(() => {
        void loadHomepage({ isRetry: true });
      }, 2500);
      return;
    }

    if (requestFailed) {
      setLoadError(
        "Some store content could not be loaded. Check your connection and try again."
      );
    }
    setIsLoading(false);
  }, []);

  useEffect(() => {
    void loadHomepage();
  }, [loadHomepage]);

  const availableCategories = useMemo(() => {
    const list = categories.length > 0 ? [...categories] : [];
    if (list.length === 0) {
      const fromProducts = new Map<number, ApiCategory>();
      products.forEach((product) => {
        if (product.category) fromProducts.set(product.category.id, product.category);
      });
      list.push(...Array.from(fromProducts.values()));
    }
    // Tech-first priority sorting: Electronics, Accessories, Gadgets first
    return list.sort((a, b) => {
      const aIsTech = /electr|tech|audio|gadget|computer|laptop|access/i.test(a.name);
      const bIsTech = /electr|tech|audio|gadget|computer|laptop|access/i.test(b.name);
      if (aIsTech && !bIsTech) return -1;
      if (!aIsTech && bIsTech) return 1;
      return a.name.localeCompare(b.name);
    });
  }, [categories, products]);

  const heroProducts = useMemo(
    () => products.filter((product) => product.stock > 0),
    [products]
  );

  const isFiltered = useMemo(() => {
    return (
      selectedCategory !== "all" ||
      priceRange !== "all" ||
      minRating > 0 ||
      inStockOnly ||
      sortBy !== "featured"
    );
  }, [selectedCategory, priceRange, minRating, inStockOnly, sortBy]);

  const handleResetFilters = useCallback(() => {
    setSelectedCategory("all");
    setPriceRange("all");
    setMinRating(0);
    setInStockOnly(false);
    setSortBy("featured");
  }, []);

  // Filtered products based on user discovery selections
  const filteredProducts = useMemo(() => {
    let list = [...products];

    // 1. Category
    if (selectedCategory !== "all") {
      list = list.filter(
        (p) =>
          p.category?.name?.toLowerCase() === selectedCategory.toLowerCase() ||
          String(p.category_id) === selectedCategory
      );
    }

    // 2. Price Range
    if (priceRange === "under-50") {
      list = list.filter((p) => getEffectivePrice(p) < 50);
    } else if (priceRange === "50-100") {
      list = list.filter((p) => {
        const price = getEffectivePrice(p);
        return price >= 50 && price <= 100;
      });
    } else if (priceRange === "over-100") {
      list = list.filter((p) => getEffectivePrice(p) > 100);
    }

    // 3. Rating
    if (minRating > 0) {
      list = list.filter((p) => Number(p.rating || 0) >= minRating);
    }

    // 4. In Stock
    if (inStockOnly) {
      list = list.filter((p) => p.stock > 0);
    }

    // 5. Sorting
    if (sortBy === "price-asc") {
      list.sort((a, b) => getEffectivePrice(a) - getEffectivePrice(b));
    } else if (sortBy === "price-desc") {
      list.sort((a, b) => getEffectivePrice(b) - getEffectivePrice(a));
    } else if (sortBy === "rating") {
      list.sort((a, b) => Number(b.rating || 0) - Number(a.rating || 0));
    }

    return list;
  }, [products, selectedCategory, priceRange, minRating, inStockOnly, sortBy]);

  // Featured tech products showing genuine catalog items (tech-prioritized)
  const featuredTechProducts = useMemo(() => {
    const techMatches = products.filter((p) =>
      /electr|tech|audio|gadget|watch|headphone|buds|earbud/i.test(
        `${p.category?.name || ""} ${p.name}`
      )
    );
    return (techMatches.length > 0 ? techMatches : products).slice(0, 8);
  }, [products]);

  const discountedProducts = useMemo(
    () =>
      products
        .filter((product) => getDiscountPercent(product) > 0)
        .sort((a, b) => getDiscountPercent(b) - getDiscountPercent(a))
        .slice(0, 4),
    [products]
  );

  const retryButton = (label = "Try again") => (
    <PrimaryButton type="button" variant="secondary" onClick={() => void loadHomepage()}>
      <RefreshCw size={16} aria-hidden="true" /> {label}
    </PrimaryButton>
  );

  return (
    <div className="pb-4">
      <PromoHero products={heroProducts} isLoading={isLoading} />

      {/* Store Highlights & Tech Guarantees */}
      <section aria-label="Store highlights" className="bp-container mt-8 sm:mt-12">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 sm:gap-4">
          <div className="flex items-center gap-3.5 rounded-2xl border border-blue-100 bg-gradient-to-br from-blue-50/70 via-white to-blue-50/30 p-4 shadow-xs transition-all hover:border-blue-300 hover:shadow-md hover:shadow-blue-500/10">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-blue-600 text-white shadow-sm shadow-blue-500/30">
              <Zap size={20} aria-hidden="true" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-slate-900">Fast Tech Dispatch</h4>
              <p className="text-xs text-slate-600">Same-day order processing</p>
            </div>
          </div>
          <div className="flex items-center gap-3.5 rounded-2xl border border-emerald-100 bg-gradient-to-br from-emerald-50/70 via-white to-teal-50/30 p-4 shadow-xs transition-all hover:border-emerald-300 hover:shadow-md hover:shadow-emerald-500/10">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-emerald-600 text-white shadow-sm shadow-emerald-500/30">
              <ShieldCheck size={20} aria-hidden="true" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-slate-900">2-Year Warranty</h4>
              <p className="text-xs text-slate-600">100% genuine hardware</p>
            </div>
          </div>
          <div className="flex items-center gap-3.5 rounded-2xl border border-indigo-100 bg-gradient-to-br from-indigo-50/70 via-white to-purple-50/30 p-4 shadow-xs transition-all hover:border-indigo-300 hover:shadow-md hover:shadow-indigo-500/10">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-sm shadow-indigo-500/30">
              <Truck size={20} aria-hidden="true" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-slate-900">Free Express Delivery</h4>
              <p className="text-xs text-slate-600">On all orders over $100</p>
            </div>
          </div>
          <div className="flex items-center gap-3.5 rounded-2xl border border-amber-100 bg-gradient-to-br from-amber-50/70 via-white to-orange-50/30 p-4 shadow-xs transition-all hover:border-amber-300 hover:shadow-md hover:shadow-amber-500/10">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-amber-500 text-white shadow-sm shadow-amber-500/30">
              <Sparkles size={20} aria-hidden="true" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-slate-900">30-Day Easy Returns</h4>
              <p className="text-xs text-slate-600">Risk-free trial guarantee</p>
            </div>
          </div>
        </div>
      </section>

      {loadError && (
        <div className="bp-container mt-6">
          <div
            role="alert"
            className="flex flex-col gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 sm:flex-row sm:items-center sm:justify-between"
          >
            <span>{loadError}</span>
            <PrimaryButton
              type="button"
              variant="secondary"
              onClick={() => void loadHomepage()}
              className="border-amber-300 bg-transparent text-amber-900 hover:border-amber-900"
            >
              <RefreshCw size={16} aria-hidden="true" /> Retry
            </PrimaryButton>
          </div>
        </div>
      )}

      {/* 1 — Departments: the quickest route into the catalog */}
      <section aria-labelledby="home-categories" className="bp-container mt-(--section-gap)">
        <SectionHeader
          id="home-categories"
          eyebrow="Departments"
          title="Shop by category"
          href="/categories"
          action="All categories"
        />

        {isLoading ? (
          <div className="grid grid-cols-2 gap-x-4 gap-y-8 sm:grid-cols-3 sm:gap-x-6 lg:grid-cols-6">
            {Array.from({ length: 6 }).map((_, index) => (
              <div key={index} aria-hidden="true" className="animate-pulse">
                <div className="aspect-square rounded-3xl bg-surface-subtle" />
                <div className="mt-3 h-4 w-2/3 rounded bg-surface-subtle" />
              </div>
            ))}
          </div>
        ) : availableCategories.length > 0 ? (
          <div className="grid grid-cols-2 gap-x-4 gap-y-8 sm:grid-cols-3 sm:gap-x-6 lg:grid-cols-6">
            {availableCategories.slice(0, 6).map((category) => {
              const categoryProduct = products.find(
                (product) =>
                  product.category_id === category.id || product.category?.id === category.id
              );
              const categoryImage = resolveCategoryImage(category.image);
              const image = categoryImage
                ? categoryImage
                : categoryProduct
                ? resolveProductImage(categoryProduct)
                : null;

              return <CategoryCard key={category.id} category={category} image={image} />;
            })}
          </div>
        ) : categoriesError ? (
          <StatePanel
            tone="error"
            icon={<Grid2X2 size={30} />}
            title="Categories didn't load"
            description="We couldn't reach the catalog. Check your connection and try again."
            action={retryButton()}
          />
        ) : (
          <StatePanel
            icon={<Grid2X2 size={30} />}
            title="No categories yet"
            description="Departments will appear here as soon as they're published."
          />
        )}
      </section>

      {/* 2 — Catalog: curated picks, or filtered results when the shopper narrows down */}
      <section aria-labelledby="home-catalog" className="mt-(--section-gap)">
        <div className="bp-container">
          <SectionHeader
            id="home-catalog"
            eyebrow={isFiltered ? "Filtered results" : "Featured"}
            title={isFiltered ? "Products matching your filters" : "Picked from the catalog"}
            href="/shop"
            action="Shop all products"
          />
        </div>

        <FilterToolbar
          categories={availableCategories}
          selectedCategory={selectedCategory}
          onSelectCategory={setSelectedCategory}
          priceRange={priceRange}
          onSelectPriceRange={setPriceRange}
          minRating={minRating}
          onSelectMinRating={setMinRating}
          inStockOnly={inStockOnly}
          onToggleInStockOnly={() => setInStockOnly((prev) => !prev)}
          sortBy={sortBy}
          onSelectSortBy={setSortBy}
          totalResults={isFiltered ? filteredProducts.length : products.length}
          onResetFilters={handleResetFilters}
          isFiltered={isFiltered}
        />

        <div className="bp-container mt-8">
          {isFiltered ? (
            filteredProducts.length > 0 ? (
              <ProductGrid products={filteredProducts} />
            ) : (
              <StatePanel
                icon={<FilterX size={34} />}
                title="Nothing matches those filters"
                description="Widen the price range or pick another category to see more products."
                action={
                  <PrimaryButton type="button" onClick={handleResetFilters}>
                    <RotateCcw size={16} aria-hidden="true" /> Reset filters
                  </PrimaryButton>
                }
              />
            )
          ) : isLoading ? (
            <ProductGrid isLoading skeletonCount={8} />
          ) : featuredTechProducts.length > 0 ? (
            <ProductGrid products={featuredTechProducts} editorial />
          ) : productsError ? (
            <StatePanel
              tone="error"
              icon={<PackageOpen size={34} />}
              title="Products didn't load"
              description="We couldn't reach the catalog. Check your connection and try again."
              action={retryButton()}
            />
          ) : (
            <StatePanel
              icon={<PackageOpen size={34} />}
              title="No products yet"
              description="New products will appear here as soon as they're in stock."
              action={retryButton("Refresh")}
            />
          )}
        </div>
      </section>

      {!isFiltered && !isLoading && products.length > 0 && (
        <section aria-labelledby="home-new" className="bp-container mt-(--section-gap)">
          <SectionHeader id="home-new" eyebrow="Recently added" title="New arrivals" href="/new-arrivals" action="View all arrivals" />
          <ProductGrid products={[...products].sort((a, b) => {
            const dateDifference = Date.parse(b.created_at || "") - Date.parse(a.created_at || "");
            return Number.isNaN(dateDifference) || dateDifference === 0 ? b.id - a.id : dateDifference;
          }).slice(0, 4)} />
        </section>
      )}

      {/* Real discounts only */}
      {!isFiltered && !isLoading && discountedProducts.length > 0 && (
        <section
          aria-labelledby="home-deals"
          className="mt-(--section-gap) border-y border-amber-200/70 bg-gradient-to-b from-amber-50/60 via-rose-50/30 to-white py-16 sm:py-20"
        >
          <div className="bp-container">
            <SectionHeader
              id="home-deals"
              eyebrow="🔥 Selected Hot Deals"
              title="Verified discounts & offers"
              href="/deals"
              action="All deals & coupons"
            />
            <ProductGrid products={discountedProducts} />
          </div>
        </section>
      )}
    </div>
  );
}
