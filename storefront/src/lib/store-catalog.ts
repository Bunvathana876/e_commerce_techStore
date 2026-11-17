import {
  API_BASE_URL,
  categoriesApi,
  couponsApi,
  productsApi,
  reviewsApi,
  sellersApi,
  type ApiCategory,
  type ApiCoupon,
  type ApiProduct,
  type ApiReview,
  type ApiSeller,
} from "./api";

const BACKEND_ORIGIN = API_BASE_URL.replace(/\/api\/?$/, "");

export const NEUTRAL_PRODUCT_PLACEHOLDER =
  'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="600" height="600" viewBox="0 0 600 600" fill="none"><rect width="600" height="600" fill="%23EEEEEC"/><g transform="translate(240, 240)" stroke="%23686868" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" fill="none"><rect x="3" y="3" width="114" height="114" rx="8" fill="%23DDDDDA" stroke="none"/><path d="m21 80 25-25a12 12 0 0 1 17 0l42 42"/><circle cx="45" cy="45" r="9" fill="%23686868"/><path d="M78 68l11-11a12 12 0 0 1 17 0l14 14"/></g><text x="300" y="390" text-anchor="middle" font-family="system-ui,-apple-system,sans-serif" font-size="14" font-weight="500" fill="%23686868">Image unavailable</text></svg>';

export function resolveProductImage(
  product?: Partial<ApiProduct> | null
): string {
  const raw = product?.image_url?.trim() || "";
  if (raw) {
    if (
      raw.startsWith("http://") ||
      raw.startsWith("https://") ||
      raw.startsWith("data:image/")
    ) {
      return raw;
    }
    if (raw.startsWith("/uploads") || raw.startsWith("uploads/")) {
      return `${BACKEND_ORIGIN}${raw.startsWith("/") ? raw : `/${raw}`}`;
    }
    if (raw.startsWith("/images/")) {
      return raw;
    }
    if (raw.startsWith("assets/images/products/")) {
      return `${BACKEND_ORIGIN}/${raw}`;
    }
  }

  return NEUTRAL_PRODUCT_PLACEHOLDER;
}

export function applyProductImageFallback(event: {
  currentTarget: HTMLImageElement;
}): void {
  if (event.currentTarget.src !== NEUTRAL_PRODUCT_PLACEHOLDER) {
    event.currentTarget.src = NEUTRAL_PRODUCT_PLACEHOLDER;
  }
}

export function getEffectivePrice(product: ApiProduct): number {
  const regular = Number(product.price) || 0;
  const discount = Number(product.discount_price) || 0;
  return discount > 0 && discount < regular ? discount : regular;
}

export function getOriginalPrice(product: ApiProduct): number | null {
  const regular = Number(product.price) || 0;
  const discount = Number(product.discount_price) || 0;
  return discount > 0 && discount < regular ? regular : null;
}

export function getDiscountPercent(product: ApiProduct): number {
  const regular = Number(product.price) || 0;
  const discount = Number(product.discount_price) || 0;
  if (discount > 0 && discount < regular) {
    return Math.round(((regular - discount) / regular) * 100);
  }
  return 0;
}

// ==========================================
// Isolated Demo / Test Fixtures Only
// (Never returned by production catalog fetchers)
// ==========================================
export function isDemoModeEnabled(): boolean {
  if (process.env.NODE_ENV === "production") {
    return false;
  }
  return process.env.NEXT_PUBLIC_ENABLE_DEMO_MODE === "true";
}

