# BLUE PANDA E-COMMERCE — COMPLETE PROJECT ANALYSIS & TECHNICAL AUDIT

> **Audit Date:** 2026-11-14  
> **Audit Mode:** Strictly Read-Only Analysis & Safe Isolated Quality Verification (Zero application code, database, or deployment mutations performed)  
> **Audited Workspace:** `/Users/bunvathana/Documents/Code/Project/e-commerce`

---

## 1. Executive Summary

**Blue Panda E-Commerce** is a multi-client marketplace platform comprising a **FastAPI + SQLAlchemy 2 + Alembic** backend (`backend/`), a **Next.js 16 Customer Storefront** (`storefront/`), a **Next.js 16 Admin & Seller Management Portal** (`management/`), a **Flutter/Dart Mobile App** (`mobile-app/`), a legacy combined web repository (`web-app/`), and **PostgreSQL** (hosted on **Supabase** in production and **PostgreSQL 16 via Docker Compose** locally).

### Overall Engineering Assessment

The local codebase has undergone substantial hardening across authentication sessions, server-authoritative checkout pricing, atomic inventory deduction (`InventoryService.deduct_stock`), rate limiting (`RateLimiter`), image upload verification (`UploadService`), and mock-fallback removal. **All local automated test suites pass** (`702 passed, 2 skipped` in `pytest`; `55 passed` in `storefront`; `86 passed` in `management`; `51 passed` in `web-app`; `188 passed` in `flutter test`; `0` issues in `flutter analyze`).

However, **critical production blockers and cross-layer drift currently break or endanger the live deployment**:

1. **P0 Production Outage — Live Login Returns HTTP 500 Masked as a Browser CORS Error:**
   - The deployed Render backend (`https://blue-panda-api-demo.onrender.com`, commit `ad26cef`) maps `User.legacy_tokens_revoked_at` (`backend/app/models/user.py:44-47`) and queries `SELECT ... FROM users ... FOR UPDATE` in `AuthService.login` (`backend/app/services/auth_service.py:60-63`).
   - The production Supabase PostgreSQL database (`blue-panda-demo`) is at Alembic revision `a1b2c3d4e5f6` and **lacks column `users.legacy_tokens_revoked_at`** (added in unapplied migration `backend/alembic/versions/d7e8f9012abc_add_legacy_token_revocation.py:19-22`).
   - Every login request crashes with `psycopg2.errors.UndefinedColumn` (`HTTP 500`). Because committed `ad26cef` registered `CORSMiddleware` inside Starlette's `ServerErrorMiddleware`, unhandled 500 responses omit `Access-Control-Allow-Origin`, causing browsers on `https://blue-panda-management.vercel.app` and `https://blue-panda-storefront-iota.vercel.app` to report a CORS failure (`docs/deployment/MANAGEMENT_LOGIN_CORS_REPORT.md:16-30`, `docs/deployment/ADMIN_LOGIN_SCHEMA_MISMATCH_RELEASE_PLAN.md:7-28`).
2. **P0 Production Security Exposure — Supabase Data API Exposes `public.users`, `public.user_sessions`, and `public.refresh_tokens` Without RLS:**
   - Verified production evidence (`docs/upgrade/phase_1c_security/dashboard_evidence_20261107.json:14-60`, `docs/upgrade/PHASE_1C_SECURITY_REMEDIATION_PLAN.md:18-65`) shows the Supabase Data API (`PostgREST`) is enabled on `public` while **Row-Level Security (`rls`) is `false`** on all 15 tables and `anon` / `authenticated` roles hold `SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER, MAINTAIN` (`arwdDxtm`) table privileges on `users` (`password_hash`), `user_sessions`, and `refresh_tokens` (`token_hash`). Remediation SQL (`docs/upgrade/phase_1c_security/apply.sql`) is prepared locally but **not yet applied**.
3. **P0 Live Storefront Fictional Data Leak (Fixed Only in Uncommitted Local Working Tree):**
   - Committed `storefront` `HEAD` (`04dacab`, deployed on Vercel) still falls back to fictional `SHOWCASE_PRODUCTS`, `SHOWCASE_CATEGORIES`, `SHOWCASE_SELLERS`, `SHOWCASE_COUPONS`, and `SHOWCASE_REVIEWS` whenever the API fails or during initial state hydration (`storefront/src/lib/store-catalog.ts` at `04dacab`). The fix removing showcase fallbacks exists **only in uncommitted local changes** across 35 modified files in `storefront/`—and even in the uncommitted tree, `storefront/src/app/sitemap.ts:50,58` still falls back to `SHOWCASE_PRODUCTS`.
4. **P1 Electronic Payment Deadlock & Cross-Client Shipping/Cart Contract Mismatches:**
   - Checkout and POS accept `Credit / Debit Card`, `KHQR Scan & Pay`, `ABA / KHQR Pay`, `QR Pay`, and `Apple Pay`, creating orders with `payment_status="pending"` (`backend/app/services/order_service.py:227`, `pos_service.py:116`), while `OrderService.update_order_status` (`order_service.py:473-481`) forbids manual settlement of non-cash methods and no payment gateway webhook exists.
   - Shipping fee formulas disagree across all 3 layers: Backend charges `$2.00` under `$100` (`order_service.py:214`), Storefront displays `$4.99` under `$50` (`storefront/src/app/(store)/checkout/page.tsx:58`), and Mobile displays `$10.00` Standard / `$15.00` Express under `$100` (`mobile-app/lib/features/checkout/screens/checkout_screen.dart:99-107`).
   - Mobile `CartProvider.loadRemoteCart()` (`mobile-app/lib/features/cart/providers/cart_provider.dart:283-302`) is dead code (never called), and `OrderTrackingScreen` (`mobile-app/lib/features/orders/screens/order_tracking_screen.dart:1-1048`) renders a fabricated live GPS map and fake courier (`Sokha Rith`) for every order.

---

## 2. Architecture

### 2.1 System Architecture Diagram

```mermaid
flowchart TB
  subgraph Clients["Client Applications"]
    SF["Customer Storefront<br/>Next.js 16 / React 19 / Zustand<br/>Vercel: blue-panda-storefront-iota.vercel.app"]
    MP["Management Portal (Admin & Seller)<br/>Next.js 16 / React 19<br/>Vercel: blue-panda-management.vercel.app"]
    MOB["Flutter Mobile App<br/>Flutter / Provider / http / SharedPreferences<br/>Android Emulator :8000 / iOS Simulator :8000"]
    WEB_LEGACY["Legacy Monolith (web-app/)<br/>Next.js 16 (Superseded by storefront/ + management/)"]
  end

  subgraph Backend["FastAPI Backend (Render: blue-panda-api-demo.onrender.com)"]
    CORS["Outer CORSMiddleware (uncommitted main.py:381)<br/>or Inner Middleware (committed ad26cef)"]
    SEC["Security Headers & RateLimiter<br/>(MemoryRateLimitStorage / RedisRateLimitStorage)"]
    ROUTERS["Dual API Routers<br/>/api/* (Web default) & /api/v1/* (Mobile default)<br/>16 Route Modules"]
    SERVICES["Domain Services<br/>AuthService, AuthSessionService, ProductService,<br/>OrderService, InventoryService, PosService,<br/>CouponService, CartService, UploadService, ..."]
    UPLOADS["Local Disk Static Mount (/uploads)<br/>Ephemeral on Render Free Tier"]
  end

  subgraph DataLayer["Data & Persistence Layer"]
    SUPA_POOL["Supabase PgBouncer Pooler<br/>aws-1-ap-northeast-1.pooler.supabase.com:6543 / :5432"]
    PG[("PostgreSQL 17.11 (Supabase Production)<br/>PostgreSQL 16 (Local Docker :5433)<br/>14 SQLAlchemy Models + alembic_version")]
    POSTGREST["Supabase Data API (PostgREST)<br/>⚠️ EXPOSED on public schema without RLS"]
    REDIS[("Optional Redis 7<br/>(Rate Limit Sliding Window)")]
  end

  SF -->|"HTTPS JSON + Bearer JWT (/api/*)"| CORS
  MP -->|"HTTPS JSON + Bearer JWT (/api/*)"| CORS
  MOB -->|"HTTP/HTTPS JSON + Bearer JWT (/api/v1/*)"| CORS
  WEB_LEGACY -.->|"Legacy (/api/*)"| CORS

  CORS --> SEC --> ROUTERS --> SERVICES
  ROUTERS --> UPLOADS
  SERVICES -->|"SQLAlchemy 2 QueuePool (SSL)"| SUPA_POOL --> PG
  SEC -.->|"Optional RATE_LIMIT_STORAGE_URL"| REDIS
  PG -.->|"Public Schema Grants (anon/authenticated)"| POSTGREST
```

### 2.2 Communication & Request Lifecycle

```mermaid
sequenceDiagram
  autonumber
  participant C as Client (Storefront / Management / Mobile)
  participant API as FastAPI Backend (/api or /api/v1)
  participant RL as RateLimiter + Auth Dependencies
  participant SVC as Service Layer (OrderService / InventoryService)
  participant DB as PostgreSQL (Supabase / Docker)

  C->>API: POST /api/auth/login {email, password}
  API->>RL: Check IP sliding-window quota (5 req / 60s)
  API->>SVC: AuthService.login(db, request)
  SVC->>DB: SELECT * FROM users WHERE email = :email FOR UPDATE
  Note over SVC,DB: ⚠️ Fails on Production Supabase with HTTP 500<br/>because users.legacy_tokens_revoked_at is unmigrated
  SVC->>DB: INSERT INTO user_sessions (...)
  SVC-->>C: {success: true, data: {access_token, user}}

  C->>API: POST /api/orders (Authorization: Bearer <JWT>)
  API->>RL: get_current_user() -> decode_access_token()
  RL->>DB: SELECT User + AuthSessionService.validate_access()
  API->>SVC: OrderService.create_order(db, user.id, request)
  SVC->>DB: Load cart_items + products
  SVC->>DB: Atomic UPDATE products SET stock = stock - qty WHERE stock >= qty
  SVC->>DB: CouponService.redeem_coupon_atomic() (if coupon_code)
  SVC->>DB: INSERT INTO orders, order_items, notifications + DELETE cart_items
  SVC->>DB: COMMIT
  SVC-->>C: {success: true, data: OrderResponse}
```

### 2.3 How Each Component Communicates
1. **Storefront (`storefront/`) ↔ FastAPI Backend (`backend/`)**:
   - Uses `storefront/src/lib/api.ts:4-25` with `API_BASE_URL` defaulting to `http://localhost:8000/api` locally and `https://blue-panda-api-demo.onrender.com/api` on Vercel.
   - Attaches `Authorization: Bearer <token>` from `localStorage` (`token`) via `getAuthHeaders()` (`storefront/src/lib/api.ts:36-47`).
   - Unwraps `{ success, message, data }` envelopes in `handleResponse<T>()` (`storefront/src/lib/api.ts:49-85`).
2. **Management Portal (`management/`) ↔ FastAPI Backend (`backend/`)**:
   - Uses `management/src/lib/config.ts:62-97` (`getApiBaseUrl()`) and `management/src/lib/api.ts:28-115`.
   - Enforces HTTPS for non-local `NEXT_PUBLIC_API_URL` at build time (`management/next.config.ts:3-31`) and runtime (`management/src/lib/config.ts:47-60`).
   - Supports cross-app login redirect when a `seller` or `admin` logs in on `storefront` (`storefront/src/app/(auth)/components/AuthForm.tsx:16,52-55`) or when a `customer` logs in on `management` (`management/src/app/(auth)/components/AuthForm.tsx:52-55`), though tokens are **not** shared across domains (`localStorage` is origin-isolated).
