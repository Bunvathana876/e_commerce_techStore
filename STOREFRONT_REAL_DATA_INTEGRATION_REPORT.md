# Storefront Real Data Integration Report — Blue Panda 2.0

**Date:** November 14, 2026  
**Project Root:** `/Users/bunvathana/Documents/Code/Project/e-commerce`  
**Storefront:** `/Users/bunvathana/Documents/Code/Project/e-commerce/storefront`  
**Backend API:** `https://blue-panda-api-demo.onrender.com/api` (configured via `NEXT_PUBLIC_API_URL`)

---

## 1. Executive Summary

This report documents the removal of all fictional fallback data, keyword-guessed stock imagery, fabricated listing counters, and silent fallback behaviors across the **Blue Panda 2.0** Next.js storefront (`storefront/`), while preserving 100% of the existing Blue Panda 2.0 UI design, layouts, animations, components, color palette, navigation, and responsiveness.

Every backend-powered storefront route (`Homepage`, `Shop`, `Categories`, `Deals`, `New Arrivals`, `Product Details`, `Official Partner Stores`, `Command Search`, `Cart`, `Wishlist`, `Checkout`, `Orders`, and `Sitemap`) now renders exclusively authoritative records returned by the FastAPI backend and implements explicit four-state handling:
1. **Loading** (skeleton placeholders / spinners without fictional data)
2. **Success** (real API records with authentic IDs, pricing, stock, ratings, categories, and sellers)
3. **Empty** (clear, truthful empty-catalog messaging when the API returns `200 OK` with zero records)
4. **Error** (distinct error banners/cards with working **Retry** buttons when the API request fails)

---

## 2. Fake Data Sources Found

During the Phase 1 inspection, the following fictional or misleading fallback patterns were identified in `storefront/`:

1. **`SHOWCASE_PRODUCTS` in [`storefront/src/app/sitemap.ts`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/storefront/src/app/sitemap.ts)**
   - `sitemap.ts` imported `SHOWCASE_PRODUCTS` from `src/lib/store-catalog.ts` and fell back to generating `/product/1` through `/product/16` from `SHOWCASE_PRODUCTS` whenever the backend returned an empty list or failed during build/runtime.
2. **Product-Name Keyword Image Guessing in [`storefront/src/lib/store-catalog.ts`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/storefront/src/lib/store-catalog.ts)**
   - `resolveProductImage(product)` previously inspected `product.name.toLowerCase()` for keywords (`laptop`, `macbook`, `keyboard`, `mouse`, `gpu`, `rtx`, `monitor`, `nike`, `adidas`, `puma`, `new balance`, `headphone`, `watch`, `buds`, `jacket`, `hoodie`, `chino`, `wallet`, `oil`) and substituted unrelated external Unsplash photographs whenever a product's `image_url` was missing or unrecognized.
3. **Indistinguishable Empty vs. Failed Array Fetchers in [`storefront/src/lib/store-catalog.ts`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/storefront/src/lib/store-catalog.ts)**
   - `fetchStoreCategories()`, `fetchStoreSellers()`, `fetchStoreCoupons()`, and `fetchStoreReviews()` caught network/API errors and returned a plain `[]`, making it impossible for callers (`categories/page.tsx`, `deals/page.tsx`, `stores/page.tsx`, `product/[id]/page.tsx`) to distinguish a genuinely empty database table (`200 OK` with `[]`) from a failed HTTP request.
   - `categories/page.tsx` treated `loadedCats.length === 0 && loadedProds.length === 0` as a network error even when both endpoints succeeded with `200 OK`.
4. **Product ID `1` Fallback & Indistinguishable 404 vs. Network Error in [`storefront/src/app/(store)/product/[id]/page.tsx`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/storefront/src/app/(store)/product/[id]/page.tsx)**
   - `const numericId = Number(id) || 1;` silently substituted product ID `1` when the route parameter was `0` or non-numeric.
   - `fetchStoreProductById(id)` returned `{ product: null, isLiveBackend: false }` on both `404 Not Found` and `500`/network failures, preventing `product/[id]/page.tsx` from distinguishing a non-existent product ID (`Product Not Found`) from a failed backend request (`Unable to Load Product` + `Retry`).
