import test from "node:test";
import assert from "node:assert/strict";
import {
  applyProductImageFallback,
  fetchStoreCategories,
  fetchStoreCoupons,
  fetchStoreProductById,
  fetchStoreProducts,
  fetchStoreReviews,
  fetchStoreSellers,
  isDemoModeEnabled,
  NEUTRAL_PRODUCT_PLACEHOLDER,
  resolveProductImage,
} from "../store-catalog";
import { generateStorefrontSitemap } from "../../app/sitemap";
import { useShopStore } from "../store";
import {
  createCheckoutSubmissionLock,
  executeCheckoutOrder,
} from "../checkout-security";
import type {
  ApiCategory,
  ApiCoupon,
  ApiProduct,
  ApiReview,
  ApiSeller,
} from "../api";

// Ensure minimal browser storage globals exist for Zustand store in Node tests
class MemoryStorage {
  private map = new Map<string, string>();
  getItem(key: string) {
    return this.map.get(key) ?? null;
  }
  setItem(key: string, val: string) {
    this.map.set(key, String(val));
  }
  removeItem(key: string) {
    this.map.delete(key);
  }
  clear() {
    this.map.clear();
  }
}

(globalThis as any).localStorage = new MemoryStorage();
if (typeof globalThis.window === "undefined") {
  (globalThis as any).window = {
    setTimeout: globalThis.setTimeout.bind(globalThis),
    clearTimeout: globalThis.clearTimeout.bind(globalThis),
    dispatchEvent: () => true,
    addEventListener: () => {},
    removeEventListener: () => {},
  };
}

const REAL_PRODUCT: ApiProduct = {
  id: 501,
  name: "Real Studio Reference Headphones",
  description: "Authoritative product record from PostgreSQL",
  price: 249.99,
  discount_price: 199.99,
  rating: 4.9,
  stock: 14,
  image_url: "/uploads/products/real-headphones.webp",
  category_id: 10,
  seller_id: 3,
  is_active: true,
  created_at: "2026-03-01T10:00:00Z",
  category: {
    id: 10,
    name: "Audio & Headphones",
    description: "Studio audio",
    is_active: true,
  },
  seller: {
    id: 3,
    name: "Blue Panda Audio Lab",
    rating: 4.9,
    status: "Active",
  },
};

