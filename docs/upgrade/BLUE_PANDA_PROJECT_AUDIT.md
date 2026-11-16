# Blue Panda E-Commerce — Production-Grade Project Audit

**Document:** Comprehensive Multi-Domain Architecture, Security, Performance, and Operational Audit  
**Version:** 1.0.0  
**Audit Date:** 2026-11-03  
**Status:** Verified against Source Code & Graphify Knowledge Graph (`graphify-out/graph.json`)  
**Auditors:** Senior Software Architect, Full-Stack Engineer, Security Engineer, DevOps Engineer  

---

## 1. Executive Summary

Blue Panda is an active multi-client e-commerce marketplace consisting of:
- **Customer Storefront (`storefront/`):** Next.js 16.3.4, React 19, Tailwind CSS 4, Zustand 5, Plus Jakarta Sans.
- **Admin & Seller Portal (`management/`):** Next.js 16.3.4, React 19, Tailwind CSS 4, Plus Jakarta Sans.
- **REST API Backend (`backend/`):** Python 3.12, FastAPI, SQLAlchemy 2 (sync), Pydantic 2, Alembic, PostgreSQL 16.
- **Customer Mobile App (`mobile-app/`):** Flutter / Dart, Material 3, Provider / ChangeNotifier, SharedPreferences.
- **Preserved Legacy Application (`web-app/`):** Monolithic Next.js application preserved as fallback.
- **Production Infrastructure Skeleton (`deploy/production/`):** Caddy reverse proxy, compose specification, environment templates.

The project has achieved significant milestones: separation of customer and management frontends, initial multi-vendor seller center scaffolding (Phase B.1, B.2, C.1), backend role dependencies, atomic stock deduction, upload raster validation, and isolated PostgreSQL migration testing.

However, the platform is **not yet internet-facing production-ready**. Critical vulnerabilities, API contract ambiguities, data integrity hazards, lack of production Docker builds, missing rate limiting, and unhedged database recovery procedures represent urgent release gates.

---

## 2. In-Depth Analysis Across 10 System Domains

### Domain 1: Project Architecture and Dependencies

#### Current State
- **Topology:** Decoupled into four distinct runtime components (`storefront`, `management`, `backend`, `mobile-app`), plus root development Docker Compose and production deployment skeleton.
- **Submodules & Repositories:** `backend/`, `mobile-app/`, and `web-app/` are gitlinks with nested `.git` repositories. `storefront/` and `management/` are untracked directories in the root worktree. No formal `.gitmodules` mapping exists, creating repository boundary confusion during CI/CD checkout.
- **Dependency Health:**
  - `backend/`: Pinned in `requirements.txt` (FastAPI 0.110.0, SQLAlchemy 2.0.28, Pydantic 2.6.4, Alembic 1.13.1, Pillow 10.2.0, Passlib/Bcrypt).
  - `storefront/` & `management/`: Next.js 16.3.4, React 19.2.8, Tailwind 4. Single-stage dev Dockerfiles execute `npm install` without lockfile enforcement (`npm ci`).
  - `mobile-app/`: Flutter 3.x, `http: ^1.2.0`, `provider: ^6.1.1`, `shared_preferences: ^2.2.2`.

#### Deficiencies & Risks
1. **Repository Boundary Fragility:** Lack of standardized Git submodules or monorepo workspace configuration blocks reproducible automated CI builds.
2. **Container Build Drift:** Frontends install floating dependencies via `npm install` inside Alpine containers, risking silent upstream breakage.

---

### Domain 2: Customer Authentication and Authorization

#### Current State
- **Backend Auth Flow:** `POST /api/v1/auth/login` and `POST /api/v1/auth/register` issue standard HS256 JWT access tokens signed with `JWT_SECRET_KEY` and default 7-day expiration (`backend/app/core/security.py`).
- **Authorization Dependencies:** Server-side dependency injection via `require_roles("admin")`, `require_roles("seller", "admin")`, and `get_current_user` in `backend/app/core/dependencies.py`.
- **Client Token Storage:** Frontends store JWTs in browser `localStorage` under `storefront_token` and `mgmt_token`. Mobile persists tokens via `SharedPreferences`.