export const SHOWCASE_CATEGORIES: ApiCategory[] = [
  {
    id: 1,
    name: "Shoes",
    description: "Running sneakers, casual trainers, and luxury footwear.",
    image: "assets/images/products/shoe.png",
    is_active: true,
  },
  {
    id: 2,
    name: "Electronics",
    description: "Smart gadgets, headphones, wearables, and audio gear.",
    image: "assets/images/products/headphone.png",
    is_active: true,
  },
  {
    id: 3,
    name: "Fashion",
    description: "Trendy apparel, streetwear, jackets, and everyday wear.",
    image: "assets/images/products/hoodie.png",
    is_active: true,
  },
  {
    id: 4,
    name: "Accessories",
    description: "Bags, wallets, watches, and smart accessories.",
    image: "assets/images/products/watch.png",
    is_active: true,
  },
  {
    id: 5,
    name: "Beauty",
    description: "Skincare, perfumes, organic oils, and cosmetics.",
    image: "assets/images/products/skincare.png",
    is_active: true,
  },
];

export const SHOWCASE_SELLERS: ApiSeller[] = [
  {
    id: 1,
    name: "TechGadgets Official Store",
    owner_name: "Alex Rivera",
    email: "seller@ecommerce.com",
    phone: "+855 12 999 001",
    address: "Building 4, Monivong Blvd, Phnom Penh",
    description:
      "Authorized retailer for premier tech accessories, studio audio, and smart electronics.",
    status: "Active",
    rating: 4.9,
    products_count: 6,
    orders_count: 428,
    total_revenue: 64200,
    created_at: "2026-01-15T08:00:00Z",
    updated_at: "2026-10-01T08:00:00Z",
  },
  {
    id: 2,
    name: "Urban Chic Boutique",
    owner_name: "Sarah Chen",
    email: "seller2@ecommerce.com",
    phone: "+855 12 999 002",
    address: "Norodom Blvd, BKK1, Phnom Penh",
    description:
      "Modern street fashion, heavyweight essentials, and curated lifestyle pieces.",
    status: "Active",
    rating: 4.85,
    products_count: 5,
    orders_count: 312,
    total_revenue: 29850,
    created_at: "2026-02-10T08:00:00Z",
    updated_at: "2026-10-01T08:00:00Z",
  },
  {
    id: 3,
    name: "Blue Panda Athletics Lab",
    owner_name: "Marcus Vance",
    email: "athletics@ecommerce.com",
    phone: "+855 12 888 108",
    address: "AEON Mall Sen Sok, Phnom Penh",
    description:
      "100% authenticity-verified performance footwear, limited-edition drops, and clean skincare.",
    status: "Active",
    rating: 4.95,
    products_count: 5,
    orders_count: 519,
    total_revenue: 78400,
    created_at: "2026-03-01T08:00:00Z",
    updated_at: "2026-10-01T08:00:00Z",
  },
];

