import { getAccessToken, getSessionEpoch, logout } from "./auth";
import { API_BASE_URL } from "./config";

export { API_BASE_URL };

export interface ApiResponse<T = any> {
  success: boolean;
  message: string;
  data: T;
}

export interface ApiUser {
  id: number;
  name: string;
  email: string;
  phone?: string | null;
  avatar?: string | null;
  role: string;
  is_active: boolean;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: ApiUser;
}

export interface ApiCategory {
  id: number;
  name: string;
  description?: string | null;
  image?: string | null;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface ApiSellerSummary {
  id: number;
  name: string;
  owner_name?: string;
  email?: string;
  phone?: string | null;
  address?: string | null;
  logo?: string | null;
  rating: number;
  status: string;
}

export interface ApiProduct {
  id: number;
  category_id: number;
  seller_id?: number | null;
  name: string;
  description?: string | null;
  price: number | string;
  discount_price?: number | string | null;
  stock: number;
  image_url?: string | null;
  rating: number | string;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
  category?: ApiCategory | null;
  seller?: ApiSellerSummary | null;
}

export interface ApiProductPagination {
  items: ApiProduct[];
  total: number;
  page: number;
  limit: number;
  total_pages: number;
}

export interface ApiCoupon {
  id: number;
  code: string;
  description?: string | null;
  discount_type: string;
  discount_value: number;
  min_order_amount: number;
  max_discount_amount?: number | null;
  is_active: boolean;
  expires_at?: string | null;
  usage_limit?: number | null;
  per_user_limit?: number | null;
  used_count?: number;
}

export interface DashboardStats {
  total_products: number;
  total_categories: number;
  total_orders: number;
  pending_orders_count?: number;
  processing_orders_count?: number;
  delivered_orders_count?: number;
  total_users: number;
  total_revenue: number;
  low_stock_count: number;
  out_of_stock_count: number;
}

export interface ApiOrderItem {
  id: number;
  order_id: number;
  product_id?: number | null;
  product_name: string;
  price: number | string;
  quantity: number;
  subtotal: number | string;
  created_at: string;
}

export interface ApiOrderShipment {
  id: number;
  order_id: number;
  carrier: string;
  tracking_number?: string | null;
  tracking_url?: string | null;
  status: string;
  estimated_delivery_at?: string | null;
  shipped_at?: string | null;
  delivered_at?: string | null;
  notes?: string | null;
  updated_at: string;
}

export interface ApiOrderTrackingEvent {
  id?: number | null;
  status: string;
  title: string;
  description?: string | null;
  location?: string | null;
  occurred_at: string;
}

export interface ApiOrderTracking {
  order_id: number;
  order_status: string;
  payment_status: string;
  shipping_address: string;
  has_shipment_record: boolean;
  shipment?: ApiOrderShipment | null;
  events: ApiOrderTrackingEvent[];
}

export interface ApiOrder {
  id: number;
  user_id: number;
  user?: ApiUser | null;
  status: string;
  subtotal: number | string;
  discount_amount: number | string;
  coupon_code?: string | null;
  shipping_fee: number | string;
  total: number | string;
  payment_method: string;
  payment_status: string;
  shipping_address: string;
  created_at: string;
  updated_at: string;
  items: ApiOrderItem[];
  shipment?: ApiOrderShipment | null;
}

export interface ApiSellerOrder extends ApiOrder {
  seller_items: ApiOrderItem[];
  seller_subtotal: number | string;
  can_update_status: boolean;
}

export interface ApiSellerOrderPagination {
  items: ApiSellerOrder[];
  total: number;
  page: number;
  limit: number;
  total_pages: number;
}

export interface ApiSellerDashboardLowStockProduct {
  id: number;
  name: string;
  price: number | string;
  stock: number;
  is_active: boolean;
}

export interface ApiSellerDashboard {
  seller_id: number;
  store_name: string;
  store_status: string;
  rating: number | string;
  total_products: number;
  active_products: number;
  low_stock_products_count: number;
  out_of_stock_products_count: number;
  total_orders: number;
  pending_orders: number;
  processing_orders: number;
  shipped_orders: number;
  delivered_orders: number;
  cancelled_orders: number;
  gross_revenue: number | string;
  recent_orders: ApiSellerOrder[];
  low_stock_items: ApiSellerDashboardLowStockProduct[];
}

export interface ApiReview {
  id: number;
  product_id: number;
  user_id: number;
  order_id?: number | null;
  rating: number;
  comment: string;
  status: string;
  admin_reply?: string | null;
  admin_replied_at?: string | null;
  created_at: string;
  updated_at: string;
  user?: (Pick<ApiUser, "id" | "name"> & Partial<Omit<ApiUser, "id" | "name">>) | null;
  product?: ApiProduct | null;
}

export interface ApiSeller {
  id: number;
  user_id?: number | null;
  name: string;
  owner_name?: string;
  email?: string;
  phone?: string | null;
  address?: string | null;
  description?: string | null;
  logo?: string | null;
  status: string;
  rating: number;
  products_count: number;
  orders_count?: number;
  total_revenue?: number;
  created_at: string;
  updated_at: string;
}



/**
 * Generic HTTP client with JWT token attachment and error extraction
 */
async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  const token = getAccessToken();
  const sessionEpoch = getSessionEpoch();
  if (typeof window !== "undefined") {
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
  }

  const response = await fetch(url, {
    ...options,
    headers,
    cache: "no-store",
  });

  const json = await response.json().catch(() => ({}));

  if (!response.ok) {
    if (response.status === 401 && typeof window !== "undefined" &&
        sessionEpoch === getSessionEpoch() && token === getAccessToken()) {
      logout();
      // Auth layouts observe logout and perform the framework navigation.
    }

    const errorMessage =
      json.detail || json.message || `Request failed with status ${response.status}`;
    throw new Error(
      typeof errorMessage === "string" ? errorMessage : JSON.stringify(errorMessage)
    );
  }

  return json;
}