#### Deficiencies & Risks
1. **Ineffective Logout (Revocation Gap):** `POST /api/v1/auth/logout` is a server-side no-op returning `{"success": True}` (`backend/app/api/v1/routes/auth.py` lines 80–85). Issued JWTs cannot be revoked and remain valid until expiry (up to 7 days).
2. **XSS & Token Theft:** Storing tokens in `localStorage` makes user sessions vulnerable to cross-site scripting.
3. **No Refresh Token Flow:** `mobile-app/lib/core/constants/api_endpoints.dart` specifies `refreshToken = '/api/v1/auth/refresh'`, but no such route exists on the backend. When a 7-day token expires, users are abruptly kicked out without silent refresh.
4. **Brute Force & Credential Stuffing:** Zero rate limiting or IP throttling on `/login`, `/register`, or `/me`.
5. **Weak Password Policy:** Passwords require only 6 characters (`backend/app/schemas/user.py`), with no complexity, entropy, or breached-password checks.

---

### Domain 3: Product Catalog and Categories

#### Current State
- **Catalog Management:** `ProductService.get_products` and `ProductService.get_seller_products` handle queries, category filtering, price filtering, and pagination.
- **Frontend Presentation:** Storefront renders responsive product grids, category shelves, discount comparisons, and product detail views (`/product/[id]`).

#### Deficiencies & Risks
1. **Unindexed ILIKE Text Search:** Search queries execute `(Product.name.ilike(search_term)) | (Product.description.ilike(search_term))` (`backend/app/services/product_service.py` lines 108–112). This triggers full sequential table scans in PostgreSQL on every keystroke/query.
2. **Missing Compound Indexes:** Missing indexes on `(seller_id, is_active)` and `(category_id, is_active, created_at)` cause slow filtering as catalog size scales.
3. **Overly Permissive Remote Image Policy:** `storefront/next.config.ts` and `management/next.config.ts` configure `remotePatterns` with `protocol: 'https'` and `hostname: '**'`, opening the Next.js image optimization endpoint to SSRF and third-party bandwidth abuse.

---

### Domain 4: Shopping Cart and Checkout

#### Current State
- **Storefront Cart:** Zustand store provides optimistic UI cart management synchronized with backend `/api/cart`.
- **Checkout Process:** Order creation validates shipping address, calculates coupon discounts, applies shipping fee tiers, deducts inventory atomically, records order items with historical price snapshots, creates user notification, and empties the cart.

#### Deficiencies & Risks
1. **Ambiguous Cart Item Targeting Hazard:** In `backend/app/services/cart_service.py` (lines 111 & 136):
   ```python
   where((CartItem.id == item_id) | (CartItem.product_id == item_id))
   ```
   - Storefront sends `CartItem.id` via `/api/cart/items/{itemId}`.
   - Mobile sends `Product.id` via `/api/v1/cart/{productId}`.
   - If User has CartItem #5 (Product #10) and CartItem #10 (Product #22), calling `/cart/10` produces a non-deterministic match that mutates or deletes the wrong cart item.
2. **Client-Server Contract Mismatch:** Mobile's `ApiEndpoints.cartItem(int productId)` violates REST resource naming conventions by passing product ID into a cart item route parameter.

---

### Domain 5: Payment and Order Handling

#### Current State
- **Payment Method:** Exclusively Cash on Delivery (COD) and Cash Settlement.
- **State Machine:** Orders progress through `pending` -> `processing` -> `shipped` -> `delivered` / `cancelled`. Order creation enforces `payment_status="pending"` truthfully.
- **Atomic Rollback:** Database commit failures roll back order creation, stock deductions, and coupon usage atomically.

#### Deficiencies & Risks
1. **Distorted Dashboard Revenue Fallback:** In `backend/app/api/v1/routes/stats.py` (lines 29–31):
   ```python
   # If no paid orders yet, sum all orders for development preview
   if total_revenue == 0:
       total_revenue = db.scalar(select(func.sum(Order.total))) or Decimal("0.00")
   ```
   This violates truthful data guarantees. If a new store has 5 pending or cancelled orders worth $500, it falsely reports "$500.00 Revenue".