export const SHOWCASE_PRODUCTS: ApiProduct[] = [
  {
    id: 1,
    category_id: 1,
    seller_id: 3,
    name: "Nike Air Max 270",
    description:
      "The Nike Air Max 270 delivers unmatched all-day comfort with a large Air unit in the heel and a sleek, running-inspired design.",
    price: 159.99,
    discount_price: 139.99,
    stock: 25,
    rating: 4.80,
    image_url: "assets/images/products/nike_airmax.png",
    is_active: true,
    category: SHOWCASE_CATEGORIES[0],
    seller: SHOWCASE_SELLERS[2],
  },
  {
    id: 2,
    category_id: 1,
    seller_id: 3,
    name: "Adidas Ultraboost Light",
    description:
      "Experience epic energy return with our lightest Ultraboost ever made, engineered with lightweight BOOST material.",
    price: 189.99,
    discount_price: 169.99,
    stock: 18,
    rating: 4.70,
    image_url: "assets/images/products/adidas_ultraboost.png",
    is_active: true,
    category: SHOWCASE_CATEGORIES[0],
    seller: SHOWCASE_SELLERS[2],
  },
  {
    id: 3,
    category_id: 1,
    seller_id: 3,
    name: "Puma RS-X Efekt",
    description:
      "Progressive aesthetic meets chunky comfort with premium suede overlays and bold color blocking.",
    price: 119.99,
    discount_price: null,
    stock: 30,
    rating: 4.50,
    image_url: "assets/images/products/puma_rsx.png",
    is_active: true,
    category: SHOWCASE_CATEGORIES[0],
    seller: SHOWCASE_SELLERS[2],
  },
  {
    id: 4,
    category_id: 1,
    seller_id: 3,
    name: "New Balance 574 Legacy",
    description:
      "The most iconic New Balance silhouette crafted with ENCAP midsole cushioning for durable comfort.",
    price: 99.99,
    discount_price: 84.99,
    stock: 40,
    rating: 4.60,
    image_url: "assets/images/products/new_balance.png",
    is_active: true,
    category: SHOWCASE_CATEGORIES[0],
    seller: SHOWCASE_SELLERS[2],
  },
  {
    id: 5,
    category_id: 2,
    seller_id: 1,
    name: "Sony WH-1000XM5 Wireless Headphones",
    description:
      "Industry-leading noise cancellation with two processors, 8 microphones, and ultra-comfortable lightweight design.",
    price: 399.99,
    discount_price: 349.99,
    stock: 15,
    rating: 4.90,
    image_url: "assets/images/products/sony_headphones.png",
    is_active: true,
    category: SHOWCASE_CATEGORIES[1],
    seller: SHOWCASE_SELLERS[0],
  },
  {
    id: 6,
    category_id: 2,
    seller_id: 1,
    name: "Apple Watch Series 9 GPS",
    description:
      "Powerful sensors for health, safety and fitness insights with the brilliant Always-On Retina display.",
    price: 399.00,
    discount_price: null,
    stock: 12,
    rating: 4.85,
    image_url: "assets/images/products/apple_watch.png",
    is_active: true,
    category: SHOWCASE_CATEGORIES[1],
    seller: SHOWCASE_SELLERS[0],
  },
  {
    id: 7,
    category_id: 2,
    seller_id: 1,
    name: "Samsung Galaxy Buds2 Pro",
    description:
      "24-bit Hi-Fi sound quality with intelligent Active Noise Cancellation and studio-grade voice clarity.",
    price: 229.99,
    discount_price: 179.99,
    stock: 20,
    rating: 4.65,
    image_url: "assets/images/products/galaxy_buds.png",
    is_active: true,
    category: SHOWCASE_CATEGORIES[1],
    seller: SHOWCASE_SELLERS[0],
  },
  {
    id: 8,
    category_id: 3,
    seller_id: 2,
    name: "Classic Vintage Denim Jacket",
    description:
      "Timeless relaxed-fit trucker denim jacket crafted from 100% durable heavyweight washed cotton.",
    price: 79.99,
    discount_price: 59.99,
    stock: 35,
    rating: 4.55,
    image_url: "assets/images/products/denim_jacket.png",
    is_active: true,
    category: SHOWCASE_CATEGORIES[2],
    seller: SHOWCASE_SELLERS[1],
  },
  {
    id: 9,
    category_id: 3,
    seller_id: 2,
    name: "Heavyweight Fleece Hoodie",
    description:
      "Ultra-soft brushed fleece interior with a double-layered hood and front kangaroo pocket.",
    price: 54.99,
    discount_price: null,
    stock: 50,
    rating: 4.75,
    image_url: "assets/images/products/fleece_hoodie.png",
    is_active: true,
    category: SHOWCASE_CATEGORIES[2],
    seller: SHOWCASE_SELLERS[1],
  },
  {
    id: 10,
    category_id: 3,
    seller_id: 2,
    name: "Modern Slim-Fit Chinos",
    description:
      "Comfort stretch chino trousers featuring a clean tapered silhouette for everyday office and casual wear.",
    price: 49.99,
    discount_price: 39.99,
    stock: 28,
    rating: 4.40,
    image_url: "assets/images/products/chinos.png",
    is_active: true,
    category: SHOWCASE_CATEGORIES[2],
    seller: SHOWCASE_SELLERS[1],
  },
  {
    id: 11,
    category_id: 4,
    seller_id: 2,
    name: "Minimalist Full-Grain Leather Wallet",
    description:
      "Slim bifold wallet with RFID blocking technology, 8 card slots, and genuine top-grain leather finish.",
    price: 45.00,
    discount_price: 35.00,
    stock: 60,
    rating: 4.80,
    image_url: "assets/images/products/leather_wallet.png",
    is_active: true,
    category: SHOWCASE_CATEGORIES[3],
    seller: SHOWCASE_SELLERS[1],
  },
  {
    id: 12,
    category_id: 5,
    seller_id: 3,
    name: "Organic Botanical Face Oil",
    description:
      "Cold-pressed nourishing facial oil infused with rosehip, jojoba, and vitamin E for glowing hydration.",
    price: 38.00,
    discount_price: null,
    stock: 45,
    rating: 4.90,
    image_url: "assets/images/products/face_oil.png",
    is_active: true,
    category: SHOWCASE_CATEGORIES[4],
    seller: SHOWCASE_SELLERS[2],
  },
];