5. **Fabricated Seller Listing Counts in [`storefront/src/app/(store)/stores/page.tsx`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/storefront/src/app/(store)/stores/page.tsx)**
   - Line 128 rendered `{seller.products_count || 5}+ Active Listings`, fabricating `"5+ Active Listings"` whenever a seller had `0` products or an unset `products_count`.
6. **Fake Stock Ceiling Fallback (`product.stock || 99`)**
   - `storefront/src/lib/store.ts` (`updateQuantity`), `storefront/src/app/(store)/product/[id]/page.tsx`, and `storefront/src/components/store/QuickViewDialog.tsx` used `product.stock || 99`, treating `stock === 0` as `99` available units.
7. **Unfiltered Regex Hiding Real Products on Homepage (`storefront/src/app/(store)/page.tsx`)**
   - `featuredTechProducts` filtered `products` strictly by `/electr|tech|audio|gadget|watch|headphone|buds|earbud/i`, hiding real backend products if their names/categories did not match that regex.

---

## 3. Files Modified

| File | Summary of Changes |
| :--- | :--- |
| [`storefront/src/lib/api.ts`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/storefront/src/lib/api.ts) | Attached HTTP `status` code (`err.status = response.status`) to thrown `Error` instances in `request<T>` so callers can distinguish `404 Not Found` from network/5xx errors. |
| [`storefront/src/lib/store-catalog.ts`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/storefront/src/lib/store-catalog.ts) | Removed keyword-guessed Unsplash image fallbacks from `resolveProductImage`; added `applyProductImageFallback`; added `isDemoModeEnabled()`; added `CatalogArrayResult<T>` metadata (`isLiveBackend`, `error`) to `fetchStoreCategories`, `fetchStoreSellers`, `fetchStoreCoupons`, and `fetchStoreReviews`; added `notFound` and `error` to `fetchStoreProductById`; enforced `status: "approved"` filtering in `fetchStoreReviews`; restricted `validateCouponLocally` to explicit non-production demo mode. |
| [`storefront/src/app/sitemap.ts`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/storefront/src/app/sitemap.ts) | Removed `SHOWCASE_PRODUCTS` import and fallback; exported testable `generateStorefrontSitemap` that emits only real active backend product URLs when `isLiveBackend` is true. |
| [`storefront/src/lib/store.ts`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/storefront/src/lib/store.ts) | Hardened `addToCart` to reject invalid/inactive/out-of-stock products (`id <= 0`, `is_active === false`, `stock <= 0`); fixed `updateQuantity` to remove `product.stock || 99` and clamp strictly to real `product.stock`. |
| [`storefront/src/lib/checkout-security.ts`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/storefront/src/lib/checkout-security.ts) | Hardened `executeCheckoutOrder` to reject cart items with non-positive or non-integer `productId` or `quantity` before submitting to the backend. |
| [`storefront/src/app/(store)/page.tsx`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/storefront/src/app/(store)/page.tsx) | Added distinct `productsError` and `categoriesError` states with Retry buttons; updated empty states to Phase 4 copy; updated `featuredTechProducts` to fall back to `products` when no tech-keyword match exists so real backend products are never hidden. |
| [`storefront/src/app/(store)/shop/page.tsx`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/storefront/src/app/(store)/shop/page.tsx) | Aligned empty catalog (`No Products Available`) and failed request (`Unable to Load Products` + `Retry`) states with Phase 4 requirements. |
| [`storefront/src/app/(store)/categories/page.tsx`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/storefront/src/app/(store)/categories/page.tsx) | Fixed `loadData` to check `!catRes.value.isLiveBackend` instead of treating an empty category array as a network error; updated empty/error copy; guarded `techCategories.length > 0`. |
| [`storefront/src/app/(store)/deals/page.tsx`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/storefront/src/app/(store)/deals/page.tsx) | Added `couponsError` and `productsError` states and functioning **Retry** buttons for both Available Promo Coupons and Discounted Hardware sections. |
| [`storefront/src/app/(store)/new-arrivals/page.tsx`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/storefront/src/app/(store)/new-arrivals/page.tsx) | Fixed error detection on `!prodRes.value.isLiveBackend`, added a **Retry** button on error, and separated empty catalog (`No Products Available`) from empty filter results (`No Items Found`). |
| [`storefront/src/app/(store)/product/[id]/page.tsx`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/storefront/src/app/(store)/product/[id]/page.tsx) | Removed `|| 1` product ID fallback; separated API failure (`Unable to Load Product` + `Retry`) from 404 (`Product Not Found`); added `reviewsError` state + `Retry`; updated empty reviews copy to `No Reviews Yet`; replaced `"New Release"` when `rating <= 0` with `"No ratings yet"`; fixed `product.stock || 99`; added `onError={applyProductImageFallback}`. |
| [`storefront/src/app/(store)/stores/page.tsx`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/storefront/src/app/(store)/stores/page.tsx) | Added `loadError` state and **Retry** button when `fetchStoreSellers()` fails; replaced fabricated `{seller.products_count || 5}+ Active Listings` with real `{seller.products_count ?? 0} Active Listings`. |
| [`storefront/src/components/store/SearchCommandDialog.tsx`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/storefront/src/components/store/SearchCommandDialog.tsx) | Added `loadError` state with **Retry** button, empty catalog state (`No Products Available`), and `onError={applyProductImageFallback}` on search result thumbnails. |
| [`storefront/src/components/store/ProductCard.tsx`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/storefront/src/components/store/ProductCard.tsx) | Added `onError={applyProductImageFallback}` to both grid and list product `<img>` elements. |
| [`storefront/src/components/store/QuickViewDialog.tsx`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/storefront/src/components/store/QuickViewDialog.tsx) | Added `onError={applyProductImageFallback}`, replaced `"New Arrival"` when `rating <= 0` with `"No ratings yet"`, and fixed `product.stock || 99`. |
| [`storefront/src/components/store/CartDrawer.tsx`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/storefront/src/components/store/CartDrawer.tsx) | Added `onError={applyProductImageFallback}` to cart item thumbnails. |
| [`storefront/src/app/(store)/cart/page.tsx`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/storefront/src/app/(store)/cart/page.tsx) | Added `onError={applyProductImageFallback}` to shopping bag thumbnails. |
| [`storefront/src/app/(store)/orders/page.tsx`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/storefront/src/app/(store)/orders/page.tsx) | Added `onError={applyProductImageFallback}` to order line-item thumbnails. |
| [`storefront/src/components/store/CategoryCard.tsx`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/storefront/src/components/store/CategoryCard.tsx) | Added `onError={applyProductImageFallback}` to category card imagery. |
| [`storefront/src/components/store/promotions/CategoryFeatureCard.tsx`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/storefront/src/components/store/promotions/CategoryFeatureCard.tsx) | Added `onError={applyProductImageFallback}` to category feature card cover imagery. |
| [`storefront/src/lib/__tests__/store-real-data-integration.test.ts`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/storefront/src/lib/__tests__/store-real-data-integration.test.ts) | Added 13-scenario automated test suite verifying real data integration, empty vs. error state separation, retry recovery, 404 product handling, image fallbacks, cart/checkout validation, sitemap safety, and production demo-mode disablement. |

