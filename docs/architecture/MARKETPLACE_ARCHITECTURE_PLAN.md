# Blue Panda Multi-Vendor Marketplace Architecture Plan

**Document Version:** 1.0.0  
**Phase:** Phase A — Read-Only Architecture Audit & Implementation Plan  
**Target Date:** 2026-10-31  
**Status:** Completed Audit — Awaiting User Approval to Proceed to Phase B  

---

## 1. Executive Summary

Blue Panda E-Commerce is currently a functional full-stack multi-client application featuring:
- **FastAPI backend** with synchronous SQLAlchemy 2, Alembic migrations, PostgreSQL 16, JWT authentication, and database-enforced RBAC.
- **Next.js 16 App Router customer storefront** in `web-app/src/app/(store)` with active product browsing, search, shopping cart, server-confirmed checkout, and order history.
- **Next.js 16 admin dashboard** in `web-app/src/app/(admin)/admin` sharing UI layouts between platform admins and sellers.
- **Flutter mobile app** consuming `/api/v1` endpoints with typed models and providers.

This audit establishes the concrete architectural path to transition Blue Panda from a monolithic retail system with mixed admin/seller layouts into a **multi-vendor marketplace** offering three strictly segregated experiences:
1. **Customer Storefront** (`shop.bluepanda.com` / `web-app/src/app/(store)/`)
2. **Platform Admin Dashboard** (`admin.bluepanda.com` / `web-app/src/app/(admin)/admin/`)
3. **Seller Center** (`seller.bluepanda.com` / `web-app/src/app/(seller)/seller/`)

---

## 2. Current Architecture (Verified State)

### 2.1 Backend Architecture (`backend/`)
- **FastAPI Routing**: Exposed simultaneously under `/api` (used by web) and `/api/v1` (used by mobile).
- **Authentication**: JWT bearer tokens containing `sub` (user email) and claims. `get_current_user` loads active database user; `require_roles(*roles)` inspects `user.role`.
- **Database Layer**: SQLAlchemy 2 models mapped to PostgreSQL (`users`, `sellers`, `products`, `orders`, `order_items`, `categories`, `coupons`, `reviews`, `cart_items`, `addresses`).
- **Product Ownership**: `Product.seller_id` is a foreign key to `sellers.id`. When creating or modifying products, `AuthorizationService.require_seller(db, current_user)` ensures sellers can only manipulate products linked to their own store. Admins have platform-wide access.
- **Order Model**: Monolithic `Order` table linked to `OrderItem` rows. `OrderItem.product_id` references `Product`. Order status transitions are controlled by a state machine in `OrderService.update_order_status`.
- **Stock Service**: `InventoryService.atomic_deduct_and_verify` locks rows (`with_for_update`) during checkout to prevent overselling.

### 2.2 Web Architecture (`web-app/`)
- **Framework**: Next.js 16.3.4 (Turbopack / App Router), React 19, TypeScript strict mode, Tailwind CSS 4.
- **Storefront Route Group**: `web-app/src/app/(store)/` containing:
  - `/` (Home), `/shop` (Catalog), `/categories`, `/deals`, `/stores` (Seller directory), `/product/[id]` (Detail), `/cart`, `/checkout`, `/wishlist`, `/orders`, `/account`.
- **Admin Route Group**: `web-app/src/app/(admin)/admin/` containing:
  - `/admin/dashboard`, `/admin/products`, `/admin/orders`, `/admin/inventory`, `/admin/categories`, `/admin/sellers`, `/admin/customers`, `/admin/reviews`, `/admin/coupons`, `/admin/pos`, `/admin/analytics`, `/admin/settings`.
- **Auth Routes**: `web-app/src/app/(auth)/login` and `web-app/src/app/(auth)/register`.
- **Client State**: Zustand for cart and wishlist sync; `localStorage` for JWT tokens (`panda_access_token`, `panda_user`).

### 2.3 Mobile Architecture (`mobile-app/`)
- **Flutter / Dart**: Material 3 UI with Provider / ChangeNotifier state management.
- **API Client**: Singleton `ApiClient` with baseUrl defaulting to `http://localhost:8000/api/v1`.
- **Features**: Authentication, catalog browsing, cart, checkout, order tracking, and profile management.

---

## 3. Gap Analysis & Vulnerabilities