export const SHOWCASE_COUPONS: ApiCoupon[] = [
  {
    id: 1,
    code: "WELCOME10",
    description: "10% off your entire order — no minimum spend",
    discount_type: "percent",
    discount_value: 10,
    min_order_amount: 0,
    max_discount_amount: 100,
    is_active: true,
  },
  {
    id: 2,
    code: "SAVE20",
    description: "$20 instant discount on orders over $50",
    discount_type: "fixed",
    discount_value: 20,
    min_order_amount: 50,
    max_discount_amount: null,
    is_active: true,
  },
  {
    id: 3,
    code: "SUMMER15",
    description: "15% off seasonal drop on orders $30+",
    discount_type: "percent",
    discount_value: 15,
    min_order_amount: 30,
    max_discount_amount: 75,
    is_active: true,
  },
  {
    id: 4,
    code: "SUPER50",
    description: "$50 VIP savings on orders over $150",
    discount_type: "fixed",
    discount_value: 50,
    min_order_amount: 150,
    max_discount_amount: null,
    is_active: true,
  },
];

export const SHOWCASE_REVIEWS: ApiReview[] = [
  {
    id: 101,
    product_id: 1,
    user_id: 2,
    rating: 5,
    comment:
      "Unbelievable comfort right out of the box! Shipped to Phnom Penh in less than 24 hours and 100% authentic packaging.",
    status: "Approved",
    admin_reply:
      "Thank you for shopping with Blue Panda! Enjoy every step in your Air Max 270s!",
    created_at: "2026-10-18T10:20:00Z",
    updated_at: "2026-10-18T12:00:00Z",
    user: {
      id: 2,
      name: "Sophea Lim",
      email: "sophea@example.com",
      role: "customer",
      is_active: true,
      created_at: "2026-06-01T00:00:00Z",
    },
  },
  {
    id: 102,
    product_id: 5,
    user_id: 3,
    rating: 5,
    comment:
      "Noise cancellation completely silences coffee shop chatter and flights. Battery easily lasts my whole work week.",
    status: "Approved",
    created_at: "2026-10-21T14:40:00Z",
    updated_at: "2026-10-21T14:40:00Z",
    user: {
      id: 3,
      name: "David Vann",
      email: "david@example.com",
      role: "customer",
      is_active: true,
      created_at: "2026-07-12T00:00:00Z",
    },
  },
  {
    id: 103,
    product_id: 1,
    user_id: 4,
    rating: 4,
    comment:
      "True to size, super bouncy heel cushion, and the colorway pops even better in person.",
    status: "Approved",
    created_at: "2026-10-24T09:15:00Z",
    updated_at: "2026-10-24T09:15:00Z",
    user: {
      id: 4,
      name: "Nary Chan",
      email: "nary@example.com",
      role: "customer",
      is_active: true,
      created_at: "2026-08-03T00:00:00Z",
    },
  },
];

// ==========================================
// Verified Live API Fetchers (Strict Data Integrity)
// ==========================================
export type CatalogArrayResult<T> = T[] & {
  readonly isLiveBackend: boolean;
  readonly error?: string;
};