---

## 4. Catalog Integration Changes

- **`fetchStoreProducts(deps?)`**: Queries `/api/products?limit=100`, filters out `is_active === false`, and returns `{ products, isLiveBackend: true }` on success or `{ products: [], isLiveBackend: false, error: "We couldn't load the catalog. Please try again." }` on error. Never returns `SHOWCASE_PRODUCTS`.
- **`fetchStoreCategories(deps?)`**: Queries `/api/categories?active_only=true`, filters out `is_active === false`, and returns a `CatalogArrayResult<ApiCategory>` (`ApiCategory[] & { isLiveBackend: boolean; error?: string }`). Never returns `SHOWCASE_CATEGORIES`.
- **Homepage (`page.tsx`), Shop (`shop/page.tsx`), Categories (`categories/page.tsx`), and New Arrivals (`new-arrivals/page.tsx`)**: All consume live backend responses and distinguish `isLiveBackend: true` with `0` items (Empty state) from `isLiveBackend: false` (Error state with Retry button).

---

## 5. Product Detail Changes

- **Removed Product ID `1` Substitution**: In [`storefront/src/app/(store)/product/[id]/page.tsx`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/storefront/src/app/(store)/product/[id]/page.tsx), `const numericId = Number(id);` no longer falls back to `|| 1`. Invalid or non-positive IDs immediately resolve to the **Product Not Found** state.
- **404 vs. Network Error Separation**: `fetchStoreProductById(id)` inspects HTTP status (`404`) to return `{ product: null, isLiveBackend: true, notFound: true }` when a product ID does not exist in PostgreSQL, and `{ product: null, isLiveBackend: false, notFound: false, error }` when the request fails.
- **Quantity Clamping**: Removed `product.stock || 99` in `product/[id]/page.tsx` and `QuickViewDialog.tsx`, clamping quantity strictly to `Math.max(1, product.stock)` and disabling purchase controls when `product.stock <= 0`.