| Component / Domain | Current State | Target Marketplace State | Architectural Gap |
| :--- | :--- | :--- | :--- |
| **Frontend Seller Portal** | No `/seller` route exists. Sellers are routed to `/admin/*`. | Dedicated `(seller)` route group (`/seller/*`) with its own layout, branding, and navigation. | **Critical UI Bleed**: Sellers see admin menus and routes; routes fail with 403 Forbidden. |
| **Seller Navigation & Stats** | `AdminSidebar.tsx` polls `statsApi.getOverview()` (`/stats/overview`). | Seller sidebar polls seller-scoped metrics (`/api/v1/seller/stats`). | **Permission Failure**: Admin stats API rejects sellers (`403 Forbidden`), filling logs with network errors. |
| **Seller Profile Management** | Only admin can call `POST/PUT /sellers/{id}`. | Seller can query `GET /api/v1/seller/me` and update store info via `PUT /api/v1/seller/me`. | **Missing Self-Service**: Sellers cannot update store name, logo, phone, or description without admin intervention. |
| **Seller Orders Endpoint** | No endpoint exists for sellers to retrieve orders containing their items. | `GET /api/v1/seller/orders` returns orders filtered strictly to items sold by the authenticated seller. | **Blocker**: Sellers cannot see or fulfill orders containing their products. |
| **Multi-Vendor Order Fulfillment** | Monolithic order fulfillment blocks status update if order contains items from other sellers (`any(item.seller_id != seller.id)`). | Order state machine supports multi-vendor fulfillment (item-level status or sub-orders per seller). | **Blocker**: In mixed checkouts, sellers cannot fulfill their items because of all-or-nothing check. |
| **Seller Inventory View** | `/admin/inventory` loads platform-wide stock. | `/seller/inventory` loads stock scoped to `seller_id` with quick-adjust actions. | **Data Leak / Authorization**: Sellers cannot view or adjust their own stock securely without admin rights. |
| **Seller Sales Analytics** | `/admin/analytics` and `/stats/overview` require admin role. | Dedicated `GET /api/v1/seller/analytics` calculates revenue, order volume, and top products for the seller. | **Missing Feature**: Sellers have zero visibility into their store performance. |
| **Storefront Seller Profile** | `/stores` lists active sellers, but `/stores/[id]` or `/shop?seller=X` lacks rich vendor branding. | Public vendor storefront page showing store banner, rating, verified badge, policy, and catalog. | **UX Gap**: Customers cannot easily browse a specific vendor's products. |

---

## 4. Target Architecture

```
                                  +------------------------------------+
                                  |         DNS / Ingress Proxy        |
                                  +-----------------+------------------+
                                                    |
                   +--------------------------------+-------------------------------+
                   |                                |                                |
                   v                                v                                v
       [ shop.bluepanda.com ]             [ admin.bluepanda.com ]          [ seller.bluepanda.com ]
       Customer Storefront                Platform Admin Center            Seller Center
       Next.js (store) Routes             Next.js (admin) Routes           Next.js (seller) Routes
       Role: Public / Customer            Role: admin, staff               Role: seller
                   |                                |                                |
                   +--------------------------------+--------------------------------+
                                                    |
                                                    v
                                      +----------------------------+
                                      |    FastAPI REST Backend    |
                                      |    /api and /api/v1        |
                                      +--------------+-------------+
                                                     |
                                                     v
                                      +----------------------------+
                                      |   PostgreSQL 16 Database   |
                                      |   Row-Level Tenant Scoping |
                                      +----------------------------+
```

### 4.1 Client Segregation Strategy
To avoid disrupting existing working customer and admin routes, the target architecture will be realized **incrementally within `web-app/`** using Next.js App Router route groups:
1. `(store)`: Customer storefront routes (`/`, `/shop`, `/product/[id]`, `/cart`, `/checkout`, `/account`).
2. `(admin)`: Platform administrative routes (`/admin/*`). Access strictly guarded for `admin` role.
3. `(seller)`: Dedicated Seller Center routes (`/seller/*`). Access strictly guarded for `seller` role.
4. `(auth)`: Shared authentication routes (`/login`, `/register`). Automatically redirects users to their appropriate portal post-login:
   - `admin` -> `/admin/dashboard`
   - `seller` -> `/seller/dashboard`
   - `customer` -> `/account` or `/shop`

Once route separation is fully verified and stabilized, a future extraction into a Turborepo monorepo (`apps/storefront`, `apps/management`) can be performed cleanly without code breakage.

---

## 5. Feature Inventory