// ==========================================
// Authentication APIs
// ==========================================
export const authApi = {
  login: async (credentials: { email: string; password: string }): Promise<ApiResponse<AuthResponse>> => {
    return request<ApiResponse<AuthResponse>>("/auth/login", {
      method: "POST",
      body: JSON.stringify(credentials),
    });
  },

  register: async (data: { name: string; email: string; password: string; phone?: string }): Promise<ApiResponse<AuthResponse>> => {
    return request<ApiResponse<AuthResponse>>("/auth/register", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  getMe: async (): Promise<ApiResponse<ApiUser>> => {
    return request<ApiResponse<ApiUser>>("/auth/me");
  },

  updateMe: async (data: Partial<ApiUser>): Promise<ApiResponse<ApiUser>> => {
    return request<ApiResponse<ApiUser>>("/auth/me", {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },

  changePassword: async (data: {
    current_password: string;
    new_password: string;
  }): Promise<ApiResponse<null>> => {
    const epoch = getSessionEpoch();
    const response = await request<ApiResponse<null>>("/auth/change-password", {
      method: "PUT",
      body: JSON.stringify(data),
    });
    if (response.success && epoch === getSessionEpoch()) logout("password_changed");
    return response;
  },

  forgotPassword: async (
    email: string
  ): Promise<ApiResponse<{ reset_url?: string } | null>> => {
    return request<ApiResponse<{ reset_url?: string } | null>>("/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email, client: "management" }),
    });
  },

  validateResetToken: async (
    token: string
  ): Promise<ApiResponse<{ valid: boolean }>> => {
    return request<ApiResponse<{ valid: boolean }>>("/auth/reset-password/validate", {
      method: "POST",
      body: JSON.stringify({ token }),
    });
  },

  resetPassword: async (data: {
    token: string;
    new_password: string;
  }): Promise<ApiResponse<null>> => {
    return request<ApiResponse<null>>("/auth/reset-password", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },
};

// ==========================================
// Product APIs
// ==========================================
export const productsApi = {
  list: async (params?: {
    category_id?: number;
    search?: string;
    min_price?: number;
    max_price?: number;
    sort?: string;
    page?: number;
    limit?: number;
  }): Promise<ApiResponse<ApiProductPagination>> => {
    const query = new URLSearchParams();
    if (params?.category_id) query.append("category_id", params.category_id.toString());
    if (params?.search) query.append("search", params.search);
    if (params?.min_price !== undefined) query.append("min_price", params.min_price.toString());
    if (params?.max_price !== undefined) query.append("max_price", params.max_price.toString());
    if (params?.sort) query.append("sort", params.sort);
    if (params?.page) query.append("page", params.page.toString());
    if (params?.limit) query.append("limit", params.limit.toString());

    const queryString = query.toString() ? `?${query.toString()}` : "";
    return request<ApiResponse<ApiProductPagination>>(`/products${queryString}`);
  },

  get: async (id: number): Promise<ApiResponse<ApiProduct>> => {
    return request<ApiResponse<ApiProduct>>(`/products/${id}`);
  },

  create: async (data: {
    category_id: number;
    seller_id?: number | null;
    name: string;
    description?: string;
    price: number;
    discount_price?: number | null;
    stock: number;
    image_url?: string;
    rating?: number;
    is_active?: boolean;
  }): Promise<ApiResponse<ApiProduct>> => {
    return request<ApiResponse<ApiProduct>>("/products", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  update: async (
    id: number,
    data: Partial<{
      category_id: number;
      seller_id: number | null;
      name: string;
      description: string;
      price: number;
      discount_price: number | null;
      stock: number;
      image_url: string;
      is_active: boolean;
    }>
  ): Promise<ApiResponse<ApiProduct>> => {
    return request<ApiResponse<ApiProduct>>(`/products/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },

  delete: async (id: number): Promise<ApiResponse<null>> => {
    return request<ApiResponse<null>>(`/products/${id}`, {
      method: "DELETE",
    });
  },
};

// ==========================================
// Category APIs
// ==========================================
export const categoriesApi = {
  list: async (active_only?: boolean): Promise<ApiResponse<ApiCategory[]>> => {
    const url = active_only !== undefined ? `/categories?active_only=${active_only}` : "/categories";
    return request<ApiResponse<ApiCategory[]>>(url);
  },

  get: async (id: number): Promise<ApiResponse<ApiCategory>> => {
    return request<ApiResponse<ApiCategory>>(`/categories/${id}`);
  },

  create: async (data: {
    name: string;
    description?: string;
    image?: string;
    is_active?: boolean;
  }): Promise<ApiResponse<ApiCategory>> => {
    return request<ApiResponse<ApiCategory>>("/categories", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  update: async (
    id: number,
    data: {
      name: string;
      description?: string;
      image?: string;
      is_active?: boolean;
    }
  ): Promise<ApiResponse<ApiCategory>> => {
    return request<ApiResponse<ApiCategory>>(`/categories/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },

  delete: async (id: number): Promise<ApiResponse<null>> => {
    return request<ApiResponse<null>>(`/categories/${id}`, {
      method: "DELETE",
    });
  },
};

// ==========================================
// Orders & Vouchers APIs
// ==========================================
export const ordersApi = {
  create: async (data: {
    shipping_address?: string;
    shipping_address_id?: number;
    payment_method: string;
    phone?: string;
    full_name?: string;
    coupon_code?: string;
  }): Promise<ApiResponse<ApiOrder>> => {
    return request<ApiResponse<ApiOrder>>("/orders", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  list: async (): Promise<ApiResponse<ApiOrder[]>> => {
    return request<ApiResponse<ApiOrder[]>>("/orders");
  },

  listAll: async (): Promise<ApiResponse<ApiOrder[]>> => {
    return request<ApiResponse<ApiOrder[]>>("/orders/all");
  },

  get: async (id: number): Promise<ApiResponse<ApiOrder>> => {
    return request<ApiResponse<ApiOrder>>(`/orders/${id}`);
  },

  updateStatus: async (
    id: number,
    data: { status?: string; payment_status?: string; reason?: string }
  ): Promise<ApiResponse<ApiOrder>> => {
    return request<ApiResponse<ApiOrder>>(`/orders/${id}/status`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },

  delete: async (
    id: number,
    reason?: string
  ): Promise<ApiResponse<ApiOrder | null>> => {
    const query = reason ? `?reason=${encodeURIComponent(reason)}` : "";
    return request<ApiResponse<ApiOrder | null>>(`/orders/${id}${query}`, {
      method: "DELETE",
    });
  },

  getTracking: async (id: number): Promise<ApiResponse<ApiOrderTracking>> => {
    return request<ApiResponse<ApiOrderTracking>>(`/orders/${id}/tracking`);
  },

  updateTracking: async (
    id: number,
    data: {
      carrier: string;
      tracking_number?: string | null;
      tracking_url?: string | null;
      status: string;
      estimated_delivery_at?: string | null;
      event_title?: string | null;
      event_description?: string | null;
      location?: string | null;
      notes?: string | null;
    }
  ): Promise<ApiResponse<ApiOrderTracking>> => {
    return request<ApiResponse<ApiOrderTracking>>(`/orders/${id}/tracking`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },
};

export interface ApiCouponValidation {
  valid: boolean;
  code: string;
  discount_type: string;
  discount_value: number | string;
  discount_amount: number | string;
  new_subtotal: number | string;
  message: string;
}

export interface CouponCreatePayload {
  code: string;
  description?: string | null;
  discount_type: "percent" | "fixed";
  discount_value: number;
  min_order_amount?: number;
  max_discount_amount?: number | null;
  is_active?: boolean;
  expires_at?: string | null;
  usage_limit?: number | null;
  per_user_limit?: number | null;
}

export interface CouponUpdatePayload {
  description?: string | null;
  discount_type?: "percent" | "fixed";
  discount_value?: number;
  min_order_amount?: number;
  max_discount_amount?: number | null;
  is_active?: boolean;
  expires_at?: string | null;
  usage_limit?: number | null;
  per_user_limit?: number | null;
}

export const couponsApi = {
  available: async (): Promise<ApiResponse<ApiCoupon[]>> => {
    return request<ApiResponse<ApiCoupon[]>>("/coupons/available");
  },

  validate: async (data: {
    code: string;
    subtotal: number;
  }): Promise<ApiResponse<ApiCouponValidation>> => {
    return request<ApiResponse<ApiCouponValidation>>("/coupons/validate", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  list: async (): Promise<ApiResponse<ApiCoupon[]>> => {
    return request<ApiResponse<ApiCoupon[]>>("/coupons");
  },

  create: async (data: CouponCreatePayload): Promise<ApiResponse<ApiCoupon>> => {
    return request<ApiResponse<ApiCoupon>>("/coupons", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  update: async (
    id: number,
    data: CouponUpdatePayload
  ): Promise<ApiResponse<ApiCoupon>> => {
    return request<ApiResponse<ApiCoupon>>(`/coupons/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },

  delete: async (id: number): Promise<ApiResponse<null>> => {
    return request<ApiResponse<null>>(`/coupons/${id}`, {
      method: "DELETE",
    });
  },
};

// ==========================================
// Customer Cart, Wishlist & Address APIs
// ==========================================
export interface ApiCartItem {
  id: number;
  product_id: number;
  quantity: number;
  product: ApiProduct;
  item_total: number | string;
  created_at: string;
  updated_at: string;
}

export interface ApiCart {
  items: ApiCartItem[];
  total_items: number;
  subtotal: number | string;
}

export const cartApi = {
  get: async (): Promise<ApiResponse<ApiCart>> => {
    return request<ApiResponse<ApiCart>>("/cart");
  },

  addItem: async (data: {
    product_id: number;
    quantity: number;
  }): Promise<ApiResponse<ApiCart>> => {
    return request<ApiResponse<ApiCart>>("/cart/items", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  updateItem: async (
    itemId: number,
    quantity: number
  ): Promise<ApiResponse<ApiCart>> => {
    return request<ApiResponse<ApiCart>>(`/cart/items/${itemId}`, {
      method: "PUT",
      body: JSON.stringify({ quantity }),
    });
  },

  removeItem: async (itemId: number): Promise<ApiResponse<ApiCart>> => {
    return request<ApiResponse<ApiCart>>(`/cart/items/${itemId}`, {
      method: "DELETE",
    });
  },

  clear: async (): Promise<ApiResponse<ApiCart>> => {
    return request<ApiResponse<ApiCart>>("/cart", {
      method: "DELETE",
    });
  },
};

export interface ApiFavorite {
  id: number;
  product_id: number;
  product: ApiProduct;
  created_at: string;
}

export const favoritesApi = {
  list: async (): Promise<ApiResponse<ApiFavorite[]>> => {
    return request<ApiResponse<ApiFavorite[]>>("/favorites");
  },

  toggle: async (
    productId: number
  ): Promise<ApiResponse<{ is_favorite: boolean; message: string }>> => {
    return request<ApiResponse<{ is_favorite: boolean; message: string }>>(
      `/favorites/${productId}/toggle`,
      { method: "POST" }
    );
  },
};

export interface ApiAddress {
  id: number;
  user_id: number;
  full_name: string;
  phone: string;
  address_line: string;
  city: string;
  province?: string | null;
  postal_code?: string | null;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export const addressesApi = {
  list: async (): Promise<ApiResponse<ApiAddress[]>> => {
    return request<ApiResponse<ApiAddress[]>>("/addresses");
  },

  create: async (data: {
    full_name: string;
    phone: string;
    address_line: string;
    city: string;
    province?: string;
    postal_code?: string;
    is_default?: boolean;
  }): Promise<ApiResponse<ApiAddress>> => {
    return request<ApiResponse<ApiAddress>>("/addresses", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  update: async (
    id: number,
    data: Partial<{
      full_name: string;
      phone: string;
      address_line: string;
      city: string;
      province: string;
      postal_code: string;
      is_default: boolean;
    }>
  ): Promise<ApiResponse<ApiAddress>> => {
    return request<ApiResponse<ApiAddress>>(`/addresses/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },

  delete: async (id: number): Promise<ApiResponse<null>> => {
    return request<ApiResponse<null>>(`/addresses/${id}`, {
      method: "DELETE",
    });
  },

  setDefault: async (id: number): Promise<ApiResponse<ApiAddress>> => {
    return request<ApiResponse<ApiAddress>>(`/addresses/${id}/default`, {
      method: "PUT",
    });
  },
};

// ==========================================
// Reviews & Ratings APIs
// ==========================================
export const reviewsApi = {
  list: async (params?: {
    status?: string;
    rating?: number;
    product_id?: number;
  }): Promise<ApiResponse<ApiReview[]>> => {
    const query = new URLSearchParams();
    if (params?.status && params.status !== "All") query.append("status", params.status);
    if (params?.rating) query.append("rating", params.rating.toString());
    if (params?.product_id) query.append("product_id", params.product_id.toString());
    const qs = query.toString() ? `?${query.toString()}` : "";
    return request<ApiResponse<ApiReview[]>>(`/reviews${qs}`);
  },

  get: async (id: number): Promise<ApiResponse<ApiReview>> => {
    return request<ApiResponse<ApiReview>>(`/reviews/${id}`);
  },

  create: async (
    productId: number,
    data: { rating: number; comment: string; order_id?: number }
  ): Promise<ApiResponse<ApiReview>> => {
    return request<ApiResponse<ApiReview>>(`/reviews/product/${productId}`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  updateStatus: async (
    id: number,
    status: string
  ): Promise<ApiResponse<ApiReview>> => {
    return request<ApiResponse<ApiReview>>(`/reviews/${id}/status`, {
      method: "PUT",
      body: JSON.stringify({ status }),
    });
  },

  reply: async (
    id: number,
    admin_reply: string
  ): Promise<ApiResponse<ApiReview>> => {
    return request<ApiResponse<ApiReview>>(`/reviews/${id}/reply`, {
      method: "PUT",
      body: JSON.stringify({ admin_reply }),
    });
  },

  delete: async (id: number): Promise<ApiResponse<null>> => {
    return request<ApiResponse<null>>(`/reviews/${id}`, {
      method: "DELETE",
    });
  },
};

// ==========================================
// Users & Customers APIs
// ==========================================
export const usersApi = {
  list: async (role?: string): Promise<ApiResponse<ApiUser[]>> => {
    const url = role ? `/users?role=${encodeURIComponent(role)}` : "/users";
    return request<ApiResponse<ApiUser[]>>(url);
  },

  get: async (id: number): Promise<ApiResponse<ApiUser>> => {
    return request<ApiResponse<ApiUser>>(`/users/${id}`);
  },

  create: async (data: {
    name: string;
    email: string;
    password: string;
    phone?: string;
    avatar?: string;
    role?: string;
    is_active?: boolean;
  }): Promise<ApiResponse<ApiUser>> => {
    return request<ApiResponse<ApiUser>>("/users", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  update: async (
    id: number,
    data: {
      name?: string;
      email?: string;
      phone?: string;
      avatar?: string;
      role?: string;
      is_active?: boolean;
      password?: string;
    }
  ): Promise<ApiResponse<ApiUser>> => {
    return request<ApiResponse<ApiUser>>(`/users/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },

  delete: async (id: number): Promise<ApiResponse<null>> => {
    return request<ApiResponse<null>>(`/users/${id}`, {
      method: "DELETE",
    });
  },
};

// ==========================================
// Sellers APIs
// ==========================================
export const sellersApi = {
  list: async (params?: { status?: string; search?: string }): Promise<ApiResponse<ApiSeller[]>> => {
    const query = new URLSearchParams();
    if (params?.status && params.status !== "All") query.append("status", params.status);
    if (params?.search) query.append("search", params.search);
    const qs = query.toString() ? `?${query.toString()}` : "";
    return request<ApiResponse<ApiSeller[]>>(`/sellers${qs}`);
  },

  get: async (id: number): Promise<ApiResponse<ApiSeller>> => {
    return request<ApiResponse<ApiSeller>>(`/sellers/${id}`);
  },

  create: async (data: {
    name: string;
    owner_name: string;
    email: string;
    phone?: string;
    address?: string;
    description?: string;
    logo?: string;
    status?: string;
    password?: string;
  }): Promise<ApiResponse<ApiSeller>> => {
    return request<ApiResponse<ApiSeller>>("/sellers", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  update: async (
    id: number,
    data: Partial<{
      name: string;
      owner_name: string;
      email: string;
      phone: string;
      address: string;
      description: string;
      logo: string;
      status: string;
    }>
  ): Promise<ApiResponse<ApiSeller>> => {
    return request<ApiResponse<ApiSeller>>(`/sellers/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },

  delete: async (id: number): Promise<ApiResponse<null>> => {
    return request<ApiResponse<null>>(`/sellers/${id}`, {
      method: "DELETE",
    });
  },
};

// ==========================================
// Seller Self-Service API (Task B.2)
// ==========================================
export const sellerMeApi = {
  getStore: async (): Promise<ApiResponse<ApiSeller>> => {
    return request<ApiResponse<ApiSeller>>("/seller/me");
  },

  updateStore: async (data: {
    name?: string;
    description?: string;
    phone?: string;
    address?: string;
    logo?: string;
  }): Promise<ApiResponse<ApiSeller>> => {
    return request<ApiResponse<ApiSeller>>("/seller/me", {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },
};

// ==========================================
// Seller Products API (Task C.1)
// ==========================================
export const sellerProductsApi = {
  list: async (params?: {
    page?: number;
    limit?: number;
    search?: string;
    category_id?: number;
    status?: string;
  }): Promise<ApiResponse<ApiProductPagination>> => {
    const query = new URLSearchParams();
    if (params?.page) query.append("page", String(params.page));
    if (params?.limit) query.append("limit", String(params.limit));
    if (params?.search) query.append("search", params.search);
    if (params?.category_id) query.append("category_id", String(params.category_id));
    if (params?.status && params.status !== "all") query.append("status", params.status);
    const qs = query.toString() ? `?${query.toString()}` : "";
    return request<ApiResponse<ApiProductPagination>>(`/seller/products${qs}`);
  },
};

// ==========================================
// Seller Dashboard & Fulfillment Orders API
// ==========================================
export const sellerApi = {
  getDashboard: async (): Promise<ApiResponse<ApiSellerDashboard>> => {
    return request<ApiResponse<ApiSellerDashboard>>("/seller/dashboard");
  },

  getOrders: async (params?: {
    page?: number;
    limit?: number;
    status?: string;
    search?: string;
  }): Promise<ApiResponse<ApiSellerOrderPagination>> => {
    const query = new URLSearchParams();
    if (params?.page) query.append("page", String(params.page));
    if (params?.limit) query.append("limit", String(params.limit));
    if (params?.status && params.status !== "all") query.append("status", params.status);
    if (params?.search) query.append("search", params.search);
    const qs = query.toString() ? `?${query.toString()}` : "";
    return request<ApiResponse<ApiSellerOrderPagination>>(`/seller/orders${qs}`);
  },

  updateOrderStatus: async (
    orderId: number,
    data: { status: string; reason?: string }
  ): Promise<ApiResponse<ApiOrder>> => {
    return ordersApi.updateStatus(orderId, data);
  },

  updateOrderTracking: async (
    orderId: number,
    data: {
      carrier: string;
      tracking_number?: string | null;
      tracking_url?: string | null;
      status: string;
      estimated_delivery_at?: string | null;
      event_title?: string | null;
      event_description?: string | null;
      location?: string | null;
      notes?: string | null;
    }
  ): Promise<ApiResponse<ApiOrderTracking>> => {
    return ordersApi.updateTracking(orderId, data);
  },
};

// ==========================================
// Store Settings & RBAC Roles API
// ==========================================
export interface ApiStoreSettings {
  id: number;
  key: string;
  store_name: string;
  store_email: string;
  store_phone?: string | null;
  store_address?: string | null;
  store_logo_url?: string | null;
  currency: string;
  language: string;
  timezone: string;
  theme: string;
  primary_color: string;
  sidebar_style: string;
  free_shipping_min: number | string;
  standard_shipping_fee: number | string;
  express_shipping_fee: number | string;
  estimated_delivery_days: string;
  enable_card_payment: boolean;
  enable_cod_payment: boolean;
  notify_new_order: boolean;
  notify_low_stock: boolean;
  notify_customer_message: boolean;
  notify_weekly_report: boolean;
  updated_at: string;
}

export interface ApiInfrastructureStatus {
  database_dialect: string;
  database_connected: boolean;
  table_count: number;
  table_names: string[];
  upload_storage_backend: string;
  email_provider: string;
  card_gateway_configured: boolean;
}

export interface ApiAdminSettingsBundle {
  settings: ApiStoreSettings;
  infrastructure: ApiInfrastructureStatus;
}

export interface ApiStoreSettingsUpdate {
  store_name: string;
  store_email: string;
  store_phone?: string | null;
  store_address?: string | null;
  store_logo_url?: string | null;
  currency: string;
  language: string;
  timezone: string;
  theme: string;
  primary_color: string;
  sidebar_style: string;
  free_shipping_min: number;
  standard_shipping_fee: number;
  express_shipping_fee: number;
  estimated_delivery_days: string;
  enable_card_payment: boolean;
  enable_cod_payment: boolean;
  notify_new_order: boolean;
  notify_low_stock: boolean;
  notify_customer_message: boolean;
  notify_weekly_report: boolean;
}

export interface ApiRoleDefinition {
  id: string;
  name: string;
  description: string;
  is_system: boolean;
  permissions_count: number;
  permission_groups: Array<{ module: string; permissions: string[] }>;
  users_count: number;
  users: Array<{ id: number; name: string; email: string; is_active: boolean }>;
}

export const settingsApi = {
  get: async (): Promise<ApiResponse<ApiAdminSettingsBundle>> => {
    return request<ApiResponse<ApiAdminSettingsBundle>>("/settings");
  },

  update: async (
    data: ApiStoreSettingsUpdate
  ): Promise<ApiResponse<ApiAdminSettingsBundle>> => {
    return request<ApiResponse<ApiAdminSettingsBundle>>("/settings", {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },

  getRoles: async (): Promise<ApiResponse<ApiRoleDefinition[]>> => {
    return request<ApiResponse<ApiRoleDefinition[]>>("/settings/roles");
  },
};

// ==========================================
// Dashboard Statistics API
// ==========================================
export const statsApi = {
  getOverview: async (): Promise<ApiResponse<DashboardStats>> => {
    return request<ApiResponse<DashboardStats>>("/stats/overview");
  },
};

// ==========================================
// Media & File Upload API
// ==========================================
export const uploadApi = {
  uploadImage: async (file: File): Promise<ApiResponse<{ filename: string; url: string; relative_url: string; storage_backend?: string }>> => {
    const formData = new FormData();
    formData.append("file", file);

    const url = `${API_BASE_URL}/upload/image`;
    const headers: Record<string, string> = {};

    const token = getAccessToken();
    const sessionEpoch = getSessionEpoch();
    if (typeof window !== "undefined") {
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }
    }

    const response = await fetch(url, {
      method: "POST",
      headers,
      body: formData,
    });

    const json = await response.json().catch(() => ({}));

    if (!response.ok) {
      if (response.status === 401 && typeof window !== "undefined" &&
          sessionEpoch === getSessionEpoch() && token === getAccessToken()) {
        logout();
      }
      const errorMessage =
        json.detail || json.message || `Upload failed with status ${response.status}`;
      throw new Error(
        typeof errorMessage === "string" ? errorMessage : JSON.stringify(errorMessage)
      );
    }

    return json;
  },
};

// ==========================================
// Notifications API
// ==========================================
export interface ApiNotification {
  id: number;
  user_id: number | null;
  type: string;
  title: string;
  message: string;
  link?: string | null;
  read: boolean;
  created_at: string;
  updated_at: string;
}

export const notificationsApi = {
  getAll: async (params?: {
    type?: string;
    unread_only?: boolean;
    skip?: number;
    limit?: number;
  }): Promise<ApiResponse<ApiNotification[]> & { unread_count: number }> => {
    const searchParams = new URLSearchParams();
    if (params?.type && params.type !== "all" && params.type !== "All") {
      searchParams.append("type", params.type.toLowerCase());
    }
    if (params?.unread_only) {
      searchParams.append("unread_only", "true");
    }
    if (params?.skip) {
      searchParams.append("skip", String(params.skip));
    }
    if (params?.limit) {
      searchParams.append("limit", String(params.limit));
    }
    const qs = searchParams.toString();
    return request<ApiResponse<ApiNotification[]> & { unread_count: number }>(
      `/notifications/admin${qs ? `?${qs}` : ""}`
    );
  },

  getUnreadCount: async (): Promise<{ success: boolean; unread_count: number }> => {
    return request<{ success: boolean; unread_count: number }>("/notifications/admin/unread-count");
  },

  markAsRead: async (id: number): Promise<ApiResponse<ApiNotification>> => {
    return request<ApiResponse<ApiNotification>>(`/notifications/admin/${id}/read`, {
      method: "PATCH",
    });
  },

  markAllAsRead: async (): Promise<{ success: boolean; message: string; updated_count: number }> => {
    return request<{ success: boolean; message: string; updated_count: number }>("/notifications/admin/read-all", {
      method: "POST",
    });
  },

  delete: async (id: number): Promise<{ success: boolean; message: string }> => {
    return request<{ success: boolean; message: string }>(`/notifications/admin/${id}`, {
      method: "DELETE",
    });
  },

  clearAll: async (): Promise<{ success: boolean; message: string; deleted_count: number }> => {
    return request<{ success: boolean; message: string; deleted_count: number }>("/notifications/admin", {
      method: "DELETE",
    });
  },

  create: async (data: {
    type?: string;
    title: string;
    message: string;
    link?: string;
    user_id?: number | null;
  }): Promise<ApiResponse<ApiNotification>> => {
    return request<ApiResponse<ApiNotification>>("/notifications", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },
};

// ==========================================
// Point of Sale (POS) APIs
// ==========================================
export interface PosItemInput {
  product_id: number;
  quantity: number;
  price?: number;
}

export interface PosCheckoutRequest {
  items: PosItemInput[];
  customer_id?: number | null;
  customer_name?: string;
  customer_phone?: string;
  payment_method: string;
  amount_paid: number;
  change_due: number;
  discount_amount?: number;
  tax_amount?: number;
  notes?: string;
}

export interface PosReceiptItem {
  product_id: number | null;
  product_name: string;
  price: number;
  quantity: number;
  subtotal: number;
}

export interface PosReceipt {
  order_id: number;
  order_number: string;
  subtotal: number;
  discount_amount: number;
  tax_amount: number;
  shipping_fee: number;
  total: number;
  payment_method: string;
  payment_status: string;
  amount_paid: number;
  change_due: number;
  customer_name: string;
  customer_phone?: string;
  cashier_name: string;
  notes?: string;
  created_at: string;
  items: PosReceiptItem[];
}

export interface PosSummary {
  date: string;
  today_orders_count: number;
  today_total_sales: number;
  today_cash_sales: number;
  today_card_sales: number;
  today_qr_sales: number;
}

export const posApi = {
  checkout: async (data: PosCheckoutRequest): Promise<ApiResponse<PosReceipt>> => {
    return request<ApiResponse<PosReceipt>>("/pos/checkout", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  getSummary: async (): Promise<ApiResponse<PosSummary>> => {
    return request<ApiResponse<PosSummary>>("/pos/summary");
  },

  searchCustomers: async (
    q: string = ""
  ): Promise<ApiResponse<Array<{ id: number; name: string; email: string; phone?: string }>>> => {
    return request<ApiResponse<Array<{ id: number; name: string; email: string; phone?: string }>>>(
      `/pos/customers?q=${encodeURIComponent(q)}`
    );
  },
};

// ==========================================
// DIGITAL PAYMENTS (CARD & COD ONLY)
// ==========================================

export interface ApiPaymentConfig {
  supported_methods: string[];
  card_gateway_configured: boolean;
  card_provider: string;
  stripe_publishable_key?: string | null;
  currency: string;
}

export interface ApiPaymentTransaction {
  id: number;
  transaction_ref: string;
  order_id: number;
  customer_id?: number | null;
  customer_name?: string | null;
  customer_email?: string | null;
  order_status?: string | null;
  provider: string;
  payment_method: string;
  amount: number;
  currency: string;
  status: string;
  provider_reference?: string | null;
  card_brand?: string | null;
  card_last4?: string | null;
  failure_reason?: string | null;
  created_at: string;
  updated_at: string;
}

export const paymentsApi = {
  getConfig: async (): Promise<ApiResponse<ApiPaymentConfig>> => {
    return request<ApiResponse<ApiPaymentConfig>>("/payments/config");
  },

  getAll: async (params?: {
    status?: string;
    method?: string;
    search?: string;
  }): Promise<ApiResponse<ApiPaymentTransaction[]>> => {
    const query = new URLSearchParams();
    if (params?.status) query.set("status", params.status);
    if (params?.method) query.set("method", params.method);
    if (params?.search) query.set("search", params.search);
    const qs = query.toString();
    return request<ApiResponse<ApiPaymentTransaction[]>>(
      `/payments${qs ? `?${qs}` : ""}`
    );
  },

  getById: async (identifier: string | number): Promise<ApiResponse<ApiPaymentTransaction>> => {
    return request<ApiResponse<ApiPaymentTransaction>>(
      `/payments/${encodeURIComponent(String(identifier))}`
    );
  },
};

// ==========================================
// DEDICATED SUPPLIERS API
// ==========================================

export interface ApiSupplierPurchaseOrderSummary {
  id: number;
  po_number: string;
  warehouse_id: number;
  warehouse_name?: string | null;
  status: string;
  total_cost: number;
  expected_at?: string | null;
  ordered_at?: string | null;
  received_at?: string | null;
  created_at: string;
}

export interface ApiSupplier {
  id: number;
  code: string;
  name: string;
  contact_name: string;
  email: string;
  phone?: string | null;
  address?: string | null;
  city?: string | null;
  country?: string | null;
  tax_id?: string | null;
  payment_terms: string;
  lead_time_days: number;
  status: string;
  notes?: string | null;
  purchase_orders_count: number;
  open_purchase_orders_count: number;
  total_procured_amount: number;
  recent_purchase_orders: ApiSupplierPurchaseOrderSummary[];
  created_at: string;
  updated_at: string;
}

export const suppliersApi = {
  getAll: async (params?: {
    status?: string;
    search?: string;
  }): Promise<ApiResponse<ApiSupplier[]>> => {
    const query = new URLSearchParams();
    if (params?.status) query.set("status", params.status);
    if (params?.search) query.set("search", params.search);
    const qs = query.toString();
    return request<ApiResponse<ApiSupplier[]>>(`/suppliers${qs ? `?${qs}` : ""}`);
  },

  getById: async (id: number): Promise<ApiResponse<ApiSupplier>> => {
    return request<ApiResponse<ApiSupplier>>(`/suppliers/${id}`);
  },

  create: async (data: {
    code?: string;
    name: string;
    contact_name: string;
    email: string;
    phone?: string;
    address?: string;
    city?: string;
    country?: string;
    tax_id?: string;
    payment_terms?: string;
    lead_time_days?: number;
    status?: string;
    notes?: string;
  }): Promise<ApiResponse<ApiSupplier>> => {
    return request<ApiResponse<ApiSupplier>>("/suppliers", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  update: async (
    id: number,
    data: Partial<{
      code: string;
      name: string;
      contact_name: string;
      email: string;
      phone: string;
      address: string;
      city: string;
      country: string;
      tax_id: string;
      payment_terms: string;
      lead_time_days: number;
      status: string;
      notes: string;
    }>
  ): Promise<ApiResponse<ApiSupplier>> => {
    return request<ApiResponse<ApiSupplier>>(`/suppliers/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },

  delete: async (id: number): Promise<ApiResponse<null>> => {
    return request<ApiResponse<null>>(`/suppliers/${id}`, {
      method: "DELETE",
    });
  },
};

// ==========================================
// MULTI-WAREHOUSE INVENTORY & LEDGER API
// ==========================================

export interface ApiWarehouse {
  id: number;
  code: string;
  name: string;
  location?: string | null;
  address?: string | null;
  contact_name?: string | null;
  contact_phone?: string | null;
  is_default: boolean;
  is_active: boolean;
  total_units: number;
  sku_count: number;
  created_at: string;
  updated_at: string;
}

export interface ApiWarehouseStock {
  id: number;
  warehouse_id: number;
  warehouse_code: string;
  warehouse_name: string;
  product_id: number;
  product_name: string;
  product_price: number;
  product_is_active: boolean;
  quantity: number;
  reserved_quantity: number;
  reorder_point: number;
  updated_at: string;
}

export interface ApiInventoryLedgerLine {
  id: number;
  journal_entry_id: number;
  product_id: number;
  product_name: string;
  warehouse_id?: number | null;
  warehouse_name?: string | null;
  account_type: string;
  debit_qty: number;
  credit_qty: number;
  unit_cost: number;
  balance_after?: number | null;
  created_at: string;
}

export interface ApiInventoryJournalEntry {
  id: number;
  entry_number: string;
  entry_type: string;
  reference_type?: string | null;
  reference_id?: number | null;
  reason?: string | null;
  created_by_user_id?: number | null;
  created_at: string;
  lines: ApiInventoryLedgerLine[];
}

export interface ApiInventoryLedgerTrialBalance {
  total_debits: number;
  total_credits: number;
  balanced: boolean;
  total_entries: number;
}

export interface ApiInventoryLedgerResponse {
  entries: ApiInventoryJournalEntry[];
  trial_balance: ApiInventoryLedgerTrialBalance;
  total: number;
  page: number;
  limit: number;
}

export interface ApiPurchaseOrderItem {
  id: number;
  purchase_order_id: number;
  product_id?: number | null;
  product_name: string;
  quantity_ordered: number;
  quantity_received: number;
  unit_cost: number;
  line_total: number;
}

export interface ApiPurchaseOrder {
  id: number;
  po_number: string;
  supplier_id: number;
  supplier_name?: string | null;
  warehouse_id: number;
  warehouse_name?: string | null;
  status: string;
  total_cost: number;
  expected_at?: string | null;
  ordered_at?: string | null;
  received_at?: string | null;
  notes?: string | null;
  created_by_user_id?: number | null;
  created_at: string;
  updated_at: string;
  items: ApiPurchaseOrderItem[];
}

export interface ApiWarehouseTransferItem {
  id: number;
  transfer_id: number;
  product_id?: number | null;
  product_name: string;
  quantity: number;
}

export interface ApiWarehouseTransfer {
  id: number;
  transfer_number: string;
  source_warehouse_id: number;
  source_warehouse_name?: string | null;
  destination_warehouse_id: number;
  destination_warehouse_name?: string | null;
  status: string;
  notes?: string | null;
  created_by_user_id?: number | null;
  dispatched_at?: string | null;
  completed_at?: string | null;
  created_at: string;
  updated_at: string;
  items: ApiWarehouseTransferItem[];
}

export const inventoryApi = {
  getWarehouses: async (): Promise<ApiResponse<ApiWarehouse[]>> => {
    return request<ApiResponse<ApiWarehouse[]>>("/inventory/warehouses");
  },

  createWarehouse: async (data: {
    code: string;
    name: string;
    location?: string;
    address?: string;
    contact_name?: string;
    contact_phone?: string;
    is_default?: boolean;
    is_active?: boolean;
  }): Promise<ApiResponse<ApiWarehouse>> => {
    return request<ApiResponse<ApiWarehouse>>("/inventory/warehouses", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  updateWarehouse: async (
    id: number,
    data: Partial<{
      code: string;
      name: string;
      location: string;
      address: string;
      contact_name: string;
      contact_phone: string;
      is_default: boolean;
      is_active: boolean;
    }>
  ): Promise<ApiResponse<ApiWarehouse>> => {
    return request<ApiResponse<ApiWarehouse>>(`/inventory/warehouses/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },

  getStocks: async (params?: {
    warehouse_id?: number;
    product_id?: number;
  }): Promise<ApiResponse<ApiWarehouseStock[]>> => {
    const query = new URLSearchParams();
    if (params?.warehouse_id) query.set("warehouse_id", String(params.warehouse_id));
    if (params?.product_id) query.set("product_id", String(params.product_id));
    const qs = query.toString();
    return request<ApiResponse<ApiWarehouseStock[]>>(
      `/inventory/stocks${qs ? `?${qs}` : ""}`
    );
  },

  getProductStocks: async (productId: number): Promise<ApiResponse<ApiWarehouseStock[]>> => {
    return request<ApiResponse<ApiWarehouseStock[]>>(
      `/inventory/products/${productId}/stocks`
    );
  },

  createAdjustment: async (data: {
    product_id: number;
    warehouse_id?: number;
    quantity_delta: number;
    reason: string;
    unit_cost?: number;
  }): Promise<ApiResponse<ApiInventoryJournalEntry>> => {
    return request<ApiResponse<ApiInventoryJournalEntry>>("/inventory/adjustments", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  getLedger: async (params?: {
    product_id?: number;
    warehouse_id?: number;
    entry_type?: string;
    page?: number;
    limit?: number;
  }): Promise<ApiResponse<ApiInventoryLedgerResponse>> => {
    const query = new URLSearchParams();
    if (params?.product_id) query.set("product_id", String(params.product_id));
    if (params?.warehouse_id) query.set("warehouse_id", String(params.warehouse_id));
    if (params?.entry_type) query.set("entry_type", params.entry_type);
    if (params?.page) query.set("page", String(params.page));
    if (params?.limit) query.set("limit", String(params.limit));
    const qs = query.toString();
    return request<ApiResponse<ApiInventoryLedgerResponse>>(
      `/inventory/ledger${qs ? `?${qs}` : ""}`
    );
  },

  getPurchaseOrders: async (status?: string): Promise<ApiResponse<ApiPurchaseOrder[]>> => {
    const qs = status ? `?status=${encodeURIComponent(status)}` : "";
    return request<ApiResponse<ApiPurchaseOrder[]>>(`/inventory/purchase-orders${qs}`);
  },

  createPurchaseOrder: async (data: {
    supplier_id: number;
    warehouse_id: number;
    expected_at?: string;
    notes?: string;
    items: Array<{ product_id: number; quantity_ordered: number; unit_cost: number }>;
  }): Promise<ApiResponse<ApiPurchaseOrder>> => {
    return request<ApiResponse<ApiPurchaseOrder>>("/inventory/purchase-orders", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  orderPurchaseOrder: async (id: number): Promise<ApiResponse<ApiPurchaseOrder>> => {
    return request<ApiResponse<ApiPurchaseOrder>>(`/inventory/purchase-orders/${id}/order`, {
      method: "POST",
    });
  },

  receivePurchaseOrder: async (
    id: number,
    data?: {
      items?: Array<{ item_id: number; quantity_received: number }>;
      notes?: string;
    }
  ): Promise<ApiResponse<ApiPurchaseOrder>> => {
    return request<ApiResponse<ApiPurchaseOrder>>(`/inventory/purchase-orders/${id}/receive`, {
      method: "POST",
      body: JSON.stringify(data || {}),
    });
  },

  cancelPurchaseOrder: async (id: number): Promise<ApiResponse<ApiPurchaseOrder>> => {
    return request<ApiResponse<ApiPurchaseOrder>>(`/inventory/purchase-orders/${id}/cancel`, {
      method: "POST",
    });
  },

  getTransfers: async (status?: string): Promise<ApiResponse<ApiWarehouseTransfer[]>> => {
    const qs = status ? `?status=${encodeURIComponent(status)}` : "";
    return request<ApiResponse<ApiWarehouseTransfer[]>>(`/inventory/transfers${qs}`);
  },

  createTransfer: async (data: {
    source_warehouse_id: number;
    destination_warehouse_id: number;
    notes?: string;
    items: Array<{ product_id: number; quantity: number }>;
  }): Promise<ApiResponse<ApiWarehouseTransfer>> => {
    return request<ApiResponse<ApiWarehouseTransfer>>("/inventory/transfers", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  dispatchTransfer: async (id: number): Promise<ApiResponse<ApiWarehouseTransfer>> => {
    return request<ApiResponse<ApiWarehouseTransfer>>(`/inventory/transfers/${id}/dispatch`, {
      method: "POST",
    });
  },

  completeTransfer: async (id: number): Promise<ApiResponse<ApiWarehouseTransfer>> => {
    return request<ApiResponse<ApiWarehouseTransfer>>(`/inventory/transfers/${id}/complete`, {
      method: "POST",
    });
  },

  cancelTransfer: async (id: number): Promise<ApiResponse<ApiWarehouseTransfer>> => {
    return request<ApiResponse<ApiWarehouseTransfer>>(`/inventory/transfers/${id}/cancel`, {
      method: "POST",
    });
  },
};

// ==========================================
// DEDICATED REFUNDS & ACCOUNTING LEDGER API
// ==========================================

export interface ApiRefundLedgerEntry {
  id: number;
  journal_ref: string;
  refund_id: number;
  order_id: number;
  entry_type: string;
  account_code: string;
  account_name: string;
  debit_amount: number;
  credit_amount: number;
  currency: string;
  memo?: string | null;
  created_by_user_id?: number | null;
  created_at: string;
}

export interface ApiRefund {
  id: number;
  refund_number: string;
  order_id: number;
  customer_id?: number | null;
  customer_name?: string | null;
  customer_email?: string | null;
  order_total?: number | null;
  order_status?: string | null;
  order_payment_status?: string | null;
  amount: number;
  currency: string;
  refund_method: string;
  status: string;
  reason: string;
  notes?: string | null;
  restock_items: boolean;
  restocked: boolean;
  warehouse_id?: number | null;
  external_reference?: string | null;
  requested_at: string;
  approved_at?: string | null;
  processed_at?: string | null;
  created_at: string;
  updated_at: string;
  ledger_entries: ApiRefundLedgerEntry[];
}

export interface ApiRefundAccountBalance {
  account_code: string;
  account_name: string;
  total_debits: number;
  total_credits: number;
  net_balance: number;
}

export interface ApiRefundLedgerTrialBalance {
  total_debits: number;
  total_credits: number;
  balanced: boolean;
  accounts: ApiRefundAccountBalance[];
}

export interface ApiRefundLedgerResponse {
  entries: ApiRefundLedgerEntry[];
  trial_balance: ApiRefundLedgerTrialBalance;
  total: number;
  page: number;
  limit: number;
}

export const refundsApi = {
  getAll: async (params?: {
    status?: string;
    search?: string;
    order_id?: number;
  }): Promise<ApiResponse<ApiRefund[]>> => {
    const query = new URLSearchParams();
    if (params?.status) query.set("status", params.status);
    if (params?.search) query.set("search", params.search);
    if (params?.order_id) query.set("order_id", String(params.order_id));
    const qs = query.toString();
    return request<ApiResponse<ApiRefund[]>>(`/refunds${qs ? `?${qs}` : ""}`);
  },

  getById: async (identifier: string | number): Promise<ApiResponse<ApiRefund>> => {
    return request<ApiResponse<ApiRefund>>(
      `/refunds/${encodeURIComponent(String(identifier))}`
    );
  },

  create: async (data: {
    order_id: number;
    amount?: number;
    refund_method?: string;
    reason: string;
    notes?: string;
    restock_items?: boolean;
    warehouse_id?: number;
  }): Promise<ApiResponse<ApiRefund>> => {
    return request<ApiResponse<ApiRefund>>("/refunds", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  approve: async (
    identifier: string | number,
    data?: { notes?: string }
  ): Promise<ApiResponse<ApiRefund>> => {
    return request<ApiResponse<ApiRefund>>(
      `/refunds/${encodeURIComponent(String(identifier))}/approve`,
      {
        method: "POST",
        body: JSON.stringify(data || {}),
      }
    );
  },

  process: async (
    identifier: string | number,
    data?: {
      external_reference?: string;
      restock_items?: boolean;
      warehouse_id?: number;
      notes?: string;
    }
  ): Promise<ApiResponse<ApiRefund>> => {
    return request<ApiResponse<ApiRefund>>(
      `/refunds/${encodeURIComponent(String(identifier))}/process`,
      {
        method: "POST",
        body: JSON.stringify(data || {}),
      }
    );
  },

  reject: async (
    identifier: string | number,
    data: { reason: string }
  ): Promise<ApiResponse<ApiRefund>> => {
    return request<ApiResponse<ApiRefund>>(
      `/refunds/${encodeURIComponent(String(identifier))}/reject`,
      {
        method: "POST",
        body: JSON.stringify(data),
      }
    );
  },

  getLedger: async (params?: {
    refund_id?: number;
    account_code?: string;
    page?: number;
    limit?: number;
  }): Promise<ApiResponse<ApiRefundLedgerResponse>> => {
    const query = new URLSearchParams();
    if (params?.refund_id) query.set("refund_id", String(params.refund_id));
    if (params?.account_code) query.set("account_code", params.account_code);
    if (params?.page) query.set("page", String(params.page));
    if (params?.limit) query.set("limit", String(params.limit));
    const qs = query.toString();
    return request<ApiResponse<ApiRefundLedgerResponse>>(
      `/refunds/ledger${qs ? `?${qs}` : ""}`
    );
  },
};

// ==========================================
// ADMINISTRATIVE REPORTING API
// ==========================================

export interface ApiPaymentMethodBreakdown {
  payment_method: string;
  orders_count: number;
  gross_amount: number;
}

export interface ApiDailyTrendPoint {
  date: string;
  orders_count: number;
  gross_revenue: number;
  refunds_total: number;
  net_revenue: number;
}

export interface ApiExecutiveReport {
  days: number;
  gross_paid_revenue: number;
  settled_refunds_total: number;
  pending_refund_liability: number;
  net_revenue: number;
  total_orders: number;
  paid_orders_count: number;
  cancelled_orders_count: number;
  average_order_value: number;
  payment_method_breakdown: ApiPaymentMethodBreakdown[];
  daily_trend: ApiDailyTrendPoint[];
}

export interface ApiWarehouseInventorySummary {
  warehouse_id: number;
  warehouse_code: string;
  warehouse_name: string;
  is_default: boolean;
  sku_count: number;
  total_units: number;
  low_stock_skus: number;
  out_of_stock_skus: number;
  retail_valuation: number;
}

export interface ApiInventoryReport {
  total_products: number;
  total_warehouses: number;
  total_on_hand_units: number;
  total_retail_valuation: number;
  total_po_cost_committed: number;
  open_purchase_orders_count: number;
  in_transit_transfers_count: number;
  ledger_total_debits: number;
  ledger_total_credits: number;
  ledger_balanced: boolean;
  warehouses: ApiWarehouseInventorySummary[];
}

export const reportsApi = {
  getExecutive: async (days: number = 30): Promise<ApiResponse<ApiExecutiveReport>> => {
    return request<ApiResponse<ApiExecutiveReport>>(`/reports/executive?days=${days}`);
  },

  getInventory: async (): Promise<ApiResponse<ApiInventoryReport>> => {
    return request<ApiResponse<ApiInventoryReport>>("/reports/inventory");
  },

  downloadLedgerCsv: async (ledger: "inventory" | "refunds"): Promise<string> => {
    const token = getAccessToken();
    const res = await fetch(
      `${API_BASE_URL}/reports/ledger-export?ledger=${encodeURIComponent(ledger)}`,
      {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      }
    );
    if (!res.ok) {
      throw new Error(`Failed to export ${ledger} ledger (${res.status}).`);
    }
    return res.text();
  },
};




