import type {
  ApiAddress,
  ApiCart,
  ApiCouponValidation,
  ApiOrder,
  ApiResponse,
} from "./api";

export const DEFAULT_CHECKOUT_PAYMENT_METHOD = "Cash on Delivery";

export interface CheckoutPaymentMethodMeta {
  id: string;
  title: string;
  subtitle: string;
  isDemo: boolean;
  badge: "DEMO" | null;
}

export const CHECKOUT_PAYMENT_METHODS: readonly CheckoutPaymentMethodMeta[] = [
  {
    id: "Cash on Delivery",
    title: "Cash on Delivery (COD)",
    subtitle: "Pay in cash when your parcel arrives",
    isDemo: false,
    badge: null,
  },
  {
    id: "Credit / Debit Card",
    title: "Credit or Debit Card",
    subtitle: "Pay securely with Visa or Mastercard",
    isDemo: false,
    badge: null,
  },
];

const SUPPORTED_CHECKOUT_METHODS = new Set([
  "cash on delivery",
  "cash on delivery (cod)",
  "cod",
  "credit / debit card",
  "credit or debit card",
  "credit card",
  "debit card",
  "card",
]);

export function isSupportedCheckoutPaymentMethod(
  method?: string | null
): boolean {
  const normalized = (method || "").trim().toLowerCase();
  return Boolean(normalized && SUPPORTED_CHECKOUT_METHODS.has(normalized));
}

export function isCardPaymentMethod(method?: string | null): boolean {
  const normalized = (method || "").trim().toLowerCase();
  return (
    normalized === "credit / debit card" ||
    normalized === "credit or debit card" ||
    normalized === "credit card" ||
    normalized === "debit card" ||
    normalized === "card"
  );
}

export function isUnverifiedPaymentMethod(method?: string | null): boolean {
  const normalized = (method || "").trim().toLowerCase();
  if (!normalized) return true;
  if (
    normalized === "cash on delivery" ||
    normalized === "cash on delivery (cod)" ||
    normalized === "cod" ||
    isCardPaymentMethod(normalized)
  ) {
    return false;
  }
  return true;
}

export function isNetworkTransportError(err: unknown): boolean {
  const msg = err instanceof Error ? err.message : String(err || "");
  return (
    msg.includes("Failed to fetch") ||
    msg.includes("NetworkError") ||
    msg.includes("Load failed") ||
    msg.includes("ECONNREFUSED")
  );
}

export function toCheckoutErrorMessage(err: unknown): string {
  if (isNetworkTransportError(err)) {
    return "Unable to reach the server to place your order. Your shopping bag has been kept intact—please check your connection and try again.";
  }
  const msg = err instanceof Error ? err.message.trim() : "";
  return msg || "Could not complete your order. Please verify your details and try again.";
}

export function normalizeServerConfirmedOrder(
  response: ApiResponse<ApiOrder> | null | undefined,
  requestedPaymentMethod: string
): ApiOrder {
  if (!response || response.success === false || !response.data) {
    throw new Error(
      response?.message || "Order could not be confirmed by the server."
    );
  }

  const raw = response.data;
  const orderId = Number(raw.id);
  if (!Number.isInteger(orderId) || orderId <= 0) {
    throw new Error("Server returned an invalid order confirmation ID.");
  }

  const resolvedMethod = (raw.payment_method || requestedPaymentMethod || "").trim() ||
    DEFAULT_CHECKOUT_PAYMENT_METHOD;
  const rawPaymentStatus = (raw.payment_status || "pending").trim().toLowerCase();

  // Only the backend can settle COD. Preserve its paid status, including on retries.
  // Electronic demo methods still have no payment integration.
  const safePaymentStatus =
    rawPaymentStatus === "paid" && isUnverifiedPaymentMethod(resolvedMethod)
      ? "pending"
      : rawPaymentStatus || "pending";

  return {
    ...raw,
    id: orderId,
    status: (raw.status || "pending").trim() || "pending",
    payment_method: resolvedMethod,
    payment_status: safePaymentStatus,
    items: Array.isArray(raw.items) ? raw.items : [],
  };
}

export interface OrderPaymentPresentation {
  isPaid: boolean;
  orderStatusLabel: string;
  paymentStatusLabel: string;
  totalLabel: "Total Paid" | "Order Total";
}