### A. Customer Storefront (`web-app/src/app/(store)`)
- **Catalog & Discovery**: Home hero banners, category showcase, product grid, sorting, price/category filters.
- **Search**: Dynamic instant search across active products.
- **Seller Storefront**: Browse individual seller stores (`/stores/[id]`).
- **Cart & Wishlist**: Optimistic local storage synchronized with user account on login.
- **Checkout & COD**: Real-time shipping calculation, coupon validation, Cash on Delivery (COD), order creation.
- **Customer Account**: Profile editing, saved addresses, order tracking with real-time status indicators.
- **Product Reviews**: Submit reviews with ratings, view verified buyer badges and admin replies.

### B. Platform Admin Dashboard (`web-app/src/app/(admin)/admin`)
- **Executive Dashboard**: Platform GMV, total revenue, platform order count, new seller registrations.
- **Seller Management**: Approve pending sellers, suspend offending stores, view store details.
- **Product Moderation**: Inspect all platform products, toggle active/featured status, category management.
- **Order Administration**: Full platform order view, payment verification, fulfillment overrides, refund handling.
- **Customer Oversight**: View registered customers, manage account status and permissions.
- **Promotion & Coupons**: Create global coupons, percentage/fixed discounts, redemption limit controls.
- **Point of Sale (POS)**: In-person quick barcode scanning, order creation, cash register reconciliation.
- **Platform Audit & Security**: Monitor admin actions, failed logins, system health.

### C. Seller Center (`web-app/src/app/(seller)/seller`)
- **Seller Dashboard (`/seller`)**:
  - Live revenue ticker, pending orders badge, total active products, store customer rating.
  - Recent order list with direct fulfillment shortcuts.
- **Product Management (`/seller/products`)**:
  - Filterable product table (all, active, draft, out-of-stock).
  - Add Product wizard (`/seller/products/new`) with secure image upload, category selection, price & discount inputs.
  - Edit Product (`/seller/products/[id]/edit`) with strict backend ownership enforcement.
- **Order Fulfillment (`/seller/orders`)**:
  - View incoming orders containing the seller's items.
  - Advance status (`processing` -> `shipped`).
  - Print packing slips / order summary.
- **Stock & Inventory (`/seller/inventory`)**:
  - Low-stock alerts, out-of-stock indicators.
  - Inline stock quantity update with optimistic rollback.
- **Store Profile (`/seller/store`)**:
  - Update store banner, store logo, customer service phone, store bio, physical address.
- **Sales Analytics (`/seller/analytics`)**:
  - Revenue by day/week/month, top-selling products, fulfillment speed metrics.
- **Seller Settings (`/seller/settings`)**:
  - Notification preferences, business registration information, payout bank details (display/record).

---

## 6. Recommended Folder Structure

```text
web-app/src/
├── app/
│   ├── (auth)/
│   │   ├── login/page.tsx
│   │   └── register/page.tsx
│   ├── (store)/                     # Public & Customer Experience
│   │   ├── layout.tsx               # Storefront Header, Nav, Footer
│   │   ├── page.tsx                 # Home Page
│   │   ├── shop/page.tsx
│   │   ├── categories/page.tsx
│   │   ├── stores/
│   │   │   ├── page.tsx             # All sellers directory
│   │   │   └── [id]/page.tsx        # Public seller storefront page
│   │   ├── product/[id]/page.tsx
│   │   ├── cart/page.tsx
│   │   ├── checkout/page.tsx
│   │   ├── orders/page.tsx
│   │   └── account/page.tsx
│   ├── (admin)/                     # Admin Back-Office Experience
│   │   └── admin/
│   │       ├── layout.tsx           # AdminLayout (strictly admin role)
│   │       ├── dashboard/page.tsx
│   │       ├── products/page.tsx
│   │       ├── orders/page.tsx
│   │       ├── sellers/page.tsx
│   │       ├── customers/page.tsx
│   │       ├── inventory/page.tsx
│   │       ├── categories/page.tsx
│   │       ├── coupons/page.tsx
│   │       ├── reviews/page.tsx
│   │       ├── pos/page.tsx
│   │       └── settings/page.tsx
│   └── (seller)/                    # Dedicated Seller Center Experience
│       └── seller/
│           ├── layout.tsx           # SellerLayout (strictly seller role)
│           ├── page.tsx             # Seller Dashboard overview
│           ├── products/
│           │   ├── page.tsx         # Seller's products list
│           │   ├── new/page.tsx     # Add product form
│           │   └── [id]/edit/page.tsx # Edit product form
│           ├── orders/
│           │   ├── page.tsx         # Orders containing seller items
│           │   └── [id]/page.tsx    # Order detail & fulfillment
│           ├── inventory/page.tsx   # Stock tracking & fast adjustments
│           ├── analytics/page.tsx   # Store performance metrics
│           ├── store/page.tsx       # Store branding & profile
│           └── settings/page.tsx    # Seller operational settings
├── components/
│   ├── store/                       # Customer storefront components
│   ├── admin/                       # Admin management components
│   ├── seller/                      # Seller Center components
│   │   ├── SellerSidebar.tsx        # Seller navigation sidebar
│   │   ├── SellerNavbar.tsx         # Seller topbar (store selector, notifications)
│   │   ├── SellerMetricCard.tsx
│   │   ├── SellerProductTable.tsx
│   │   └── SellerOrderTable.tsx
│   └── shared/                      # Shared design system components
│       ├── Button.tsx
│       ├── Modal.tsx
│       ├── Table.tsx
│       ├── Input.tsx
│       └── Badge.tsx
```

