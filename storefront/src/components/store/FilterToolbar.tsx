"use client";

import { useEffect, useRef, useState } from "react";
import { Check, ChevronDown, RotateCcw, SlidersHorizontal, Star } from "lucide-react";
import type { ApiCategory } from "@/lib/api";

export interface FilterToolbarProps {
  categories: ApiCategory[];
  selectedCategory: string;
  onSelectCategory: (category: string) => void;
  priceRange: string;
  onSelectPriceRange: (range: string) => void;
  minRating: number;
  onSelectMinRating: (rating: number) => void;
  inStockOnly: boolean;
  onToggleInStockOnly: () => void;
  sortBy: string;
  onSelectSortBy: (sort: string) => void;
  totalResults: number;
  onResetFilters: () => void;
  isFiltered: boolean;
}

const PRICE_OPTIONS = [
  { value: "all", label: "All Prices" },
  { value: "under-50", label: "Under $50" },
  { value: "50-100", label: "$50 to $100" },
  { value: "over-100", label: "Over $100" },
];

const SORT_OPTIONS = [
  { value: "featured", label: "Featured" },
  { value: "price-asc", label: "Price: Low to High" },
  { value: "price-desc", label: "Price: High to Low" },
  { value: "rating", label: "Customer Rating" },
];

export default function FilterToolbar({
  categories,
  selectedCategory,
  onSelectCategory,
  priceRange,
  onSelectPriceRange,
  minRating,
  onSelectMinRating,
  inStockOnly,
  onToggleInStockOnly,
  sortBy,
  onSelectSortBy,
  totalResults,
  onResetFilters,
  isFiltered,
}: FilterToolbarProps) {
  const [openDropdown, setOpenDropdown] = useState<string | null>(null);
  const toolbarRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (
        toolbarRef.current &&
        !toolbarRef.current.contains(e.target as Node)
      ) {
        setOpenDropdown(null);
      }
    };
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpenDropdown(null);
    };

    document.addEventListener("mousedown", handleOutsideClick);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handleOutsideClick);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  const toggleDropdown = (name: string) => {
    setOpenDropdown((current) => (current === name ? null : name));
  };

  const getPriceLabel = () => {
    const found = PRICE_OPTIONS.find((o) => o.value === priceRange);
    return found && found.value !== "all" ? found.label : "Price Range";
  };

  const getSortLabel = () => {
    const found = SORT_OPTIONS.find((o) => o.value === sortBy);
    return found ? found.label : "Sort by";
  };

  // One chip shape for every filter control; active state is a filled vibrant blue chip.
  const chip = (active: boolean) =>
    `bp-press inline-flex min-h-11 items-center gap-1.5 rounded-xl border px-3.5 text-sm font-semibold transition-all ${
      active
        ? "border-blue-600 bg-gradient-to-r from-blue-600 to-indigo-600 text-white shadow-sm shadow-blue-500/30"
        : "border-slate-200 bg-white text-slate-700 hover:border-blue-300 hover:text-blue-600 shadow-2xs"
    }`;

  const menu = "absolute left-0 z-30 mt-2 w-56 rounded-2xl border border-line bg-white p-1.5 shadow-lg";

  const menuItem = (active: boolean) =>
    `flex w-full min-h-10 items-center justify-between rounded-xl px-3 text-left text-sm font-medium ${
      active ? "bg-brand-soft text-brand" : "text-ink hover:bg-surface-subtle"
    }`;

  return (
    <div
      ref={toolbarRef}
      className="bp-container"
      aria-label="Product discovery filters"
    >
      <div className="flex flex-col gap-4 border-y border-line py-4 md:flex-row md:items-center md:justify-between">
        {/* Horizontal scrollable pill filters */}
        <div className="flex flex-wrap items-center gap-2 sm:gap-2.5">
          <span className="mr-1 hidden items-center gap-1.5 text-sm font-medium text-muted sm:inline-flex">
            <SlidersHorizontal size={16} aria-hidden="true" />
            Filter
          </span>

          {/* 1. Category Dropdown Pill */}
          <div className="relative">
            <button
              type="button"
              onClick={() => toggleDropdown("category")}
              aria-haspopup="true"
              aria-expanded={openDropdown === "category"}
              className={chip(selectedCategory !== "all")}
            >
              <span className="truncate max-w-28 sm:max-w-36">
                {selectedCategory === "all" ? "Category" : selectedCategory}
              </span>
              <ChevronDown
                size={14}
                className={`opacity-60 transition-transform ${
                  openDropdown === "category" ? "rotate-180" : ""
                }`}
              />
            </button>

            {openDropdown === "category" && (
              <div className={`${menu} max-h-72 overflow-y-auto`}>
                <button
                  type="button"
                  onClick={() => {
                    onSelectCategory("all");
                    setOpenDropdown(null);
                  }}
                  className={menuItem(selectedCategory === "all")}
                >
                  <span>All Categories</span>
                  {selectedCategory === "all" && <Check size={14} />}
                </button>
                {categories.map((cat) => (
                  <button
                    key={cat.id}
                    type="button"
                    onClick={() => {
                      onSelectCategory(cat.name);
                      setOpenDropdown(null);
                    }}
                    className={menuItem(selectedCategory === cat.name)}
                  >
                    <span className="truncate">{cat.name}</span>
                    {selectedCategory === cat.name && <Check size={14} />}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* 2. Price Range Dropdown Pill */}
          <div className="relative">
            <button
              type="button"
              onClick={() => toggleDropdown("price")}
              aria-haspopup="true"
              aria-expanded={openDropdown === "price"}
              className={chip(priceRange !== "all")}
            >
              <span>{getPriceLabel()}</span>
              <ChevronDown
                size={14}
                className={`opacity-60 transition-transform ${
                  openDropdown === "price" ? "rotate-180" : ""
                }`}
              />
            </button>

            {openDropdown === "price" && (
              <div className={menu}>
                {PRICE_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => {
                      onSelectPriceRange(opt.value);
                      setOpenDropdown(null);
                    }}
                    className={menuItem(priceRange === opt.value)}
                  >
                    <span>{opt.label}</span>
                    {priceRange === opt.value && <Check size={14} />}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* 3. Customer Rating Pill */}
          <div className="relative">
            <button
              type="button"
              onClick={() => toggleDropdown("rating")}
              aria-haspopup="true"
              aria-expanded={openDropdown === "rating"}
              className={chip(minRating > 0)}
            >
              <span>{minRating > 0 ? "4 stars & up" : "Rating"}</span>
              <ChevronDown
                size={14}
                className={`opacity-60 transition-transform ${
                  openDropdown === "rating" ? "rotate-180" : ""
                }`}
              />
            </button>

            {openDropdown === "rating" && (
              <div className={menu}>
                <button
                  type="button"
                  onClick={() => {
                    onSelectMinRating(0);
                    setOpenDropdown(null);
                  }}
                  className={menuItem(minRating === 0)}
                >
                  <span>All Ratings</span>
                  {minRating === 0 && <Check size={14} />}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    onSelectMinRating(4);
                    setOpenDropdown(null);
                  }}
                  className={menuItem(minRating === 4)}
                >
                  <span className="inline-flex items-center gap-1">
                    <Star size={14} aria-hidden="true" className="fill-amber-400 text-amber-400" />
                    4 stars &amp; up
                  </span>
                  {minRating === 4 && <Check size={14} />}
                </button>
              </div>
            )}
          </div>

          {/* 4. In Stock Only Toggle Pill */}
          <button
            type="button"
            onClick={onToggleInStockOnly}
            aria-pressed={inStockOnly}
            className={chip(inStockOnly)}
          >
            <span>In stock</span>
            {inStockOnly && <Check size={14} aria-hidden="true" />}
          </button>

          {/* Reset Filters Button */}
          {isFiltered && (
            <button
              type="button"
              onClick={onResetFilters}
              className="bp-press inline-flex min-h-11 items-center gap-1.5 rounded-xl px-3 text-sm font-semibold text-rose-600 hover:bg-rose-50 border border-rose-200/80 transition-colors"
            >
              <RotateCcw size={14} aria-hidden="true" />
              <span>Clear all</span>
            </button>
          )}
        </div>

        {/* Right side: Sort by & result counter */}
        <div className="flex items-center justify-between gap-3 sm:justify-end">
          <span aria-live="polite" className="bp-price text-sm text-muted">
            {totalResults} {totalResults === 1 ? "product" : "products"}
          </span>

          {/* 5. Sort Dropdown Pill */}
          <div className="relative">
            <button
              type="button"
              onClick={() => toggleDropdown("sort")}
              aria-haspopup="true"
              aria-expanded={openDropdown === "sort"}
              className={chip(false)}
            >
              <span className="text-muted">Sort:</span>
              <span className="font-semibold">{getSortLabel()}</span>
              <ChevronDown
                size={14}
                className={`opacity-60 transition-transform ${
                  openDropdown === "sort" ? "rotate-180" : ""
                }`}
              />
            </button>

            {openDropdown === "sort" && (
              <div className={`${menu} left-auto right-0`}>
                {SORT_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => {
                      onSelectSortBy(opt.value);
                      setOpenDropdown(null);
                    }}
                    className={menuItem(sortBy === opt.value)}
                  >
                    <span>{opt.label}</span>
                    {sortBy === opt.value && <Check size={14} />}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