---

## 6. Reviews and Ratings Changes

- **Approved Reviews Only**: `fetchStoreReviews(productId)` passes `{ product_id: productId, status: "approved" }` to `/api/reviews` and filters out any non-approved review records. Never falls back to `SHOWCASE_REVIEWS`.
- **Honest Rating Display**: When `Number(product.rating) <= 0`, `ProductCard` hides the rating badge and `product/[id]/page.tsx` / `QuickViewDialog.tsx` display `"No ratings yet"` instead of misleading labels.
- **Reviews Tab States**: On `product/[id]/page.tsx`, the Customer Reviews tab renders **Unable to Load Reviews** with a **Retry** button when `reviewsError` is set, and **No Reviews Yet** — *"Be the first customer to leave a review."* when `reviews.length === 0`.

---

## 7. Seller and Promotion Changes

- **Official Partner Stores (`stores/page.tsx`)**:
  - `fetchStoreSellers()` queries `/api/sellers?status=Active`, filters active sellers, and never falls back to `SHOWCASE_SELLERS`.
  - Replaced `{seller.products_count || 5}+ Active Listings` with `{seller.products_count ?? 0} Active Listings` so zero-product sellers never display a fabricated `5+` count.
  - Added **Unable to Load Partner Stores** error state with a working **Retry** button when `!data.isLiveBackend`.
- **Deals & Promotions (`deals/page.tsx`)**:
  - `fetchStoreCoupons()` queries `/api/coupons/available`, filters active coupons, and never falls back to `SHOWCASE_COUPONS`.
  - Added independent error states and **Retry** buttons for both `couponsError` (**Unable to Load Promotions**) and `productsError` (**Unable to Load Products**).
  - `validateCouponLocally` in `store-catalog.ts` is locked behind `isDemoModeEnabled()` / `options.allowDemoMode === true` and never runs in production (`NODE_ENV === "production"`).

---

## 8. Image Fallback Changes