3. **Flutter Mobile App (`mobile-app/`) ↔ FastAPI Backend (`backend/`)**:
   - Uses `ApiEndpoints.baseUrl` (`mobile-app/lib/core/constants/api_endpoints.dart:14-40`), defaulting to `http://10.0.2.2:8000` on Android and `http://localhost:8000` on iOS/Web/macOS unless compiled with `--dart-define=API_URL=...`.
   - Calls `/api/v1/*` routes (`api_endpoints.dart:195-239`), which map to the exact same FastAPI route handlers as `/api/*` (`backend/app/api/v1/__init__.py:39-45`).
4. **FastAPI Backend (`backend/`) ↔ PostgreSQL (`Supabase` / Local Docker)**:
   - Synchronous SQLAlchemy 2 `QueuePool` (`pool_size=5, max_overflow=5, pool_timeout=30, pool_recycle=1800, pool_pre_ping=True`) in `backend/app/db/database.py:24-32`. Automatically injects `sslmode="require"` when `supabase.co` or `supabase.com` is in `DATABASE_URL` (`database.py:21-22`).

---

## 3. Project Structure & Git Safety Audit (Phases 1 & 2)

### 3.1 Multi-Repository Topology & Git Remotes

The workspace at `/Users/bunvathana/Documents/Code/Project/e-commerce` contains **7 separate `.git` repositories** (a root parent repo plus 6 nested Git repositories, with orphan gitlinks in the root index and **no `.gitmodules` file**):

| # | Repository Path | Branch | Local `HEAD` | `origin/main` | Ahead / Behind | Remote URL | Working Tree Status |
|---|---|---|---|---|---|---|---|
| 1 | `.` (Root Workspace) | `main` | `2b7965c` | `2b7965c` | `0 / 0` | `https://github.com/Bunvathana876/Full_mobile_web_App_backend_e_commerce.git` | **Dirty:** 8 modified (`.DS_Store`, `README.md`, `backend` gitlink, `docker-compose.yml`, `mobile-app` gitlink, `pgadmin/servers.json`, `run.sh`, `web-app` gitlink), 1 staged rename (`PROJECT_UI_UX_ANALYSIS.md -> docs/architecture/PROJECT_UI_UX_ANALYSIS.md`), 17 untracked paths (including `storefront/`, `management/`, `deploy/`, `docs/`, `backups/`). |
| 2 | `backend/` | `main` | `ad26cef` | `ad26cef` | `0 / 0` | `https://github.com/Bunvathana876/e_commerce_backend.git` | **Dirty:** 2 modified (`app/main.py`, `tests/test_cors_security.py`). |
| 3 | `storefront/` | `main` | `04dacab` | `04dacab` | `0 / 0` | `https://github.com/Bunvathana876/e_commerce_storefront.git` | **Dirty:** 34 modified, 1 deleted (`public/robots.txt`), 8 untracked paths (`Dockerfile.prod`, `public/images/blue-panda-hero-background.webp`, `src/app/(store)/new-arrivals/`, `src/app/robots.ts`, `src/app/sitemap.ts`, `src/components/store/promotions/`, `src/lib/__tests__/seo-metadata.test.ts`, `src/lib/__tests__/server-logout.test.mjs`). |
| 4 | `management/` | `main` | `869204e` | `869204e` | `0 / 0` | `https://github.com/Bunvathana876/e_commerce_mangement.git` *(note typo `mangement` in GitHub repo name)* | **Dirty:** 4 modified (`src/components/layout/Sidebar.tsx`, `src/components/seller/SellerSidebar.tsx`, `src/lib/api.ts`, `src/lib/auth.ts`), 2 untracked (`Dockerfile.prod`, `src/lib/__tests__/server-logout.test.mjs`). |
| 5 | `mobile-app/` | `main` | `5395017` | `5395017` | `0 / 0` | `https://github.com/Bunvathana876/e_commerce_mobile_app_flutter.git` | **Dirty:** 29 modified files, 6 untracked files. |
| 6 | `web-app/` (Legacy) | `main` | `163a5e2` | `163a5e2` | `0 / 0` | `https://github.com/Bunvathana876/web-app-e-commerce.git` | **Dirty:** 55 staged (`A`/`M`/`D`) changes, 1 untracked image. |
| 7 | `mobile-app/web/` | `main` | `5ef2834` | *(none)* | N/A | *(No remote configured)* | Clean (`1` commit). |

### 3.2 Git Safety & Sensitive File Audit
- **Orphan Gitlinks in Root Repo:** Root `git ls-files --stage` records `160000` submodule gitlinks for `backend` (`999de81`), `mobile-app` (`4aa7a69`), and `web-app` (`ea164cf`), all lagging behind the actual nested repos (`ad26cef`, `5395017`, `163a5e2`), with **no `.gitmodules` file**. Meanwhile `storefront/` and `management/` are untracked in the root repo.
- **Environment & Secret Files:**
  - Local `.env` files exist on disk (`backend/.env`, `backend/.env.supabase`, `storefront/.env.local`, `management/.env.local`, `web-app/.env.local`) and are **not tracked by Git** in their respective repositories (verified via `git ls-files`).
  - **Root `.gitignore` is Untracked:** In the root repo, `.gitignore` is currently untracked (`?? .gitignore`).
  - **Hardcoded Fallback Password in `docker-compose.yml:68`:** `DATABASE_URL: ${BACKEND_DATABASE_URL:-postgresql+psycopg2://ecommerce_user:lee123456789%40@host.docker.internal:5433/ecommerce_db}` embeds a password literal in a tracked file.
  - **Tracked `pgadmin/servers.json`:** Tracked in root repo (`pgadmin/servers.json:1-16`), containing local dev DB connection metadata (`ecommerce_user` / `ecommerce_db` on `postgres:5432`).
- **Are Local Uncommitted Updates Deployed?**
  - **No.** All 5 remote-backed repositories have `HEAD == origin/main` (`0 ahead / 0 behind`), meaning **none of the uncommitted working-tree fixes** in `backend/` (outer `CORSMiddleware`), `storefront/` (showcase fallback removal, server logout, SEO routes), `management/` (server logout, production Dockerfile), or `mobile-app/` (mock fallback removal, server logout, UI updates) have been committed, pushed to GitHub, or deployed to Render/Vercel.

---

## 4. Feature Matrix

| # | Feature / Subsystem | FastAPI Backend (`backend/`) | Customer Storefront (`storefront/`) | Management Portal (`management/`) | Flutter Mobile App (`mobile-app/`) | Overall Status |
|---|---|---|---|---|---|---|
| 1 | **Registration & Login** | Implemented (`routes/auth.py:20-51`); **LIVE PROD BROKEN (HTTP 500)** due to unmigrated `users.legacy_tokens_revoked_at`; 500 on `name=None` or >72B password | Implemented (`AuthForm.tsx:1-214`); client checks `<6` chars instead of 8 (`line 90`) | Implemented (`AuthForm.tsx:1-269`); blocked in prod by backend 500 | Implemented (`auth_service.dart:13-64`); social buttons on welcome screen redirect to email login (`auth_welcome_screen.dart:199-284`) | **Broken in Prod / Partial Locally** |
| 2 | **JWT & Session Revocation** | Implemented (`security.py:31-111`, `auth_session_service.py:36-204`); `AUTH_ISSUE_SESSION_TOKENS=False` by default (`config.py:67`) | Bearer JWT in `localStorage`; uncommitted `clearAuthUser()` calls `POST /api/auth/logout` (`auth.ts:138-159`) | Bearer JWT in `localStorage`; uncommitted `clearAuthUser()` calls `POST /api/auth/logout` (`auth.ts:137-159`) | Bearer JWT in plaintext `SharedPreferences`; uncommitted `logout()` calls `POST /api/v1/auth/logout` (`auth_provider.dart:254-282`) | **Partially Implemented** |
| 3 | **User & Role Management** | Admin CRUD in `routes/users.py:16-170`; bypasses password policy (`lines 76, 136`); `DELETE` cascades orders (`models/user.py:100`) | Customer profile edit & password change (`account/page.tsx:120-346`) | Admin User CRUD (`admin/users/page.tsx:1-462`); lacks password policy pre-check | Read-only profile (`profile_screen.dart:1-1323`); guest shows hardcoded `'Bun Vathana'` (`lines 46-52`); no profile edit API | **Partially Implemented** |
| 4 | **Product Catalog & Search** | Implemented (`routes/products.py:17-163`, `product_service.py:72-301`); lacks `gt=0`/`ge=0` schema checks (`schemas/product.py:18-46`) | Committed `04dacab` shows fake `SHOWCASE_PRODUCTS` on failure; fixed in uncommitted tree except `sitemap.ts:50,58` | Admin & Seller CRUD (`admin/products/page.tsx`, `seller/products/page.tsx`); admin list capped at `limit=100` (`line 47`) | Implemented (`product_provider.dart:1-602`), but drops `stock`/`is_active` (`product_model.dart:3-107`) and fakes pagination over 50 items (`line 486`) | **Partially Implemented** |
| 5 | **Categories** | Implemented (`routes/categories.py:16-116`); `DELETE` cascades and deletes all products (`models/category.py:58`) | Implemented (`categories/page.tsx:1-178`); committed `04dacab` falls back to showcase categories | Admin CRUD (`admin/categories/page.tsx:1-340`); image field is URL-only (no file upload) | Implemented (`categories_screen.dart:1-457`), but `ProductDetailScreen` uses duplicate hardcoded `CategoryModel` (`product_detail_screen.dart:110`) | **Partially Implemented** |
| 6 | **Seller Marketplace** | Implemented (`routes/sellers.py`, `routes/seller.py`, `seller_service.py`); `create_seller` uses `"Seller123!"` & skips role upgrade (`lines 57, 69`) | Public directory (`stores/page.tsx:1-162`); fabricates `5+ Active Listings` when count is 0 (`line 128`) | Admin Seller CRUD (`admin/sellers/page.tsx`) + Seller Portal (`seller/page.tsx`, `seller/products`, `seller/store`) | **Missing** — mobile app does not display seller stores or seller info | **Partially Implemented** |
| 7 | **Inventory & Stock** | Atomic `InventoryService.deduct_stock` (`inventory_service.py:26-83`); `DELETE /orders/{id}` fails to restore stock (`orders.py:92-112`) | Checks stock in cart/checkout; `updateQuantity` uses `stock \|\| 99` when `stock === 0` (`store.ts:295`) | Admin inventory table (`admin/inventory/page.tsx:1-360`); capped at first 100 products (`line 38`) | **Broken** — `ProductModel` omits `stock`; out-of-stock items show `'In Stock'` (`product_detail_screen.dart:519-549`) | **Partially Implemented** |
| 8 | **Shopping Cart** | Implemented (`routes/cart.py:13-144`, `cart_service.py:12-345`); N+1 on `Product.seller` (`line 18`) | Zustand + optimistic sync (`store.ts:1-421`); checkout clears & re-adds sequentially (`checkout-security.ts:282-288`) | N/A (Admin uses POS cart) | **Broken Sync** — `loadRemoteCart()` (`cart_provider.dart:283`) is never called; swallows API errors (`lines 332-398`) | **Partially Implemented** |
| 9 | **Wishlist / Favorites** | Implemented (`routes/favorites.py:12-63`, `favorite_service.py:11-105`) | Implemented (`wishlist/page.tsx`, `store.ts:320-375`) | N/A | **Broken** — never calls `GET /api/v1/favorites` and never persists locally; wiped on every app restart (`product_provider.dart:503-541`) | **Partially Implemented** |
| 10 | **Coupons & Discounts** | Atomic global `used_count` (`coupon_service.py:213-274`); `user_id` unused (no per-user limit, `line 107`) | Validated via `/api/coupons/validate` (`checkout-security.ts:164-205`); `deals/page.tsx` shows live coupons | Admin Coupon CRUD (`admin/coupons/page.tsx:1-415`) | Validates remotely (`cart_provider.dart:223-270`), but `CartScreen` suggests invalid `SUPER50`/`SUMMER15` chips (`cart_screen.dart:889`) | **Partially Implemented** |
| 11 | **Checkout & Orders** | Server-authoritative (`order_service.py:99-605`); sellers cannot `GET` orders (`orders.py:16, 65, 83`); shipping is `$2.00` (`line 214`) | Implemented (`checkout/page.tsx`, `orders/page.tsx`); UI shows `$4.99` shipping (`checkout/page.tsx:58`); no cancel button | Admin orders (`admin/orders/page.tsx`); Seller dashboard shows `0` orders because `/orders` returns buyer orders (`seller/page.tsx:46`) | Calls `POST /api/v1/orders` (`checkout_screen.dart:304`), but Express `+$5` fee isn't sent to server; `OrderTrackingScreen` is 100% fake GPS | **Partially Implemented** |
| 12 | **Payments** | **Missing Gateway** — only COD & POS Cash can be marked `paid` (`order_service.py:473-481`, `pos_service.py:84-116`) | Labels Card / KHQR as demo; creates `pending` orders (`checkout/page.tsx:76-94`) | Admin can settle COD after ship/delivery with reason (`admin/orders/[id]/page.tsx:85-135`) | Labels KHQR / Card as demo (`checkout_screen.dart:62-84`); renders fake painted QR (`_KhqrQrPatternPainter`, `line 1438`) | **Missing (Gateway) / COD Only** |
| 13 | **Reviews & Ratings** | Moderation & rating recalc (`review_service.py:15-205`); allows unpurchased & duplicate reviews (`lines 84-99`) | Displays & submits reviews (`product/[id]/page.tsx:88-140`); `fetchStoreReviews` omits `status: "Approved"` (`store-catalog.ts:663`) | Admin moderation & reply (`admin/reviews/page.tsx:1-365`); Seller has no review reply UI | Submits reviews (`review_provider.dart:173-207`), but masks 400/401/403 as `'Network is not connected'` (`line 201`) | **Partially Implemented** |
| 14 | **Notifications** | Implemented (`notification_service.py:14-182`); **Bug:** Admin `read-all` / `clear-all` mutates all users' private notifications (`lines 146-181`) | Customer notifications bell/list in `StoreNavbar.tsx` | Admin broadcast & list (`admin/notifications/page.tsx`, `Navbar.tsx`) | **Bug:** `clearAll()` sets `_hasCleared = true` in prefs, permanently hiding all future backend notifications (`notification_provider.dart:121`) | **Partially Implemented** |
| 15 | **POS (Point of Sale)** | Implemented (`routes/pos.py:14-76`, `pos_service.py:37-398`); walk-in orders set `user_id = cashier.id` (`line 137`) | N/A | Implemented (`admin/pos/page.tsx:1-695`); loads only first 100 products (`line 62`); Card/KHQR stay `pending` | N/A | **Partially Implemented** |
| 16 | **Reports & Analytics** | Basic counts + paid revenue in `GET /stats/overview` (`routes/stats.py:16-63`); no time-series or seller stats | N/A | `admin/reports/page.tsx:1-385` computes analytics client-side by downloading all orders/products (`limit: 100`) | N/A | **Partially Implemented** |

