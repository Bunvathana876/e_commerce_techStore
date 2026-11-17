"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  ArrowRight,
  Check,
  ChevronLeft,
  ChevronRight,
  Copy,
  Flame,
  ShieldCheck,
  ShoppingBag,
  Smartphone,
  Sparkles,
  Star,
  Store,
  Tag,
  Truck,
  Zap,
} from "lucide-react";
import type {
  ApiCategory,
  ApiCoupon,
  ApiProduct,
  ApiSeller,
} from "@/lib/api";
import {
  fetchStoreCategories,
  fetchStoreCoupons,
  fetchStoreProducts,
  fetchStoreSellers,
  getCategoryVisualMeta,
  getDiscountPercent,
  getEffectivePrice,
  SHOWCASE_CATEGORIES,
  SHOWCASE_COUPONS,
  SHOWCASE_PRODUCTS,
  SHOWCASE_SELLERS,
} from "@/lib/store-catalog";
import { useShopStore } from "@/lib/store";
import ProductCard from "@/components/store/ProductCard";

const HERO_SLIDES = [
  {
    badge: "The new-season edit",
    title: "Good finds, from stores you can trust.",
    subtitle:
      "Discover standout sneakers, everyday tech, and modern essentials in one calm, easy-to-shop marketplace.",
    ctaLabel: "Explore new arrivals",
    ctaHref: "/shop",
    secondaryLabel: "Claim 10% Voucher",
    secondaryHref: "#vouchers",
    image:
      "https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=1200&q=85",
    accent: "from-slate-950 via-blue-950 to-indigo-950",
    spotName: "Nike Air Max 270",
    spotPrice: "$134.99",
    spotOldPrice: "$159.99",
    spotId: 1,
  },
  {
    badge: "Audio & smart gear",
    title: "Better sound for work, travel, and everything between.",
    subtitle:
      "Compare headphones, watches, and everyday tech from verified sellers—without the noise.",
    ctaLabel: "Shop electronics",
    ctaHref: "/shop?category=Electronics",
    secondaryLabel: "View Flash Deals",
    secondaryHref: "/deals",
    image:
      "https://images.unsplash.com/photo-1618366712010-f4ae9c647dcb?auto=format&fit=crop&w=1200&q=85",
    accent: "from-slate-950 via-slate-900 to-blue-950",
    spotName: "Sony WH-1000XM5 Wireless",
    spotPrice: "$339.99",
    spotOldPrice: "$399.99",
    spotId: 2,
  },
  {
    badge: "The everyday wardrobe",
    title: "Easy layers made for the way you live.",
    subtitle:
      "Build a wardrobe around comfortable staples, clean silhouettes, and accessories that go anywhere.",
    ctaLabel: "Shop fashion",
    ctaHref: "/shop?category=Fashion",
    secondaryLabel: "Official Boutiques",
    secondaryHref: "/stores",
    image:
      "https://images.unsplash.com/photo-1556821840-3a63f95609a7?auto=format&fit=crop&w=1200&q=85",
    accent: "from-indigo-950 via-slate-950 to-violet-950",
    spotName: "Heavyweight Fleece Hoodie",
    spotPrice: "$49.99",
    spotOldPrice: "$64.99",
    spotId: 7,
  },
];

const COLLECTION_TABS = [
  { id: "all", label: "Trending Now" },
  { id: "top", label: "Top Rated 4.8★+" },
  { id: "deals", label: "On Sale" },
  { id: "under100", label: "Under $100" },
];