- **Removed Keyword-Based Unsplash Guessing**: Removed all product-name regex/keyword checks (`laptop`, `keyboard`, `gpu`, `monitor`, `nike`, `adidas`, `puma`, `new balance`, `headphone`, `watch`, `buds`, `jacket`, `hoodie`, `chino`, `wallet`, `oil`) from `resolveProductImage(product)` in [`storefront/src/lib/store-catalog.ts`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/storefront/src/lib/store-catalog.ts).
- **Authoritative Image Resolution**: `resolveProductImage` now resolves only:
  1. Exact seeded asset path mappings in `SEEDED_IMAGE_MAP` (for backend-seeded records that reference `assets/images/products/*.png`)
  2. Valid `http://`, `https://`, or `data:image/` URLs
  3. Backend `/uploads/...` paths (prefixed with the backend origin)
  4. Valid root-relative `/images/...` paths
  5. Otherwise returns `NEUTRAL_PRODUCT_PLACEHOLDER` (`/images/product-placeholder.svg`)
- **Runtime Broken-Image Protection**: Added `applyProductImageFallback` (`onError` handler) to `<img>` elements across `ProductCard.tsx`, `QuickViewDialog.tsx`, `product/[id]/page.tsx`, `SearchCommandDialog.tsx`, `CartDrawer.tsx`, `cart/page.tsx`, `orders/page.tsx`, `CategoryCard.tsx`, and `CategoryFeatureCard.tsx`.

---

## 9. Loading, Empty, and Error State Coverage

| Surface | Loading State | Empty State | Error State + Retry |
| :--- | :--- | :--- | :--- |
| **Homepage (`page.tsx`)** | `PromoHero` skeleton + 8 `ProductSkeleton` cards + 6 category skeletons | **No Products Available** / **No Categories Available** | Top alert banner + section-level **Unable to Load Products** / **Unable to Load Categories** with **Retry** buttons |
| **Shop (`shop/page.tsx`)** | 6 `ProductSkeleton` cards (grid/list aware) | **No Products Available** (or **No Products Match Your Filters** with Reset button) | **Unable to Load Products** + **Retry** button |
| **Categories (`categories/page.tsx`)** | 6 department card skeletons | **No Categories Available** — *"There are currently no categories to display."* | **Unable to Load Categories** + **Retry** button |
| **Deals (`deals/page.tsx`)** | 4 coupon skeletons + 4 product skeletons | *"No active promotional codes at this moment"* / **No Markdown Discounts Currently Active** | **Unable to Load Promotions** + **Retry** / **Unable to Load Products** + **Retry** |
| **New Arrivals (`new-arrivals/page.tsx`)** | 8 `ProductSkeleton` cards | **No Products Available** (or **No Items Found** when filtered) | **Unable to Load Products** + **Retry** button |
| **Product Detail (`product/[id]/page.tsx`)** | Centered loading spinner | **Product Not Found** (404 / inactive / invalid ID) + **No Reviews Yet** | **Unable to Load Product** + **Retry** / **Unable to Load Reviews** + **Retry** |
| **Partner Stores (`stores/page.tsx`)** | 3 store card skeletons | **No Official Partner Stores Listed** | **Unable to Load Partner Stores** + **Retry** button |
| **Command Search (`SearchCommandDialog.tsx`)** | Spinner (`Searching live inventory...`) | **No Products Available** (or `No products found for "..."`) | **Unable to Load Products** + **Retry** button |

---

## 10. Sitemap and Metadata Changes

- Updated [`storefront/src/app/sitemap.ts`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/storefront/src/app/sitemap.ts) to remove the `SHOWCASE_PRODUCTS` import and fallback completely.
- `generateStorefrontSitemap()` now calls `fetchStoreProducts()` and appends `/product/{id}` entries **only** when `isLiveBackend && products.length > 0` and each product has a positive integer `id` and `is_active !== false`.
- When the backend is unreachable or returns an empty catalog, `sitemap()` returns only the 6 canonical static routes (`/`, `/shop`, `/categories`, `/deals`, `/new-arrivals`, `/stores`).

---

## 11. Automated Tests Added