---

## 5. Backend Audit (Phase 3)

### 5.1 Application Structure & Middleware (`backend/app/main.py`)
- **Entry Point:** `backend/app/main.py:1-391` defines `create_app(custom_settings)` (`line 252`) and module-level `app = create_app()` (`line 391`).
- **Dual Router Registration:** `backend/app/api/v1/__init__.py:20-45` mounts all 16 route modules under both `/api` (`api_router`) and `/api/v1` (`api_v1_router`).
- **Uncommitted `CORSMiddleware` Wrapper Side Effect (`backend/app/main.py:252, 381-388`):**
  - In committed `HEAD` (`ad26cef`), `app_instance.add_middleware(CORSMiddleware, ...)` was used, which sits inside Starlette's `ServerErrorMiddleware` and drops CORS headers on unhandled 500 responses.
  - In the uncommitted working tree, `create_app()` returns `CORSMiddleware(app=app_instance, ...)` (`main.py:381-388`). While this ensures `Access-Control-Allow-Origin` is attached even on unhandled 500s, **`app` is no longer a `FastAPI` instance** (`isinstance(app, FastAPI) == False`). Any code or test accessing `app.dependency_overrides` or `app.openapi()` directly will fail with `AttributeError` unless accessing `app.app`.
  - **Better Pattern:** Keep `create_app() -> FastAPI`, register `app_instance.add_middleware(CORSMiddleware, ...)`, and add an `@app_instance.exception_handler(Exception)` handler returning a `JSONResponse(status_code=500, content={"success": False, "message": "Internal server error."})` so unhandled exceptions pass through `CORSMiddleware` and `add_security_headers` without changing the return type of `create_app()`.
- **Import-Time Side Effects (`backend/app/main.py:29-48`):**
  - Importing `app.main` when `AUTO_INIT_DB=True` and `not settings.is_production` immediately executes `Base.metadata.create_all(bind=engine)` (`line 31`) and seeds notifications/demo data (`lines 40-48`).

### 5.2 Concrete Backend Bugs (With Exact File & Line Numbers)

1. **HTTP 500 `AttributeError` on Registration When `name` and `full_name` Are Omitted**
   - **Location:** `backend/app/schemas/auth.py:8-24` and `backend/app/services/auth_service.py:37`
   - **Evidence:** `RegisterRequest` declares `name: str | None = None` (`line 9`) and `full_name: str | None = None` (`line 10`). Its `@model_validator` (`lines 14-24`) only populates `self.name` if `self.full_name` was provided. Sending `{"email": "a@b.com", "password": "ValidPassword123!"}` passes Pydantic validation with `data.name = None`, and `AuthService.register` crashes at `name=data.name.strip()` (`auth_service.py:37`) with an unhandled `AttributeError` (`HTTP 500`).
2. **HTTP 500 `ValueError` on Passwords Between 73 and 128 UTF-8 Bytes**
   - **Location:** `backend/app/core/password_policy.py:16`, `backend/app/core/security.py:14-17`, `backend/requirements.txt:47`
   - **Evidence:** `MAX_PASSWORD_LENGTH = 128` (`password_policy.py:16`), but `bcrypt==5.0.0` (`requirements.txt:47`) raises `ValueError: password cannot be longer than 72 bytes` in `bcrypt.hashpw()` (`security.py:17`). Any password of 73–128 ASCII characters (or shorter multi-byte UTF-8 characters) passes `validate_password_strength()` and crashes registration or password change with `HTTP 500`.
3. **Database Row Lock Held Across CPU-Intensive `bcrypt.checkpw` in `AuthService.login`**
   - **Location:** `backend/app/services/auth_service.py:60-65`
   - **Evidence:** `AuthService.login` executes `select(User).where(User.email == ...).with_for_update()` (`line 61`) **before** calling `verify_password(data.password, user.password_hash)` (`line 65`), holding a PostgreSQL row lock for ~100–300ms of bcrypt hashing per login attempt.
4. **Admin Notification Actions Mutate or Delete Every Customer's Private Notifications**
   - **Location:** `backend/app/api/v1/routes/notifications.py:27, 50, 80, 94, 111, 124` and `backend/app/services/notification_service.py:83-87, 146-181`
   - **Evidence:** Every notification route sets `user_id = None if current_user.role == "admin" else current_user.id`. In `NotificationService.mark_all_read` (`lines 146-154`) and `NotificationService.clear_all` (`lines 172-181`), when `user_id is None`, **no `WHERE user_id ...` filter is applied**. If an admin clicks "Mark all read" or "Clear all" in the Management Portal, it marks or deletes **every customer's private order/delivery notifications across the entire database**. Conversely, broadcast notifications (`user_id = None`) are never shown to customers because `list_notifications` filters by `Notification.user_id == user_id` (`lines 85-87`).