test("Storefront Real Backend Integration & Fake Data Removal Suite", async (t) => {
  await t.test("1. Real products display when API succeeds", async () => {
    const inactiveProduct: ApiProduct = {
      ...REAL_PRODUCT,
      id: 502,
      name: "Archived Inactive Product",
      is_active: false,
    };

    const res = await fetchStoreProducts({
      listProducts: async () => ({
        success: true,
        message: "OK",
        data: {
          items: [REAL_PRODUCT, inactiveProduct],
          total: 2,
          page: 1,
          limit: 50,
          total_pages: 1,
        },
      }),
    });

    assert.equal(res.isLiveBackend, true);
    assert.equal(res.products.length, 1);
    assert.equal(res.products[0].id, 501);
    assert.equal(res.products[0].name, "Real Studio Reference Headphones");
  });

  await t.test("2. Empty API response produces empty state without fictional fallback", async () => {
    const res = await fetchStoreProducts({
      listProducts: async () => ({
        success: true,
        message: "OK",
        data: { items: [], total: 0, page: 1, limit: 50, total_pages: 0 },
      }),
    });

    assert.equal(res.isLiveBackend, true);
    assert.deepEqual(res.products, []);
    assert.equal(res.error, undefined);
  });

  await t.test("3. Failed requests produce error state without fictional fallback", async () => {
    const res = await fetchStoreProducts({
      listProducts: async () => {
        throw new Error("Network connection refused");
      },
    });

    assert.equal(res.isLiveBackend, false);
    assert.deepEqual(res.products, []);
    assert.equal(res.error, "We couldn't load the catalog. Please try again.");
  });

  await t.test("4. Retry performs another request and recovers when backend responds", async () => {
    let attempts = 0;
    const mockListProducts = async () => {
      attempts += 1;
      if (attempts === 1) {
        throw new Error("Temporary 503 Service Unavailable");
      }
      return {
        success: true,
        message: "OK",
        data: {
          items: [REAL_PRODUCT],
          total: 1,
          page: 1,
          limit: 50,
          total_pages: 1,
        },
      };
    };

    const firstAttempt = await fetchStoreProducts({ listProducts: mockListProducts });
    assert.equal(firstAttempt.isLiveBackend, false);
    assert.equal(firstAttempt.products.length, 0);

    const retryAttempt = await fetchStoreProducts({ listProducts: mockListProducts });
    assert.equal(attempts, 2);
    assert.equal(retryAttempt.isLiveBackend, true);
    assert.equal(retryAttempt.products.length, 1);
    assert.equal(retryAttempt.products[0].id, 501);
  });

  await t.test("5. Unknown product IDs show not-found and never substitute showcase products", async () => {
    // Showcase product ID 1 exists in SHOWCASE_PRODUCTS; verify 404 for ID 1 returns null, not fake ID 1
    const notFoundErr = Object.assign(new Error("Product not found"), { status: 404 });
    const res404 = await fetchStoreProductById(1, {
      getProduct: async () => {
        throw notFoundErr;
      },
    });

    assert.equal(res404.product, null);
    assert.equal(res404.isLiveBackend, true);
    assert.equal(res404.notFound, true);

    // Invalid / non-positive ID
    const resInvalid = await fetchStoreProductById(0);
    assert.equal(resInvalid.product, null);
    assert.equal(resInvalid.notFound, true);

    // Network error vs 404 distinction
    const resNetworkErr = await fetchStoreProductById(1, {
      getProduct: async () => {
        throw new Error("Socket hang up");
      },
    });
    assert.equal(resNetworkErr.product, null);
    assert.equal(resNetworkErr.isLiveBackend, false);
    assert.equal(resNetworkErr.notFound, false);
  });

  await t.test("6. Empty categories remain empty and failed categories report failure without fake data", async () => {
    const emptyCategories = await fetchStoreCategories({
      listCategories: async () => ({
        success: true,
        message: "OK",
        data: [],
      }),
    });
    assert.equal(emptyCategories.length, 0);
    assert.equal(emptyCategories.isLiveBackend, true);

    const failedCategories = await fetchStoreCategories({
      listCategories: async () => {
        throw new Error("Categories endpoint failed");
      },
    });
    assert.equal(failedCategories.length, 0);
    assert.equal(failedCategories.isLiveBackend, false);
    assert.equal(
      failedCategories.error,
      "We couldn't load categories. Please try again."
    );

    const realCategory: ApiCategory = {
      id: 10,
      name: "Audio & Headphones",
      description: "Studio gear",
      is_active: true,
    };
    const activeCategories = await fetchStoreCategories({
      listCategories: async () => ({
        success: true,
        message: "OK",
        data: [realCategory],
      }),
    });
    assert.equal(activeCategories.length, 1);
    assert.equal(activeCategories.isLiveBackend, true);
    assert.equal(activeCategories[0].name, "Audio & Headphones");
  });

  await t.test("7. Empty reviews remain empty and unapproved reviews are filtered out", async () => {
    const emptyReviews = await fetchStoreReviews(1, {
      listReviews: async () => ({
        success: true,
        message: "OK",
        data: [],
      }),
    });
    assert.equal(emptyReviews.length, 0);
    assert.equal(emptyReviews.isLiveBackend, true);

    const approvedReview: ApiReview = {
      id: 91,
      user_id: 12,
      product_id: 501,
      rating: 5,
      comment: "Crisp studio soundstage.",
      status: "approved",
      created_at: "2026-03-10T10:00:00Z",
      updated_at: "2026-03-10T10:00:00Z",
      user: { id: 12, name: "Real Buyer", email: "buyer@example.com" },
    };
    const pendingReview: ApiReview = {
      ...approvedReview,
      id: 92,
      status: "pending",
      comment: "Unmoderated review",
    };

    const filteredReviews = await fetchStoreReviews(501, {
      listReviews: async () => ({
        success: true,
        message: "OK",
        data: [approvedReview, pendingReview],
      }),
    });
    assert.equal(filteredReviews.length, 1);
    assert.equal(filteredReviews[0].id, 91);
    assert.equal(filteredReviews.isLiveBackend, true);

    const failedReviews = await fetchStoreReviews(501, {
      listReviews: async () => {
        throw new Error("Reviews DB timeout");
      },
    });
    assert.equal(failedReviews.length, 0);
    assert.equal(failedReviews.isLiveBackend, false);
  });

  await t.test("8. Failed seller requests do not show fake sellers", async () => {
    const failedSellers = await fetchStoreSellers({
      listSellers: async () => {
        throw new Error("Sellers service unreachable");
      },
    });
    assert.equal(failedSellers.length, 0);
    assert.equal(failedSellers.isLiveBackend, false);

    const realSeller: ApiSeller = {
      id: 7,
      name: "Official Tech Merchant",
      rating: 4.8,
      status: "Active",
      products_count: 0,
      created_at: "2026-02-01T00:00:00Z",
      updated_at: "2026-02-01T00:00:00Z",
    };
    const inactiveSeller: ApiSeller = {
      ...realSeller,
      id: 8,
      status: "Suspended",
    };

    const liveSellers = await fetchStoreSellers({
      listSellers: async () => ({
        success: true,
        message: "OK",
        data: [realSeller, inactiveSeller],
      }),
    });
    assert.equal(liveSellers.length, 1);
    assert.equal(liveSellers[0].id, 7);
    assert.equal(liveSellers[0].products_count, 0);
    assert.equal(liveSellers.isLiveBackend, true);
  });

  await t.test("9. Failed coupon requests do not show fake promotions", async () => {
    const failedCoupons = await fetchStoreCoupons({
      listCoupons: async () => {
        throw new Error("Coupons endpoint 500");
      },
    });
    assert.equal(failedCoupons.length, 0);
    assert.equal(failedCoupons.isLiveBackend, false);

    const activeCoupon: ApiCoupon = {
      id: 1,
      code: "REAL15",
      discount_type: "percent",
      discount_value: 15,
      min_order_amount: 100,
      is_active: true,
    };
    const inactiveCoupon: ApiCoupon = {
      ...activeCoupon,
      id: 2,
      code: "EXPIRED50",
      is_active: false,
    };

    const liveCoupons = await fetchStoreCoupons({
      listCoupons: async () => ({
        success: true,
        message: "OK",
        data: [activeCoupon, inactiveCoupon],
      }),
    });
    assert.equal(liveCoupons.length, 1);
    assert.equal(liveCoupons[0].code, "REAL15");
    assert.equal(liveCoupons.isLiveBackend, true);
  });

  await t.test("10. Missing or broken product images use placeholder and never keyword-guessed Unsplash photos", () => {
    // Even if product name contains keywords like "Laptop", "Nike", "Headphone", "Watch",
    // missing images must use NEUTRAL_PRODUCT_PLACEHOLDER instead of unrelated stock photos
    const missingImageLaptop = {
      name: "Pro Gaming Laptop RTX",
      image_url: null,
    };
    assert.equal(resolveProductImage(missingImageLaptop), NEUTRAL_PRODUCT_PLACEHOLDER);

    const brokenPathWatch = {
      name: "Apple Watch Ultra",
      image_url: "invalid-relative-path-without-slash.jpg",
    };
    assert.equal(resolveProductImage(brokenPathWatch), NEUTRAL_PRODUCT_PLACEHOLDER);

    // Valid backend upload path resolves to backend origin + /uploads/...
    const uploadedImageProduct = {
      name: "Custom Hardware",
      image_url: "/uploads/custom-gear.png",
    };
    const resolvedUpload = resolveProductImage(uploadedImageProduct);
    assert.ok(resolvedUpload.endsWith("/uploads/custom-gear.png"));

    // Runtime onError handler replaces broken src with NEUTRAL_PRODUCT_PLACEHOLDER
    const fakeImgElement = { src: "https://broken.example.com/404.png" };
    applyProductImageFallback({ currentTarget: fakeImgElement as any });
    assert.equal(fakeImgElement.src, NEUTRAL_PRODUCT_PLACEHOLDER);
  });

  await t.test("11. Cart and checkout reject invalid, inactive, or out-of-stock products", async () => {
    const store = useShopStore.getState();
    await store.clearCart();

    // Out-of-stock product rejected
    await useShopStore.getState().addToCart(
      { ...REAL_PRODUCT, id: 601, stock: 0 },
      1,
      undefined,
      false
    );
    assert.equal(useShopStore.getState().items.length, 0);

    // Inactive product rejected
    await useShopStore.getState().addToCart(
      { ...REAL_PRODUCT, id: 602, is_active: false },
      1,
      undefined,
      false
    );
    assert.equal(useShopStore.getState().items.length, 0);

    // Invalid ID rejected
    await useShopStore.getState().addToCart(
      { ...REAL_PRODUCT, id: 0 },
      1,
      undefined,
      false
    );
    assert.equal(useShopStore.getState().items.length, 0);

    // Valid in-stock product accepted and clamped to real stock
    await useShopStore.getState().addToCart(
      { ...REAL_PRODUCT, id: 501, stock: 3 },
      2,
      "Standard",
      false
    );
    assert.equal(useShopStore.getState().items.length, 1);
    assert.equal(useShopStore.getState().items[0].quantity, 2);

    // Updating quantity above stock clamps strictly to product.stock (3), never 99
    const itemKey = useShopStore.getState().items[0].key;
    await useShopStore.getState().updateQuantity(itemKey, 25);
    assert.equal(useShopStore.getState().items[0].quantity, 3);

    await useShopStore.getState().clearCart();

    // Checkout rejects invalid product IDs
    await assert.rejects(
      async () => {
        await executeCheckoutOrder({
          lock: createCheckoutSubmissionLock(),
          isAuthenticated: true,
          items: [{ productId: 0, quantity: 1 }],
          shippingAddress: "123 Street, Phnom Penh",
          paymentMethod: "COD",
          deps: {
            clearServerCart: async () => {},
            addServerCartItem: async () => ({
              success: true,
              message: "OK",
              data: {} as any,
            }),
            createOrder: async () => ({
              success: true,
              message: "OK",
              data: {} as any,
            }),
            clearClientCart: async () => {},
          },
        });
      },
      /invalid or unavailable product/i
    );
  });

  await t.test("12. Sitemap does not contain fictional products and includes only real backend products", async () => {
    const failedSitemap = await generateStorefrontSitemap({
      fetchProducts: async () => ({
        products: [],
        isLiveBackend: false,
        error: "Backend unreachable",
      }),
    });
    assert.equal(
      failedSitemap.some((entry) => entry.url.includes("/product/")),
      false,
      "Failed backend sitemap must not include any /product/ URLs"
    );

    const emptySitemap = await generateStorefrontSitemap({
      fetchProducts: async () => ({
        products: [],
        isLiveBackend: true,
      }),
    });
    assert.equal(
      emptySitemap.some((entry) => entry.url.includes("/product/")),
      false,
      "Empty catalog sitemap must not include any /product/ URLs"
    );

    const liveSitemap = await generateStorefrontSitemap({
      fetchProducts: async () => ({
        products: [REAL_PRODUCT],
        isLiveBackend: true,
      }),
    });
    assert.equal(
      liveSitemap.some((entry) => entry.url.endsWith("/product/501")),
      true,
      "Live catalog sitemap must include real product URL /product/501"
    );
  });

  await t.test("13. Production does not activate demo fallbacks", () => {
    const prevNodeEnv = process.env.NODE_ENV;
    const prevDemoFlag = process.env.NEXT_PUBLIC_ENABLE_DEMO_MODE;
    try {
      (process.env as any).NODE_ENV = "production";
      process.env.NEXT_PUBLIC_ENABLE_DEMO_MODE = "true";
      assert.equal(
        isDemoModeEnabled(),
        false,
        "Demo mode must never activate when NODE_ENV is production"
      );

      (process.env as any).NODE_ENV = "development";
      delete process.env.NEXT_PUBLIC_ENABLE_DEMO_MODE;
      assert.equal(
        isDemoModeEnabled(),
        false,
        "Demo mode must default to false when NEXT_PUBLIC_ENABLE_DEMO_MODE is unset"
      );
    } finally {
      (process.env as any).NODE_ENV = prevNodeEnv;
      if (prevDemoFlag === undefined) {
        delete process.env.NEXT_PUBLIC_ENABLE_DEMO_MODE;
      } else {
        process.env.NEXT_PUBLIC_ENABLE_DEMO_MODE = prevDemoFlag;
      }
    }
  });
});