---

## 7. API Integration Requirements

To empower the Seller Center without compromising security, the following backend endpoints must be added to FastAPI (`backend/app/api/v1/`):

### 7.1 Seller Profile & Settings API (`/api/v1/seller/me`)
- `GET /api/v1/seller/me`: Returns the authenticated seller's store profile, status (`Active`/`Pending`/`Suspended`), metrics, and settings.
- `PUT /api/v1/seller/me`: Allows the seller to update their own store name, phone, address, description, and logo. Rejects modifications to `status`, `rating`, or `user_id`.

### 7.2 Seller Products API (`/api/v1/seller/products`)
- `GET /api/v1/seller/products`: Returns products belonging strictly to the current seller's store ID (`seller_id == user.seller.id`). Supports pagination, status filtering (`is_active`), and stock status.
- `POST /api/v1/products`: Already implemented; persists product with the caller's `seller_id`.
- `PUT /api/v1/products/{id}`: Already verifies seller ownership through `AuthorizationService.require_product`.

### 7.3 Seller Orders API (`/api/v1/seller/orders`)
- `GET /api/v1/seller/orders`: Queries orders containing at least one item from the seller's store. Returns sanitized order records containing:
  - Order ID, date, status, payment status.
  - Shipping recipient name and masked address (for privacy).
  - List of `OrderItem` records belonging *strictly* to the calling seller (hiding items from other vendors in multi-vendor checkouts).
  - Total calculated for the seller's items.
- `PUT /api/v1/orders/{order_id}/status`: Refined to allow seller fulfillment updates on multi-vendor orders for the seller's portion.

### 7.4 Seller Stock / Inventory API (`/api/v1/seller/inventory`)
- `GET /api/v1/seller/inventory`: List products with low stock, out of stock, and stock levels.
- `PATCH /api/v1/seller/inventory/{product_id}`: Rapid inline stock update with verification.

### 7.5 Seller Analytics API (`/api/v1/seller/stats`)
- `GET /api/v1/seller/stats`: Returns:
  - `total_revenue`: Sum of item subtotals for completed/paid orders belonging to this seller.
  - `pending_orders`: Count of orders requiring fulfillment.
  - `total_products`: Total product count.
  - `low_stock_count`: Items with stock <= 5.
  - `recent_sales`: Daily revenue data points for charting.

---

## 8. Security Requirements

1. **Role Separation & Route Protection**:
   - `admin` role has platform oversight but cannot pose as a seller without explicit audit trail.
   - `seller` role is strictly restricted to `/seller/*`. Navigating to `/admin/*` triggers immediate 403 / redirect to `/seller`.
   - `customer` role cannot access `/admin/*` or `/seller/*`.
   - Client-side navigation guards must be backed by 100% server-side token and role enforcement.

2. **Multi-Tenant Data Isolation**:
   - A seller must never see another seller's products, cost data, order items, or customer PII.
   - All seller queries must be parameterized by `seller_id` extracted from the authenticated user's database record, **never** from request body or query parameters supplied by the client.

3. **Multi-Vendor Order Privacy**:
   - When customer places an order containing items from Seller A and Seller B:
     - Seller A only sees Seller A's items and item subtotals.
     - Seller B only sees Seller B's items and item subtotals.
     - Neither seller sees the total basket size or items purchased from competitors.

4. **Upload Validation**:
   - Product and store images must follow the strict Phase 1 MIME-type, extension, and file size magic-byte validation.

5. **Inventory Concurrency**:
   - Seller stock updates must execute inside transactions with row locking (`with_for_update`) to prevent race conditions during active customer checkouts.

---

## 9. Implementation Phases