2. **No Real Payment Gateway:** UI mentions simulated payment cards/wallets in legacy paths. No real payment processor (Stripe, PayPal, Bakong KHQR, etc.), webhook signature verifier, or idempotency keys exist.

---

### Domain 6: Inventory Management

#### Current State
- **Concurrency Control:** `InventoryService.deduct_stock` and `restore_stock` use `SELECT ... FOR UPDATE` row-level locks ordered deterministically by `Product.id ASC` to eliminate deadlocks.
- **Verification:** Verified by comprehensive concurrency test suite (`backend/tests/test_stock_concurrency.py`).

#### Deficiencies & Risks
1. **Missing Seller Stock Adjustment UI:** Sellers cannot update stock levels directly from the Seller Center. Phase C.3 (`/seller/inventory`) is pending.
2. **Lack of Inventory Audit Ledger:** Stock deductions modify `Product.stock` directly without logging an immutable inventory transaction entry (`StockMovement` table with reason, user, order ID, timestamp).

---

### Domain 7: Admin and Seller Features

#### Current State
- **Admin Portal (`management/src/app/(admin)/admin`):** Full dashboard, product administration, category management, seller moderation, orders, inventory, POS terminal, transactions, and reports.
- **Seller Center (`management/src/app/(seller)/seller`):**
  - Completed: Dedicated layout with role check, `/seller/store` (profile view & update), `/seller/products` (scoped product list with search/filters).
  - Backend Scoping: Strict isolation where `Product.seller_id == seller.id`, ignoring client-supplied `seller_id` parameters.

#### Deficiencies & Risks
1. **Incomplete Seller Center Workflow:**
   - Phase C.2: Cannot create or edit products (`/seller/products/new`, `/seller/products/[id]/edit` are disabled with placeholder badges).
   - Phase C.3: Cannot adjust low/out-of-stock items (`/seller/inventory` does not exist).
   - Phase D: Cannot view or fulfill orders (`/seller/orders` and `/seller/stats` do not exist).
2. **Admin Seller Approval Enforcement:** Platform allows sellers to register, but administrative verification/suspension gates need end-to-end integration with storefront visibility.

---

### Domain 8: Flutter API Integration

#### Current State
- **Networking Architecture:** `ApiClient` singleton with interceptors, base URL switching (`--dart-define=API_URL=...`), typed exceptions, and Provider-based state management.
- **Compatibility:** Communicates with `/api/v1/*` endpoints.

#### Deficiencies & Risks
1. **Hardcoded Mock Fallbacks:** `AuthService`, `ReviewsApiService`, and `CouponApiService` include explicit offline mock fallbacks. If `useRemoteBackend: false` is accidentally used or network fails, fake data or mock authentication (`Bun Vathana / student@example.com`) can appear.
2. **Broken Refresh Endpoint:** Mobile relies on `/api/v1/auth/refresh` which returns HTTP 404 on the backend.
3. **Cart Endpoint Contract Divergence:** Mobile targets cart by `productId` instead of `cartItemId`.
4. **Theme / Dark Mode Inconsistencies:** High contrast issues and hardcoded color values exist on selected mobile checkout and notification screens.

---

### Domain 9: Docker and Deployment Configuration

#### Current State
- **Development Compose:** `docker-compose.yml` runs 5 services (`storefront`, `management`, `backend`, `postgres`, `pgadmin`). Mounts host folders, runs dev servers with hot reload, auto-applies Alembic and seeds demo data on every startup.
- **Production Skeleton:** `deploy/production/compose.yaml` establishes private proxy/data networks, read-only root filesystems, tmpfs, Caddy TLS ingress, and explicit environment validation.

#### Deficiencies & Risks
1. **Absence of Production Dockerfiles:** Both Next.js frontends and FastAPI only have single-stage development Dockerfiles that run `npm run dev` and `uvicorn --reload` as root.
2. **Dangerous Startup Migration & Seeding:** `backend/docker-entrypoint.sh` executes `alembic upgrade head`, `init_db` (create_all), and `seed_data` on every boot. A container crash/restart could mutate or corrupt production database tables without prior backup.
3. **Missing Health vs Readiness Separation:** `/health` returns static `{"status": "healthy"}` without pinging PostgreSQL. If PostgreSQL crashes, the backend container remains marked healthy by Docker and Caddy keeps routing traffic to it.