function createCatalogArrayResult<T>(
  items: T[],
  isLiveBackend: boolean,
  error?: string
): CatalogArrayResult<T> {
  const clone = [...items] as CatalogArrayResult<T>;
  Object.defineProperty(clone, "isLiveBackend", {
    value: isLiveBackend,
    enumerable: false,
    writable: false,
  });
  if (error) {
    Object.defineProperty(clone, "error", {
      value: error,
      enumerable: false,
      writable: false,
    });
  }
  return clone;
}

export async function fetchStoreProducts(deps?: {
  listProducts?: typeof productsApi.list;
}): Promise<{
  products: ApiProduct[];
  isLiveBackend: boolean;
  error?: string;
}> {
  const listFn = deps?.listProducts ?? productsApi.list;
  try {
    const res = await listFn({ limit: 100 });
    if (res.success === false) {
      return {
        products: [],
        isLiveBackend: false,
        error: res.message || "We couldn't load the catalog. Please try again.",
      };
    }
    const items = (res.data?.items || []).filter((p) => p.is_active !== false);
    return { products: items, isLiveBackend: true };
  } catch {
    // When live backend is offline or unreachable, return empty list rather than silent fake catalog
    return {
      products: [],
      isLiveBackend: false,
      error: "We couldn't load the catalog. Please try again.",
    };
  }
}

export async function fetchStoreProductById(
  id: number,
  deps?: { getProduct?: typeof productsApi.get }
): Promise<{
  product: ApiProduct | null;
  isLiveBackend: boolean;
  notFound: boolean;
  error?: string;
}> {
  if (!Number.isInteger(id) || id <= 0) {
    return { product: null, isLiveBackend: true, notFound: true };
  }
  const getFn = deps?.getProduct ?? productsApi.get;
  try {
    const res = await getFn(id);
    if (res.success === false) {
      return {
        product: null,
        isLiveBackend: false,
        notFound: false,
        error: res.message || "We couldn't load this product. Please try again.",
      };
    }
    if (res.data && res.data.is_active !== false) {
      return { product: res.data, isLiveBackend: true, notFound: false };
    }
    return { product: null, isLiveBackend: true, notFound: true };
  } catch (err: unknown) {
    const status = (err as { status?: number })?.status;
    const msg = err instanceof Error ? err.message : "";
    if (status === 404 || /product not found|404/i.test(msg)) {
      return { product: null, isLiveBackend: true, notFound: true };
    }
    // Do not fabricate product data on API failure
    return {
      product: null,
      isLiveBackend: false,
      notFound: false,
      error: "We couldn't load this product. Please try again.",
    };
  }
}

export async function fetchStoreCategories(deps?: {
  listCategories?: typeof categoriesApi.list;
}): Promise<CatalogArrayResult<ApiCategory>> {
  const listFn = deps?.listCategories ?? categoriesApi.list;
  try {
    const res = await listFn(true);
    if (res.success === false) {
      return createCatalogArrayResult(
        [],
        false,
        res.message || "We couldn't load categories. Please try again."
      );
    }
    const items = (res.data || []).filter((c) => c.is_active !== false);
    return createCatalogArrayResult(items, true);
  } catch {
    // Fail gracefully without fabricating categories, while preserving error distinction
    return createCatalogArrayResult(
      [],
      false,
      "We couldn't load categories. Please try again."
    );
  }
}

export async function fetchStoreSellers(deps?: {
  listSellers?: typeof sellersApi.list;
}): Promise<CatalogArrayResult<ApiSeller>> {
  const listFn = deps?.listSellers ?? sellersApi.list;
  try {
    const res = await listFn({ status: "Active" });
    if (res.success === false) {
      return createCatalogArrayResult(
        [],
        false,
        res.message || "We couldn't load partner stores. Please try again."
      );
    }
    const items = (res.data || []).filter(
      (s) => !s.status || s.status.toLowerCase() === "active"
    );
    return createCatalogArrayResult(items, true);
  } catch {
    // Fail gracefully without fabricating sellers, while preserving error distinction
    return createCatalogArrayResult(
      [],
      false,
      "We couldn't load partner stores. Please try again."
    );
  }
}