```
  Phase A: Read-Only Audit & Blueprint (Current)
     |
     v
  Phase B: Admin & Seller Role Separation (Web Layouts & Route Guards)
     |
     v
  Phase C: Seller Center UI Construction (/seller/* pages)
     |
     v
  Phase D: Backend Seller APIs & Database Scoping (FastAPI endpoints)
     |
     v
  Phase E: Admin Marketplace Oversight (Approvals, Moderation, Monitoring)
     |
     v
  Phase F: End-to-End Multi-Vendor Customer Flow Verification
     |
     v
  Phase G: Docker Development Orchestration & Handoff
```

- **Phase B**: Separate admin and seller layouts. Build `web-app/src/app/(seller)/seller/layout.tsx`. Remove seller links from `AdminSidebar.tsx`. Add role-based post-login redirection.
- **Phase C**: Construct `/seller` dashboard, `/seller/products`, `/seller/products/new`, `/seller/orders`, `/seller/inventory`, `/seller/store`, and `/seller/analytics`.
- **Phase D**: Implement FastAPI seller routes (`/seller/me`, `/seller/orders`, `/seller/inventory`, `/seller/stats`), update `web-app/src/lib/api.ts`, and wire components to live backend.
- **Phase E**: Enhance Admin panel: seller approval workflow, vendor suspension toggle, store fee/commission tracking.
- **Phase F**: Run full integration test: Admin approves Seller -> Seller uploads Product -> Customer purchases Product via COD -> Stock deducts -> Seller ships order -> Customer reviews order.
- **Phase G**: Verify Docker Compose operation across web, backend, and PostgreSQL with zero data loss.

---

## 10. Risks & Compatibility Concerns

1. **Monolithic Orders in Database**:
   - *Risk*: Modifying the `Order` model to support multi-vendor order items could break existing checkout and mobile app order history.
   - *Mitigation*: Maintain the root `Order` and `OrderItem` schema. Add a `seller_id` reference to `OrderItem` (or resolve via `OrderItem.product_id -> Product.seller_id`). Seller order endpoints return filtered item slices without altering customer-facing order response shapes.
2. **Mobile App API Compatibility**:
   - *Risk*: Mobile app currently calls `/api/v1/orders` and `/api/v1/products`.
   - *Mitigation*: Do not change the existing response contracts of `/api/v1/products` or `/api/v1/orders`. All new seller capabilities will be placed under new `/api/v1/seller/*` sub-routes.
3. **Session State Desynchronization**:
   - *Risk*: Changing user roles on the backend does not invalidate cached JWT tokens in browser `localStorage`.
   - *Mitigation*: Provide token refresh mechanism or check `me` endpoint on navigation to ensure active role changes are respected immediately.

---

## 11. Verification & Test Plan

1. **Role Authorization Tests (`backend/tests/test_seller_authorization.py`)**:
   - Customer token accessing `/seller/*` endpoints -> 403 Forbidden.
   - Seller token accessing `/admin/*` endpoints -> 403 Forbidden.
   - Seller A attempting to update Seller B's product -> 403 Forbidden.
   - Seller A attempting to read Seller B's order items -> 403 Forbidden or empty list.
2. **Order Fulfillment Tests (`backend/tests/test_seller_order_fulfillment.py`)**:
   - Single-vendor order status progression (`pending` -> `processing` -> `shipped`).
   - Multi-vendor order protection: Seller cannot alter items outside their store.
3. **Frontend Compilation & Lint Verification**:
   - `rtk npm run lint` in `web-app/`: 0 warnings, 0 errors.
   - `rtk npm run build` in `web-app/`: clean Next.js static and dynamic route compilation.
4. **Mobile Verification**:
   - `rtk flutter analyze`: 0 errors.
   - `rtk flutter test`: verify existing mobile test suite passes without regressions.

---

## 12. Recommended First Implementation Task

**Task B.1: Create Dedicated Seller Route Group & Segregate Layouts**
1. Create `web-app/src/app/(seller)/seller/layout.tsx` with dedicated `SellerLayout` and `SellerSidebar`.
2. Restrict `web-app/src/app/(admin)/admin/layout.tsx` exclusively to `user.role === "admin"`.
3. Remove seller menu items and the failing `statsApi.getOverview()` call from `AdminSidebar.tsx`.
4. Update login redirect logic in `web-app/src/app/(auth)/login/page.tsx` and auth helpers so sellers land on `/seller` and admins land on `/admin/dashboard`.
5. Verify clean Next.js build (`npm run build`).

---

*Phase A Read-Only Audit is complete. Awaiting user instruction to begin Phase B.*
