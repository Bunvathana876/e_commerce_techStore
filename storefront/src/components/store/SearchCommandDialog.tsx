"use client";

import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  AlertCircle,
  ArrowRight,
  Flame,
  RefreshCw,
  Search,
  X,
  SlidersHorizontal,
} from "lucide-react";
import type { ApiProduct } from "@/lib/api";
import {
  applyProductImageFallback,
  fetchStoreProducts,
  getEffectivePrice,
  getOriginalPrice,
  resolveProductImage,
} from "@/lib/store-catalog";
import { useShopStore } from "@/lib/store";

const QUICK_SEARCH_CHIPS = [
  "Laptops",
  "Headphones",
  "Monitors",
  "Apple Watch",
  "Sony",
  "Keyboards",
  "Components",
];

export default function SearchCommandDialog() {
  const isOpen = useShopStore((s) => s.isSearchOpen);
  const closeSearch = useShopStore((s) => s.closeSearch);
  const openSearch = useShopStore((s) => s.openSearch);

  const router = useRouter();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const titleId = useId();

  const [query, setQuery] = useState("");
  const [catalog, setCatalog] = useState<ApiProduct[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const loadCatalog = useCallback(() => {
    setIsLoading(true);
    setLoadError(null);
    fetchStoreProducts()
      .then(({ products, isLiveBackend }) => {
        setCatalog(products);
        if (!isLiveBackend && products.length === 0) {
          setLoadError("We couldn't load the catalog. Please try again.");
        }
      })
      .finally(() => setIsLoading(false));
  }, []);

  // Global Cmd+K / Ctrl+K shortcut
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        if (isOpen) closeSearch();
        else openSearch();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [isOpen, openSearch, closeSearch]);

  // Load live catalog once when opened
  useEffect(() => {
    if (!isOpen) return;
    loadCatalog();
  }, [isOpen, loadCatalog]);

  // Manage native top-layer <dialog>
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    if (isOpen) {
      if (!dialog.open) dialog.showModal();
      window.setTimeout(() => inputRef.current?.focus(), 40);
    } else if (dialog.open) {
      dialog.close();
    }
  }, [isOpen]);

  // Light-dismiss backdrop click
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    const handleClose = () => closeSearch();
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
  }, [closeSearch]);

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return catalog.slice(0, 6);
    return catalog
      .filter(
        (p) =>
          p.name.toLowerCase().includes(q) ||
          (p.description || "").toLowerCase().includes(q) ||
          (p.category?.name || "").toLowerCase().includes(q) ||
          (p.seller?.name || "").toLowerCase().includes(q)
      )
      .slice(0, 8);
  }, [catalog, query]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    dialogRef.current?.close();
    if (query.trim()) {
      router.push(`/shop?q=${encodeURIComponent(query.trim())}`);
    } else {
      router.push("/shop");
    }
  };

  return (
    <dialog
      ref={dialogRef}
      {...({ closedby: "any" } as any)}
      aria-labelledby={titleId}
      className="mx-auto mt-12 sm:mt-20 w-[calc(100%-1.5rem)] max-w-2xl rounded-3xl bg-white p-0 text-slate-900 shadow-2xl border border-slate-200/90 overflow-hidden backdrop:bg-[#181818]/60 backdrop:backdrop-blur-sm"
    >
      {/* Header Search Field */}
      <div className="border-b border-line p-4 sm:p-5">
        <h2 id={titleId} className="sr-only">
          Search Storefront Catalog
        </h2>
        <form onSubmit={handleSearchSubmit} className="relative flex items-center">
          <Search size={20} className="absolute left-3.5 text-[#245BE7]" />
          <input
            ref={inputRef}
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search audio, monitors, hardware, components, gear..."
            className="w-full pl-11 pr-24 py-3 rounded-2xl bg-white border border-slate-200 text-sm font-semibold text-[#181818] placeholder:text-slate-400 placeholder:font-normal focus:outline-none focus:ring-2 focus:ring-[#245BE7] focus:border-[#245BE7] transition shadow-xs"
          />
          {query && (
            <button
              type="button"
              onClick={() => setQuery("")}
              className="absolute right-12 text-xs font-bold text-slate-400 hover:text-slate-700 px-2 py-1 cursor-pointer"
            >
              Clear
            </button>
          )}
          <button
            type="button"
            onClick={() => dialogRef.current?.close()}
            aria-label="Close search"
            className="ml-2 w-9 h-9 rounded-xl bg-slate-100 hover:bg-slate-200 flex items-center justify-center text-slate-600 shrink-0 cursor-pointer transition"
          >
            <X size={16} />
          </button>
        </form>

        {/* Quick Search Chips */}
        <div className="flex items-center gap-1.5 mt-3 overflow-x-auto no-scrollbar pt-1">
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold uppercase tracking-wider text-slate-400 shrink-0 pr-1">
            <Flame size={12} className="text-orange-500" />
            Quick:
          </span>
          {QUICK_SEARCH_CHIPS.map((chip) => (
            <button
              key={chip}
              type="button"
              onClick={() => setQuery(chip)}
              className="px-2.5 py-1 rounded-full bg-white hover:bg-blue-50 border border-slate-200/80 hover:border-blue-300 text-xs font-medium text-slate-700 hover:text-[#245BE7] shrink-0 transition cursor-pointer shadow-2xs"
            >
              {chip}
            </button>
          ))}
        </div>
      </div>

      {/* Results Section */}
      <div className="p-4 sm:p-5 max-h-[60vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-3 px-1">
          <p className="text-sm font-medium text-muted">
            {query.trim() ? `Results for “${query}”` : "Popular products"}
          </p>
          <Link
            href={
              query.trim()
                ? `/shop?q=${encodeURIComponent(query.trim())}`
                : "/shop"
            }
            onClick={() => dialogRef.current?.close()}
            className="text-xs font-bold text-[#245BE7] hover:underline inline-flex items-center gap-1"
          >
            Explore all in Shop <ArrowRight size={12} />
          </Link>
        </div>

        {isLoading ? (
          <div className="py-12 text-center">
            <div className="w-7 h-7 border-3 border-[#245BE7] border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="text-xs text-slate-400 mt-2">Searching live inventory...</p>
          </div>
        ) : loadError && catalog.length === 0 ? (
          <div className="py-12 text-center px-4">
            <div className="w-12 h-12 rounded-2xl bg-rose-50 text-rose-600 flex items-center justify-center mx-auto mb-3">
              <AlertCircle size={22} />
            </div>
            <p className="text-base font-bold text-[#181818]">
              Unable to Load Products
            </p>
            <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto leading-relaxed">
              {loadError}
            </p>
            <button
              type="button"
              onClick={loadCatalog}
              className="mt-4 inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#245BE7] text-white text-xs font-bold hover:bg-blue-700 transition shadow-xs cursor-pointer"
            >
              <RefreshCw size={13} /> Retry
            </button>
          </div>
        ) : catalog.length === 0 ? (
          <div className="py-12 text-center px-4">
            <div className="w-12 h-12 rounded-2xl bg-blue-50 text-[#245BE7] flex items-center justify-center mx-auto mb-3">
              <SlidersHorizontal size={22} />
            </div>
            <p className="text-base font-bold text-[#181818]">
              No Products Available
            </p>
            <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto leading-relaxed">
              New products will appear here when they become available.
            </p>
          </div>
        ) : matches.length === 0 ? (
          <div className="py-12 text-center px-4">
            <div className="w-12 h-12 rounded-2xl bg-blue-50 text-[#245BE7] flex items-center justify-center mx-auto mb-3">
              <SlidersHorizontal size={22} />
            </div>
            <p className="text-base font-bold text-[#181818]">
              No products found for &ldquo;{query}&rdquo;
            </p>
            <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto leading-relaxed">
              We couldn&apos;t find an exact match. Try searching for &ldquo;Headphones&rdquo;, &ldquo;Watch&rdquo;, &ldquo;Monitors&rdquo;, or browse our entire catalog in Shop.
            </p>
            <Link
              href="/shop"
              onClick={() => dialogRef.current?.close()}
              className="mt-4 inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#181818] text-white text-xs font-bold hover:bg-[#245BE7] transition shadow-xs"
            >
              Browse All Products
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            {matches.map((item) => {
              const effective = getEffectivePrice(item);
              const original = getOriginalPrice(item);

              return (
                <Link
                  key={item.id}
                  href={`/product/${item.id}`}
                  onClick={() => dialogRef.current?.close()}
                  className="flex items-center gap-3 p-3 rounded-2xl hover:bg-slate-50 border border-slate-100 hover:border-blue-200 transition group"
                >
                  <div className="w-14 h-14 rounded-xl bg-paper flex items-center justify-center p-1 shrink-0 overflow-hidden">
                    <img
                      src={resolveProductImage(item)}
                      alt={item.name}
                      onError={applyProductImageFallback}
                      fetchPriority="low"
                      loading="lazy"
                      width={64}
                      height={64}
                      className="w-full h-full object-contain transition-transform group-hover:scale-105"
                    />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-bold text-[#181818] group-hover:text-[#245BE7] truncate leading-tight">
                      {item.name}
                    </p>
                    <div className="flex items-center gap-1 text-[11px] text-slate-400 mt-0.5 truncate">
                      <span>{item.category?.name || "Hardware"}</span>
                      {item.seller?.name && (
                        <>
                          <span>•</span>
                          <span className="truncate">{item.seller.name}</span>
                        </>
                      )}
                    </div>
                    <div className="flex items-baseline gap-1.5 mt-1">
                      <span className="text-xs font-semibold text-[#181818]">
                        ${effective.toFixed(2)}
                      </span>
                      {original && (
                        <span className="text-[10px] text-slate-400 line-through">
                          ${original.toFixed(2)}
                        </span>
                      )}
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </dialog>
  );
}