export default function StoreHomePage() {
  const pushToast = useShopStore((s) => s.pushToast);
  const addToCart = useShopStore((s) => s.addToCart);

  const [products, setProducts] = useState<ApiProduct[]>(SHOWCASE_PRODUCTS);
  const [categories, setCategories] =
    useState<ApiCategory[]>(SHOWCASE_CATEGORIES);
  const [sellers, setSellers] = useState<ApiSeller[]>(SHOWCASE_SELLERS);
  const [coupons, setCoupons] = useState<ApiCoupon[]>(SHOWCASE_COUPONS);

  const [heroIndex, setHeroIndex] = useState(0);
  const [activeTab, setActiveTab] = useState("all");
  const [copiedVoucher, setCopiedVoucher] = useState<string | null>(null);

  useEffect(() => {
    fetchStoreProducts().then(({ products: list }) => setProducts(list));
    fetchStoreCategories().then(setCategories);
    fetchStoreSellers().then(setSellers);
    fetchStoreCoupons().then(setCoupons);
  }, []);

  // Auto-advance hero every 6.5s
  useEffect(() => {
    const id = window.setInterval(() => {
      setHeroIndex((i) => (i + 1) % HERO_SLIDES.length);
    }, 6500);
    return () => window.clearInterval(id);
  }, []);

  const flashDeals = useMemo(() => {
    const discounted = products
      .filter((p) => getDiscountPercent(p) > 0)
      .sort((a, b) => getDiscountPercent(b) - getDiscountPercent(a));
    return (discounted.length > 0 ? discounted : products).slice(0, 4);
  }, [products]);

  const tabProducts = useMemo(() => {
    switch (activeTab) {
      case "top":
        return products
          .filter((p) => (Number(p.rating) || 4.8) >= 4.8)
          .slice(0, 8);
      case "deals":
        return products.filter((p) => getDiscountPercent(p) > 0).slice(0, 8);
      case "under100":
        return products.filter((p) => getEffectivePrice(p) < 100).slice(0, 8);
      default:
        return products.slice(0, 8);
    }
  }, [products, activeTab]);

  const handleCopyCoupon = (code: string) => {
    navigator.clipboard?.writeText(code);
    setCopiedVoucher(code);
    pushToast({
      title: `Voucher ${code} Copied!`,
      description: "Apply it inside your Shopping Bag or Checkout.",
      tone: "success",
    });
    window.setTimeout(() => setCopiedVoucher(null), 2400);
  };

  const activeSlide = HERO_SLIDES[heroIndex];

  return (
    <div className="space-y-14 sm:space-y-20 pb-8">
      {/* =========================================
          1. HERO EDITORIAL CAROUSEL
      ========================================= */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-6">
        <div
          className={`relative rounded-[2rem] overflow-hidden bg-gradient-to-br ${activeSlide.accent} text-white shadow-[0_24px_80px_rgba(15,23,42,0.18)] transition-colors duration-700`}
        >
          {/* Ambient Glow Orbs */}
          <div className="pointer-events-none absolute -top-24 -right-24 w-96 h-96 rounded-full bg-blue-500/25 blur-3xl" />
          <div className="pointer-events-none absolute -bottom-28 -left-20 w-80 h-80 rounded-full bg-indigo-500/20 blur-3xl" />

          <div className="relative z-10 grid grid-cols-1 lg:grid-cols-12 gap-8 items-center p-7 sm:p-11 lg:p-14">
            {/* Left Copy */}
            <div className="lg:col-span-7 space-y-6">
              <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-white/10 border border-white/15 backdrop-blur-md text-xs font-extrabold tracking-wide text-blue-200">
                <Sparkles size={14} className="text-amber-300" />
                {activeSlide.badge}
              </div>

              <h1 className="text-4xl sm:text-5xl lg:text-[58px] font-extrabold tracking-[-0.04em] leading-[1.04] max-w-3xl">
                {activeSlide.title}
              </h1>

              <p className="text-sm sm:text-base text-slate-300 max-w-xl leading-relaxed">
                {activeSlide.subtitle}
              </p>

              <div className="flex flex-wrap items-center gap-3.5 pt-1">
                <Link
                  href={activeSlide.ctaHref}
                  className="w-full sm:w-auto px-7 py-4 rounded-2xl bg-blue-600 hover:bg-blue-500 text-white text-sm font-extrabold inline-flex items-center justify-center gap-2.5 shadow-xl shadow-blue-600/30 transition"
                >
                  <ShoppingBag size={17} />
                  {activeSlide.ctaLabel}
                  <ArrowRight size={16} />
                </Link>
                <a
                  href={activeSlide.secondaryHref}
                  className="w-full sm:w-auto px-6 py-4 rounded-2xl bg-white/10 hover:bg-white/18 border border-white/15 text-white text-sm font-bold text-center backdrop-blur-md transition"
                >
                  {activeSlide.secondaryLabel}
                </a>
              </div>

              {/* Shopper essentials */}
              <div className="pt-4 grid grid-cols-3 gap-4 max-w-md border-t border-white/10">
                <div>
                  <p className="text-sm sm:text-base font-extrabold text-white">
                    Free delivery
                  </p>
                  <p className="text-[11px] text-slate-400">
                    On orders over $100
                  </p>
                </div>
                <div>
                  <p className="text-sm sm:text-base font-extrabold text-white">
                    Easy returns
                  </p>
                  <p className="text-[11px] text-slate-400">
                    Within 30 days
                  </p>
                </div>
                <div>
                  <p className="text-sm sm:text-base font-extrabold text-white">
                    Secure checkout
                  </p>
                  <p className="text-[11px] text-slate-400">
                    Multiple ways to pay
                  </p>
                </div>
              </div>
            </div>

            {/* Right Visual Showcase */}
            <div className="lg:col-span-5 relative">
              <div className="relative aspect-4/3 sm:aspect-square max-w-md mx-auto rounded-3xl overflow-hidden border border-white/15 shadow-2xl bg-slate-900">
                {HERO_SLIDES.map((slide, idx) => {
                  const isCurrent = idx === heroIndex;
                  return (
                    <img
                      key={slide.title}
                      src={slide.image}
                      alt={slide.spotName}
                      {...(idx === 0
                        ? { fetchPriority: "high" as const }
                        : {
                            fetchPriority: "low" as const,
                            loading: "lazy" as const,
                          })}
                      width={700}
                      height={700}
                      className={`absolute inset-0 w-full h-full object-cover transition-all duration-700 ${
                        isCurrent
                          ? "opacity-100 scale-100"
                          : "opacity-0 scale-105 pointer-events-none"
                      }`}
                    />
                  );
                })}

                {/* Floating Spotlight Product Pill */}
                <div className="absolute inset-x-4 bottom-4 p-4 rounded-2xl bg-slate-950/80 backdrop-blur-xl border border-white/15 flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <span className="text-[10px] font-extrabold uppercase tracking-wider text-blue-400 block">
                      Featured Spotlight
                    </span>
                    <Link
                      href={`/product/${activeSlide.spotId}`}
                      className="text-sm font-extrabold text-white hover:text-blue-300 truncate block"
                    >
                      {activeSlide.spotName}
                    </Link>
                    <div className="flex items-baseline gap-2 mt-0.5">
                      <span className="text-base font-extrabold text-emerald-400">
                        {activeSlide.spotPrice}
                      </span>
                      <span className="text-xs text-slate-400 line-through">
                        {activeSlide.spotOldPrice}
                      </span>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      const target =
                        products.find((p) => p.id === activeSlide.spotId) ||
                        products[0];
                      if (target) addToCart(target, 1);
                    }}
                    className="px-3.5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-extrabold shrink-0 transition cursor-pointer"
                  >
                    + Bag
                  </button>
                </div>
              </div>

              {/* Carousel Controls */}
              <div className="flex items-center justify-center gap-2 mt-4">
                <button
                  type="button"
                  onClick={() =>
                    setHeroIndex(
                      (i) => (i - 1 + HERO_SLIDES.length) % HERO_SLIDES.length
                    )
                  }
                  aria-label="Previous slide"
                  className="w-8 h-8 rounded-full bg-white/10 hover:bg-white/20 flex items-center justify-center transition cursor-pointer"
                >
                  <ChevronLeft size={16} />
                </button>
                {HERO_SLIDES.map((s, idx) => (
                  <button
                    key={s.title}
                    type="button"
                    onClick={() => setHeroIndex(idx)}
                    aria-label={`Go to slide ${idx + 1}`}
                    className={`h-2 rounded-full transition-all cursor-pointer ${
                      idx === heroIndex
                        ? "w-8 bg-blue-400"
                        : "w-2 bg-white/30 hover:bg-white/50"
                    }`}
                  />
                ))}
                <button
                  type="button"
                  onClick={() =>
                    setHeroIndex((i) => (i + 1) % HERO_SLIDES.length)
                  }
                  aria-label="Next slide"
                  className="w-8 h-8 rounded-full bg-white/10 hover:bg-white/20 flex items-center justify-center transition cursor-pointer"
                >
                  <ChevronRight size={16} />
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* =========================================
          2. TRUST VALUE PILLARS
      ========================================= */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3.5 sm:gap-5">
          {[
            {
              icon: <Truck size={20} className="text-blue-600" />,
              bg: "bg-blue-50",
              title: "Free Shipping $100+",
              desc: "Tracked express courier to your door",
            },
            {
              icon: <ShieldCheck size={20} className="text-emerald-600" />,
              bg: "bg-emerald-50",
              title: "Authenticity Verified",
              desc: "Direct from official partner stores",
            },
            {
              icon: <Zap size={20} className="text-amber-600" />,
              bg: "bg-amber-50",
              title: "Instant Promo Rewards",
              desc: "Stackable vouchers up to $50 OFF",
            },
            {
              icon: <Smartphone size={20} className="text-indigo-600" />,
              bg: "bg-indigo-50",
              title: "Web + App Synced",
              desc: "Real-time cart & order status",
            },
          ].map((pillar) => (
            <div
              key={pillar.title}
              className="p-4 sm:p-5 rounded-3xl bg-white border border-slate-200/75 shadow-xs flex items-center gap-3.5"
            >
              <div
                className={`w-11 h-11 rounded-2xl ${pillar.bg} flex items-center justify-center shrink-0`}
              >
                {pillar.icon}
              </div>
              <div className="min-w-0">
                <h2 className="text-sm font-extrabold text-slate-900 truncate">
                  {pillar.title}
                </h2>
                <p className="text-xs text-slate-500 mt-0.5 line-clamp-1">
                  {pillar.desc}
                </p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* =========================================
          3. SHOP BY CATEGORY SHOWCASE
      ========================================= */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-end justify-between gap-4 mb-7">
          <div>
            <span className="text-xs font-extrabold uppercase tracking-wider text-blue-600">
              Curated Worlds
            </span>
            <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900 mt-1">
              Shop by Category
            </h2>
          </div>
          <Link
            href="/categories"
            className="text-sm font-bold text-blue-600 hover:text-blue-700 inline-flex items-center gap-1"
          >
            All Categories <ArrowRight size={15} />
          </Link>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
          {categories.slice(0, 5).map((cat) => {
            const meta = getCategoryVisualMeta(cat.name);
            const itemCount = products.filter(
              (p) =>
                p.category_id === cat.id ||
                p.category?.name?.toLowerCase() === cat.name.toLowerCase()
            ).length;

            return (
              <Link
                key={cat.id}
                href={`/shop?category=${encodeURIComponent(cat.name)}`}
                className="group relative h-56 rounded-3xl overflow-hidden bg-slate-900 shadow-sm hover:shadow-xl transition-all"
              >
                <img
                  src={meta.coverImage}
                  alt={cat.name}
                  loading="lazy"
                  width={400}
                  height={500}
                  className="w-full h-full object-cover opacity-80 group-hover:scale-110 transition-transform duration-500"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/35 to-transparent" />
                <div className="absolute inset-x-4 bottom-4 text-white">
                  <span className="text-[10px] font-extrabold uppercase tracking-wider px-2 py-0.5 rounded-full bg-white/20 backdrop-blur-md">
                    {itemCount > 0 ? `${itemCount} items` : meta.badge}
                  </span>
                  <h3 className="text-lg font-extrabold mt-1.5 group-hover:text-blue-300 transition-colors">
                    {cat.name}
                  </h3>
                  <p className="text-[11px] text-slate-300 line-clamp-1">
                    {cat.description || meta.tagline}
                  </p>
                </div>
              </Link>
            );
          })}
        </div>
      </section>

      {/* =========================================
          4. FEATURED DEALS
      ========================================= */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="rounded-[2rem] bg-gradient-to-br from-blue-600 via-indigo-600 to-slate-950 p-6 sm:p-9 text-white shadow-xl">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-7">
            <div className="flex items-center gap-3.5">
              <div className="w-12 h-12 rounded-2xl bg-white/15 backdrop-blur-md flex items-center justify-center text-amber-300">
                <Flame size={24} />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-2xl sm:text-3xl font-extrabold">
                    Fresh price drops
                  </h2>
                  <span className="px-2.5 py-0.5 rounded-full bg-rose-500 text-[11px] font-extrabold uppercase">
                    While stock lasts
                  </span>
                </div>
                <p className="text-xs sm:text-sm text-blue-100 mt-0.5">
                  A short list of worthwhile deals from verified stores.
                </p>
              </div>
            </div>

            <Link
              href="/deals"
              className="inline-flex items-center gap-2 self-start md:self-auto px-4 py-2.5 rounded-xl bg-white/10 hover:bg-white/20 border border-white/10 text-xs font-extrabold transition"
            >
              View all deals <ArrowRight size={14} />
            </Link>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
            {flashDeals.map((product) => (
              <ProductCard key={product.id} product={product} />
            ))}
          </div>

        </div>
      </section>

      {/* =========================================
          5. CURATED PRODUCT COLLECTION WITH TABS
      ========================================= */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-7">
          <div>
            <span className="text-xs font-extrabold uppercase tracking-wider text-blue-600">
              Handpicked Catalog
            </span>
            <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900 mt-1">
              Discover Customer Favorites
            </h2>
          </div>

          <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar bg-white p-1.5 rounded-2xl border border-slate-200/80">
            {COLLECTION_TABS.map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`px-4 py-2 rounded-xl text-xs font-extrabold transition shrink-0 cursor-pointer ${
                  activeTab === tab.id
                    ? "bg-slate-900 text-white shadow-sm"
                    : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5">
          {tabProducts.map((product) => (
            <ProductCard key={product.id} product={product} />
          ))}
        </div>

        <div className="mt-9 text-center">
          <Link
            href="/shop"
            className="inline-flex items-center gap-2 px-7 py-3.5 rounded-2xl bg-slate-900 hover:bg-blue-600 text-white text-sm font-extrabold shadow-lg transition"
          >
            Browse Complete Catalog ({products.length} Products)
            <ArrowRight size={16} />
          </Link>
        </div>
      </section>

      {/* =========================================
          6. INTERACTIVE PROMO VOUCHER VAULT
      ========================================= */}
      <section
        id="vouchers"
        className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 scroll-mt-24"
      >
        <div className="flex items-end justify-between gap-4 mb-6">
          <div>
            <span className="text-xs font-extrabold uppercase tracking-wider text-emerald-600">
              Instant Checkout Rewards
            </span>
            <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900 mt-1">
              Claim Official Store Vouchers
            </h2>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {coupons.slice(0, 4).map((coupon) => {
            const isCopied = copiedVoucher === coupon.code;
            const badgeLabel =
              coupon.discount_type === "percent"
                ? `${Number(coupon.discount_value)}% OFF`
                : `$${Number(coupon.discount_value)} OFF`;

            return (
              <div
                key={coupon.id}
                className="relative p-5 rounded-3xl bg-white border-2 border-dashed border-blue-200 hover:border-blue-500 transition flex flex-col justify-between gap-4 shadow-xs"
              >
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="px-3 py-1 rounded-xl bg-blue-600 text-white text-sm font-extrabold">
                      {badgeLabel}
                    </span>
                    <Tag size={16} className="text-blue-500" />
                  </div>
                  <p className="text-sm font-bold text-slate-800 mt-3">
                    {coupon.description || "Special storewide discount voucher"}
                  </p>
                  <p className="text-xs text-slate-400 mt-1">
                    {Number(coupon.min_order_amount) > 0
                      ? `Min. order $${Number(coupon.min_order_amount).toFixed(0)}`
                      : "No minimum spend required"}
                  </p>
                </div>

                <div className="pt-3 border-t border-slate-100 flex items-center justify-between gap-2">
                  <code className="px-2.5 py-1 rounded-lg bg-slate-100 text-slate-900 text-xs font-extrabold tracking-wider">
                    {coupon.code}
                  </code>
                  <button
                    type="button"
                    onClick={() => handleCopyCoupon(coupon.code)}
                    className={`px-3.5 py-1.5 rounded-xl text-xs font-extrabold inline-flex items-center gap-1.5 transition cursor-pointer ${
                      isCopied
                        ? "bg-emerald-500 text-white"
                        : "bg-slate-900 hover:bg-blue-600 text-white"
                    }`}
                  >
                    {isCopied ? (
                      <>
                        <Check size={13} /> Copied
                      </>
                    ) : (
                      <>
                        <Copy size={13} /> Copy Code
                      </>
                    )}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* =========================================
          7. VERIFIED OFFICIAL STORES
      ========================================= */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-end justify-between gap-4 mb-6">
          <div>
            <span className="text-xs font-extrabold uppercase tracking-wider text-blue-600">
              Authorized Partners
            </span>
            <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900 mt-1">
              Verified Official Stores
            </h2>
          </div>
          <Link
            href="/stores"
            className="text-sm font-bold text-blue-600 hover:text-blue-700 inline-flex items-center gap-1"
          >
            All Stores <ArrowRight size={15} />
          </Link>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {sellers.slice(0, 3).map((seller) => (
            <div
              key={seller.id}
              className="p-6 rounded-3xl bg-white border border-slate-200/80 shadow-xs hover:shadow-lg transition flex flex-col justify-between gap-5"
            >
              <div>
                <div className="flex items-start justify-between gap-3">
                  <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-blue-600 to-indigo-600 text-white font-extrabold text-lg flex items-center justify-center shadow-md shadow-blue-600/20">
                    {seller.name.charAt(0)}
                  </div>
                  <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-amber-50 text-amber-700 text-xs font-extrabold">
                    <Star size={12} className="fill-amber-400 text-amber-400" />
                    {Number(seller.rating || 4.9).toFixed(1)}
                  </span>
                </div>

                <h3 className="text-lg font-extrabold text-slate-900 mt-4 flex items-center gap-1.5">
                  {seller.name}
                  <ShieldCheck size={16} className="text-blue-600 shrink-0" />
                </h3>
                <p className="text-xs text-slate-500 mt-1.5 leading-relaxed line-clamp-2">
                  {seller.description ||
                    "Official verified Blue Panda merchant offering authentic inventory and fast fulfillment."}
                </p>
              </div>

              <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-400 flex items-center gap-1">
                  <Store size={13} />
                  {seller.products_count || 5}+ Products
                </span>
                <Link
                  href={`/shop?seller=${seller.id}`}
                  className="text-xs font-extrabold text-blue-600 hover:text-blue-700 inline-flex items-center gap-1"
                >
                  Visit Store <ArrowRight size={13} />
                </Link>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* =========================================
          8. MOBILE APP ECOSYSTEM BANNER
      ========================================= */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="rounded-[2rem] bg-slate-950 text-white p-8 sm:p-12 grid grid-cols-1 lg:grid-cols-12 gap-8 items-center overflow-hidden relative">
          <div className="pointer-events-none absolute -right-16 -bottom-16 w-80 h-80 rounded-full bg-blue-600/25 blur-3xl" />

          <div className="lg:col-span-8 space-y-4 relative z-10">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-600/25 text-blue-300 text-xs font-extrabold">
              <Smartphone size={14} /> Cross-Platform Sync
            </span>
            <h2 className="text-2xl sm:text-4xl font-extrabold leading-tight">
              Start on the Web. Track Live on the Blue Panda Mobile App.
            </h2>
            <p className="text-sm text-slate-300 max-w-2xl leading-relaxed">
              Use one account on the website and mobile app, so your bag,
              wishlist, saved addresses, and order updates are always close at
              hand.
            </p>
            <div className="flex flex-wrap gap-3 pt-2">
              <Link
                href="/register"
                className="px-6 py-3.5 rounded-2xl bg-blue-600 hover:bg-blue-500 text-white text-xs sm:text-sm font-extrabold transition"
              >
                Create Free Account
              </Link>
              <Link
                href="/orders"
                className="px-6 py-3.5 rounded-2xl bg-white/10 hover:bg-white/20 text-white text-xs sm:text-sm font-bold transition"
              >
                Track Existing Orders
              </Link>
            </div>
          </div>

          <div className="lg:col-span-4 flex justify-center relative z-10">
            <div className="p-6 rounded-3xl bg-white/8 border border-white/15 backdrop-blur-xl flex items-center gap-4 animate-float-slow">
              <img
                src="/images/logo_panda_blue.png"
                alt="Blue Panda App Icon"
                loading="lazy"
                width={72}
                height={72}
                className="w-18 h-18 rounded-2xl shadow-lg"
              />
              <div>
                <p className="text-base font-extrabold text-white">
                  Blue Panda App
                </p>
                <p className="text-xs text-blue-300 font-semibold">
                  iOS • Android • Web Store
                </p>
                <p className="text-[11px] text-slate-400 mt-1">
                  One account across every device
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
