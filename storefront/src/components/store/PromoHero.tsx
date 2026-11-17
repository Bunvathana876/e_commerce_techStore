"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, ArrowRight, ImageOff } from "lucide-react";
import type { ApiProduct } from "@/lib/api";
import { selectHeroProductsWithImages } from "@/lib/hero-images";
import { getEffectivePrice, resolveProductImage } from "@/lib/store-catalog";

interface PromoHeroProps {
  products: ApiProduct[];
  isLoading: boolean;
}

export default function PromoHero({ products, isLoading }: PromoHeroProps) {
  const [activeIndex, setActiveIndex] = useState(0);
  const [imageSelection, setImageSelection] = useState<{
    source: ApiProduct[];
    products: ApiProduct[];
    failedIds: Set<number>;
  } | null>(null);
  const hasCheckedImages = imageSelection?.source === products;
  const usableProducts = hasCheckedImages
    ? imageSelection.products.filter((item) => !imageSelection.failedIds.has(item.id))
    : [];
  const featured = hasCheckedImages && usableProducts.length === 0
    ? products.slice(0, 4)
    : usableProducts;
  const product = featured[activeIndex] ?? featured[0] ?? products[0] ?? null;
  const hasUsableImage = usableProducts.some((item) => item.id === product?.id);

  useEffect(() => {
    let cancelled = false;
    void selectHeroProductsWithImages(products).then((usableProducts) => {
      if (!cancelled) {
        setImageSelection({ source: products, products: usableProducts, failedIds: new Set() });
        setActiveIndex(0);
      }
    });
    return () => { cancelled = true; };
  }, [products]);

  useEffect(() => {
    if (activeIndex >= featured.length) setActiveIndex(0);
  }, [activeIndex, featured.length]);

  const move = (step: number) => {
    setActiveIndex((index) => (index + step + featured.length) % featured.length);
  };

  return (
    <section aria-labelledby="hero-title" className="bp-container pt-5 sm:pt-8">
      <div className="grid min-h-[580px] overflow-hidden bg-surface-subtle md:min-h-[640px] md:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <div className="flex flex-col justify-between px-6 pb-7 pt-9 sm:px-10 sm:pb-10 sm:pt-12 lg:px-16 lg:py-16">
          <div>
            <p className="bp-eyebrow">Blue Panda / Selected technology</p>
            {isLoading ? (
              <div className="mt-16 space-y-4" aria-busy="true" aria-label="Loading featured product">
                <div className="h-12 w-4/5 animate-pulse bg-line" />
                <div className="h-5 w-2/3 animate-pulse bg-line" />
              </div>
            ) : product ? (
              <div className="mt-14 md:mt-24">
                <p className="text-xs uppercase tracking-[0.15em] text-muted">{product.category?.name || "Featured product"}</p>
                <h1 id="hero-title" className="mt-5 max-w-lg text-4xl font-medium leading-[1.08] text-ink sm:text-5xl lg:text-6xl">{product.name}</h1>
                {product.description && <p className="mt-6 max-w-md line-clamp-3 text-sm leading-7 text-muted sm:text-base">{product.description}</p>}
                <p className="bp-price mt-7 text-xl font-medium text-ink">${getEffectivePrice(product).toFixed(2)}</p>
                <Link href={`/product/${product.id}`} className="mt-7 inline-flex min-h-12 items-center gap-3 border-b border-ink text-sm font-semibold text-ink transition-colors hover:border-brand hover:text-brand">
                  Discover product <ArrowRight size={17} aria-hidden="true" />
                </Link>
              </div>
            ) : (
              <div className="mt-14 md:mt-24">
                <h1 id="hero-title" className="max-w-lg text-4xl font-medium leading-[1.08] text-ink sm:text-5xl">Technology worth living with.</h1>
                <p className="mt-5 max-w-sm text-sm leading-7 text-muted">There are no featured products available right now. Browse the catalog for the latest selection.</p>
                <Link href="/shop" className="mt-7 inline-flex min-h-12 items-center gap-3 border-b border-ink text-sm font-semibold text-ink">Explore the shop <ArrowRight size={17} aria-hidden="true" /></Link>
              </div>
            )}
          </div>
          <div className="mt-10 flex items-center justify-between gap-4">
            <span className="text-xs uppercase tracking-[0.14em] text-muted">An independent perspective on tech</span>
            {!isLoading && featured.length > 1 && (
              <div className="flex items-center gap-2" aria-label="Featured product navigation">
                <span aria-live="polite" className="mr-2 text-xs tabular-nums text-muted">{String(activeIndex + 1).padStart(2, "0")} / {String(featured.length).padStart(2, "0")}</span>
                <button type="button" onClick={() => move(-1)} aria-label="Previous featured product" className="flex h-11 w-11 items-center justify-center border border-line-strong text-ink hover:border-ink"><ArrowLeft size={18} /></button>
                <button type="button" onClick={() => move(1)} aria-label="Next featured product" className="flex h-11 w-11 items-center justify-center border border-line-strong text-ink hover:border-ink"><ArrowRight size={18} /></button>
              </div>
            )}
          </div>
        </div>
        <div className="relative min-h-[360px] overflow-hidden bg-[#e9e9e6] sm:min-h-[440px] md:min-h-[640px]">
          {isLoading || (product && !hasCheckedImages) ? (
            <div className="absolute inset-8 animate-pulse bg-line/60 sm:inset-10" aria-label="Loading product photography" role="status" />
          ) : product && hasUsableImage ? (
            <img
              key={product.id}
              src={resolveProductImage(product)}
              alt={product.name}
              onError={() => setImageSelection((current) => {
                if (!current || current.source !== products) return current;
                return { ...current, failedIds: new Set(current.failedIds).add(product.id) };
              })}
              fetchPriority="high"
              width={900}
              height={900}
              className="absolute inset-0 h-full w-full object-contain p-7 sm:p-10 lg:p-12"
            />
          ) : product ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center px-8 text-center" role="status">
              <ImageOff size={28} strokeWidth={1.5} className="text-muted" aria-hidden="true" />
              <p className="mt-5 text-lg font-medium text-ink">Product photography unavailable</p>
              <p className="mt-2 max-w-xs text-sm leading-6 text-muted">View its details, price, and availability in the catalog.</p>
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}
