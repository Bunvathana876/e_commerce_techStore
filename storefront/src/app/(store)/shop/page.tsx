"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import PageHeader from "@/components/store/PageHeader";
import {
  Filter,
  LayoutGrid,
  List,
  RotateCcw,
  Search,
  SlidersHorizontal,
  X,
  AlertCircle,
} from "lucide-react";
import type { ApiCategory, ApiProduct, ApiSeller } from "@/lib/api";
import {
  fetchStoreCategories,
  fetchStoreProducts,
  fetchStoreSellers,
  getDiscountPercent,
  getEffectivePrice,
} from "@/lib/store-catalog";
import ProductCard from "@/components/store/ProductCard";
import ProductSkeleton from "@/components/store/ProductSkeleton";

const PRICE_PRESETS = [
  { label: "All Prices", min: 0, max: Infinity },
  { label: "Under $50", min: 0, max: 50 },
  { label: "$50 – $150", min: 50, max: 150 },
  { label: "$150 – $300", min: 150, max: 300 },
  { label: "$300+", min: 300, max: Infinity },
];

function ShopCatalogContent() {
  const searchParams = useSearchParams();
  const router = useRouter();

  // URL Initial State
  const initialQuery = searchParams.get("q") || "";
  const initialCategory = searchParams.get("category") || "All";
  const initialSeller = searchParams.get("seller") || "All";
  const initialSort = searchParams.get("sort") || "popular";
  const initialStock = searchParams.get("stock") === "true";
  const initialSale = searchParams.get("sale") === "true";
  const initialRating = Number(searchParams.get("rating")) || 0;
  const initialMaxPrice = searchParams.get("max_price")
    ? Number(searchParams.get("max_price"))
    : null;
  const initialViewMode =
    searchParams.get("view") === "list" ? "list" : "grid";

  // Data states
  const [products, setProducts] = useState<ApiProduct[]>([]);
  const [categories, setCategories] = useState<ApiCategory[]>([]);
  const [sellers, setSellers] = useState<ApiSeller[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Filter states
  const [search, setSearch] = useState(initialQuery);
  const [selectedCategory, setSelectedCategory] = useState(initialCategory);
  const [selectedSeller, setSelectedSeller] = useState(initialSeller);
  const [maxPrice, setMaxPrice] = useState<number>(initialMaxPrice ?? 1500);
  const [minRating, setMinRating] = useState(initialRating);
  const [onlyDiscounted, setOnlyDiscounted] = useState(initialSale);
  const [onlyInStock, setOnlyInStock] = useState(initialStock);
  const [sortBy, setSortBy] = useState(initialSort);
  const [viewMode, setViewMode] = useState<"grid" | "list">(initialViewMode);
  const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false);

  // Load Catalog Data
  const loadCatalogData = useCallback(() => {
    setIsLoading(true);
    setLoadError(null);
    Promise.allSettled([
      fetchStoreProducts(),
      fetchStoreCategories(),
      fetchStoreSellers(),
    ]).then(([prodRes, catRes, selRes]) => {
      if (prodRes.status === "fulfilled") {
        setProducts(prodRes.value.products);
        if (!prodRes.value.isLiveBackend && prodRes.value.products.length === 0) {
          setLoadError(
            "We couldn't load the catalog. Please try again."
          );
        }
      } else {
        setLoadError(
          "We couldn't load the catalog. Please try again."
        );
      }
      if (catRes.status === "fulfilled") setCategories(catRes.value);
      if (selRes.status === "fulfilled") setSellers(selRes.value);
      setIsLoading(false);
    });
  }, []);

  useEffect(() => {
    loadCatalogData();
  }, [loadCatalogData]);

  // Determine highest price from products
  const highestCatalogPrice = useMemo(() => {
    if (products.length === 0) return 1000;
    const max = Math.max(...products.map((p) => getEffectivePrice(p)), 200);
    return Math.ceil(max / 50) * 50;
  }, [products]);

  // Sync highest catalog price if no explicit maxPrice from URL
  useEffect(() => {
    if (initialMaxPrice === null && highestCatalogPrice > 0) {
      setMaxPrice(highestCatalogPrice);
    }
  }, [highestCatalogPrice, initialMaxPrice]);

  // Sync state with URL search params on Back / Forward navigation
  useEffect(() => {
    setSearch(searchParams.get("q") || "");
    setSelectedCategory(searchParams.get("category") || "All");
    setSelectedSeller(searchParams.get("seller") || "All");
    setSortBy(searchParams.get("sort") || "popular");
    setOnlyInStock(searchParams.get("stock") === "true");
    setOnlyDiscounted(searchParams.get("sale") === "true");
    setMinRating(Number(searchParams.get("rating")) || 0);
    if (searchParams.get("max_price")) {
      setMaxPrice(Number(searchParams.get("max_price")));
    }
    if (searchParams.get("view") === "list") setViewMode("list");
    else if (searchParams.get("view") === "grid") setViewMode("grid");
  }, [searchParams]);

  // URL updater helper
  const updateUrlParams = useCallback(
    (updates: Record<string, string | null>) => {
      const nextParams = new URLSearchParams(searchParams.toString());
      Object.entries(updates).forEach(([key, val]) => {
        if (val === null || val === "" || val === "All" || val === "0" || val === "false") {
          nextParams.delete(key);
        } else {
          nextParams.set(key, val);
        }
      });
      const qs = nextParams.toString();
      router.replace(qs ? `/shop?${qs}` : "/shop", { scroll: false });
    },
    [router, searchParams]
  );

  // Filter handlers
  const handleCategoryChange = (cat: string) => {
    setSelectedCategory(cat);
    updateUrlParams({ category: cat === "All" ? null : cat });
  };

  const handleSellerChange = (sellerId: string) => {
    setSelectedSeller(sellerId);
    updateUrlParams({ seller: sellerId === "All" ? null : sellerId });
  };

  const handleSortChange = (sort: string) => {
    setSortBy(sort);
    updateUrlParams({ sort: sort === "popular" ? null : sort });
  };

  const handleMaxPriceChange = (val: number) => {
    setMaxPrice(val);
    updateUrlParams({
      max_price: val >= highestCatalogPrice ? null : String(val),
    });
  };

  const handleRatingChange = (rating: number) => {
    setMinRating(rating);
    updateUrlParams({ rating: rating === 0 ? null : String(rating) });
  };

  const handleStockToggle = () => {
    const next = !onlyInStock;
    setOnlyInStock(next);
    updateUrlParams({ stock: next ? "true" : null });
  };

  const handleSaleToggle = () => {
    const next = !onlyDiscounted;
    setOnlyDiscounted(next);
    updateUrlParams({ sale: next ? "true" : null });
  };

  const handleSearchChange = (q: string) => {
    setSearch(q);
    updateUrlParams({ q: q.trim() || null });
  };

  const handleViewModeChange = (mode: "grid" | "list") => {
    setViewMode(mode);
    updateUrlParams({ view: mode === "grid" ? null : "list" });
  };

  const resetFilters = () => {
    setSearch("");
    setSelectedCategory("All");
    setSelectedSeller("All");
    setMaxPrice(highestCatalogPrice);
    setMinRating(0);
    setOnlyDiscounted(false);
    setOnlyInStock(false);
    setSortBy("popular");
    router.replace("/shop", { scroll: false });
  };

  // Lock body scroll when mobile drawer is open
  useEffect(() => {
    if (mobileDrawerOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [mobileDrawerOpen]);

  // Compute category counts
  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    products.forEach((p) => {
      const name = p.category?.name || "General";
      counts[name] = (counts[name] || 0) + 1;
    });
    return counts;
  }, [products]);

  // Filtered & Sorted products
  const filteredProducts = useMemo(() => {
    const q = search.trim().toLowerCase();

    const list = products.filter((p) => {
      if (q) {
        const haystack = `${p.name} ${p.description || ""} ${
          p.category?.name || ""
        } ${p.seller?.name || ""}`.toLowerCase();
        if (!haystack.includes(q)) return false;
      }

      if (selectedCategory !== "All") {
        const catMatch =
          p.category?.name?.toLowerCase() === selectedCategory.toLowerCase() ||
          String(p.category_id) === selectedCategory;
        if (!catMatch) return false;
      }

      if (selectedSeller !== "All") {
        const sellerMatch =
          String(p.seller_id) === selectedSeller ||
          String(p.seller?.id) === selectedSeller;
        if (!sellerMatch) return false;
      }

      const price = getEffectivePrice(p);
      if (price > maxPrice) return false;

      if (minRating > 0 && (Number(p.rating) || 0) < minRating) return false;
      if (onlyDiscounted && getDiscountPercent(p) <= 0) return false;
      if (onlyInStock && p.stock <= 0) return false;

      return true;
    });

    return list.sort((a, b) => {
      if (sortBy === "price_asc") {
        return getEffectivePrice(a) - getEffectivePrice(b);
      }
      if (sortBy === "price_desc") {
        return getEffectivePrice(b) - getEffectivePrice(a);
      }
      if (sortBy === "rating") {
        return (Number(b.rating) || 0) - (Number(a.rating) || 0);
      }
      if (sortBy === "discount") {
        return getDiscountPercent(b) - getDiscountPercent(a);
      }
      if (sortBy === "newest") {
        return b.id - a.id;
      }
      // "popular" or default
      return (Number(b.rating) || 0) * 10 + (b.stock > 0 ? 5 : 0) - ((Number(a.rating) || 0) * 10 + (a.stock > 0 ? 5 : 0));
    });
  }, [
    products,
    search,
    selectedCategory,
    selectedSeller,
    maxPrice,
    minRating,
    onlyDiscounted,
    onlyInStock,
    sortBy,
  ]);

  const activeFilterCount =
    (search.trim() ? 1 : 0) +
    (selectedCategory !== "All" ? 1 : 0) +
    (selectedSeller !== "All" ? 1 : 0) +
    (maxPrice < highestCatalogPrice ? 1 : 0) +
    (minRating > 0 ? 1 : 0) +
    (onlyDiscounted ? 1 : 0) +
    (onlyInStock ? 1 : 0);

  const hasActiveFilters = activeFilterCount > 0;

  // Render Filter Form (reused in desktop sidebar and mobile drawer)
  const renderFilterControls = (isMobile = false) => (
    <div className="space-y-6">
      {/* Categories */}
      <div>
        <h3 className="mb-2 text-sm font-semibold text-ink">Category</h3>
        <div className="space-y-1">
          <button
            type="button"
            onClick={() => {
              handleCategoryChange("All");
              if (isMobile) setMobileDrawerOpen(false);
            }}
            className={`flex min-h-11 w-full items-center justify-between rounded-xl px-3 text-left text-sm font-medium transition-colors ${
              selectedCategory === "All"
                ? "bg-ink text-white"
                : "text-ink-soft hover:bg-surface-subtle hover:text-ink"
            }`}
          >
            <span>All categories</span>
            <span
              className={`bp-price text-xs ${
                selectedCategory === "All"
                  ? "text-white/70"
                  : "text-muted"
              }`}
            >
              {products.length}
            </span>
          </button>

          {categories.map((c) => {
            const active =
              selectedCategory.toLowerCase() === c.name.toLowerCase() ||
              selectedCategory === String(c.id);
            const count = categoryCounts[c.name] || 0;

            return (
              <button
                key={c.id}
                type="button"
                onClick={() => {
                  handleCategoryChange(c.name);
                  if (isMobile) setMobileDrawerOpen(false);
                }}
                className={`flex min-h-11 w-full items-center justify-between rounded-xl px-3 text-left text-sm font-medium transition-colors ${
                  active
                    ? "bg-ink text-white"
                    : "text-ink-soft hover:bg-surface-subtle hover:text-ink"
                }`}
              >
                <span className="truncate">{c.name}</span>
                {count > 0 && (
                  <span
                    className={`bp-price text-xs ${
                      active
                        ? "text-white/70"
                        : "text-muted"
                    }`}
                  >
                    {count}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Price Filtering */}
      <div className="pt-4 border-t border-line">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-ink">
            Maximum price
          </h3>
          <span className="bp-price text-sm font-medium text-muted">
            Up to ${maxPrice}
          </span>
        </div>

        <input
          type="range"
          min={10}
          max={highestCatalogPrice}
          step={5}
          value={maxPrice}
          onChange={(e) => handleMaxPriceChange(Number(e.target.value))}
          className="h-11 w-full accent-brand"
        />

        <div className="bp-price flex justify-between text-xs text-muted">
          <span>$10</span>
          <span>${highestCatalogPrice}</span>
        </div>

        {/* Price Presets */}
        <div className="flex flex-wrap gap-1.5 mt-3">
          {PRICE_PRESETS.map((preset) => {
            const isSelected =
              preset.max === Infinity
                ? maxPrice >= highestCatalogPrice
                : maxPrice === preset.max;

            return (
              <button
                key={preset.label}
                type="button"
                onClick={() => {
                  handleMaxPriceChange(
                    preset.max === Infinity ? highestCatalogPrice : preset.max
                  );
                }}
                className={`min-h-9 rounded-lg border px-2.5 text-xs font-medium transition-colors ${
                  isSelected
                    ? "border-ink bg-ink text-white"
                    : "border-line-strong bg-white text-ink hover:border-ink"
                }`}
              >
                {preset.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Official Sellers */}
      {sellers.length > 0 && (
        <div className="pt-4 border-t border-line">
          <h3 className="mb-2 text-sm font-semibold text-ink">
            Seller
          </h3>
          <select
            value={selectedSeller}
            onChange={(e) => handleSellerChange(e.target.value)}
            aria-label="Filter by seller"
            className="min-h-11 w-full rounded-xl border border-line-strong bg-white px-3.5 text-sm text-ink focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20"
          >
            <option value="All">All sellers</option>
            {sellers.map((s) => (
              <option key={s.id} value={String(s.id)}>
                {s.name}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Customer Rating */}
      <div className="pt-4 border-t border-line">
        <h3 className="mb-2 text-sm font-semibold text-ink">
          Minimum rating
        </h3>
        <div className="grid grid-cols-4 gap-1.5">
          {[0, 4.0, 4.5, 4.8].map((r) => (
            <button
              key={r}
              type="button"
              onClick={() => handleRatingChange(r)}
              aria-pressed={minRating === r}
              className={`min-h-10 rounded-lg border px-2 text-center text-xs font-medium transition-colors ${
                minRating === r
                  ? "border-ink bg-ink text-white"
                  : "border-line-strong bg-white text-ink hover:border-ink"
              }`}
            >
              {r === 0 ? "Any" : `${r}+`}
            </button>
          ))}
        </div>
      </div>

      {/* Availability & Deals Toggles */}
      <div className="space-y-3 pt-4 border-t border-line">
        <label className="flex min-h-11 cursor-pointer items-center justify-between text-sm text-ink">
          <span>In stock only</span>
          <input
            type="checkbox"
            checked={onlyInStock}
            onChange={handleStockToggle}
            className="h-5 w-5 cursor-pointer rounded accent-brand"
          />
        </label>

        <label className="flex min-h-11 cursor-pointer items-center justify-between text-sm text-ink">
          <span>On sale</span>
          <input
            type="checkbox"
            checked={onlyDiscounted}
            onChange={handleSaleToggle}
            className="h-5 w-5 cursor-pointer rounded accent-brand"
          />
        </label>
      </div>
    </div>
  );

  return (
    <div className="bp-container space-y-8 py-10 sm:py-14">
      <PageHeader
        eyebrow="Shop"
        title="The product collection"
        description="Explore the current Blue Panda catalog, with live prices and availability."
        aside={
          <div>
            <label htmlFor="shop-search" className="sr-only">
              Search products
            </label>
            <div className="relative">
              <Search
                size={18}
                aria-hidden="true"
                className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-muted"
              />
              <input
                id="shop-search"
                type="search"
                value={search}
                onChange={(e) => handleSearchChange(e.target.value)}
                placeholder="Search by name or model"
                className="min-h-12 w-full rounded-xl border border-line-strong bg-white pl-11 pr-11 text-base text-ink placeholder:text-muted focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20 sm:text-sm"
              />
              {search && (
                <button
                  type="button"
                  onClick={() => handleSearchChange("")}
                  aria-label="Clear search"
                  className="absolute right-1 top-1/2 flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-lg text-muted hover:text-ink"
                >
                  <X size={16} aria-hidden="true" />
                </button>
              )}
            </div>
          </div>
        }
      />

      <nav aria-label="Browse categories" className="no-scrollbar flex gap-7 overflow-x-auto border-y border-line py-4 text-sm">
        <button type="button" onClick={() => handleCategoryChange("All")} aria-current={selectedCategory === "All" ? "page" : undefined} className={`shrink-0 min-h-9 ${selectedCategory === "All" ? "font-semibold text-ink underline underline-offset-8" : "text-muted hover:text-ink"}`}>All products</button>
        {categories.map((category) => (
          <button key={category.id} type="button" onClick={() => handleCategoryChange(category.name)} aria-current={selectedCategory === category.name ? "page" : undefined} className={`shrink-0 min-h-9 ${selectedCategory === category.name ? "font-semibold text-ink underline underline-offset-8" : "text-muted hover:text-ink"}`}>{category.name}</button>
        ))}
      </nav>

      {/* Main Two-Column Catalog Area */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Desktop Sidebar Filter Panel */}
        <aside className="sticky top-[calc(var(--header-h)+1.5rem)] hidden lg:col-span-3 lg:block">
          <div className="flex items-center justify-between mb-5">
            <h2 className="font-sans text-base font-semibold tracking-normal text-ink">
              Filters
            </h2>
            {hasActiveFilters && (
              <button
                type="button"
                onClick={resetFilters}
                className="text-xs font-bold text-[#245BE7] hover:underline inline-flex items-center gap-1 cursor-pointer"
              >
                <RotateCcw size={12} /> Reset
              </button>
            )}
          </div>

          {renderFilterControls(false)}
        </aside>

        {/* Right Main Product Feed */}
        <div className="space-y-6 lg:col-span-9">
          {/* Controls Toolbar */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-4">
            {/* Left: Mobile Filter Button & Product Count */}
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => setMobileDrawerOpen(true)}
                className="bp-press inline-flex min-h-11 items-center gap-2 rounded-xl border border-line-strong bg-white px-4 text-sm font-semibold text-ink hover:border-ink lg:hidden"
              >
                <Filter size={16} aria-hidden="true" />
                Filters
                {activeFilterCount > 0 && (
                  <span className="bp-price flex h-5 min-w-5 items-center justify-center rounded-full bg-ink px-1 text-[11px] font-bold text-white">
                    {activeFilterCount}
                  </span>
                )}
              </button>

              <div aria-live="polite" className="bp-price text-sm text-muted">
                <span className="font-semibold text-ink">
                  {filteredProducts.length}
                </span>{" "}
                {filteredProducts.length === 1 ? "product" : "products"}
              </div>
            </div>

            {/* Right: Sort Dropdown & Grid/List Mode */}
            <div className="flex items-center gap-3 ml-auto">
              <select
                value={sortBy}
                onChange={(e) => handleSortChange(e.target.value)}
                aria-label="Sort catalog results"
                className="min-h-11 rounded-xl border border-line-strong bg-white px-3.5 text-sm font-medium text-ink hover:border-ink focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20"
              >
                <option value="popular">Featured</option>
                <option value="price_asc">Price: Low to High</option>
                <option value="price_desc">Price: High to Low</option>
                <option value="rating">Highest rated</option>
                <option value="discount">Biggest discount</option>
                <option value="newest">Newest</option>
              </select>

              {/* Grid / List Switcher */}
              <div role="group" aria-label="Layout" className="hidden rounded-xl border border-line-strong bg-white p-1 sm:inline-flex">
                <button
                  type="button"
                  onClick={() => handleViewModeChange("grid")}
                  aria-label="Grid view"
                  aria-pressed={viewMode === "grid"}
                  className={`flex h-9 w-9 items-center justify-center rounded-lg transition-colors ${
                    viewMode === "grid" ? "bg-ink text-white" : "text-muted hover:text-ink"
                  }`}
                >
                  <LayoutGrid size={16} />
                </button>
                <button
                  type="button"
                  onClick={() => handleViewModeChange("list")}
                  aria-label="List view"
                  aria-pressed={viewMode === "list"}
                  className={`flex h-9 w-9 items-center justify-center rounded-lg transition-colors ${
                    viewMode === "list" ? "bg-ink text-white" : "text-muted hover:text-ink"
                  }`}
                >
                  <List size={16} />
                </button>
              </div>
            </div>
          </div>

          {/* Active Filter Chips Row */}
          {hasActiveFilters && (
            <div className="flex flex-wrap items-center gap-2 pt-1">
              <span className="sr-only">Active filters:</span>

              {search.trim() && (
                <span className="inline-flex min-h-9 items-center gap-1 rounded-lg bg-surface-subtle pl-3 pr-1 text-sm font-medium text-ink">
                  &ldquo;{search}&rdquo;
                  <button
                    type="button"
                    onClick={() => handleSearchChange("")}
                    aria-label="Remove search filter"
                    className="flex h-8 w-8 items-center justify-center rounded-md text-muted hover:bg-white hover:text-ink"
                  >
                    <X size={12} />
                  </button>
                </span>
              )}

              {selectedCategory !== "All" && (
                <span className="inline-flex min-h-9 items-center gap-1 rounded-lg bg-surface-subtle pl-3 pr-1 text-sm font-medium text-ink">
                  Category: {selectedCategory}
                  <button
                    type="button"
                    onClick={() => handleCategoryChange("All")}
                    aria-label="Remove category filter"
                    className="flex h-8 w-8 items-center justify-center rounded-md text-muted hover:bg-white hover:text-ink"
                  >
                    <X size={12} />
                  </button>
                </span>
              )}

              {selectedSeller !== "All" && (
                <span className="inline-flex min-h-9 items-center gap-1 rounded-lg bg-surface-subtle pl-3 pr-1 text-sm font-medium text-ink">
                  Store:{" "}
                  {sellers.find((s) => String(s.id) === selectedSeller)?.name ||
                    selectedSeller}
                  <button
                    type="button"
                    onClick={() => handleSellerChange("All")}
                    aria-label="Remove store filter"
                    className="flex h-8 w-8 items-center justify-center rounded-md text-muted hover:bg-white hover:text-ink"
                  >
                    <X size={12} />
                  </button>
                </span>
              )}

              {maxPrice < highestCatalogPrice && (
                <span className="inline-flex min-h-9 items-center gap-1 rounded-lg bg-surface-subtle pl-3 pr-1 text-sm font-medium text-ink">
                  Under ${maxPrice}
                  <button
                    type="button"
                    onClick={() => handleMaxPriceChange(highestCatalogPrice)}
                    aria-label="Reset price filter"
                    className="flex h-8 w-8 items-center justify-center rounded-md text-muted hover:bg-white hover:text-ink"
                  >
                    <X size={12} />
                  </button>
                </span>
              )}

              {minRating > 0 && (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-50 border border-amber-200 text-xs font-bold text-amber-800">
                  {minRating}+ Stars
                  <button
                    type="button"
                    onClick={() => handleRatingChange(0)}
                    aria-label="Remove rating filter"
                    className="hover:text-amber-950 cursor-pointer"
                  >
                    <X size={12} />
                  </button>
                </span>
              )}

              {onlyInStock && (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-xs font-bold text-emerald-800">
                  In Stock Only
                  <button
                    type="button"
                    onClick={handleStockToggle}
                    aria-label="Remove in-stock filter"
                    className="hover:text-emerald-950 cursor-pointer"
                  >
                    <X size={12} />
                  </button>
                </span>
              )}

              {onlyDiscounted && (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-rose-50 border border-rose-200 text-xs font-bold text-rose-800">
                  On Sale Only
                  <button
                    type="button"
                    onClick={handleSaleToggle}
                    aria-label="Remove on-sale filter"
                    className="hover:text-rose-950 cursor-pointer"
                  >
                    <X size={12} />
                  </button>
                </span>
              )}

              <button
                type="button"
                onClick={resetFilters}
                className="ml-1 min-h-9 text-sm font-medium text-brand underline-offset-4 hover:underline"
              >
                Clear all
              </button>
            </div>
          )}

          {/* Product Feed / Loading / Error / Empty States */}
          {isLoading ? (
            <div
              aria-busy="true"
              aria-label="Loading products"
              className={
                viewMode === "list"
                  ? "space-y-4"
                  : "grid grid-cols-2 gap-x-4 gap-y-10 sm:gap-x-6 xl:grid-cols-3"
              }
            >
              {Array.from({ length: 6 }).map((_, i) => (
                <ProductSkeleton key={i} layout={viewMode} />
              ))}
            </div>
          ) : loadError && products.length === 0 ? (
            <div role="alert" className="rounded-3xl border border-rose-200 bg-rose-50/40 px-6 py-14 text-center">
              <AlertCircle size={30} aria-hidden="true" className="mx-auto text-rose-500" />
              <h2 className="mt-4 font-sans text-base font-semibold tracking-normal text-ink">
                Products didn&apos;t load
              </h2>
              <p className="text-sm text-slate-500 mt-1.5 max-w-md mx-auto">
                {loadError}
              </p>
              <button
                type="button"
                onClick={loadCatalogData}
                className="bp-press mt-6 inline-flex min-h-11 items-center rounded-xl border border-line-strong bg-white px-5 text-sm font-semibold text-ink hover:border-ink"
              >
                Try again
              </button>
            </div>
          ) : products.length === 0 ? (
            <div className="rounded-3xl border border-dashed border-line-strong bg-white px-6 py-14 text-center">
              <p className="text-base font-semibold text-ink">
                No products yet
              </p>
              <p className="text-sm text-slate-500 mt-1.5">
                New products will appear here when they become available.
              </p>
            </div>
          ) : filteredProducts.length === 0 ? (
            <div className="rounded-3xl border border-dashed border-line-strong bg-white px-6 py-14 text-center">
              <SlidersHorizontal size={30} aria-hidden="true" className="mx-auto text-muted" />
              <h2 className="mt-4 font-sans text-base font-semibold tracking-normal text-ink">
                Nothing matches those filters
              </h2>
              <p className="mx-auto mt-1.5 max-w-md text-sm leading-6 text-muted">
                Widen the price range or clear a filter to see more products.
              </p>
              <button
                type="button"
                onClick={resetFilters}
                className="bp-press mt-6 inline-flex min-h-11 items-center gap-2 rounded-xl bg-ink px-5 text-sm font-semibold text-white hover:bg-brand"
              >
                <RotateCcw size={16} aria-hidden="true" /> Clear all filters
              </button>
            </div>
          ) : viewMode === "list" ? (
            <div className="space-y-4">
              {filteredProducts.map((product) => (
                <ProductCard key={product.id} product={product} layout="list" />
              ))}
            </div>
          ) : (
            <div className={`grid grid-cols-2 gap-x-4 gap-y-12 sm:gap-x-6 md:grid-cols-3 ${filteredProducts.length >= 3 ? "[&>article:first-child]:md:col-span-2 [&>article:first-child>div:first-child]:md:aspect-[2/1]" : ""}`}>
              {filteredProducts.map((product) => (
                <ProductCard key={product.id} product={product} layout="grid" />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Slide-out Mobile Filter Drawer */}
      {mobileDrawerOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Filter products"
          className="fixed inset-0 z-50 lg:hidden flex justify-end"
        >
          {/* Backdrop */}
          <div
            onClick={() => setMobileDrawerOpen(false)}
            className="fixed inset-0 animate-fade-in bg-ink/50"
          />

          {/* Drawer Body */}
          <div className="relative w-full max-w-md bg-white h-full shadow-2xl flex flex-col z-10 animate-drawer-in duration-300">
            {/* Drawer Header */}
            <div className="p-5 border-b border-slate-100 flex items-center justify-between">
              <div>
                <h2 className="text-base font-semibold text-[#181818] flex items-center gap-2">
                  <SlidersHorizontal size={17} className="text-[#245BE7]" />
                  Filters
                </h2>
                <p className="text-xs text-slate-400 mt-0.5">
                  Refine {products.length} catalog items
                </p>
              </div>

              <div className="flex items-center gap-2">
                {hasActiveFilters && (
                  <button
                    type="button"
                    onClick={resetFilters}
                    className="text-xs font-bold text-[#245BE7] px-2 py-1 rounded-lg hover:bg-blue-50 cursor-pointer"
                  >
                    Reset
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => setMobileDrawerOpen(false)}
                  aria-label="Close filters"
                  className="w-9 h-9 rounded-full bg-slate-100 hover:bg-slate-200 flex items-center justify-center text-slate-600 transition cursor-pointer"
                >
                  <X size={18} />
                </button>
              </div>
            </div>

            {/* Scrollable Filters Content */}
            <div className="p-6 flex-1 overflow-y-auto">
              {renderFilterControls(true)}
            </div>

            {/* Sticky Bottom Actions */}
            <div className="p-4 border-t border-slate-100 bg-white">
              <button
                type="button"
                onClick={() => setMobileDrawerOpen(false)}
                className="w-full py-3.5 px-6 rounded-2xl bg-[#181818] hover:bg-[#245BE7] text-white text-sm font-semibold transition cursor-pointer shadow-lg shadow-blue-900/10"
              >
                Show {filteredProducts.length}{" "}
                {filteredProducts.length === 1 ? "Product" : "Products"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function ShopPage() {
  return (
    <Suspense
      fallback={
        <div className="max-w-7xl mx-auto px-4 py-24 text-center">
          <div className="w-8 h-8 border-3 border-[#245BE7] border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-xs font-bold text-slate-400 mt-3">
            Loading Blue Panda hardware catalog...
          </p>
        </div>
      }
    >
      <ShopCatalogContent />
    </Suspense>
  );
}
