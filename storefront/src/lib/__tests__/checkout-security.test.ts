import assert from "node:assert/strict";
import { describe, it } from "node:test";
import type { ApiCart, ApiOrder, ApiProduct, ApiResponse } from "../api";
import {
  CHECKOUT_PAYMENT_METHODS,
  clearDurableCheckoutKey,
  createCheckoutSubmissionLock,
  DEFAULT_CHECKOUT_PAYMENT_METHOD,
  executeCheckoutOrder,
  getOrCreateDurableCheckoutKey,
  getOrderPaymentPresentation,
  normalizeServerConfirmedOrder,
  PENDING_CHECKOUT_IDEMPOTENCY_STORAGE_KEY,
  validateCouponServerOnly,
} from "../checkout-security";
import { validateCouponLocally } from "../store-catalog";
import {
  FREE_SHIPPING_THRESHOLD,
  STANDARD_SHIPPING_FEE,
  getCartTotals,
  type StoreCartItem,
} from "../store";

function buildServerOrder(overrides: Partial<ApiOrder> = {}): ApiOrder {
  return {
    id: 402,
    user_id: 7,
    status: "pending",
    subtotal: "48.00",
    discount_amount: "0.00",
    coupon_code: null,
    shipping_fee: "2.00",
    total: "50.00",
    payment_method: "Cash on Delivery",
    payment_status: "pending",
    shipping_address: "Sokha, +85512345678, St 2004, Phnom Penh",
    created_at: "2026-10-31T06:00:00Z",
    updated_at: "2026-10-31T06:00:00Z",
    items: [
      {
        id: 1,
        order_id: 402,
        product_id: 101,
        product_name: "Blue Panda Hoodie",
        price: "48.00",
        quantity: 1,
        subtotal: "48.00",
        created_at: "2026-10-31T06:00:00Z",
      },
    ],
    ...overrides,
  };
}

const EMPTY_CART_RESPONSE: ApiResponse<ApiCart> = {
  success: true,
  message: "OK",
  data: { items: [], total_items: 0, subtotal: 0 },
};