---

### Domain 10: Database and Upload Storage

#### Current State
- **ORM & Migrations:** SQLAlchemy 2 DeclarativeBase, Alembic with 2 revisions (`f904b613102f` and `c4b8d91a2e3f`).
- **File Upload Security:** `UploadService` validates magic bytes, verifies PNG/JPEG/WEBP chunk headers, strips metadata, enforces max byte and pixel limits, and uses random UUID filenames.

#### Deficiencies & Risks
1. **Local Disk Storage for Media:** Uploaded images are stored in `/app/uploads` on the local container filesystem. Ephemeral container redeployments without persistent volume mapping will cause image loss.
2. **No Automated Database Backups:** No automated pg_dump cron job, off-site replication, retention policy, or documented restore drill exists.
3. **Database Connection Pool Sizing:** Implicit connection pool (`pool_pre_ping=True`) without explicit pool size, overflow, or recycling limits suited for multi-worker production traffic.

---

## 3. Detailed Multi-Domain Findings Table

| Area | Observed State | Risk / Severity | Production Impact | Required Remediation |
| :--- | :--- | :--- | :--- | :--- |
| **Security** | `POST /logout` is a no-op; tokens stored in `localStorage`; no rate limiting; no server-side revocation. | **CRITICAL** | Stolen tokens remain valid for 7 days; vulnerable to credential stuffing. | Add Redis/DB token revocation blacklist, implement rate limiting with Slowapi, add refresh tokens. |
| **Data Integrity** | `stats.py` sums unpaid orders as revenue if paid revenue is $0; `cart_service.py` matches `CartItem.id == item_id \| Product.id == item_id`. | **CRITICAL** | False financial reporting in admin dashboard; non-deterministic cart item mutations. | Remove development preview fallback in stats; enforce strict `CartItem.id` parameter with explicit separate `productId` endpoint. |
| **Deployment** | Only dev Dockerfiles exist; `docker-entrypoint.sh` runs migrations and seeding on boot; root user execution. | **CRITICAL** | Production crashes, unvetted schema modifications, container privilege escalation. | Create multi-stage non-root production Dockerfiles; isolate migration runner from container entrypoint. |
| **Availability** | `/health` returns static 200 without checking PostgreSQL connection; pool unconfigured. | **HIGH** | Caddy routes customer traffic to dead backend when database is unreachable. | Implement `/readyz` with `SELECT 1` DB probe; configure connection pool limits and timeouts. |
| **Performance** | Product search uses unindexed `ILIKE %query%`; missing compound indexes on active products. | **HIGH** | High CPU utilization and slow query latency under concurrent customer searches. | Add PostgreSQL `pg_trgm` GIN index on product name/description and compound index on `(category_id, is_active)`. |
| **Client Parity** | Mobile expects `/api/v1/auth/refresh` (404); mobile cart uses `productId`; mock auth present in codebase. | **HIGH** | Mobile session refreshes fail; silent mock fallback risk; cart synchronization inconsistencies. | Implement `/auth/refresh` on backend; synchronize cart API contract; strip mock auth in release builds. |
| **Marketplace** | Seller Center missing product creation/edit (C.2), inventory adjustments (C.3), and order fulfillment (D). | **MEDIUM** | Inability for third-party sellers to operate autonomously; admin bottleneck. | Complete Phase C.2, C.3, and Phase D Seller Center workflows. |
| **Media / Storage** | Uploaded media stored on local disk; Next.js remote image policy allows wildcard `**`. | **MEDIUM** | Loss of product images upon container recreation; SSRF / image proxy abuse. | Back uploads with durable persistent volume (or S3/GCS); restrict Next.js `remotePatterns` to trusted origins. |
| **Observability** | Standard stdout logs without JSON structured fields; no request correlation IDs; no Prometheus metrics. | **MEDIUM** | Difficult distributed troubleshooting and audit tracking during production incidents. | Add structured JSON logging middleware with `X-Request-ID` propagation. |
| **Recovery** | No automated database backup script, encryption, offsite copy, or tested restore procedure. | **HIGH** | Irrecoverable data loss in event of host failure or volume corruption. | Create automated encrypted backup script with cron retention and verified restore runbook. |