Added [`storefront/src/lib/__tests__/store-real-data-integration.test.ts`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/storefront/src/lib/__tests__/store-real-data-integration.test.ts) with 13 unit/integration test cases:
1. Real products display when API succeeds (and `is_active: false` items are filtered out).
2. Empty API response produces empty state (`isLiveBackend: true`, `products: []`).
3. Failed requests produce error state (`isLiveBackend: false`, `products: []`, `error` message populated).
4. Retry performs another request and recovers when backend responds.
5. Unknown product IDs (`404` or invalid ID) return `notFound: true, product: null` and never substitute `SHOWCASE_PRODUCTS`.
6. Empty categories remain empty (`isLiveBackend: true`) and failed categories report failure (`isLiveBackend: false`).
7. Empty reviews remain empty and unapproved (`pending`) reviews are filtered out.
8. Failed seller requests do not show fake sellers (`isLiveBackend: false`, `length: 0`).
9. Failed coupon requests do not show fake promotions (`isLiveBackend: false`, `length: 0`).
10. Missing or broken product images resolve to `NEUTRAL_PRODUCT_PLACEHOLDER` and runtime `applyProductImageFallback` replaces broken image URLs without keyword-guessed Unsplash photos.
11. Cart and checkout reject invalid, inactive, or out-of-stock products and clamp quantities strictly to `product.stock`.
12. Sitemap never includes fictional product URLs when the backend fails or returns empty, and includes real product URLs when the backend succeeds.
13. Production (`NODE_ENV === "production"`) never activates demo mode (`isDemoModeEnabled() === false`).

---

## 12. Quality Check Results

| Check | Command | Result |
| :--- | :--- | :--- |
| **TypeScript Typecheck** | `rtk npx tsc --noEmit` | **PASS** (0 errors) |
| **ESLint** | `rtk npm run lint` | **PASS** (0 errors, 0 warnings) |
| **Automated Test Suite** | `rtk npm test` | **PASS** (69 / 69 tests passing across all test files) |
| **Production Build** | `rtk npm run build` | **PASS** (Next.js production build succeeded) |
| **Git Whitespace / Diff Check** | `rtk git diff --check` | **PASS** (0 formatting or whitespace issues) |

---

## 13. Remaining Backend or Data Limitations

1. **Render Free-Tier Cold Starts**: The deployed FastAPI backend (`https://blue-panda-api-demo.onrender.com/api`) is hosted on Render's free tier and may take 15–50 seconds to wake from sleep on the first request after inactivity. With the new error states and **Retry** buttons in place, customers now see a truthful error message and can retry once the instance wakes up instead of seeing fake showcase products.
2. **Seeded Legacy Asset Paths in Database**: Some products seeded by `backend/seed.py` store relative paths like `assets/images/products/nike_airmax.png` (originally written for the Flutter mobile asset bundle). `SEEDED_IMAGE_MAP` in `store-catalog.ts` continues to map those specific known database seed paths so real database records render cleanly, while any unmapped or missing image path now falls back to `/images/product-placeholder.svg` instead of guessing by product name.
3. **Variant Persistence**: Hardware configuration pills (`Standard Edition`, `Midnight Black`, etc.) on the product detail page are stored in client cart line keys (`{productId}:{variant}`), whereas the backend `cart_items` and `order_items` tables persist `product_id` and `quantity`.

---

## 14. Recommended Next Steps

1. **Backend Health Warmup / Keep-Alive**: Configure an uptime monitor or lightweight cron ping against `https://blue-panda-api-demo.onrender.com/api/health` to minimize Render cold-start timeouts for storefront visitors.
2. **Normalize Seeded Product Image URLs in PostgreSQL**: Update `backend/seed.py` (or upload product images to persistent object storage / Supabase Storage) so all database `image_url` values use canonical HTTPS URLs or `/uploads/...` paths.
3. **Server-Side Pagination on Shop Catalog**: Currently `fetchStoreProducts()` requests up to `limit=100` active products and filters client-side for instant facet updates; if the catalog grows beyond 100 active SKUs, wire `/shop` filter state directly to the backend pagination/search query parameters (`page`, `category_id`, `search`, `min_price`, `max_price`, `sort`).