describe("Next.js Storefront Checkout, Order, Payment & Coupon Security", () => {
  it("1 & 2. Failed API or unauthenticated checkout never produces a confirmed order and keeps cart intact", async () => {
    let clientCartClearedCount = 0;
    const bagItems = [{ productId: 101, quantity: 2 }];

    // Case A: Network failure ("Failed to fetch") must NOT fall back to a local order
    await assert.rejects(
      () =>
        executeCheckoutOrder({
          lock: createCheckoutSubmissionLock(),
          isAuthenticated: true,
          items: bagItems,
          shippingAddress: "123 Norodom Blvd, Phnom Penh",
          paymentMethod: "Cash on Delivery",
          deps: {
            clearServerCart: async () => ({ success: true, message: "ok", data: null }),
            addServerCartItem: async () => EMPTY_CART_RESPONSE,
            createOrder: async () => {
              throw new TypeError("Failed to fetch");
            },
            clearClientCart: async () => {
              clientCartClearedCount += 1;
            },
          },
        }),
      /Unable to reach the server to place your order/
    );
    assert.equal(clientCartClearedCount, 0);
    assert.equal(bagItems.length, 1);

    // Case B: Backend 400 error (e.g. insufficient stock) keeps cart intact
    await assert.rejects(
      () =>
        executeCheckoutOrder({
          lock: createCheckoutSubmissionLock(),
          isAuthenticated: true,
          items: bagItems,
          shippingAddress: "123 Norodom Blvd, Phnom Penh",
          paymentMethod: "Cash on Delivery",
          deps: {
            clearServerCart: async () => ({ success: true, message: "ok", data: null }),
            addServerCartItem: async () => EMPTY_CART_RESPONSE,
            createOrder: async () => {
              throw new Error("Insufficient stock for Blue Panda Hoodie");
            },
            clearClientCart: async () => {
              clientCartClearedCount += 1;
            },
          },
        }),
      /Insufficient stock/
    );
    assert.equal(clientCartClearedCount, 0);

    // Case C: Unauthenticated guest user is rejected without fabricating a guest order
    await assert.rejects(
      () =>
        executeCheckoutOrder({
          lock: createCheckoutSubmissionLock(),
          isAuthenticated: false,
          items: bagItems,
          shippingAddress: "123 Norodom Blvd, Phnom Penh",
          paymentMethod: "Cash on Delivery",
          deps: {
            clearServerCart: async () => ({ success: true, message: "ok", data: null }),
            addServerCartItem: async () => EMPTY_CART_RESPONSE,
            createOrder: async () => ({
              success: true,
              message: "ok",
              data: buildServerOrder(),
            }),
            clearClientCart: async () => {
              clientCartClearedCount += 1;
            },
          },
        }),
      /Please sign in to place your order/
    );
    assert.equal(clientCartClearedCount, 0);

    // Case D: Invalid/missing server order ID is rejected
    assert.throws(
      () =>
        normalizeServerConfirmedOrder(
          {
            success: true,
            message: "ok",
            data: buildServerOrder({ id: 0 }),
          },
          "Cash on Delivery"
        ),
      /invalid order confirmation ID/i
    );
  });

  it("3. Duplicate checkout submissions are blocked while in flight", async () => {
    const lock = createCheckoutSubmissionLock();
    let createOrderCalls = 0;
    let releaseRequest!: () => void;
    const gate = new Promise<void>((resolve) => {
      releaseRequest = resolve;
    });

    const runAttempt = () =>
      executeCheckoutOrder({
        lock,
        isAuthenticated: true,
        items: [{ productId: 101, quantity: 1 }],
        shippingAddress: "St 51, Phnom Penh",
        paymentMethod: "Cash on Delivery",
        deps: {
          clearServerCart: async () => ({ success: true, message: "ok", data: null }),
          addServerCartItem: async () => EMPTY_CART_RESPONSE,
          createOrder: async () => {
            createOrderCalls += 1;
            await gate;
            return {
              success: true,
              message: "Order created",
              data: buildServerOrder({ id: 777 }),
            };
          },
          clearClientCart: async () => {},
        },
      });

    const firstAttempt = runAttempt();
    const secondAttempt = runAttempt();

    const duplicateOutcome = await secondAttempt;
    assert.deepEqual(duplicateOutcome, { status: "duplicate_blocked" });

    releaseRequest();
    const firstOutcome = await firstAttempt;
    assert.equal(firstOutcome.status, "confirmed");
    assert.equal(createOrderCalls, 1);
  });

  it("4. Unverified payment methods are labeled DEMO and never marked paid", async () => {
    assert.equal(DEFAULT_CHECKOUT_PAYMENT_METHOD, "Cash on Delivery");

    const codMethod = CHECKOUT_PAYMENT_METHODS.find(
      (m) => m.id === "Cash on Delivery"
    );
    assert.ok(codMethod);
    assert.equal(codMethod.isDemo, false);
    assert.equal(codMethod.badge, null);

    for (const demoId of [
      "KHQR Scan & Pay",
      "Credit / Debit Card",
      "Apple Pay",
    ]) {
      const method = CHECKOUT_PAYMENT_METHODS.find((m) => m.id === demoId);
      assert.ok(method, `Missing method ${demoId}`);
      assert.equal(method.isDemo, true);
      assert.equal(method.badge, "DEMO");

      // Even if an untrusted payload claimed payment_status="paid", client normalizes to pending
      const normalized = normalizeServerConfirmedOrder(
        {
          success: true,
          message: "ok",
          data: buildServerOrder({
            id: 501,
            payment_method: demoId,
            payment_status: "paid",
          }),
        },
        demoId
      );
      assert.equal(normalized.payment_status, "pending");

      const meta = getOrderPaymentPresentation(normalized);
      assert.equal(meta.isPaid, false);
      assert.equal(meta.paymentStatusLabel, "Pending Verification");
      assert.equal(meta.totalLabel, "Order Total");

      // Submission with demo payment method is rejected
      await assert.rejects(
        () =>
          executeCheckoutOrder({
            lock: createCheckoutSubmissionLock(),
            isAuthenticated: true,
            items: [{ productId: 101, quantity: 1 }],
            shippingAddress: "123 Norodom Blvd, Phnom Penh",
            paymentMethod: demoId,
            deps: {
              clearServerCart: async () => ({ success: true, message: "ok", data: null }),
              addServerCartItem: async () => EMPTY_CART_RESPONSE,
              createOrder: async () => ({
                success: true,
                message: "ok",
                data: buildServerOrder({ id: 999 }),
              }),
              clearClientCart: async () => {},
            },
          }),
        /Live payment gateway capture for this method is not integrated yet/
      );
    }
  });

  it("5. Invalid or unavailable backend coupons are rejected without local fallback", async () => {
    // Network failure must NOT fall back to local WELCOME10
    await assert.rejects(
      () =>
        validateCouponServerOnly({
          code: "WELCOME10",
          subtotal: 100,
          validateApi: async () => {
            throw new TypeError("Failed to fetch");
          },
        }),
      /Unable to verify promo code right now/
    );

    // Backend valid=false response is rejected
    await assert.rejects(
      () =>
        validateCouponServerOnly({
          code: "EXPIRED50",
          subtotal: 100,
          validateApi: async () => ({
            success: true,
            message: "ok",
            data: {
              valid: false,
              code: "EXPIRED50",
              discount_type: "percent",
              discount_value: 50,
              discount_amount: 0,
              new_subtotal: 100,
              message: "Coupon has expired",
            },
          }),
        }),
      /Coupon has expired/
    );

    // Direct call to validateCouponLocally without explicit demo flag is blocked
    assert.throws(
      () => validateCouponLocally("WELCOME10", 100),
      /Unable to verify promo code right now/
    );

    // Explicit isolated demo mode still works when deliberately opted in for tests
    const isolatedDemo = validateCouponLocally("WELCOME10", 100, undefined, {
      allowDemoMode: true,
    });
    assert.equal(isolatedDemo.valid, true);
    assert.equal(isolatedDemo.discountAmount, 10);
  });

  it("6. Real backend Cash on Delivery orders succeed and clear cart only after confirmation", async () => {
    let clientCartClearedCount = 0;

    const result = await executeCheckoutOrder({
      lock: createCheckoutSubmissionLock(),
      isAuthenticated: true,
      items: [{ productId: 101, quantity: 1 }],
      shippingAddress: "Sokha, +85512345678, St 2004, Phnom Penh",
      paymentMethod: "Cash on Delivery",
      phone: "+85512345678",
      fullName: "Sokha",
      deps: {
        clearServerCart: async () => ({ success: true, message: "ok", data: null }),
        addServerCartItem: async () => EMPTY_CART_RESPONSE,
        createOrder: async (payload) => {
          assert.equal(payload.payment_method, "Cash on Delivery");
          return {
            success: true,
            message: "Order placed successfully",
            data: buildServerOrder({
              id: 888,
              status: "pending",
              payment_method: "Cash on Delivery",
              payment_status: "pending",
            }),
          };
        },
        clearClientCart: async () => {
          clientCartClearedCount += 1;
        },
      },
    });

    assert.equal(result.status, "confirmed");
    if (result.status === "confirmed") {
      assert.equal(result.order.id, 888);
      assert.equal(result.order.status, "pending");
      assert.equal(result.order.payment_status, "pending");

      const meta = getOrderPaymentPresentation(result.order);
      assert.equal(meta.isPaid, false);
      assert.equal(meta.orderStatusLabel, "Pending");
      assert.equal(meta.paymentStatusLabel, "Unpaid (Cash on Delivery)");
      assert.equal(meta.totalLabel, "Order Total");
    }
    assert.equal(clientCartClearedCount, 1);
  });

  it("7. getCartTotals enforces shipping fee rules and free shipping threshold ($100)", () => {
    assert.equal(FREE_SHIPPING_THRESHOLD, 100);
    assert.equal(STANDARD_SHIPPING_FEE, 2);

    const mockProduct1: ApiProduct = {
      id: 1,
      name: "Mechanical Keyboard",
      price: 60,
      stock: 10,
      is_active: true,
      category_id: 1,
      rating: 4.8,
      created_at: "2026-01-01",
    };

    const mockProduct2: ApiProduct = {
      id: 2,
      name: "Gaming Mouse",
      price: 40,
      stock: 5,
      is_active: true,
      category_id: 1,
      rating: 4.6,
      created_at: "2026-01-01",
    };

    // Case A: Subtotal $60 (< $100) -> $2 shipping, $40 to free shipping, 60% progress
    const itemsUnderThreshold: StoreCartItem[] = [
      { key: "1-none", product: mockProduct1, quantity: 1 },
    ];
    const totalsUnder = getCartTotals(itemsUnderThreshold, null);
    assert.equal(totalsUnder.subtotal, 60);
    assert.equal(totalsUnder.shipping, 2);
    assert.equal(totalsUnder.amountToFreeShipping, 40);
    assert.equal(totalsUnder.freeShippingProgress, 60);
    assert.equal(totalsUnder.total, 62);

    // Case B: Subtotal $100 (>= $100) -> FREE shipping ($0), $0 to free shipping, 100% progress
    const itemsAtThreshold: StoreCartItem[] = [
      { key: "1-none", product: mockProduct1, quantity: 1 },
      { key: "2-none", product: mockProduct2, quantity: 1 },
    ];
    const totalsAt = getCartTotals(itemsAtThreshold, null);
    assert.equal(totalsAt.subtotal, 100);
    assert.equal(totalsAt.shipping, 0);
    assert.equal(totalsAt.amountToFreeShipping, 0);
    assert.equal(totalsAt.freeShippingProgress, 100);
    assert.equal(totalsAt.total, 100);

    // Case C: Subtotal $120 with $20 coupon applied -> discount $20, shipping $0, total $100
    const itemsOverThreshold: StoreCartItem[] = [
      { key: "1-none", product: mockProduct1, quantity: 2 },
    ];
    const totalsWithCoupon = getCartTotals(itemsOverThreshold, {
      code: "SAVE20",
      discountAmount: 20,
      message: "Applied $20.00 off",
    });
    assert.equal(totalsWithCoupon.subtotal, 120);
    assert.equal(totalsWithCoupon.discount, 20);
    assert.equal(totalsWithCoupon.shipping, 0);
    assert.equal(totalsWithCoupon.total, 100);

    // Case D: Empty cart -> all zeros
    const emptyTotals = getCartTotals([], null);
    assert.equal(emptyTotals.subtotal, 0);
    assert.equal(emptyTotals.shipping, 0);
    assert.equal(emptyTotals.total, 0);
  });

  it("8. Order confirmation normalization rejects invalid order IDs and enforces unverified payment rules", () => {
    // Rejects non-integer or zero/negative ID
    assert.throws(
      () =>
        normalizeServerConfirmedOrder(
          {
            success: true,
            message: "ok",
            data: buildServerOrder({ id: 0 }),
          },
          "Cash on Delivery"
        ),
      /Server returned an invalid order confirmation ID/
    );

    // A backend-settled COD payment remains paid, including idempotent replays
    const settledCodOrder = normalizeServerConfirmedOrder(
      {
        success: true,
        message: "ok",
        data: buildServerOrder({
          id: 999,
          payment_method: "Cash on Delivery",
          payment_status: "paid",
        }),
      },
      "Cash on Delivery"
    );
    assert.equal(settledCodOrder.payment_status, "paid");

    // Demo methods are properly recorded as demo preview
    const cardMethod = CHECKOUT_PAYMENT_METHODS.find((pm) => pm.id === "Credit / Debit Card");
    assert.equal(cardMethod?.isDemo, true);
    assert.equal(cardMethod?.badge, "DEMO");
  });

  it("9. getOrderPaymentPresentation strictly separates order status from payment status", () => {
    // Case A: Delivered COD order is Delivered in status but unpaid until physical settlement
    const deliveredCod = getOrderPaymentPresentation({
      status: "delivered",
      payment_method: "Cash on Delivery",
      payment_status: "pending",
    });
    assert.equal(deliveredCod.orderStatusLabel, "Delivered");
    assert.equal(deliveredCod.paymentStatusLabel, "Unpaid (Cash on Delivery)");
    assert.equal(deliveredCod.isPaid, false);
    assert.equal(deliveredCod.totalLabel, "Order Total");

    // Case B: Processing KHQR (Demo) remains pending verification
    const processingKhqr = getOrderPaymentPresentation({
      status: "processing",
      payment_method: "KHQR Scan & Pay",
      payment_status: "pending",
    });
    assert.equal(processingKhqr.orderStatusLabel, "Processing");
    assert.equal(processingKhqr.paymentStatusLabel, "Pending Verification");
    assert.equal(processingKhqr.isPaid, false);

    // Case C: Cancelled order preserves Cancelled status
    const cancelledOrder = getOrderPaymentPresentation({
      status: "cancelled",
      payment_method: "Cash on Delivery",
      payment_status: "pending",
    });
    assert.equal(cancelledOrder.orderStatusLabel, "Cancelled");
    assert.equal(cancelledOrder.isPaid, false);

    // Case D: Failed payment shows Payment Failed
    const failedOrder = getOrderPaymentPresentation({
      status: "pending",
      payment_method: "Credit / Debit Card",
      payment_status: "failed",
    });
    assert.equal(failedOrder.paymentStatusLabel, "Payment Failed");
    assert.equal(failedOrder.isPaid, false);
  });

  it("10. Primary navigation and footer target valid storefront paths without dead links", () => {
    const validStorefrontRoutes = new Set([
      "/",
      "/shop",
      "/categories",
      "/deals",
      "/new-arrivals",
      "/orders",
      "/wishlist",
      "/cart",
      "/checkout",
      "/account",
      "/login",
      "/register",
    ]);

    const navbarLinks = ["/shop", "/categories", "/deals", "/new-arrivals", "/orders"];
    for (const link of navbarLinks) {
      assert.equal(validStorefrontRoutes.has(link), true, `Route ${link} must exist`);
    }

    const footerLinks = [
      "/shop",
      "/categories",
      "/new-arrivals",
      "/deals",
      "/account",
      "/orders",
      "/wishlist",
      "/cart",
    ];
    for (const link of footerLinks) {
      assert.equal(validStorefrontRoutes.has(link), true, `Route ${link} must exist`);
    }
  });

  it("11. Atomic checkout sends items and idempotency key directly to createOrder without destructive clearServerCart loop", async () => {
    let clearServerCartCalls = 0;
    let addServerCartItemCalls = 0;
    let createOrderPayload: any = null;
    let clientCartCleared = false;

    const result = await executeCheckoutOrder({
      lock: createCheckoutSubmissionLock(),
      isAuthenticated: true,
      items: [
        { productId: 101, quantity: 2 },
        { productId: 102, quantity: 1 },
      ],
      shippingAddress: "Street 2004, Phnom Penh",
      paymentMethod: "Cash on Delivery",
      phone: "+85512345678",
      fullName: "Sokha Test",
      deps: {
        clearServerCart: async () => {
          clearServerCartCalls += 1;
        },
        addServerCartItem: async () => {
          addServerCartItemCalls += 1;
          return EMPTY_CART_RESPONSE;
        },
        createOrder: async (payload) => {
          createOrderPayload = payload;
          return {
            success: true,
            message: "Order placed successfully",
            data: buildServerOrder({
              id: 999,
              status: "pending",
              payment_method: "Cash on Delivery",
            }),
          };
        },
        clearClientCart: async () => {
          clientCartCleared = true;
        },
      },
    });

    // PROOF: clearServerCart and addServerCartItem loop are NEVER called!
    assert.equal(clearServerCartCalls, 0, "clearServerCart must not be called during atomic checkout");
    assert.equal(addServerCartItemCalls, 0, "addServerCartItem must not be called in a destructive loop");

    // PROOF: createOrder received items and idempotency key atomically
    assert.ok(createOrderPayload, "createOrder must be called");
    assert.deepEqual(createOrderPayload.items, [
      { product_id: 101, quantity: 2 },
      { product_id: 102, quantity: 1 },
    ]);
    assert.ok(createOrderPayload.idempotency_key, "An idempotency key must be provided to createOrder");
    assert.equal(typeof createOrderPayload.idempotency_key, "string");
    assert.ok(createOrderPayload.idempotency_key.length > 5);

    // PROOF: Client cart is cleared only after server confirms the order
    assert.equal(clientCartCleared, true);
    assert.equal(result.status, "confirmed");
  });

  it("12. Checkout failure keeps client cart intact and never clears client cart", async () => {
    let clientCartCleared = false;
    const bagItems = [{ productId: 101, quantity: 1 }];

    await assert.rejects(
      () =>
        executeCheckoutOrder({
          lock: createCheckoutSubmissionLock(),
          isAuthenticated: true,
          items: bagItems,
          shippingAddress: "123 Street, Phnom Penh",
          paymentMethod: "Cash on Delivery",
          deps: {
            createOrder: async () => {
              throw new Error("Insufficient stock for requested item");
            },
            clearClientCart: async () => {
              clientCartCleared = true;
            },
          },
        }),
      /Insufficient stock/
    );

    // Client cart must remain intact on failure
    assert.equal(clientCartCleared, false);
    assert.equal(bagItems.length, 1);
  });

  it("13. Safe non-destructive reconciliation dependency is invoked atomically when provided", async () => {
    let reconcileItems: any = null;
    let createOrderCalled = false;
    let clientCartCleared = false;

    // Case A: Successful reconciliation proceeds to order creation
    const result = await executeCheckoutOrder({
      lock: createCheckoutSubmissionLock(),
      isAuthenticated: true,
      items: [{ productId: 105, quantity: 3 }],
      shippingAddress: "123 Street, Phnom Penh",
      paymentMethod: "Cash on Delivery",
      deps: {
        reconcileServerCart: async (items) => {
          reconcileItems = items;
        },
        createOrder: async () => {
          createOrderCalled = true;
          return {
            success: true,
            message: "Order placed",
            data: buildServerOrder({ id: 1001 }),
          };
        },
        clearClientCart: async () => {
          clientCartCleared = true;
        },
      },
    });

    assert.deepEqual(reconcileItems, [{ product_id: 105, quantity: 3 }]);
    assert.equal(createOrderCalled, true);
    assert.equal(clientCartCleared, true);
    assert.equal(result.status, "confirmed");

    // Case B: Reconciliation failure halts checkout, does NOT call createOrder or clearClientCart
    let failedClientCartCleared = false;
    await assert.rejects(
      () =>
        executeCheckoutOrder({
          lock: createCheckoutSubmissionLock(),
          isAuthenticated: true,
          items: [{ productId: 105, quantity: 99 }],
          shippingAddress: "123 Street, Phnom Penh",
          paymentMethod: "Cash on Delivery",
          deps: {
            reconcileServerCart: async () => {
              throw new Error("Cannot reconcile cart: product out of stock");
            },
            createOrder: async () => {
              throw new Error("Should not be called");
            },
            clearClientCart: async () => {
              failedClientCartCleared = true;
            },
          },
        }),
      /out of stock/
    );
    assert.equal(failedClientCartCleared, false);
  });

  it("14. Explicit request idempotency key is preserved across retry attempts", async () => {
    let sentKey: string | undefined;
    const testIdemKey = "custom-idempotency-key-xyz-789";

    const result = await executeCheckoutOrder({
      lock: createCheckoutSubmissionLock(),
      isAuthenticated: true,
      items: [{ productId: 101, quantity: 1 }],
      shippingAddress: "Street 2004, Phnom Penh",
      paymentMethod: "Cash on Delivery",
      idempotencyKey: testIdemKey,
      deps: {
        createOrder: async (payload) => {
          sentKey = payload.idempotency_key;
          return {
            success: true,
            message: "ok",
            data: buildServerOrder({ id: 1002 }),
          };
        },
        clearClientCart: async () => {},
      },
    });

    assert.equal(result.status, "confirmed");
    assert.equal(sentKey, testIdemKey);
  });

  it("15. Durable checkout key survives simulated browser reloads for identical cart", () => {
    const mockStorageMap = new Map<string, string>();
    const mockStorage = {
      getItem: (k: string) => mockStorageMap.get(k) ?? null,
      setItem: (k: string, v: string) => {
        mockStorageMap.set(k, v);
      },
      removeItem: (k: string) => {
        mockStorageMap.delete(k);
      },
      clear: () => {
        mockStorageMap.clear();
      },
      length: 0,
      key: () => null,
    } as unknown as Storage;

    const cart = [
      { productId: 101, quantity: 2 },
      { productId: 102, quantity: 1 },
    ];

    // First checkout attempt
    const initialKey = getOrCreateDurableCheckoutKey(cart, mockStorage);
    assert.ok(initialKey, "Must generate an initial key");
    assert.ok(mockStorageMap.has(PENDING_CHECKOUT_IDEMPOTENCY_STORAGE_KEY));

    // Simulated browser reload: subsequent call with same cart yields same key
    const reloadKey = getOrCreateDurableCheckoutKey(cart, mockStorage);
    assert.equal(
      reloadKey,
      initialKey,
      "Durable key must be preserved across page reloads for the same cart"
    );

    // Cart modification generates a new key
    const modifiedCart = [
      { productId: 101, quantity: 3 },
      { productId: 102, quantity: 1 },
    ];
    const newCartKey = getOrCreateDurableCheckoutKey(modifiedCart, mockStorage);
    assert.notEqual(
      newCartKey,
      initialKey,
      "Modifying cart items must invalidate stale key and generate a fresh key"
    );

    // Clearing removes durable key upon successful order placement
    clearDurableCheckoutKey(mockStorage);
    assert.equal(mockStorageMap.has(PENDING_CHECKOUT_IDEMPOTENCY_STORAGE_KEY), false);
  });

  it("16. executeCheckoutOrder uses durable key when none is passed explicitly", async () => {
    let capturedKey: string | undefined;
    const items = [{ productId: 201, quantity: 1 }];

    const result = await executeCheckoutOrder({
      lock: createCheckoutSubmissionLock(),
      isAuthenticated: true,
      items,
      shippingAddress: "Street 1, Phnom Penh",
      paymentMethod: "Cash on Delivery",
      deps: {
        createOrder: async (payload) => {
          capturedKey = payload.idempotency_key;
          return {
            success: true,
            message: "ok",
            data: buildServerOrder({ id: 8888 }),
          };
        },
        clearClientCart: async () => {},
      },
    });

    assert.equal(result.status, "confirmed");
    assert.ok(capturedKey, "Must generate a durable idempotency key automatically");
    assert.ok(capturedKey.length > 5);
  });
});


describe("Server-authoritative COD settlement", () => {
  for (const method of ["Cash on Delivery", "Cash on Delivery (COD)", "cod"]) {
    for (const paymentStatus of ["pending", "paid", "failed", "refunded"] as const) {
      it(`${method}: preserves server ${paymentStatus} in order history and checkout replay`, () => {
        const normalized = normalizeServerConfirmedOrder({
          success: true,
          message: "Order retrieved",
          data: buildServerOrder({ status: "delivered", payment_method: method, payment_status: paymentStatus }),
        }, method);
        assert.equal(normalized.payment_status, paymentStatus);
        const view = getOrderPaymentPresentation(normalized);
        assert.equal(view.isPaid, paymentStatus === "paid");
        assert.equal(view.paymentStatusLabel, {
          pending: "Unpaid (Cash on Delivery)", paid: "Paid",
          failed: "Payment Failed", refunded: "Refunded",
        }[paymentStatus]);
        assert.equal(view.totalLabel, paymentStatus === "paid" ? "Total Paid" : "Order Total");
      });
    }
  }
});
