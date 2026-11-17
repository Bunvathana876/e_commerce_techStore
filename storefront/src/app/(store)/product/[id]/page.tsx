"use client";

import { use, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  Check,
  ChevronRight,
  Heart,
  Minus,
  Plus,
  RefreshCw,
  ShoppingBag,
  Star,
  Truck,
} from "lucide-react";
import {
  reviewsApi,
  type ApiProduct,
  type ApiReview,
} from "@/lib/api";
import { isLoggedIn } from "@/lib/auth";
import {
  applyProductImageFallback,
  fetchStoreProductById,
  fetchStoreProducts,
  fetchStoreReviews,
  getDiscountPercent,
  getEffectivePrice,
  getOriginalPrice,
  resolveProductImage,
} from "@/lib/store-catalog";
import {
  FREE_SHIPPING_THRESHOLD,
  STANDARD_SHIPPING_FEE,
  useShopStore,
} from "@/lib/store";
import ProductGrid from "@/components/store/ProductGrid";
import { PrimaryButton, PrimaryButtonLink } from "@/components/store/PrimaryButton";

export default function ProductDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const numericId = Number(id);
  const router = useRouter();

  const addToCart = useShopStore((s) => s.addToCart);
  const toggleWishlist = useShopStore((s) => s.toggleWishlist);
  const recordRecentlyViewed = useShopStore((s) => s.recordRecentlyViewed);
  const pushToast = useShopStore((s) => s.pushToast);
  const wishlist = useShopStore((s) => s.wishlist);

  const [product, setProduct] = useState<ApiProduct | null>(null);
  const [allProducts, setAllProducts] = useState<ApiProduct[]>([]);
  const [reviews, setReviews] = useState<ApiReview[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [reviewsError, setReviewsError] = useState<string | null>(null);

  const [quantity, setQuantity] = useState(1);
  const [isZoomed, setIsZoomed] = useState(false);

  // Review form state
  const [reviewRating, setReviewRating] = useState(5);
  const [reviewComment, setReviewComment] = useState("");
  const [submittingReview, setSubmittingReview] = useState(false);

  const loadProductDetails = useCallback(() => {
    setLoading(true);
    setLoadError(null);
    setReviewsError(null);

    if (!Number.isInteger(numericId) || numericId <= 0) {
      setProduct(null);
      setAllProducts([]);
      setReviews([]);
      setLoading(false);
      return () => {};
    }

    let active = true;
    Promise.all([
      fetchStoreProductById(numericId),
      fetchStoreProducts(),
      fetchStoreReviews(numericId),
    ]).then(([prodRes, listRes, revRes]) => {
      if (!active) return;
      if (prodRes.product) {
        setProduct(prodRes.product);
        recordRecentlyViewed(prodRes.product);
      } else {
        setProduct(null);
        if (!prodRes.isLiveBackend && !prodRes.notFound) {
          setLoadError("We couldn't load this product right now. Please try again.");
        }
      }
      setAllProducts(listRes.products);
      setReviews(revRes);
      if (!revRes.isLiveBackend) {
        setReviewsError("We couldn't load customer reviews right now. Please try again.");
      }
      setLoading(false);
    });
    return () => {
      active = false;
    };
  }, [numericId, recordRecentlyViewed]);

  useEffect(() => {
    const cleanup = loadProductDetails();
    return cleanup;
  }, [loadProductDetails]);

  // Phase 7: Related products logic
  const relatedProducts = useMemo(() => {
    if (!product) return [];
    // Prioritize products from same category, exclude current product
    const sameCategory = allProducts.filter(
      (p) => p.category_id === product.category_id && p.id !== product.id
    );
    // If not enough, pick other top items
    const others = allProducts.filter(
      (p) => p.category_id !== product.category_id && p.id !== product.id
    );
    return [...sameCategory, ...others].slice(0, 4);
  }, [product, allProducts]);

  if (loading && !product) {
    return (
      <div
        aria-busy="true"
        aria-label="Loading product"
        className="bp-container grid animate-pulse grid-cols-1 gap-10 py-10 lg:grid-cols-12 lg:gap-16"
      >
        <div className="aspect-square rounded-4xl bg-surface-subtle lg:col-span-7" />
        <div className="space-y-4 lg:col-span-5">
          <div className="h-4 w-24 rounded bg-surface-subtle" />
          <div className="h-10 w-full rounded bg-surface-subtle" />
          <div className="h-10 w-2/3 rounded bg-surface-subtle" />
          <div className="h-8 w-32 rounded bg-surface-subtle" />
          <div className="h-12 w-full rounded-xl bg-surface-subtle" />
        </div>
      </div>
    );
  }

  if (loadError && !product) {
    return (
      <div role="alert" className="bp-container max-w-xl py-24 text-center">
        <AlertCircle size={32} aria-hidden="true" className="mx-auto text-rose-500" />
        <h1 className="mt-4 text-3xl font-bold text-ink">This product didn&apos;t load</h1>
        <p className="mt-2 text-base leading-7 text-muted">{loadError}</p>
        <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row">
          <PrimaryButton type="button" onClick={loadProductDetails}>
            <RefreshCw size={16} aria-hidden="true" /> Try again
          </PrimaryButton>
          <PrimaryButtonLink href="/shop" variant="secondary">
            <ArrowLeft size={16} aria-hidden="true" /> Back to the shop
          </PrimaryButtonLink>
        </div>
      </div>
    );
  }

  if (!product) {
    return (
      <div className="bp-container max-w-xl py-24 text-center">
        <p className="bp-eyebrow">Not found</p>
        <h1 className="mt-3 text-3xl font-bold text-ink">We can&apos;t find that product</h1>
        <p className="mt-2 text-base leading-7 text-muted">
          It may have been removed or renamed. The shop has everything currently listed.
        </p>
        <PrimaryButtonLink href="/shop" className="mt-8">
          <ArrowLeft size={16} aria-hidden="true" /> Back to the shop
        </PrimaryButtonLink>
      </div>
    );
  }

  const effectivePrice = getEffectivePrice(product);
  const originalPrice = getOriginalPrice(product);
  const discountPercent = getDiscountPercent(product);
  const isWishlisted = wishlist.some((w) => w.id === product.id);
  const rating = Number(product.rating) || 0;
  const outOfStock = product.stock <= 0;
  const lowStock = product.stock > 0 && product.stock <= 10;

  const handleBuyNow = async () => {
    if (outOfStock) return;
    await addToCart(product, quantity, undefined, false);
    if (!isLoggedIn()) {
      router.push(`/login?redirect=${encodeURIComponent("/checkout")}`);
    } else {
      router.push("/checkout");
    }
  };

  const handleSubmitReview = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isLoggedIn()) {
      router.push(
        `/login?redirect=${encodeURIComponent(`/product/${product.id}`)}`
      );
      return;
    }
    const cleanComment = reviewComment.trim();
    if (cleanComment.length < 3) {
      pushToast({
        title: "Review too short",
        description: "Please provide at least a brief comment about your experience.",
        tone: "error",
      });
      return;
    }
    setSubmittingReview(true);

    try {
      const res = await reviewsApi.create(product.id, {
        rating: reviewRating,
        comment: cleanComment,
      });
      if (res.data) {
        setReviews((prev) => [res.data, ...prev]);
      }
      setReviewComment("");
      setReviewRating(5);
      pushToast({
        title: "Review submitted successfully!",
        description: "Thank you for sharing your feedback with the Blue Panda community.",
        tone: "success",
      });
    } catch (err: any) {
      pushToast({
        title: "Could not submit review",
        description: err?.message || "Please check your network and try again.",
        tone: "error",
      });
    } finally {
      setSubmittingReview(false);
    }
  };

  const details: [string, string][] = [
    ...(product.category?.name ? [["Category", product.category.name] as [string, string]] : []),
    ...(product.seller?.name ? [["Sold by", product.seller.name] as [string, string]] : []),
    [
      "Availability",
      outOfStock
        ? "Out of stock"
        : `${product.stock} ${product.stock === 1 ? "unit" : "units"} in stock`,
    ],
    [
      "Delivery",
      `Free over $${FREE_SHIPPING_THRESHOLD}, otherwise $${STANDARD_SHIPPING_FEE} flat`,
    ],
  ];

  const addToBag = () => addToCart(product, quantity, undefined, true);

  return (
    <div>
      <div className="bp-container py-6 sm:py-8">
        {/* Breadcrumb */}
        <nav aria-label="Breadcrumb" className="no-scrollbar overflow-x-auto">
          <ol className="flex items-center gap-1.5 whitespace-nowrap text-sm text-muted">
            <li>
              <Link href="/" className="hover:text-ink">
                Home
              </Link>
            </li>
            <li aria-hidden="true">
              <ChevronRight size={14} />
            </li>
            <li>
              <Link href="/shop" className="hover:text-ink">
                Shop
              </Link>
            </li>
            {product.category?.name && (
              <>
                <li aria-hidden="true">
                  <ChevronRight size={14} />
                </li>
                <li>
                  <Link
                    href={`/shop?category=${encodeURIComponent(product.category.name)}`}
                    className="hover:text-ink"
                  >
                    {product.category.name}
                  </Link>
                </li>
              </>
            )}
            <li aria-hidden="true">
              <ChevronRight size={14} />
            </li>
            <li aria-current="page" className="max-w-[16rem] truncate text-ink sm:max-w-md">
              {product.name}
            </li>
          </ol>
        </nav>

        {/* Product stage + buy box */}
        <div className="mt-8 grid grid-cols-1 gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.7fr)_minmax(0,1fr)] lg:gap-8 xl:gap-12">
          {/* Image */}
          <div className="lg:col-start-2 lg:row-start-1">
            <div className="relative overflow-hidden bg-surface-subtle lg:sticky lg:top-[calc(var(--header-h)+1.5rem)]">
              <button
                type="button"
                onClick={() => setIsZoomed((z) => !z)}
                aria-pressed={isZoomed}
                aria-label={isZoomed ? "Zoom out of product image" : "Zoom into product image"}
                className={`block aspect-square w-full ${isZoomed ? "cursor-zoom-out" : "cursor-zoom-in"}`}
              >
                <img
                  src={resolveProductImage(product)}
                  alt={product.name}
                  onError={applyProductImageFallback}
                  fetchPriority="high"
                  width={900}
                  height={900}
                  className={`h-full w-full object-contain p-8 transition-transform duration-500 ease-out sm:p-12 ${
                    isZoomed ? "scale-[1.6]" : "scale-100"
                  } ${outOfStock ? "opacity-60" : ""}`}
                />
              </button>

              {discountPercent > 0 && (
                <span className="bp-sale-tag pointer-events-none absolute left-5 top-5 text-xs">
                  −{discountPercent}%
                </span>
              )}

              <button
                type="button"
                onClick={() => toggleWishlist(product)}
                aria-pressed={isWishlisted}
                aria-label={isWishlisted ? "Remove from wishlist" : "Save to wishlist"}
                className={`bp-press absolute right-4 top-4 flex h-11 w-11 items-center justify-center rounded-full bg-white shadow-sm ring-1 ring-line ${
                  isWishlisted ? "text-rose-600" : "text-ink-soft hover:text-rose-600"
                }`}
              >
                <Heart size={19} aria-hidden="true" className={isWishlisted ? "fill-current" : ""} />
              </button>
            </div>
          </div>

          {/* Buy box */}
          <div className="lg:col-start-1 lg:row-start-1 lg:pt-10">
            <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted">
              {product.category?.name && <span>{product.category.name}</span>}
              {rating > 0 && (
                <a href="#reviews" className="inline-flex items-center gap-1 text-ink hover:text-brand">
                  <Star size={14} aria-hidden="true" className="fill-amber-400 text-amber-400" />
                  <span className="font-semibold">{rating.toFixed(1)}</span>
                  <span className="text-muted">
                    · {reviews.length} {reviews.length === 1 ? "review" : "reviews"}
                  </span>
                </a>
              )}
            </p>

            <h1 className="mt-3 text-3xl font-medium leading-[1.08] text-ink sm:text-4xl lg:text-[2.4rem]">
              {product.name}
            </h1>

            {product.seller && (
              <p className="mt-3 text-sm text-muted">
                Sold by{" "}
                <Link
                  href={`/shop?seller=${product.seller.id}`}
                  className="font-medium text-ink underline decoration-line-strong underline-offset-4 hover:decoration-ink"
                >
                  {product.seller.name}
                </Link>
              </p>
            )}

            {/* Price & stock */}
            <div className="mt-8 border-t border-line pt-6">
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <span className="bp-price text-4xl font-bold text-ink">
                  ${effectivePrice.toFixed(2)}
                </span>
                {originalPrice && (
                  <>
                    <span className="bp-price text-lg text-muted line-through">
                      ${originalPrice.toFixed(2)}
                    </span>
                    <span className="bp-sale-tag">
                      Save ${(originalPrice - effectivePrice).toFixed(2)}
                    </span>
                  </>
                )}
              </div>
              <p
                className={`mt-3 flex items-center gap-2 text-sm font-medium ${
                  outOfStock ? "text-muted" : lowStock ? "text-amber-700" : "text-emerald-700"
                }`}
              >
                {outOfStock ? (
                  <>
                    <AlertCircle size={16} aria-hidden="true" /> Out of stock
                  </>
                ) : lowStock ? (
                  <>
                    <AlertCircle size={16} aria-hidden="true" /> Only {product.stock} left in stock
                  </>
                ) : (
                  <>
                    <Check size={16} aria-hidden="true" /> In stock, ready to ship
                  </>
                )}
              </p>
            </div>

            {/* Quantity + actions */}
            <div className="mt-8 space-y-3">
              <div className="flex gap-3">
                <div className="inline-flex shrink-0 items-center rounded-xl border border-line-strong bg-white">
                  <button
                    type="button"
                    onClick={() => setQuantity((q) => Math.max(1, q - 1))}
                    aria-label="Decrease quantity"
                    disabled={outOfStock || quantity <= 1}
                    className="flex h-12 w-11 items-center justify-center text-ink disabled:opacity-30"
                  >
                    <Minus size={16} aria-hidden="true" />
                  </button>
                  <span
                    aria-live="polite"
                    aria-label={`Quantity ${quantity}`}
                    className="bp-price w-8 text-center text-base font-semibold text-ink"
                  >
                    {quantity}
                  </span>
                  <button
                    type="button"
                    onClick={() =>
                      setQuantity((q) => Math.min(Math.max(1, product.stock), q + 1))
                    }
                    aria-label="Increase quantity"
                    disabled={outOfStock || quantity >= product.stock}
                    className="flex h-12 w-11 items-center justify-center text-ink disabled:opacity-30"
                  >
                    <Plus size={16} aria-hidden="true" />
                  </button>
                </div>

                <PrimaryButton
                  type="button"
                  size="lg"
                  disabled={outOfStock}
                  onClick={addToBag}
                  className="flex-1"
                >
                  <ShoppingBag size={18} aria-hidden="true" />
                  {outOfStock ? "Sold out" : "Add to bag"}
                </PrimaryButton>
              </div>

              <PrimaryButton
                type="button"
                variant="brand"
                size="lg"
                disabled={outOfStock}
                onClick={handleBuyNow}
                className="w-full"
              >
                Buy now
                {!outOfStock && (
                  <span className="bp-price font-normal text-white/80">
                    · ${(effectivePrice * quantity).toFixed(2)}
                  </span>
                )}
              </PrimaryButton>
            </div>

            <p className="mt-5 flex items-start gap-2.5 text-sm leading-6 text-muted">
              <Truck size={18} aria-hidden="true" className="mt-0.5 shrink-0 text-ink" />
              Free delivery on orders over ${FREE_SHIPPING_THRESHOLD}. Below that, a ${STANDARD_SHIPPING_FEE}
              flat rate.
            </p>

          </div>
          <aside aria-label="Product overview" className="border-t border-line pt-7 lg:col-start-3 lg:row-start-1 lg:border-t-0 lg:pt-10">
            <h2 className="text-lg font-medium text-ink">Overview</h2>
            {product.description && <p className="mt-5 text-sm leading-7 text-ink-soft">{product.description}</p>}
            {details.length > 0 && (
              <section aria-labelledby="product-details" className="mt-8 border-t border-line pt-6">
                <h3 id="product-details" className="text-sm font-semibold text-ink">Product details</h3>
                <dl className="mt-3 divide-y divide-line text-sm">
                  {details.map(([label, value]) => (
                    <div key={label} className="flex justify-between gap-5 py-3">
                      <dt className="text-muted">{label}</dt>
                      <dd className="text-right font-medium text-ink">{value}</dd>
                    </div>
                  ))}
                </dl>
              </section>
            )}
            <a href="#reviews" className="mt-8 inline-flex min-h-11 items-center gap-2 border-b border-line-strong text-sm font-medium text-ink hover:border-ink">Customer reviews <ArrowRight size={15} aria-hidden="true" /></a>
          </aside>
        </div>
      </div>

      {/* Reviews */}
      <section
        id="reviews"
        aria-labelledby="reviews-title"
        className="mt-(--section-gap) border-t border-line bg-white py-16 sm:py-20"
      >
        <div className="bp-container grid grid-cols-1 gap-12 lg:grid-cols-12 lg:gap-16">
          <div className="lg:col-span-4">
            <p className="bp-eyebrow">Reviews</p>
            <h2 id="reviews-title" className="mt-2 text-3xl font-bold text-ink sm:text-4xl">
              What buyers say
            </h2>
            {rating > 0 && reviews.length > 0 && (
              <p className="mt-4 flex items-center gap-2 text-base text-ink">
                <Star size={20} aria-hidden="true" className="fill-amber-400 text-amber-400" />
                <span className="bp-price text-2xl font-bold">{rating.toFixed(1)}</span>
                <span className="text-muted">
                  from {reviews.length} {reviews.length === 1 ? "review" : "reviews"}
                </span>
              </p>
            )}

            {/* Write a review */}
            <div className="mt-8">
              {!isLoggedIn() ? (
                <div className="rounded-3xl border border-line bg-paper p-6">
                  <h3 className="text-base font-semibold text-ink">Bought this?</h3>
                  <p className="mt-1 text-sm leading-6 text-muted">
                    Sign in to rate it and leave a review.
                  </p>
                  <PrimaryButtonLink
                    href={`/login?redirect=${encodeURIComponent(`/product/${product.id}`)}`}
                    variant="secondary"
                    className="mt-4"
                  >
                    Sign in to review
                  </PrimaryButtonLink>
                </div>
              ) : (
                <form
                  onSubmit={handleSubmitReview}
                  className="space-y-5 rounded-3xl border border-line bg-paper p-6"
                >
                  <h3 className="text-base font-semibold text-ink">Write a review</h3>

                  <fieldset>
                    <legend className="mb-1.5 text-sm font-medium text-ink">Your rating</legend>
                    <div className="flex items-center gap-0.5">
                      {[1, 2, 3, 4, 5].map((star) => (
                        <button
                          key={star}
                          type="button"
                          onClick={() => setReviewRating(star)}
                          aria-label={`${star} ${star === 1 ? "star" : "stars"}`}
                          aria-pressed={star === reviewRating}
                          className="flex h-11 w-11 items-center justify-center rounded-lg"
                        >
                          <Star
                            size={24}
                            aria-hidden="true"
                            className={
                              star <= reviewRating
                                ? "fill-amber-400 text-amber-400"
                                : "text-line-strong"
                            }
                          />
                        </button>
                      ))}
                    </div>
                  </fieldset>

                  <div>
                    <label htmlFor="review-comment" className="mb-1.5 block text-sm font-medium text-ink">
                      Your review
                    </label>
                    <textarea
                      id="review-comment"
                      rows={4}
                      required
                      minLength={3}
                      value={reviewComment}
                      onChange={(e) => setReviewComment(e.target.value)}
                      placeholder="Performance, build quality, how it fits your setup…"
                      className="w-full rounded-xl border border-line-strong bg-white p-3 text-base leading-6 text-ink placeholder:text-muted focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20 sm:text-sm"
                    />
                  </div>

                  <PrimaryButton type="submit" disabled={submittingReview} className="w-full">
                    {submittingReview ? "Posting review…" : "Post review"}
                  </PrimaryButton>
                </form>
              )}
            </div>
          </div>

          {/* Review list */}
          <div className="lg:col-span-8">
            {reviewsError && reviews.length === 0 ? (
              <div role="alert" className="rounded-3xl border border-rose-200 bg-rose-50/40 p-8 text-center">
                <p className="text-base font-semibold text-ink">Reviews didn&apos;t load</p>
                <p className="mt-1 text-sm text-muted">{reviewsError}</p>
                <PrimaryButton
                  type="button"
                  variant="secondary"
                  onClick={loadProductDetails}
                  className="mt-5"
                >
                  <RefreshCw size={16} aria-hidden="true" /> Try again
                </PrimaryButton>
              </div>
            ) : reviews.length === 0 ? (
              <div className="rounded-3xl border border-dashed border-line-strong p-10 text-center">
                <p className="text-base font-semibold text-ink">No reviews yet</p>
                <p className="mt-1 text-sm text-muted">Reviews from buyers will appear here.</p>
              </div>
            ) : (
              <ul className="divide-y divide-line border-y border-line">
                {reviews.map((rev) => (
                  <li key={rev.id} className="py-6">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="flex items-center gap-3">
                        <span
                          aria-hidden="true"
                          className="flex h-9 w-9 items-center justify-center rounded-full bg-ink text-sm font-semibold text-white"
                        >
                          {(rev.user?.name || "C").charAt(0).toUpperCase()}
                        </span>
                        <div>
                          <p className="text-sm font-semibold text-ink">
                            {rev.user?.name || "Customer"}
                          </p>
                          <p className="text-xs text-muted">
                            <time dateTime={rev.created_at}>
                              {new Date(rev.created_at).toLocaleDateString(undefined, {
                                year: "numeric",
                                month: "short",
                                day: "numeric",
                              })}
                            </time>
                          </p>
                        </div>
                      </div>
                      <div
                        role="img"
                        aria-label={`${rev.rating} out of 5 stars`}
                        className="flex items-center gap-0.5"
                      >
                        {Array.from({ length: 5 }).map((_, idx) => (
                          <Star
                            key={idx}
                            size={15}
                            aria-hidden="true"
                            className={
                              idx < rev.rating ? "fill-amber-400 text-amber-400" : "text-line-strong"
                            }
                          />
                        ))}
                      </div>
                    </div>
                    <p className="mt-3 max-w-2xl text-[15px] leading-7 text-ink-soft">{rev.comment}</p>
                    {rev.admin_reply && (
                      <div className="mt-4 max-w-2xl border-l-2 border-brand pl-4 text-sm leading-6 text-ink-soft">
                        <p className="font-semibold text-ink">Reply from the store</p>
                        <p className="mt-0.5">{rev.admin_reply}</p>
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </section>

      {/* Related products */}
      {relatedProducts.length > 0 && (
        <section aria-labelledby="related-title" className="bp-container mt-(--section-gap)">
          <div className="mb-8 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="bp-eyebrow">Keep browsing</p>
              <h2 id="related-title" className="mt-2 text-3xl font-bold text-ink sm:text-4xl">
                More like this
              </h2>
            </div>
            <Link href="/shop" className="group inline-flex min-h-11 items-center gap-1.5 text-sm font-semibold text-ink">
              <span className="bp-link">Shop all products</span>
              <ArrowRight size={16} aria-hidden="true" className="transition-transform group-hover:translate-x-0.5" />
            </Link>
          </div>
          <ProductGrid products={relatedProducts} />
        </section>
      )}

      {/* Mobile purchase bar: price and the main action always in reach */}
      <div className="bp-mobile-buybar fixed inset-x-0 bottom-0 z-30 border-t border-line bg-white/95 px-4 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-3 backdrop-blur lg:hidden">
        <div className="mx-auto flex max-w-xl items-center gap-4">
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs text-muted">{product.name}</p>
            <p className="bp-price text-lg font-bold text-ink">${effectivePrice.toFixed(2)}</p>
          </div>
          <PrimaryButton
            type="button"
            size="lg"
            disabled={outOfStock}
            onClick={addToBag}
            className="shrink-0"
          >
            <ShoppingBag size={18} aria-hidden="true" />
            {outOfStock ? "Sold out" : "Add to bag"}
          </PrimaryButton>
        </div>
      </div>
    </div>
  );
}