function capitalizeWords(value: string): string {
  return value
    .split(/[\s_-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(" ");
}

export function getOrderPaymentPresentation(
  order: Pick<ApiOrder, "status" | "payment_status" | "payment_method">
): OrderPaymentPresentation {
  const rawPaymentStatus = (order.payment_status || "pending").trim().toLowerCase();
  const method = (order.payment_method || "").trim();
  const isPaid = rawPaymentStatus === "paid" && !isUnverifiedPaymentMethod(method);

  let paymentStatusLabel = "Pending Verification";
  if (isPaid) {
    paymentStatusLabel = "Paid";
  } else if (rawPaymentStatus === "failed") {
    paymentStatusLabel = "Payment Failed";
  } else if (rawPaymentStatus === "refunded") {
    paymentStatusLabel = "Refunded";
  } else if (method.toLowerCase().includes("cash") || method.toLowerCase() === "cod") {
    paymentStatusLabel = "Unpaid (Cash on Delivery)";
  }

  return {
    isPaid,
    orderStatusLabel: capitalizeWords(order.status || "pending"),
    paymentStatusLabel,
    totalLabel: isPaid ? "Total Paid" : "Order Total",
  };
}

export interface CheckoutSubmissionLock {
  isLocked: () => boolean;
  acquire: () => boolean;
  release: () => void;
}

export function createCheckoutSubmissionLock(): CheckoutSubmissionLock {
  let inFlight = false;
  return {
    isLocked: () => inFlight,
    acquire: () => {
      if (inFlight) return false;
      inFlight = true;
      return true;
    },
    release: () => {
      inFlight = false;
    },
  };
}

export interface CheckoutCartLine {
  productId: number;
  quantity: number;
}

export const PENDING_CHECKOUT_IDEMPOTENCY_STORAGE_KEY =
  "bp_pending_checkout_idempotency_v1";

export function computeCartSignature(items: CheckoutCartLine[]): string {
  return items
    .map((i) => `${i.productId}:${i.quantity}`)
    .sort()
    .join("|");
}

export function getOrCreateDurableCheckoutKey(
  items: CheckoutCartLine[],
  storage: Storage | null = typeof sessionStorage !== "undefined" ? sessionStorage : null
): string {
  const signature = computeCartSignature(items);
  if (storage) {
    try {
      const existing = storage.getItem(PENDING_CHECKOUT_IDEMPOTENCY_STORAGE_KEY);
      if (existing) {
        const parsed = JSON.parse(existing);
        if (
          parsed &&
          parsed.signature === signature &&
          typeof parsed.key === "string" &&
          parsed.key
        ) {
          return parsed.key;
        }
      }
    } catch {
      // Storage unavailable or parsing failed; proceed to generate fresh key
    }
  }

  const newKey =
    typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
      ? crypto.randomUUID()
      : `chk_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`;

  if (storage) {
    try {
      storage.setItem(
        PENDING_CHECKOUT_IDEMPOTENCY_STORAGE_KEY,
        JSON.stringify({ signature, key: newKey, createdAt: Date.now() })
      );
    } catch {
      // Storage quota or restriction; continue with in-memory key
    }
  }

  return newKey;
}

export function clearDurableCheckoutKey(
  storage: Storage | null = typeof sessionStorage !== "undefined" ? sessionStorage : null
): void {
  if (storage) {
    try {
      storage.removeItem(PENDING_CHECKOUT_IDEMPOTENCY_STORAGE_KEY);
    } catch {
      // Ignore storage errors on cleanup
    }
  }
}

export interface ExecuteCheckoutParams {
  lock: CheckoutSubmissionLock;
  isAuthenticated: boolean;
  items: CheckoutCartLine[];
  shippingAddress: string;
  shippingAddressId?: number;
  newAddressToSave?: {
    full_name: string;
    phone: string;
    address_line: string;
    city: string;
    postal_code?: string;
    is_default?: boolean;
  };
  paymentMethod: string;
  phone?: string;
  fullName?: string;
  couponCode?: string | null;
  idempotencyKey?: string;
  deps: {
    createAddress?: (data: {
      full_name: string;
      phone: string;
      address_line: string;
      city: string;
      postal_code?: string;
      is_default?: boolean;
    }) => Promise<ApiResponse<ApiAddress>>;
    reconcileServerCart?: (
      items: Array<{ product_id: number; quantity: number }>
    ) => Promise<unknown>;
    clearServerCart?: () => Promise<unknown>;
    addServerCartItem?: (data: {
      product_id: number;
      quantity: number;
    }) => Promise<ApiResponse<ApiCart>>;
    createOrder: (data: {
      shipping_address?: string;
      shipping_address_id?: number;
      payment_method: string;
      phone?: string;
      full_name?: string;
      coupon_code?: string;
      items?: Array<{ product_id: number; quantity: number }>;
      idempotency_key?: string;
    }) => Promise<ApiResponse<ApiOrder>>;
    clearClientCart: () => Promise<void>;
  };
}

export type ExecuteCheckoutResult =
  | { status: "duplicate_blocked" }
  | { status: "confirmed"; order: ApiOrder };

export async function executeCheckoutOrder(
  params: ExecuteCheckoutParams
): Promise<ExecuteCheckoutResult> {
  if (!params.lock.acquire()) {
    return { status: "duplicate_blocked" };
  }

  try {
    if (params.items.length === 0) {
      throw new Error("Your shopping bag is empty.");
    }

    const trimmedAddress = params.shippingAddress.trim();
    if (!trimmedAddress) {
      throw new Error("Please complete your delivery address.");
    }

    if (!params.isAuthenticated) {
      throw new Error(
        "Please sign in to place your order. Guest checkout is not available."
      );
    }

    if (!isSupportedCheckoutPaymentMethod(params.paymentMethod)) {
      throw new Error(
        "Unsupported payment method. Only Credit / Debit Card and Cash on Delivery are accepted."
      );
    }

    let addressIdToUse = params.shippingAddressId;
    if (!addressIdToUse && params.newAddressToSave && params.deps.createAddress) {
      try {
        const createdAddr = await params.deps.createAddress(params.newAddressToSave);
        addressIdToUse = createdAddr.data?.id;
      } catch {
        // Non-fatal: order creation still sends full shipping_address text.
      }
    }

    const orderItems = params.items.map((item) => ({
      product_id: item.productId,
      quantity: item.quantity,
    }));

    // Safe, non-destructive reconciliation if explicitly provided as dependency
    if (params.deps.reconcileServerCart) {
      await params.deps.reconcileServerCart(orderItems);
    }

    // Generate or reuse client idempotency key (durable across session reloads)
    const idempotencyKey =
      params.idempotencyKey ||
      getOrCreateDurableCheckoutKey(params.items);

    // Atomic backend checkout operation: pass items and idempotency key directly
    const orderRes = await params.deps.createOrder({
      shipping_address: trimmedAddress,
      shipping_address_id: addressIdToUse,
      payment_method: params.paymentMethod,
      phone: params.phone?.trim() || undefined,
      full_name: params.fullName?.trim() || undefined,
      coupon_code: params.couponCode?.trim() || undefined,
      items: orderItems,
      idempotency_key: idempotencyKey,
    });

    const confirmedOrder = normalizeServerConfirmedOrder(
      orderRes,
      params.paymentMethod
    );

    // Clear client cart ONLY after confirmed order creation
    await params.deps.clearClientCart();
    return { status: "confirmed", order: confirmedOrder };
  } catch (err) {
    throw new Error(toCheckoutErrorMessage(err));
  } finally {
    params.lock.release();
  }
}

export interface VerifiedCouponResult {
  code: string;
  discountAmount: number;
  message: string;
}

export async function validateCouponServerOnly(params: {
  code: string;
  subtotal: number;
  validateApi: (data: {
    code: string;
    subtotal: number;
  }) => Promise<ApiResponse<ApiCouponValidation>>;
  allowDemoFallback?: boolean;
  demoValidator?: (
    code: string,
    subtotal: number
  ) => VerifiedCouponResult;
}): Promise<VerifiedCouponResult> {
  const clean = params.code.trim().toUpperCase();
  if (!clean) {
    throw new Error("Please enter a promo code.");
  }
  if (!Number.isFinite(params.subtotal) || params.subtotal <= 0) {
    throw new Error("Add items to your bag before applying a promo code.");
  }

  try {
    const res = await params.validateApi({
      code: clean,
      subtotal: params.subtotal,
    });

    if (!res || res.success === false || !res.data || res.data.valid !== true) {
      throw new Error(
        res?.data?.message || res?.message || "Invalid or expired promo code."
      );
    }

    const discountAmount = Number(res.data.discount_amount);
    if (!Number.isFinite(discountAmount) || discountAmount <= 0) {
      throw new Error(
        res.data.message || "This promo code does not apply to your current bag."
      );
    }

    const verifiedCode = String(res.data.code || clean).trim().toUpperCase();
    return {
      code: verifiedCode,
      discountAmount,
      message: res.data.message || `Coupon '${verifiedCode}' applied.`,
    };
  } catch (err) {
    if (
      params.allowDemoFallback === true &&
      params.demoValidator &&
      isNetworkTransportError(err)
    ) {
      return params.demoValidator(clean, params.subtotal);
    }

    if (isNetworkTransportError(err)) {
      throw new Error(
        "Unable to verify promo code right now. Please check your connection and try again."
      );
    }

    throw err instanceof Error
      ? err
      : new Error("Invalid or expired promo code.");
  }
}