5. **Sellers Cannot View or List Orders Containing Their Products**
   - **Location:** `backend/app/api/v1/routes/orders.py:13-23, 62-89`
   - **Evidence:** `GET /orders/all` (`line 16`) is restricted to `require_roles("admin")`. `GET /orders` (`line 67`) and `GET /orders/{order_id}` (`line 83`) filter by `Order.user_id == current_user.id` (the buyer's user ID). Even though `PUT /orders/{order_id}/status` (`line 31`) authorizes `"seller"` to advance fulfillment to `processing` or `shipped`, sellers have **no API endpoint to list or view those orders**.
6. **`DELETE /orders/{order_id}` Bypasses `OrderService` and Leaks Inventory & Coupon Quotas**
   - **Location:** `backend/app/api/v1/routes/orders.py:92-112`
   - **Evidence:** `delete_order` queries and deletes `Order` directly in the route handler (`lines 100-107`) without calling `InventoryService.restore_stock` or `CouponService.restore_coupon_usage`. Deleting an uncancelled order permanently loses its deducted stock and coupon usage count.
7. **Admin User Creation/Update Bypasses Password Policy & `DELETE /users/{id}` Destroys Order History**
   - **Location:** `backend/app/api/v1/routes/users.py:54-170` and `backend/app/models/user.py:100-103`
   - **Evidence:** `create_user` (`users.py:76`) hashes `request.password` without calling `validate_password_strength`. `update_user` (`users.py:136`) checks `if request.password is not None and len(request.password.strip()) >= 6:` (silently ignoring 1–5 char passwords and skipping policy checks) and does not call `AuthSessionService.revoke_all` when `role` or `is_active` changes (`lines 132-135`). `delete_user` (`users.py:150-170`) allows an admin to delete their own account and cascades `DELETE` to `orders` (`models/user.py:100-103`, `models/order.py:32`), erasing paid financial records.
8. **`SellerService.create_seller` Uses Hardcoded `"Seller123!"` Password and Fails to Upgrade Existing User's Role**
   - **Location:** `backend/app/services/seller_service.py:53-71`
   - **Evidence:** When an admin creates a seller without specifying a password, line 57 assigns `pwd = data.password if data.password else "Seller123!"`. If a `User` with `data.email` already exists (e.g., a registered `"customer"`), lines 69–70 link `user_id = user.id` **without** setting `user.role = "seller"`, so that user receives `403 Permission denied` on all `/seller/*` endpoints.
9. **`ProductCreate` / `ProductUpdate` Allow Negative Stock/Prices and Seller-Manipulated Ratings**
   - **Location:** `backend/app/schemas/product.py:18-46` and `backend/app/services/product_service.py:96-100`
   - **Evidence:** `ProductBase` and `ProductUpdate` have no `gt=0` / `ge=0` constraints on `price`, `discount_price`, or `stock`, and expose `rating: Decimal` as a writable input field. Additionally, `ProductService.get_products` (`lines 96-100`) includes a seller's inactive products in public catalog responses whenever the seller is logged in.
10. **Category Deletion Cascades and Destroys All Products in That Category**
    - **Location:** `backend/app/models/category.py:56-59`, `backend/app/models/product.py:35-39`, `backend/app/services/product_service.py:62-66`
    - **Evidence:** `Category.products` has `cascade="all, delete-orphan"` and `Product.category_id` has `ondelete="CASCADE"`. Calling `DELETE /api/categories/{id}` deletes every product in that category along with its reviews, cart items, and favorites.
11. **`GET /readyz` Leaks Internal Database Exception Details to Unauthenticated Users**
    - **Location:** `backend/app/main.py:349-361`
    - **Evidence:** On DB failure, `/readyz` raises `HTTPException(status_code=503, detail=f"Database readiness check failed: {exc}")` (`line 360`), exposing internal hostnames, pooler errors, or SQL details publicly.
12. **`bootstrap_admin.py` Is Broken on Any Database Migrated to Alembic `head` (`d7e8f9012abc`)**
    - **Location:** `backend/scripts/bootstrap_admin.py:26-29, 85-86`
    - **Evidence:** `EXPECTED_COLUMNS` hardcodes the 10 pre-`d7e8f9012abc` columns of `public.users` and omits `"legacy_tokens_revoked_at"`. On any database at Alembic `head`, `validate_users_table_schema` raises `BootstrapError("Unexpected users schema; bootstrap refused.")`.

---

## 6. Database & Migration Audit (Phase 4)

### 6.1 Entity-Relationship Diagram (14 Models + `alembic_version`)

```mermaid
erDiagram
  users ||--o{ user_sessions : "has (CASCADE)"
  user_sessions ||--o{ refresh_tokens : "rotates (CASCADE)"
  users ||--o{ addresses : "owns (CASCADE)"
  users ||--o{ cart_items : "has (CASCADE)"
  users ||--o{ favorites : "saves (CASCADE)"
  users ||--o{ orders : "places (CASCADE ⚠️)"
  users ||--o{ reviews : "writes (CASCADE)"
  users ||--o{ notifications : "receives (CASCADE)"
  users ||--o{ sellers : "manages (SET NULL)"

  categories ||--o{ products : "contains (CASCADE ⚠️)"
  sellers ||--o{ products : "lists (SET NULL)"

  products ||--o{ cart_items : "in (CASCADE)"
  products ||--o{ favorites : "in (CASCADE)"
  products ||--o{ order_items : "referenced by (SET NULL)"
  products ||--o{ reviews : "reviewed in (CASCADE)"

  orders ||--|{ order_items : "contains (CASCADE)"
  orders ||--o{ reviews : "verified by (SET NULL)"
```

### 6.2 Alembic Migration Chain vs Deployed Production Database

| Revision ID | Down Revision | File | Summary | Local Codebase | Production Supabase (`blue-panda-demo`) |
|---|---|---|---|---|---|
| `f904b613102f` | `None` | `backend/alembic/versions/f904b613102f_create_initial_ecommerce_tables.py` | Initial 8 tables (`users`, `categories`, `products`, `addresses`, `orders`, `cart_items`, `favorites`, `order_items`) | Present | Applied |
| `c4b8d91a2e3f` | `f904b613102f` | `backend/alembic/versions/c4b8d91a2e3f_consolidate_ecommerce_schema.py` | Adds `sellers`, `coupons`, `notifications`, `reviews`, `products.seller_id`, `orders.discount_amount`, `orders.coupon_code`, `uq_categories_name`, and 4 `CHECK` constraints | Present | Applied |
| `a1b2c3d4e5f6` | `c4b8d91a2e3f` | `backend/alembic/versions/a1b2c3d4e5f6_create_user_sessions_and_refresh_tokens.py` | Adds `user_sessions` and `refresh_tokens` tables and indexes | Present | **Current Production `alembic_version`** (`docs/upgrade/phase_1c_security/dashboard_evidence_20261107.json:58`) |
| `d7e8f9012abc` *(head)* | `a1b2c3d4e5f6` | `backend/alembic/versions/d7e8f9012abc_add_legacy_token_revocation.py` | Adds `users.legacy_tokens_revoked_at` (`TIMESTAMP WITH TIME ZONE`, nullable) | **Local `head` & Deployed Render Code (`ad26cef`)** | **NOT APPLIED IN PRODUCTION (Causes Live Login HTTP 500)** |

### 6.3 Schema Drift & Relational Integrity Findings
1. **Production Schema Drift (`d7e8f9012abc` Missing in Supabase):**
   - Verified in `docs/deployment/ADMIN_LOGIN_SCHEMA_MISMATCH_RELEASE_PLAN.md:7-28` and `docs/deployment/MANAGEMENT_LOGIN_CORS_REPORT.md:16-30`: Render deployed commit `ad26cef` without running `alembic upgrade head` (`RUN_MIGRATIONS_ON_STARTUP` is opt-in in `backend/docker-entrypoint.sh:45`), leaving `users.legacy_tokens_revoked_at` absent in Supabase.
2. **Check Constraints Missing from SQLAlchemy Models:**
   - Migration `c4b8d91a2e3f:274-315` creates 4 PostgreSQL `CHECK` constraints (`ck_products_stock_non_negative`, `ck_coupons_used_count_non_negative`, `ck_coupons_usage_limit_valid`, `ck_reviews_rating_range`), but none of them are declared in `__table_args__` of `Product` (`models/product.py`), `Coupon` (`models/coupon.py`), or `Review` (`models/review.py`). Consequently, SQLite test databases initialized via `Base.metadata.create_all()` in `backend/tests/conftest.py:60` do not enforce these constraints.
3. **Destructive Foreign Key Cascades on Financial/Catalog Records:**
   - `orders.user_id` (`models/order.py:32`) specifies `ForeignKey("users.id", ondelete="CASCADE")`. Deleting a user deletes their completed orders.
   - `products.category_id` (`models/product.py:36`) specifies `ForeignKey("categories.id", ondelete="CASCADE")`. Deleting a category deletes all products in that category.
4. **Timezone-Naive vs Timezone-Aware `DateTime` Columns:**
   - `user_sessions`, `refresh_tokens`, and `users.legacy_tokens_revoked_at` use `DateTime(timezone=True)` (`TIMESTAMP WITH TIME ZONE`), whereas `users.created_at`, `orders.created_at`, `coupons.expires_at`, `reviews.created_at`, and `notifications.created_at` use timezone-naive `DateTime()` (`TIMESTAMP WITHOUT TIME ZONE`).

### 6.4 Supabase Connection Pooling & Database Permissions Audit
- **Connection Pooling (`backend/app/db/database.py:19-32`):**
  - Uses SQLAlchemy `QueuePool` (`DB_POOL_SIZE=5`, `DB_MAX_OVERFLOW=5`, `DB_POOL_TIMEOUT=30`, `DB_POOL_RECYCLE=1800`, `pool_pre_ping=True`).
  - Local `backend/.env.supabase` (inspected metadata only; secrets redacted) connects via the Supabase PgBouncer pooler (`aws-1-ap-northeast-1.pooler.supabase.com:6543`, transaction mode) as the privileged `postgres.<project_ref>` role. Note: When using Supabase transaction pooler on port `6543` under high concurrency, prepared statements or session-level features can conflict unless `pool_size` is kept modest or session mode (`:5432`) is used for migrations.
- **CRITICAL Security Finding — Supabase Data API & Table Grants (`docs/upgrade/phase_1c_security/dashboard_evidence_20261107.json:14-60`):**
  - Every table in `public` (`users`, `user_sessions`, `refresh_tokens`, `orders`, `order_items`, `products`, `categories`, `sellers`, `coupons`, `cart_items`, `favorites`, `addresses`, `reviews`, `notifications`, `alembic_version`) has **`rls: false`** and grants full `arwdDxtm` (`SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER, MAINTAIN`) privileges to Supabase's `anon` and `authenticated` roles while the Data API is enabled on `public`.
  - Any party holding the project's public `anon` key can read `public.users` (`password_hash`), `public.refresh_tokens` (`token_hash`), and customer PII, or mutate database tables directly via PostgREST, completely bypassing FastAPI.

---

## 7. Frontend Audit — Storefront (`storefront/`) & Management Portal (`management/`) (Phases 5 & 6)

### 7.1 Customer Storefront (`storefront/`)

#### CRITICAL VERIFICATION: Showcase / Fictional Data Exposure
We compared **committed `HEAD` (`04dacab`, currently deployed on Vercel `https://blue-panda-storefront-iota.vercel.app`)** against the **uncommitted local working tree**:

| Layer / File | Committed `HEAD` (`04dacab` — Live on Vercel) | Uncommitted Working Tree (Local Disk) |
|---|---|---|
| `storefront/src/lib/store-catalog.ts` (`lines 1-698`) | Defines fictional `SHOWCASE_CATEGORIES` (`lines 32-89`), `SHOWCASE_SELLERS` (`lines 91-177`, e.g., `"Apple Authorized Store"`, `"Sony Sound Studio"`), `SHOWCASE_PRODUCTS` (`lines 179-481`, 12 fake products with fake prices/stock/ratings), `SHOWCASE_COUPONS` (`lines 483-534`, `BLUEPANDA15`, `WELCOME10`, `FLASH30`), and `SHOWCASE_REVIEWS` (`lines 536-573`). `fetchStoreProducts`, `fetchStoreProductById`, `fetchStoreCategories`, `fetchStoreSellers`, `fetchStoreCoupons`, and `fetchStoreReviews` **all return `SHOWCASE_*` on API error or empty response**! | `fetchStore*` functions (`lines 602-669`) were updated to return `[]` or `null` in `catch` blocks instead of `SHOWCASE_*`. However, `SHOWCASE_*` arrays remain exported in `store-catalog.ts` (`lines 32-573`). |
| Storefront Pages (`shop/page.tsx`, `categories/page.tsx`, `deals/page.tsx`, `product/[id]/page.tsx`, `stores/page.tsx`, `SearchCommandDialog.tsx`) | Initial `useState(...)` hooks initialize directly with `SHOWCASE_PRODUCTS`, `SHOWCASE_CATEGORIES`, `SHOWCASE_COUPONS`, and `SHOWCASE_SELLERS`, and `orders/page.tsx:84` resolves order line thumbnails against `SHOWCASE_PRODUCTS`. **Production users see fictional products, prices, stock, coupons, sellers, ratings, and reviews whenever the backend is slow, asleep on Render free tier, or unreachable.** | Updated in uncommitted working tree to initialize with `[]` / `null` and show loading skeletons, empty states, or retry banners (`shop/page.tsx:35-87`, `page.tsx:28-64`). |
| `storefront/src/app/sitemap.ts` (`lines 37-65`, untracked new file) | Did not exist at `04dacab`. | **Still leaks `SHOWCASE_PRODUCTS` in uncommitted code (`lines 50, 58`)!** If `GET /api/products` returns empty (`items.length === 0`) or throws an error during build/request, `getProductRoutes()` falls back to `SHOWCASE_PRODUCTS`, publishing fake `/product/1`..`/product/12` URLs in `/sitemap.xml`. |

#### Additional Storefront Bugs & Issues (Verified in Uncommitted Working Tree)
1. **Unmoderated Reviews Requested in `fetchStoreReviews` (`storefront/src/lib/store-catalog.ts:661-669`):**
   - `fetchStoreReviews(productId)` calls `reviewsApi.list({ product_id: productId })` (`line 663`) without passing `status: "Approved"`. While the backend currently forces `status = "approved"` for non-admins (`backend/app/api/v1/routes/reviews.py:27-28`), if an admin previews the storefront while logged in, pending/rejected reviews appear on the public product page.
2. **Fabricated Seller Listing Count (`storefront/src/app/(store)/stores/page.tsx:128`):**
   - Renders `{seller.products_count || 5}+ Active Listings`, displaying `5+ Active Listings` for any seller whose actual `products_count` is `0`.
3. **Out-of-Stock Quantity Cap Fallback (`storefront/src/lib/store.ts:295`):**
   - In `updateQuantity`, `const maxStock = target.product.stock || 99;` evaluates `0 || 99` to `99` when a product has `stock: 0`, allowing a user to increment an out-of-stock item up to 99 in local cart state.
4. **Destructive Sequential Cart Sync During Checkout (`storefront/src/lib/checkout-security.ts:282-288`):**
   - `executeCheckoutOrder` calls `await deps.clearServerCart()` (`line 283`) and then loops `for (const item of syncedItems) { await deps.addServerCartItem(item.product.id, item.quantity); }` (`lines 285-287`) before calling `createOrder()` (`line 290`). If a network glitch or rate limit occurs mid-loop, the user's server cart is partially wiped and the order is not created.
5. **Shipping Fee UI Mismatch (`storefront/src/app/(store)/checkout/page.tsx:58` & `cart/page.tsx:39` vs `backend/app/services/order_service.py:214`):**
   - Storefront displays free shipping over `$50` and `$4.99` otherwise (`const deliveryFee = subtotal > 0 ? (subtotal > 50 ? 0 : 4.99) : 0;`), whereas the backend charges `$0.00` over `$100` and `$2.00` under `$100`.
6. **Client Password Length Check Mismatch (`storefront/src/app/(auth)/components/AuthForm.tsx:90` & `storefront/src/app/(store)/account/page.tsx:315`):**
   - Both forms validate `password.length < 6` client-side, while the backend enforces `MIN_PASSWORD_LENGTH = 8` (`backend/app/core/password_policy.py:15`).
7. **Cross-App Origin Allowlist Hardcodes Localhost (`storefront/src/lib/auth.ts:7-12`):**
   - `ALLOWED_CROSS_APP_ORIGINS` only lists `http://localhost:3000`, `http://localhost:3001`, `http://127.0.0.1:3000`, `http://127.0.0.1:3001` and does not include `process.env.NEXT_PUBLIC_MANAGEMENT_URL`.

---

### 7.2 Management Portal (`management/`)

#### Architecture & Authentication Guard (`management/src/components/layout/`, `management/src/lib/auth.ts`)
- **Admin Routes (`management/src/app/(admin)/admin/*`):** Wrapped in `DashboardLayout` (`management/src/components/layout/DashboardLayout.tsx:18-62`), which checks `getAuthUser()` on mount in a client-side `useEffect` (`lines 25-39`). Redirects unauthenticated users to `/login`, `"seller"` users to `/seller`, and `"customer"` users to the storefront (`getStorefrontOrigin()`).
- **Seller Routes (`management/src/app/(seller)/seller/*`):** Wrapped in `SellerLayout` (`management/src/components/seller/SellerLayout.tsx:16-54`), allowing `"seller"` and `"admin"` roles.
- **No Server-Side `middleware.ts`:** Route protection is purely client-side (`"use client"` layout guards + `localStorage`), though all backend admin/seller API endpoints enforce `Depends(require_roles(...))` server-side.

#### Concrete Management Portal Bugs & Contract Mismatches (With Exact File & Line Numbers)
1. **Seller Portal Dashboard Shows `0` Orders & `$0.00` Revenue Because It Calls Buyer Endpoint `ordersApi.list()`**
   - **Location:** `management/src/app/(seller)/seller/page.tsx:44-50` and `management/src/lib/api.ts:442-444`
   - **Evidence:** `SellerDashboardPage` calls `ordersApi.list()` (`GET /api/orders`), which returns orders placed **by the seller as a customer** (`Order.user_id == current_user.id`, `backend/app/api/v1/routes/orders.py:67`), NOT orders containing the seller's products! Furthermore, the Seller Portal has **no `/seller/orders` page** (`SellerSidebar.tsx:22-26` only links to `/seller`, `/seller/products`, `/seller/store`), even though the backend allows sellers to call `PUT /api/orders/{id}/status`.
2. **Hardcoded `limit: 100` Truncates Admin Products, Inventory, POS, and Reports**
   - **Locations:**
     - `management/src/app/(admin)/admin/products/page.tsx:47` (`productsApi.list({ limit: 100 })`)
     - `management/src/app/(admin)/admin/inventory/page.tsx:38` (`productsApi.list({ limit: 100 })`)
     - `management/src/app/(admin)/admin/pos/page.tsx:62` (`productsApi.list({ limit: 100 })`)
     - `management/src/app/(admin)/admin/reports/page.tsx:58` (`productsApi.list({ limit: 100 })`)
     - `management/src/app/(admin)/admin/dashboard/page.tsx:61` (`productsApi.list({ limit: 100 })`)
   - **Impact:** None of these admin screens implement server-side pagination or search requests beyond the first 100 products. Any catalog item past #100 is invisible in Admin Products, Inventory, POS, and Reports.
3. **Production Build Fails Under Default `.env.local` Due to Strict HTTPS Check in `next.config.ts`**
   - **Location:** `management/next.config.ts:3-15` and `management/.env.local`
   - **Evidence:** `resolveImageOrigins()` in `management/next.config.ts:10-12` throws `Error: NEXT_PUBLIC_API_URL must be a public HTTPS URL without credentials, query, or fragment.` during `npm run build` (`NODE_ENV=production`) whenever `.env.local` sets `NEXT_PUBLIC_API_URL=http://localhost:8000/api`.
4. **POS Non-Cash Orders (`Card` / `KHQR`) Cannot Be Settled**
   - **Location:** `management/src/app/(admin)/admin/pos/page.tsx:165-225` and `backend/app/services/pos_service.py:106-116`
   - **Evidence:** Selecting `Card` or `KHQR` in POS creates an order with `payment_status: "pending"` (`pos_service.py:116`), and `OrderService.update_order_status` (`order_service.py:473-481`) blocks admins from marking non-cash orders as `"paid"`.
5. **Admin Notification Actions Trigger Global Customer Notification Wipe**
   - **Location:** `management/src/app/(admin)/admin/notifications/page.tsx:69-94` and `management/src/components/layout/Navbar.tsx:54-62`
   - **Evidence:** Calling `notificationsApi.markAllRead()` or `notificationsApi.clearAll()` as an admin hits `POST /api/notifications/read-all` or `DELETE /api/notifications`, which (due to `backend/app/services/notification_service.py:146-181`) mutates or deletes **every customer's notifications**.

---

## 8. Flutter Mobile Application Audit (`mobile-app/`) (Phase 7)

### 8.1 Architecture & State Management
- **Entry & Providers (`mobile-app/lib/main.dart:18-55`):** Registers `ThemeProvider`, `AuthProvider`, `ProductProvider`, `CategoryProvider`, `CartProvider`, `OrderProvider`, `ReviewProvider`, and `NotificationProvider` via `MultiProvider`.
- **Networking (`mobile-app/lib/core/network/api_client.dart:11-247`):** Singleton `ApiClient.instance` with 15-second timeouts (`api_endpoints.dart:191-192`), `Bearer` token header injection, `_authEpoch` tracking, and typed `ApiException` mapping (`api_exceptions.dart:1-132`).

### 8.2 Critical Mobile Verifications
1. **Mock Authentication (`mobile-app/lib/features/auth/services/auth_service.dart:5-87`):**
   - `useRemoteBackend` defaults to `true` (`line 9`). When `true`, `login()` (`lines 17-19`) and `signUp()` (`lines 54-60`) call `AuthApiService` and **never** fall back to `_mockStudentSession` on network/API failure.
   - However, on `AuthWelcomeScreen` (`mobile-app/lib/features/auth/screens/auth_welcome_screen.dart:199-284`), `'Continue with Apple'` and `'Continue with Google'` deceptively navigate to the email/password `LoginScreen`, and `ProfileScreen` (`mobile-app/lib/features/profile/screens/profile_screen.dart:46-52`) displays `'Bun Vathana'` / `'student@example.com'` with a verified badge when logged out as a guest!
2. **Simulated Payments & Local-Only Orders (`mobile-app/lib/features/checkout/screens/checkout_screen.dart:60-84, 276-534`):**
   - Offline `ORD-...` fallback order creation has been **removed** in the uncommitted working tree: `_handlePlaceOrder` (`lines 286-328`) requires authentication, calls `_orderApiService.createOrder(...)`, and aborts with a SnackBar on any API error.
   - Payment methods `'ABA / KHQR Pay'` and `'Credit / Debit Card'` are labeled `isDemo: true` (`lines 68, 75`), and `'Preview QR'` opens `_showKhqrModal` (`lines 360-534`) labeled `'DEMO KHQR PREVIEW • UNVERIFIED'` with a custom-painted fake QR (`_KhqrQrPatternPainter`, `lines 1438-1479`).
3. **Fake Live GPS Order Tracking (`mobile-app/lib/features/orders/screens/order_tracking_screen.dart:1-1048`):**
   - Reachable from `OrderSuccessScreen` (`line 281`) and `OrderDetailScreen` (`line 394`). Renders a **100% fabricated `'Live GPS Connected'` map (`line 264`), `70%` progress (`line 185`), fake courier `'Sokha Rith'` (`'Honda PCX 160 • Phnom Penh 1KF-8822'`, `lines 384-425`), and hardcoded timeline timestamps (`lines 661-701`)** regardless of actual order status.
4. **Cart, Favorites, Shipping, and Notification Bugs:**
   - **Dead `loadRemoteCart()` (`mobile-app/lib/features/cart/providers/cart_provider.dart:283-302`):** Never called anywhere in the app; cart mutations swallow backend errors (`lines 332, 350, 372, 382, 398`), causing `POST /api/v1/orders` (which reads server `cart_items`) to fail with `"Your cart is empty"` or mismatch local items.
   - **Shipping Fee Mismatch (`checkout_screen.dart:58, 99-108, 304-311`):** Mobile charges `$10.00` Standard / `$15.00` Express under `$100`, while backend `POST /api/v1/orders` ignores mobile shipping selection and charges `$2.00` under `$100` (`order_service.py:214`).
   - **Favorites Never Loaded or Persisted (`product_provider.dart:503-595`, `product_model.dart:73`):** Mobile never calls `GET /api/v1/favorites` and never saves favorites to `SharedPreferences`; all favorites reset to `false` on app restart.
   - **Permanent Notification Blackhole (`notification_provider.dart:121-123, 207-222`):** Tapping `'Clear All'` sets `notifications_has_cleared = true` in `SharedPreferences`; `loadNotifications()` checks `if (_hasCleared)` (`line 121`) and discards all future backend notifications permanently.
   - **Missing `stock` in `ProductModel` (`product_model.dart:3-107`):** Out-of-stock products show `'In Stock'` (`product_detail_screen.dart:519-549`).
   - **Plaintext Token Storage (`auth_provider.dart:13-14, 171-172`):** Raw JWTs are stored in unencrypted `SharedPreferences` instead of `flutter_secure_storage`.

---

## 9. Security Findings (Phase 8)

Findings are classified by severity (**Critical**, **High**, **Medium**, **Low**) based on verified code and configuration evidence:

| ID | Severity | Vulnerability / Finding | Exact Evidence (File & Lines) | Realistic Impact | Recommended Remediation |
|---|---|---|---|---|---|
| **SEC-01** | **Critical** | **Supabase Data API (`PostgREST`) Exposed on `public` Schema with RLS Disabled & Full `anon`/`authenticated` Table Grants** | `docs/upgrade/phase_1c_security/dashboard_evidence_20261107.json:14-60`, `docs/upgrade/PHASE_1C_SECURITY_REMEDIATION_PLAN.md:18-65` | Anyone with the Supabase project URL and public `anon` key can dump `public.users` (`password_hash`), `public.refresh_tokens` (`token_hash`), and `public.orders`, or `INSERT`/`UPDATE`/`DELETE`/`TRUNCATE` any table directly, bypassing FastAPI auth. | Immediately execute `docs/upgrade/phase_1c_security/apply.sql` in a single transaction (`ENABLE ROW LEVEL SECURITY` on all 15 tables + `REVOKE ALL` from `PUBLIC`, `anon`, `authenticated`) and disable Data API or remove `public` from exposed schemas. |
| **SEC-02** | **High** | **Admin Notification Endpoints Read/Mutate/Delete All Users' Private Notifications** | `backend/app/api/v1/routes/notifications.py:27,50,80,94,111,124`, `backend/app/services/notification_service.py:83-87,146-181` | Admin calling `GET /notifications` reads private customer notifications; calling `POST /notifications/read-all` or `DELETE /notifications` wipes all customers' private notifications across the platform. | Scope admin notification queries to `(Notification.user_id == current_user.id) \| (Notification.user_id.is_(None))` and restrict `clear_all`/`mark_all_read` to the actor's own notifications. |
| **SEC-03** | **High** | **Unhandled HTTP 500 DoS Vector & Row-Lock Contention in Auth Endpoints** | `backend/app/core/password_policy.py:16`, `backend/app/core/security.py:17`, `backend/app/schemas/auth.py:8-24`, `backend/app/services/auth_service.py:37,60-65` | (1) Passwords of 73–128 bytes crash `bcrypt.hashpw` with 500 `ValueError`. (2) Registering without `name`/`full_name` crashes with 500 `AttributeError`. (3) `AuthService.login` acquires `SELECT ... FOR UPDATE` on `User` **before** running slow `bcrypt.checkpw`, allowing concurrent login attempts for an email to serialize and exhaust DB connections. | Enforce `max_bytes <= 72` (or pre-hash with SHA-256 before bcrypt) and NFKC-normalize consistently; require `name` in `RegisterRequest`; verify bcrypt password **before** acquiring `FOR UPDATE` row lock or opening session write transaction. |
| **SEC-04** | **High** | **Admin User Updates Do Not Revoke Active Sessions on Role Demotion or Account Deactivation & Bypass Password Policy** | `backend/app/api/v1/routes/users.py:76,132-139` | If an admin changes a user's role (e.g., `admin` -> `customer`) or deactivates and later reactivates them, existing `UserSession` and `RefreshToken` rows remain `is_revoked=False`. Also, `POST /users` and `PUT /users/{id}` bypass `validate_password_strength`, and `SellerService.create_seller` (`seller_service.py:57`) defaults to `"Seller123!"`. | Call `AuthSessionService.revoke_all(db, user, "role_or_status_changed")` whenever `role` or `is_active` changes; enforce `validate_password_strength` on all user/seller creation and password updates; remove hardcoded `"Seller123!"`. |
| **SEC-05** | **High** | **Destructive `DELETE` Cascades & Unrestored Inventory on Order/User/Category Deletion** | `backend/app/models/user.py:100-103`, `backend/app/models/category.py:56-59`, `backend/app/api/v1/routes/orders.py:92-112`, `backend/app/api/v1/routes/users.py:150-170` | (1) `DELETE /users/{id}` allows self-deletion and cascades `DELETE` to all `orders`. (2) `DELETE /categories/{id}` cascades `DELETE` to all `products`. (3) `DELETE /orders/{id}` deletes orders without restoring product stock or coupon usage. | Change `orders.user_id` FK to `RESTRICT` or `SET NULL`; block category deletion when products exist; prevent admin self-deletion/self-demotion; remove hard `DELETE /orders/{id}` or require cancelled state first. |
| **SEC-06** | **Medium** | **Client-Side Token Storage in `localStorage` (Web) and Plaintext `SharedPreferences` (Mobile) + Default `AUTH_ISSUE_SESSION_TOKENS=False`** | `storefront/src/lib/auth.ts:75-115`, `management/src/lib/auth.ts:74-114`, `mobile-app/lib/features/auth/providers/auth_provider.dart:13-14,171-172`, `backend/app/core/config.py:64,67` | Web stores 7-day JWTs in `localStorage` (accessible to any XSS payload); Mobile stores JWTs in plaintext XML/plist `SharedPreferences`. Backend defaults to 7-day legacy tokens (`ACCESS_TOKEN_EXPIRE_MINUTES=10080`) with `AUTH_ISSUE_SESSION_TOKENS=False`. | Migrate web auth to `HttpOnly; Secure; SameSite` cookies (or enable short-lived 15-minute `AUTH_ISSUE_SESSION_TOKENS=True`); migrate mobile token storage to `flutter_secure_storage` (Keychain / EncryptedSharedPreferences). |
| **SEC-07** | **Medium** | **Missing Rate Limiting on Checkout, Coupon Validation, Image Upload, Reviews, and Cart Endpoints + In-Memory Rate Limit Default** | `backend/app/core/rate_limit.py:332-356`, `backend/app/api/v1/routes/orders.py:48`, `coupons.py:24`, `upload.py:12`, `reviews.py:56` | Attackers can brute-force promo codes on `POST /coupons/validate`, spam image uploads on `POST /upload/image` (blocking the event loop with synchronous CPU/disk I/O), or flood `POST /orders`. Without `RATE_LIMIT_STORAGE_URL`, rate limits are per-worker in-memory. Also, `RedisRateLimitStorage.clear()` calls `client.flushdb()` (`rate_limit.py:336`). | Add `RateLimiter` dependencies to `/orders`, `/coupons/validate`, `/upload/image`, `/reviews`, and `/pos/checkout`; offload `UploadService` image decoding to `run_in_threadpool`; replace `flushdb()` with prefix scan deletion. |
| **SEC-08** | **Medium** | **Seller Product Schema Allows Arbitrary `rating` Manipulation & Negative Values** | `backend/app/schemas/product.py:18-46` | A seller can create or update a product with `rating: 5.00`, `price: -10.00`, or `discount_price > price`. | Remove `rating` from `ProductCreate` and `ProductUpdate`; add `Field(gt=0)` on `price`, `Field(ge=0)` on `stock`, and validate `discount_price < price`. |
| **SEC-09** | **Medium** | **Unlimited Per-User Coupon Redemptions & Unverified/Duplicate Product Reviews** | `backend/app/services/coupon_service.py:107,188,217`, `backend/app/services/review_service.py:84-99` | (1) `user_id` is ignored in `CouponService`, allowing a single user to redeem `WELCOME10` or `SAVE20` on every order. (2) Any authenticated user can submit unlimited reviews for a product without purchasing it (`order_id` is optional). | Enforce per-user coupon redemption check (e.g., `SELECT COUNT(*) FROM orders WHERE user_id = :uid AND coupon_code = :code AND status != 'cancelled'`); require a delivered order containing `product_id` and a unique `(user_id, product_id)` check in `ReviewService.create_review`. |
| **SEC-10** | **Low** | **Information Disclosure on `/readyz`, Missing HSTS/CSP Headers, and Hardcoded Dev Password in `docker-compose.yml`** | `backend/app/main.py:301-308,358-361`, `docker-compose.yml:68`, `backend/app/core/config.py:78,164-183` | `/readyz` leaks raw DB exception strings on 503; `add_security_headers` lacks HSTS and CSP; `CORS_ORIGINS` defaults to `DEFAULT_DEV_CORS_ORIGINS` if unset in production; `docker-compose.yml:68` has a fallback password literal. | Return generic `{"status": "unavailable"}` on `/readyz` and log the exception server-side; add HSTS/CSP headers; require explicit `CORS_ORIGINS` in production; remove fallback password from `docker-compose.yml`. |

---

## 10. Safe Quality Checks & Test Execution Results (Phase 10)

All quality checks were executed in isolated local environments without installing dependencies, changing runtime versions, or touching production databases.

### 10.1 Summary of Executed Commands & Results

| Target | Working Directory | Command Executed | Result | Passed | Failed | Skipped | Warnings / Notes |
|---|---|---|---|---|---|---|---|
| **FastAPI Backend (`pytest`)** | `/Users/bunvathana/Documents/Code/Project/e-commerce/backend` | `rtk .venv/bin/python -m pytest -rs -W default` | **PASS** (`154.51s`) | **702** | **0** | **2** | **2 skipped:** `tests/test_rate_limiting.py:397` & `:440` (`Test Redis server not reachable on port 6389`). **2 warnings:** Starlette `TestClient` deprecation warnings. Test isolation verified via `backend/tests/conftest.py:16-47,105-191` (temp SQLite file + ephemeral local Unix-socket PostgreSQL cluster `/tmp/bp-pg-*`). |
| **Storefront TypeScript** | `/Users/bunvathana/Documents/Code/Project/e-commerce/storefront` | `rtk ./node_modules/.bin/tsc --noEmit --incremental false` | **PASS** | All | 0 | 0 | `0` TypeScript errors. (`--incremental false` used to avoid writing `tsconfig.tsbuildinfo`). |
| **Storefront ESLint** | `/Users/bunvathana/Documents/Code/Project/e-commerce/storefront` | `rtk npm run lint` | **PASS** | All | 0 | 0 | `0` errors, `0` warnings. |
| **Storefront Unit Tests** | `/Users/bunvathana/Documents/Code/Project/e-commerce/storefront` | `rtk npm test` | **PASS** (`3.83s`) | **55** (4 suites) | **0** | **0** | Node warning: `MODULE_TYPELESS_PACKAGE_JSON` (`storefront/package.json` lacks `"type": "module"`). |
| **Storefront Prod Build** | `/Users/bunvathana/Documents/Code/Project/e-commerce/storefront` | `rtk npm run build` | **PASS** | 17 routes | 0 | 0 | Built 15 static routes + 2 dynamic routes (`/product/[id]`, `/sitemap.xml`). |
| **Management TypeScript** | `/Users/bunvathana/Documents/Code/Project/e-commerce/management` | `rtk ./node_modules/.bin/tsc --noEmit --incremental false` | **PASS** | All | 0 | 0 | `0` TypeScript errors. |
| **Management ESLint** | `/Users/bunvathana/Documents/Code/Project/e-commerce/management` | `rtk npm run lint` | **PASS (with warnings)** | All | 0 | 0 | `0` errors, **18 warnings** (unused vars & `<img>` tags in `admin/pos/page.tsx:17,27,28,31,33,34,272`, `seller/products/page.tsx:6,20,65,133,437`, `seller/store/page.tsx:69,117,433`, `DashboardLayout.tsx:17`, `Navbar.tsx:13`, `lib/api.ts:206`). |
| **Management Unit Tests** | `/Users/bunvathana/Documents/Code/Project/e-commerce/management` | `rtk npm test` | **PASS** (`0.19s`) | **86** (14 suites) | **0** | **0** | Node warning: `MODULE_TYPELESS_PACKAGE_JSON`. |
| **Management Prod Build (Default `.env.local`)** | `/Users/bunvathana/Documents/Code/Project/e-commerce/management` | `rtk npm run build` | **FAIL (Exit 1)** | — | 1 | — | Failed at `management/next.config.ts:11`: `Error: NEXT_PUBLIC_API_URL must be a public HTTPS URL without credentials, query, or fragment.` because `.env.local` has `http://localhost:8000/api`. |
| **Management Prod Build (HTTPS Env)** | `/Users/bunvathana/Documents/Code/Project/e-commerce/management` | `rtk env NEXT_PUBLIC_API_URL=https://blue-panda-api-demo.onrender.com/api NEXT_PUBLIC_STOREFRONT_URL=https://blue-panda-storefront-iota.vercel.app npm run build` | **PASS** | 45 routes | 0 | 0 | Built 34 static + 11 dynamic routes cleanly when given HTTPS env vars. |
| **Legacy `web-app` Checks** | `/Users/bunvathana/Documents/Code/Project/e-commerce/web-app` | `tsc --noEmit`, `npm run lint`, `npm test` | **PASS** | **51** (13 suites) | **0** | **0** | `0` TS errors, `0` lint errors, `51` unit tests passed. |
| **Flutter Static Analysis** | `/Users/bunvathana/Documents/Code/Project/e-commerce/mobile-app` | `rtk flutter analyze` | **PASS** (`11.5s`) | All | **0** | **0** | `No issues found! (ran in 11.5s)` |
| **Flutter Widget & Unit Tests** | `/Users/bunvathana/Documents/Code/Project/e-commerce/mobile-app` | `rtk flutter test` | **PASS** (`28.0s`) | **188** | **0** | **0** | `00:28 +188: All tests passed!` |

---

## 11. Deployment & DevOps Status (Phase 9)

### 11.1 Live Cloud Services vs Local Configurations

| Service | Platform | Reference URL / Target | Local Config / Evidence | Current Deployment Status & Findings |
|---|---|---|---|---|
| **Backend API** | Render (Web Service) | `https://blue-panda-api-demo.onrender.com` | `docs/deployment/RENDER_DEPLOYMENT_GUIDE.md:1-130`, `backend/Dockerfile.prod:1-70` | **DEGRADED (Login HTTP 500):** Running committed `ad26cef` from `Bunvathana876/e_commerce_backend`. Health (`/health`) and public product reads work, but `POST /api/auth/login` fails with HTTP 500 because migration `d7e8f9012abc` (`users.legacy_tokens_revoked_at`) has not been applied to Supabase, and committed `ad26cef` omits CORS headers on unhandled 500s (`docs/deployment/MANAGEMENT_LOGIN_CORS_REPORT.md:16-30`). Also, Render Free Tier uses an **ephemeral filesystem**, so images uploaded to `/uploads/products` are wiped on every container redeploy/sleep! |
| **Database** | Supabase (PostgreSQL 17.11) | `blue-panda-demo` (`aws-1-ap-northeast-1`) | `backend/.env.supabase` (redacted), `docs/upgrade/phase_1c_security/dashboard_evidence_20261107.json` | **DRIFTED & EXPOSED:** At Alembic revision `a1b2c3d4e5f6` (1 migration behind `d7e8f9012abc`). Supabase Data API is enabled with `rls = false` and full `arwdDxtm` grants to `anon` and `authenticated` across all 15 `public` tables. |
| **Customer Storefront** | Vercel | `https://blue-panda-storefront-iota.vercel.app` | `storefront/.vercel/project.json` (`prj_SmAezcEOwu3WLSRycrALnompTePe`) | Running committed `04dacab` from `Bunvathana876/e_commerce_storefront`. **Still serves fictional `SHOWCASE_*` products/coupons/sellers/reviews on API error or initial hydration** because the local fixes in `storefront/` are uncommitted. |
| **Management Portal** | Vercel | `https://blue-panda-management.vercel.app` | `management/.vercel/project.json` (`prj_XQODv5hgZp3lPJtSbhqDdK8d5NrQ`) | Running committed `869204e` from `Bunvathana876/e_commerce_mangement`. Admin and seller login are currently blocked by the backend HTTP 500 / missing-CORS-header issue. |

### 11.2 Docker, Docker Compose, and CI/CD Audit
1. **No CI/CD Pipelines Exist:** Neither the root workspace nor any of the nested repositories (`backend/`, `storefront/`, `management/`, `mobile-app/`, `web-app/`) contain a `.github/workflows/` directory or `render.yaml` / `vercel.json` IaC file. Deployments rely on manual/auto-deploy branch pushes without automated test gates.
2. **Root `docker-compose.yml` (`lines 1-118`) vs Split Frontend Architecture:**
   - Root `docker-compose.yml:83-107` still builds and runs `./web-app` (the legacy monolith) on port `3000` instead of `storefront/` and `management/`.
   - Meanwhile, `deploy/production/compose.yaml:1-145` (untracked in root repo) properly defines `postgres`, `redis`, `migrate`, `api`, `storefront`, `management`, and `caddy`, using `Dockerfile.prod` for each service.
3. **`backend/Dockerfile.prod` Upload Path Mismatch (`backend/Dockerfile.prod:54` vs `backend/app/core/config.py:51`):**
   - `Dockerfile.prod:54` creates `/var/lib/blue-panda/uploads` owned by `appuser`, and `deploy/production/compose.yaml:84` mounts a volume at `/var/lib/blue-panda/uploads`, **but `Dockerfile.prod` does not set `ENV UPLOAD_DIR=/var/lib/blue-panda/uploads`**. If run without `compose.yaml` (e.g., on Render), `Settings.UPLOAD_DIR` defaults to `"uploads"` (`/app/uploads`).

---

## 12. End-to-End Integration & Code Quality Review (Phases 11 & 12)

### 12.1 End-to-End Workflow Trace Summary

| # | Workflow | Trace Across Clients & Backend | Verdict & Specific Breakpoints |
|---|---|---|---|
| 1 | **Register → Login → Profile** | `POST /auth/register` → `POST /auth/login` → `GET /auth/me` | **Broken in Prod (HTTP 500 on login due to `users.legacy_tokens_revoked_at`).** Locally works across Web & Mobile, except passwords <8 chars pass web client validation (`AuthForm.tsx:90`) and >72 bytes crash backend (`security.py:17`). |
| 2 | **Browse Product → Product Details** | `GET /products` → `GET /products/{id}` + `GET /reviews?product_id={id}` | **Works locally.** On deployed Storefront (`04dacab`), API errors silently display fake `SHOWCASE_PRODUCTS`. On Mobile, `ProductModel` drops `stock` and `is_active`, showing out-of-stock products as `'In Stock'` (`product_detail_screen.dart:519`). |
| 3 | **Add to Cart → Update Quantity** | Web: Zustand + `/api/cart`; Mobile: `CartProvider` + `/api/v1/cart` | **Works on Web; Broken Sync on Mobile.** Mobile `CartProvider` never calls `loadRemoteCart()` (`cart_provider.dart:283`) and swallows API errors (`lines 332-398`). |
| 4 | **Apply Coupon → Checkout** | `POST /coupons/validate` → `POST /orders` (`CouponService.redeem_coupon_atomic`) | **Server-authoritative discount calculation works.** However: (1) Mobile `CartScreen` suggests invalid chips `SUPER50`/`SUMMER15` *(note: `SUPER50` and `SUMMER15` exist in `DEFAULT_COUPONS` in `coupon_service.py:39-55`, while `seed_data.py:305-315` seeds `WELCOME10`, `SAVE20`, `SUPER50`, `SUMMER15` — if not seeded in prod, they 404)*; (2) No per-user redemption limit exists (`coupon_service.py:107`). |
| 5 | **Place COD Order → Order History** | `POST /orders` → `GET /orders` → `GET /orders/{id}` | **Works, with shipping fee mismatch:** Backend always charges `$2.00` shipping under `$100` (`order_service.py:214`), while Storefront displays `$4.99` under `$50` (`checkout/page.tsx:58`) and Mobile displays `$10.00` Standard / `$15.00` Express (`checkout_screen.dart:99-107`). |
| 6 | **Order Creation → Inventory Deduction** | `OrderService.create_order` → `InventoryService.deduct_stock` | **Verified & Atomic (`inventory_service.py:26-83`).** Uses deterministic `product_id` ordering and atomic conditional `UPDATE ... WHERE stock >= required_qty`, raising `409 Conflict` on race conditions (verified by `backend/tests/test_stock_concurrency.py`). |
| 7 | **Admin Order Management → Customer Status** | `PUT /orders/{id}/status` (`OrderService.update_order_status`) | **Works for COD orders.** Enforces transition graph (`pending -> processing -> shipped -> delivered`) and creates customer notifications. **Broken for Card/KHQR orders**, which can never be marked `paid` (`order_service.py:473-481`). |
| 8 | **Seller Ownership → Product Management** | `GET /seller/products`, `POST/PUT/DELETE /products` + `AuthorizationService` | **Product CRUD ownership works (`authorization_service.py:16-39`).** However, sellers **cannot view or list orders** (`orders.py:16,65,83`), so `management/src/app/(seller)/seller/page.tsx:46` always shows `0` seller orders. |
| 9 | **Wishlist → User Synchronization** | `GET/POST/DELETE /favorites` | **Works on Web Storefront (`store.ts:320-375`). Broken on Mobile:** Mobile never calls `GET /api/v1/favorites` and never persists favorites locally (`product_provider.dart:503-541`). |
| 10 | **Mobile/Web → Shared Backend State** | Shared PostgreSQL `cart_items`, `orders`, `favorites`, `notifications` | **Orders sync across Web & Mobile.** Cart and Favorites do **not** sync on Mobile login because `AuthProvider.login` (`auth_provider.dart:143-189`) wipes local providers without fetching remote cart/favorites/orders/notifications. |

### 12.2 Code Quality, Duplication & Maintainability (Phase 12)

1. **Repository & Code Duplication (`web-app/` vs `storefront/` + `management/`):**
   - `web-app/` duplicates almost the entire codebase of `storefront/` and `management/`, including duplicated `src/lib/api.ts`, `src/lib/auth.ts`, `src/lib/store.ts`, `src/lib/checkout-security.ts`, and admin/seller/store components.
   - **Recommendation:** Formally archive/deprecate `web-app/`, update root `docker-compose.yml` and `AGENTS.md` to reference `storefront/` and `management/`, and remove orphan gitlinks.
   - *Benefit:* Eliminates triple maintenance of Next.js code. *Risk:* Low (already superseded in production by `storefront` and `management` Vercel deployments). *Estimated Scope:* Small (config & docs cleanup).
2. **Duplicate Route Modules in Backend (`routes/sellers.py` vs `routes/seller.py`):**
   - `backend/app/api/v1/routes/seller.py:14-81` (`GET /seller/me`, `PUT /seller/me`, `GET /seller/products`) is an exact copy of `routes/sellers.py:33-100` (`GET /sellers/me`, `PUT /sellers/me`, `GET /sellers/products`).
   - *Recommendation:* Keep thin alias routes delegating to shared helper functions. *Risk:* Very Low. *Scope:* Small (`~50 lines`).
3. **Missing Backend Service Layer for `users.py` and `stats.py`, and Category Logic Inside `product_service.py`:**
   - `backend/app/api/v1/routes/users.py:16-170`, `routes/stats.py:16-63`, and `routes/orders.py:92-112` (`delete_order`) execute SQLAlchemy queries and `db.commit()` directly inside route handlers.
   - *Recommendation:* Extract `UserService` and `StatsService` and move `delete_order` into `OrderService`. *Benefit:* Enforces consistent password policy, session revocation, and stock restoration rules. *Risk:* Low. *Scope:* Medium (`2–3 files`).
4. **Oversized Monolithic Files in Mobile & Management:**
   - Mobile has 6 screens over 1,000 lines (`product_detail_screen.dart`: `2,024 lines`; `home_screen.dart`: `1,775 lines`; `checkout_screen.dart`: `1,479 lines`; `profile_screen.dart`: `1,323 lines`; `cart_screen.dart`: `1,242 lines`; `order_tracking_screen.dart`: `1,048 lines`) plus duplicate `CategoryModel` classes (`lib/features/products/models/category_model.dart` and `lib/features/categories/models/category_model.dart`).
   - Management has large single-file pages (`admin/pos/page.tsx`: `695 lines`; `seller/products/page.tsx`: `615 lines`; `seller/store/page.tsx`: `520 lines`).
   - *Recommendation:* Unify `CategoryModel` in Mobile first; split sub-sections of `product_detail_screen.dart` and `checkout_screen.dart` into focused feature widgets when touching those flows.

---

## 13. Prioritized Improvement Roadmap (Phase 13) & Recommended Next Task

```mermaid
flowchart LR
  P0["P0 — Immediate Production & Security Fixes<br/>1. Apply Supabase RLS/Grant Lockdown (SEC-01)<br/>2. Run Alembic d7e8f9012abc on Supabase<br/>3. Commit & Deploy Backend CORS + Storefront Showcase Removal"] --> P1["P1 — Core Commerce & Role Integrity<br/>1. Fix Admin Notification Wipe Bug (SEC-02)<br/>2. Add Seller Orders API & UI<br/>3. Align Shipping Fee ($2 vs $4.99 vs $10)<br/>4. Fix Mobile Cart/Favorites/Stock Sync"]
  P1 --> P2["P2 — Security & Validation Hardening<br/>1. Fix bcrypt >72B & Register name=None 500s<br/>2. Revoke Sessions on Role/Active Change<br/>3. Prevent Order/User/Category Cascade Loss<br/>4. Rate Limit Checkout, Coupons & Uploads"]
  P2 --> P3["P3 — Architecture & Polish<br/>1. Retire Legacy web-app/ & Fix Root Compose<br/>2. Enable 15m Session Tokens + Secure Storage<br/>3. Add GitHub Actions CI & Cloud Object Storage"]
```

### P0 — Critical Security & Production Blockers (Do Immediately)
1. **Lock Down Production Supabase Data API & Table Grants (`SEC-01`):**
   - Apply `docs/upgrade/phase_1c_security/apply.sql` (`ENABLE ROW LEVEL SECURITY` on all 15 tables in `public` + `REVOKE ALL` from `PUBLIC`, `anon`, `authenticated`) and disable or restrict the Supabase Data API.
2. **Resolve Live Production Login HTTP 500 (`d7e8f9012abc` Migration + Backend Exception/CORS Handling):**
   - Apply Alembic migration `d7e8f9012abc_add_legacy_token_revocation.py` (`ALTER TABLE public.users ADD COLUMN legacy_tokens_revoked_at TIMESTAMP WITH TIME ZONE; UPDATE public.alembic_version SET version_num = 'd7e8f9012abc';`) on production Supabase following `docs/deployment/ADMIN_LOGIN_SCHEMA_MISMATCH_RELEASE_PLAN.md`.
   - Fix `backend/scripts/bootstrap_admin.py:26-29` to include `"legacy_tokens_revoked_at"` in `EXPECTED_COLUMNS`.
   - Commit and deploy the backend CORS/500 handling fix so unhandled exceptions always include `Access-Control-Allow-Origin` without breaking `isinstance(app, FastAPI)`.
3. **Eliminate Fictional Showcase Products from Live Storefront (`storefront/`):**
   - Remove the remaining `SHOWCASE_PRODUCTS` fallback from `storefront/src/app/sitemap.ts:50,58`, commit the pending `storefront/` working-tree fixes (which remove `SHOWCASE_*` fallbacks from `store-catalog.ts` and storefront pages), and deploy to Vercel.

### P1 — Broken Core Commerce Flows & Cross-Client Contract Alignment
1. **Fix Admin Notification Blast-Radius Bug (`SEC-02`):**
   - Update `backend/app/api/v1/routes/notifications.py` and `backend/app/services/notification_service.py:83-87,146-181` so admin `read-all` and `clear-all` never mutate or delete customers' private notifications, and include broadcast notifications (`user_id IS NULL`) for customers.
2. **Fix Seller Order Visibility & Fulfillment:**
   - Add a seller-scoped orders query (`GET /api/seller/orders` or seller filtering in `OrderService`) so sellers can view orders containing their products, and wire `management/src/app/(seller)/seller/page.tsx:46`.
3. **Unify Shipping Fee Contract Across Backend, Storefront, and Mobile:**
   - Align `backend/app/services/order_service.py:214` (`$2.00` under `$100`), `storefront/src/app/(store)/checkout/page.tsx:58` (`$4.99` under `$50`), and `mobile-app/lib/features/checkout/screens/checkout_screen.dart:99-107` (`$10.00` / `$15.00` under `$100`).
4. **Fix Mobile App Truthfulness & State Synchronization (`mobile-app/`):**
   - Remove or replace `OrderTrackingScreen` (`mobile-app/lib/features/orders/screens/order_tracking_screen.dart:1-1048`) so it does not display a fake live GPS map and fake courier `'Sokha Rith'`.
   - Add `stock` and `is_active` to `ProductModel` (`product_model.dart:3-107`).
   - Call `CartProvider.loadRemoteCart()`, `OrderProvider.fetchOrders()`, `NotificationProvider.loadNotifications()`, and `GET /api/v1/favorites` upon login and app startup, and fix the `_hasCleared` notification blackhole (`notification_provider.dart:121-123`).

### P2 — Security Hardening, Validation & Reliability
1. **Fix Backend Auth & Schema Validation Gaps (`SEC-03`, `SEC-04`, `SEC-05`, `SEC-08`, `SEC-09`):**
   - Cap or pre-hash passwords >72 UTF-8 bytes (`password_policy.py:16`, `security.py:17`); require `name` in `RegisterRequest` (`schemas/auth.py:8-24`); move `with_for_update()` in `AuthService.login` (`auth_service.py:61`) after `verify_password`.
   - Enforce `validate_password_strength` and session revocation (`AuthSessionService.revoke_all`) in `routes/users.py:76,132-139` and remove `"Seller123!"` in `seller_service.py:57`.
   - Replace destructive `ondelete="CASCADE"` on `orders.user_id` and `products.category_id`, and ensure order deletion/cancellation always restores stock and coupon usage.
   - Add `gt=0`/`ge=0` constraints and remove writable `rating` in `schemas/product.py:18-46`.
   - Enforce per-user coupon redemption tracking (`coupon_service.py:107`) and verified-purchase + single-review-per-product checks (`review_service.py:84-99`).
2. **Expand Rate Limiting & Fix Management Pagination (`SEC-07`):**
   - Attach `RateLimiter` to `/orders`, `/coupons/validate`, `/upload/image`, `/reviews`, and `/pos/checkout`.
   - Replace hardcoded `limit: 100` in Management Portal (`admin/products`, `admin/inventory`, `admin/pos`, `admin/reports`) with server-side pagination and search.
   - Fix `management/next.config.ts:3-15` so local builds with `http://localhost:8000/api` do not crash.

### P3 — Architecture Cleanup, DevOps & Long-Term Polish
1. **Retire Legacy `web-app/` & Update Root `docker-compose.yml`:**
   - Point root `docker-compose.yml` to `storefront/` and `management/` (matching `deploy/production/compose.yaml`) and clean up root orphan gitlinks.
2. **Migrate Token Storage & Enable Short-Lived Session Tokens (`SEC-06`):**
   - Enable `AUTH_ISSUE_SESSION_TOKENS=True` (15-minute access tokens + rotating refresh tokens), store mobile tokens in `flutter_secure_storage`, and move web tokens to `HttpOnly` cookies.
3. **Add GitHub Actions CI & External Object Storage for Uploads:**
   - Add automated CI workflows (`pytest`, `tsc`, `eslint`, `npm test`, `flutter analyze`, `flutter test`) and move `/uploads/products` from Render's ephemeral container disk to persistent object storage (e.g., Supabase Storage / S3 / Cloudflare R2).

---

### Recommended Next Task (Single Highest-Impact Action)

> **Execute the P0 Production Database & Login Recovery Sequence:**
> 1. **Lock down Supabase (`SEC-01`):** Run `docs/upgrade/phase_1c_security/apply.sql` against the production Supabase database to enable RLS on all 15 `public` tables and revoke `anon`/`authenticated` table privileges.
> 2. **Apply Migration `d7e8f9012abc`:** Run `alembic upgrade head` against production Supabase so `public.users.legacy_tokens_revoked_at` exists (and add `"legacy_tokens_revoked_at"` to `EXPECTED_COLUMNS` in `backend/scripts/bootstrap_admin.py:26-29`).
> 3. **Deploy Backend & Storefront Fixes:** Commit and push the backend CORS/500 handling update (`backend/app/main.py`) and the `storefront/` showcase-removal changes (plus removing `SHOWCASE_PRODUCTS` from `storefront/src/app/sitemap.ts:50,58`) so both production login and truthful storefront catalog rendering are restored immediately.

---

## 14. Remaining Unknowns (`NOT VERIFIED`)

In accordance with strict evidence-based auditing rules, the following external cloud state items could not be directly inspected from the local workspace without querying live cloud provider consoles or mutating/authenticating against production services, and are explicitly marked **NOT VERIFIED**:

1. **Live Render Dashboard Environment Variables (`NOT VERIFIED`):**
   - The exact live values of `CORS_ORIGINS`, `JWT_SECRET_KEY`, `DATABASE_URL`, `RATE_LIMIT_STORAGE_URL`, `AUTH_ISSUE_SESSION_TOKENS`, and `UPLOAD_DIR` currently configured in the Render dashboard for `https://blue-panda-api-demo.onrender.com` cannot be read from local files.
2. **Live Vercel Dashboard Environment Variables (`NOT VERIFIED`):**
   - The exact live values of `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_STOREFRONT_URL`, and `NEXT_PUBLIC_MANAGEMENT_URL` in the Vercel project settings for `blue-panda-storefront` (`prj_SmAezcEOwu3WLSRycrALnompTePe`) and `blue-panda-management` (`prj_XQODv5hgZp3lPJtSbhqDdK8d5NrQ`) are **NOT VERIFIED**.
3. **Current Live Production Supabase State Since 2026-11-07 Snapshot (`NOT VERIFIED`):**
   - Our production Supabase schema (`a1b2c3d4e5f6`) and grant/RLS evidence comes from the verified repository artifacts in `docs/upgrade/phase_1c_security/dashboard_evidence_20261107.json` and `docs/deployment/ADMIN_LOGIN_SCHEMA_MISMATCH_RELEASE_PLAN.md`. To respect production safety rules and avoid connecting to or querying live customer data during this audit, live read queries against `aws-1-ap-northeast-1.pooler.supabase.com` were not executed in this session.
4. **Redis-Backed Rate Limiting Under Multi-Worker Concurrency (`NOT VERIFIED` in this session):**
   - Two Redis integration tests in `backend/tests/test_rate_limiting.py` (`lines 397, 440`) were skipped because no local Redis instance was running on port `6389`.