export async function fetchStoreCoupons(deps?: {
  listCoupons?: typeof couponsApi.available;
}): Promise<CatalogArrayResult<ApiCoupon>> {
  const listFn = deps?.listCoupons ?? couponsApi.available;
  try {
    const res = await listFn();
    if (res.success === false) {
      return createCatalogArrayResult(
        [],
        false,
        res.message || "We couldn't load promotional coupons. Please try again."
      );
    }
    const items = (res.data || []).filter((c) => c.is_active !== false);
    return createCatalogArrayResult(items, true);
  } catch {
    // Fail gracefully without fabricating coupons, while preserving error distinction
    return createCatalogArrayResult(
      [],
      false,
      "We couldn't load promotional coupons. Please try again."
    );
  }
}

export async function fetchStoreReviews(
  productId: number,
  deps?: { listReviews?: typeof reviewsApi.list }
): Promise<CatalogArrayResult<ApiReview>> {
  if (!Number.isInteger(productId) || productId <= 0) {
    return createCatalogArrayResult([], true);
  }
  const listFn = deps?.listReviews ?? reviewsApi.list;
  try {
    const res = await listFn({ product_id: productId, status: "approved" });
    if (res.success === false) {
      return createCatalogArrayResult(
        [],
        false,
        res.message || "We couldn't load customer reviews. Please try again."
      );
    }
    const items = (res.data || []).filter(
      (r) => !r.status || r.status.toLowerCase() === "approved"
    );
    return createCatalogArrayResult(items, true);
  } catch {
    // Return empty list on failure while preserving error distinction
    return createCatalogArrayResult(
      [],
      false,
      "We couldn't load customer reviews. Please try again."
    );
  }
}

/**
 * Isolated demo/test coupon evaluator.
 * Requires explicit `options.allowDemoMode === true` or
 * `NEXT_PUBLIC_ENABLE_DEMO_COUPONS === "true"` in non-production environments.
 * Never used as an automatic fallback when backend coupon validation fails.
 */
export function validateCouponLocally(
  code: string,
  subtotal: number,
  coupons: ApiCoupon[] = SHOWCASE_COUPONS,
  options?: { allowDemoMode?: boolean }
): {
  valid: boolean;
  code: string;
  discountAmount: number;
  message: string;
} {
  const demoAllowed =
    options?.allowDemoMode === true ||
    (process.env.NODE_ENV !== "production" &&
      (process.env.NEXT_PUBLIC_ENABLE_DEMO_COUPONS === "true" ||
        isDemoModeEnabled()));
  if (!demoAllowed) {
    throw new Error(
      "Unable to verify promo code right now. Please check your connection and try again."
    );
  }
  const clean = code.trim().toUpperCase();
  const found = coupons.find((c) => c.code.toUpperCase() === clean && c.is_active);
  if (!found) {
    throw new Error(`Promo code '${clean}' is invalid or expired.`);
  }
  if (subtotal < Number(found.min_order_amount || 0)) {
    throw new Error(
      `Promo code '${clean}' requires a minimum subtotal of $${Number(
        found.min_order_amount
      ).toFixed(2)}.`
    );
  }
  let discount = 0;
  if (found.discount_type === "percent") {
    discount = (subtotal * Number(found.discount_value)) / 100;
    if (found.max_discount_amount && discount > Number(found.max_discount_amount)) {
      discount = Number(found.max_discount_amount);
    }
  } else {
    discount = Number(found.discount_value);
  }
  discount = Math.min(subtotal, Math.round(discount * 100) / 100);
  return {
    valid: true,
    code: found.code,
    discountAmount: discount,
    message: `Promo '${found.code}' applied! You saved $${discount.toFixed(2)}.`,
  };
}
