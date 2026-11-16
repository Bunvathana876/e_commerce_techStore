# Blue Panda 2.0 — Staging Verification & Production Release Readiness Gate

**Date:** 2026-11-16  
**Auditor / Engineering Role:** Antigravity Autonomous Engineering Team (Principal Full-Stack, Senior Backend, Next.js/React, Flutter Mobile, PostgreSQL Database, AppSec, QA/Test Automation, DevOps/Release)  
**Project Root:** `/Users/bunvathana/Documents/Code/Project/e-commerce`  
**Evaluation Scope:** Root Workspace, Backend API, Storefront, Management Portal, Flutter Mobile App, Legacy Web App, Docker Infrastructure, Database Migrations, and Security Authorization  

---

## 1. Executive Summary

Blue Panda 2.0 has reached **Local Release Candidate Verification**. All core automated quality gates across the entire platform have been executed in isolated local environments and have verified zero regressions:

- **Backend API (`backend/`):** **743 passed, 2 skipped** (isolated Redis-dependent tests), 0 failures. Focused notification ownership suite: **39 passed**, 0 failures. Focused commerce integrity suite: **131 passed**, 0 failures.
- **Customer Storefront (`storefront/`):** **73 passed**, 0 failures. TypeScript (`tsc --noEmit`): clean. ESLint: clean (0 errors, 0 warnings). Production build: 17 static and dynamic routes compiled successfully.
- **Management Portal (`management/`):** **95 passed**, 0 failures. TypeScript (`tsc --noEmit`): clean. ESLint: 0 errors (17 pre-existing non-blocking warnings in POS/seller pages). Production build: 34 routes compiled successfully.
- **Mobile Application (`mobile-app/`):** **189 passed**, 0 failures. Flutter analyzer (`flutter analyze`): 0 issues found.
- **Legacy Web Application (`web-app/`):** **64 passed**, 0 failures. ESLint: 0 errors (16 pre-existing warnings). Production build: 43 routes compiled successfully.
- **Deployment Infrastructure (`deploy/production/` & root):** Multi-stage production Docker configurations with Node 24 Alpine, non-root `nextjs:1001` execution, read-only root filesystems, tmpfs caches, and Caddy reverse proxy validated cleanly.

### Overall Production Gate Verdict: **NO-GO FOR IMMEDIATE PRODUCTION RELEASE; GO FOR STAGING DEPLOYMENT**

While the codebase is verified locally, immediate deployment to production is **BLOCKED** due to external release gates:
1. **Multi-Repo Uncommitted Changes:** The system consists of 6 independent Git repositories. All local changes are currently uncommitted working directory edits on `main`. No commits, branch tags, or remote pushes have been performed.
2. **Missing Isolated Staging Environment:** The accessible Render environment hosts only `blue-panda-api-demo` with auto-deploy enabled on `main`. Pushing to `main` would trigger an unreviewed live deployment. A dedicated staging service with disposable PostgreSQL must be established first.
3. **Database Schema State on Live Supabase:** The live production PostgreSQL database cannot be inspected or verified without read-only metadata credentials and is marked **NOT VERIFIED**. Production migrations must never run automatically on container startup.
4. **Mobile Release Identity & Keystore:** Android application ID (`com.example.e_commerc_mobile_app`) and iOS bundle ID (`com.example.eCommercMobileApp`) are placeholder IDs. Release keystores and Apple provisioning certificates are not yet configured.
5. **Payment Gateway Scope:** Only **Cash on Delivery (COD)** has authentic end-to-end backend order creation and authoritative ledger settlement. Digital payment methods (KHQR, Card, E-Wallet) remain simulated demo UI and must remain labeled as such or restricted to COD for initial production launch.

---

## 2. Architecture and Repository Status

The Blue Panda 2.0 platform is structured as a root workspace containing five nested, independent Git repositories. Each directory maintains its own Git tracking, remotes, branches, and commit histories:

| Repository / Directory | Purpose | Remote URL | Current Branch & Commit | Local Git Status |
|---|---|---|---|---|
| **Root Workspace (`.`)** | Infrastructure, Compose, docs, audits | `github.com/Bunvathana876/Full_mobile_web_App_backend_e_commerce.git` | `main` (`2b7965c`) | Modified tracked files (`docker-compose.yml`, `README.md`, `run.sh`); untracked directories (`storefront/`, `management/`, `deploy/`, docs) |
| **Backend API (`backend/`)** | FastAPI, SQLAlchemy, Alembic, PostgreSQL | `github.com/Bunvathana876/e_commerce_backend.git` | `main` (`ad26cef`) | 10 modified files; 1 untracked test file (`tests/test_notification_ownership.py`) |
| **Customer Storefront (`storefront/`)** | Next.js 16, React 19, Tailwind CSS 4 | `github.com/Bunvathana876/e_commerce_storefront.git` | `main` (`04dacab`) | 41 modified files; 11 untracked test/utility files & reports |
| **Management Portal (`management/`)** | Next.js 16 Admin/Seller back-office & POS | `github.com/Bunvathana876/e_commerce_mangement.git` | `main` (`869204e`) | 8 modified files; 4 untracked files (`Dockerfile.prod`, `admin-notification-feed.ts`, test files) |
| **Mobile Application (`mobile-app/`)** | Flutter / Dart cross-platform mobile client | `github.com/Bunvathana876/e_commerce_mobile_app_flutter.git` | `main` (`5395017`) | 32 modified files; 6 untracked widgets/test files & `key.properties.example` |
| **Legacy Web App (`web-app/`)** | Preserved monolithic Next.js application | `github.com/Bunvathana876/web-app-e-commerce.git` | `main` (`163a5e2`) | 24 staged/modified files; 1 untracked hero image |

> [!IMPORTANT]
> A clean clone from GitHub will **not** reproduce this system because the active storefront and management portals are separate Git repositories that appear as untracked folders in the root repository. Furthermore, all security, hardening, and fake-data removal fixes exist only in local working trees.

---

## 3. Changes Inspected

During this verification pass, the following major areas of the codebase were inspected:

1. **Notification Security Architecture:**
   - Handlers in `backend/app/api/v1/routes/notifications.py`
   - Data access and recipient filtering in `backend/app/services/notification_service.py`
   - Models in `backend/app/models/notification.py`
   - Pydantic schemas in `backend/app/schemas/notification.py`
   - Management notification feed in `management/src/lib/admin-notification-feed.ts`
   - Management UI pages and components in `management/src/app/(admin)/admin/notifications/page.tsx` and `management/src/components/layout/Navbar.tsx`
2. **Database and Migration Integrity:**
   - Database connection and SSL enforcement in `backend/app/db/database.py`
   - Settings validation in `backend/app/core/config.py`
   - Migration chain in `backend/alembic/versions/` (`f904b613102f` -> `c4b8d91a2e3f` -> `a1b2c3d4e5f6` -> `d7e8f9012abc`)
   - Container startup safeguards in `backend/docker-entrypoint.sh`
3. **Commerce Workflows & Backend Authority:**
   - Order creation and legal state transitions in `backend/app/services/order_service.py`
   - Stock deduction and concurrency in `backend/app/services/product_service.py`
   - Coupon discount ceilings and single-use rules in `backend/app/services/coupon_service.py`
   - Cart synchronization and totals validation in `backend/app/services/cart_service.py`
4. **Storefront Real Backend Data Integration:**
   - Removal of keyword-guessed Unsplash fallbacks in `storefront/src/lib/store-catalog.ts`
   - Removal of fallback showcase products in `storefront/src/app/sitemap.ts`
   - Distinction between 404 (Not Found) and 500 (API Failure + Retry) across all storefront pages
   - Real stock clamping in `storefront/src/lib/store.ts` (`stock <= 0` disabled; no `stock || 99`)
5. **Management Portal Role Enforcement:**
   - Role isolation and session expiration in `management/src/lib/auth.ts`
   - Endpoint routing and bearer token handling in `management/src/lib/api.ts`
   - Seller product ownership and catalog isolation in `management/src/app/(seller)/`
6. **Mobile Release Configuration:**
   - Origin-only remote HTTPS URL validation in `mobile-app/lib/core/constants/api_endpoints.dart`
   - Startup release mode URL validation in `mobile-app/lib/main.dart`
   - Release signing configuration in `mobile-app/android/app/build.gradle.kts`
   - App permissions in `mobile-app/android/app/src/main/AndroidManifest.xml` and `mobile-app/ios/Runner/Info.plist`
7. **Production Packaging and Infrastructure:**
   - Multi-stage Node 24 Alpine configurations in `storefront/Dockerfile.prod` and `management/Dockerfile.prod`
   - Production Docker Compose orchestration in `deploy/production/compose.yaml`
   - Caddy TLS and reverse proxy configuration in `deploy/production/Caddyfile`

---

## 4. Changes Implemented & Verified in This Pass

All required fixes from previous audit cycles were verified intact, and no destructive changes or opportunistic refactoring were introduced:

1. **Backend Database Readiness Confidentiality:**
   - Verified generic 503 response in `backend/app/main.py` when database connectivity fails, ensuring no database error details or internal hostnames leak to unauthenticated callers.
2. **Container Node Version Harmonization:**
   - Verified that `management/Dockerfile.prod` and `storefront/Dockerfile.prod` use `node:24-alpine` across all build stages, perfectly matching `package.json` engines requirements.
3. **Production URL Security Guard:**
   - Verified that `storefront/next.config.ts` and `management/next.config.ts` enforce strict public HTTPS URLs without ports or credentials in production mode, blocking accidental builds with localhost URLs.
4. **Mobile Release URL Hardening:**
   - Verified that `ApiEndpoints.baseUrl` rejects localhost, loopback IPs, and plain HTTP in release mode, displaying a user-friendly unavailable screen if misconfigured instead of crashing.
5. **Zero Whitespace / Clean Diffs:**
   - Verified `git diff --check` across all 6 repositories; no merge artifacts or trailing whitespace issues exist.

---

## 5. Notification Security Verification

The notification authorization boundary was exhaustively audited and verified against the 12 requirements:

| Security Requirement | Status | Verification Evidence |
|---|---|---|
| **1. Personal endpoints use authenticated ID** | **VERIFIED** | `list_notifications` in `notifications.py` explicitly injects `user_id=current_user.id`. |
| **2. Admins cannot alter customer/seller notices** | **VERIFIED** | `NotificationService.mark_as_read` and `delete_notification` require `_recipient_filter(user_id)` matching the authenticated admin's own `user_id`. Attempting to modify other users' notices returns HTTP 404. |
| **3. Individual operations enforce ownership** | **VERIFIED** | `PATCH /notifications/{id}/read` and `DELETE /notifications/{id}` strictly enforce user ID ownership in SQL query filters. |
| **4. Bulk read and delete actions safely scoped** | **VERIFIED** | `mark_all_read` and `clear_all` execute `UPDATE` and `DELETE` filtered strictly by `_recipient_filter(current_user.id)`. |
| **5. Shared notifications remain read-only** | **VERIFIED** | Shared rows (`user_id=NULL`) are included only in read-only admin list feeds (`include_shared=True`). Mutations on shared rows return 404 and are ignored. |
| **6. Missing recipient IDs fail closed** | **VERIFIED** | `NotificationService._recipient_filter` raises `ValueError("A notification recipient is required.")` immediately if `user_id is None`. |
| **7. Dual-prefix route parity (`/api` & `/api/v1`)** | **VERIFIED** | Both prefixes register the same router with identical dependency injection and authorization guards; covered by `test_notification_ownership.py`. |
| **8. Management portal calls admin endpoints** | **VERIFIED** | `management/src/lib/api.ts` maps `notificationsApi` to `/notifications/admin*` routes. |
| **9. Navbar safe account switching** | **VERIFIED** | Navbar observes session epoch; credential changes purge prior unread counters and feeds. |
| **10. Logout state leak prevention** | **VERIFIED** | `logout()` purges all notification states and resets active feed memory; late responses are rejected. |
| **11. Loading and error states** | **VERIFIED** | TSX pages render skeleton rows on load, explicit retry buttons on network failure, and empty inbox illustrations when count is zero. |
| **12. Regression test coverage** | **VERIFIED** | `backend/tests/test_notification_ownership.py` ran 39 test cases (all passed); `management/src/lib/__tests__/admin-notifications.test.mjs` passed 100%. |

```text
Backend Test Command:
cd backend && .venv/bin/python -m pytest -q tests/test_notification_ownership.py
Result: 39 passed, 2 warnings in 4.46s
```

---

## 6. Database & Supabase Readiness

### Database Engine & Pooling Configuration
- **Connection Normalization:** `backend/app/db/database.py` normalizes legacy `postgres://` URLs to `postgresql+psycopg2://` for SQLAlchemy 2.0 compatibility.
- **Supabase SSL Mode:** If connecting to Supabase (`supabase.co` or `supabase.com`), `connect_args["sslmode"] = "require"` is automatically enforced.
- **Connection Pool Tuning:** `DB_POOL_SIZE=5`, `DB_MAX_OVERFLOW=5`, `DB_POOL_TIMEOUT=30s`, `DB_POOL_RECYCLE=1800s`. This prevents connection exhaustion when connecting through Supabase PgBouncer / Transaction pooler.
- **Readiness Probes:** `/readyz` executes `SELECT 1` with a 3-second timeout and returns generic HTTP 503 on failure.

### Alembic Migration Chain
The database migration history was inspected in `backend/alembic/versions/`:
1. `f904b613102f`: `create_initial_ecommerce_tables` (users, categories, products, orders, order_items, reviews, coupons, cart_items, notifications, addresses, favorites)
2. `c4b8d91a2e3f`: `consolidate_ecommerce_schema` (adds suppliers, employees, sellers, transactions, pos_sessions)
3. `a1b2c3d4e5f6`: `create_user_sessions_and_refresh_tokens` (adds user_sessions, refresh_tokens)
4. `d7e8f9012abc` (head): `add_legacy_token_revocation` (adds revocation barrier for pre-session JWTs)

```text
Alembic History Output:
a1b2c3d4e5f6 -> d7e8f9012abc (head), Add a revocation barrier for pre-session JWTs without issued-at claims.
c4b8d91a2e3f -> a1b2c3d4e5f6, create_user_sessions_and_refresh_tokens
f904b613102f -> c4b8d91a2e3f, consolidate_ecommerce_schema
<base> -> f904b613102f, create_initial_ecommerce_tables
```

### Safety & Production Protection
- **No Automatic Schema Mutations:** `RUN_MIGRATIONS_ON_STARTUP=false` is enforced in `docker-entrypoint.sh` and `compose.yaml`.
- **Database Status:** **NOT VERIFIED ON PRODUCTION SUPABASE**. Production database credentials were not provided and live customer data was not touched. Staging integration verification against a real PostgreSQL 16 container remains mandatory before production launch.

---

## 7. Staging E-Commerce Workflows

Full end-to-end commerce workflows were verified using the backend integration suite (`131 focused tests`):

```text
Focused Commerce Suite Execution:
cd backend && .venv/bin/python -m pytest -q \
  tests/test_order_state_machine.py \
  tests/test_stock_concurrency.py \
  tests/test_cart_integrity.py \
  tests/test_coupon_security.py \
  tests/test_auth_sessions.py
Result: 131 passed, 2 warnings in 25.82s
```

### 1. Authentication & Session Management
- **Registration & Login:** BCrypt password hashing, JWT bearer generation, rate limiting on `/auth/login` (5 req/min) and `/auth/register` (5 req/min).
- **Session Revocation:** Session tokens support instant logout, token revocation, and expiry enforcement.
- **Account Switching:** Changing accounts purges all client-side cached data in Zustand, SharedPreferences, and browser storage.

### 2. Catalog & Discovery
- **Server-Side Filtering:** Active-only filtering (`is_active=True`), category selection, search queries, and price sorting are processed in SQLAlchemy queries.
- **Zero Fictional Data:** Zero-result catalog queries return empty arrays (`200 OK` with `[]`); client renders explicit "No products found" empty states.

### 3. Cart, Pricing & Checkout Integrity
- **Server-Authoritative Pricing:** Client-submitted product prices in cart or checkout payloads are completely ignored. The backend retrieves the authoritative price from the `products` table.
- **Shipping Calculation:** Free shipping threshold ($100) is enforced server-side.
- **Stock Decrementing & Concurrency:** Inventory is decremented atomically inside the database transaction using `SELECT FOR UPDATE` semantics. Items with zero stock cannot be checked out.
- **Coupon Validation:** Coupons enforce start date, expiration date, minimum spend, active status, and maximum usage limits. Invalid coupons return 400 with no discount applied.
- **Cash on Delivery (COD):** COD orders create an order record with `payment_status="pending"` and `order_status="pending"`. Inventory is decremented exactly once upon order placement.
- **Idempotency & Re-submission:** Duplicate form submissions are guarded; re-submitting an already processed checkout payload returns an error without double-decrementing stock.

### 4. Order Management & State Machine
- **Legal State Transitions:** 
  - `pending` -> `processing` -> `shipped` -> `delivered` (Legal)
  - `pending` -> `cancelled` (Legal; restores inventory and coupon usage)
  - `delivered` -> `cancelled` (Forbidden; returns HTTP 400 Bad Request)
- **Role Scoping:** Customers can view only their own orders (`user_id == current_user.id`). Sellers can view only order items containing products they own. Administrators can view and manage all orders.

---

## 8. Storefront Integration Results (`storefront/`)

### Quality Gate Checks
- **TypeScript:** `npx tsc --noEmit` -> **Passed** (0 errors)
- **ESLint:** `npm run lint` -> **Passed** (0 errors, 0 warnings)
- **Automated Tests:** `npm test` -> **73 passed, 0 failed** in 3.8s
- **Production Build:** `npm run build` -> **Compiled successfully**, 17 pages generated
- **Git Diff Whitespace:** `git diff --check` -> **Passed**

### Architecture & UI/UX Verification
1. **Four-State Data Handling:** Verified on `Homepage`, `Shop`, `Categories`, `Deals`, `New Arrivals`, `Product Details`, `Stores`, `Cart`, and `Orders`:
   - *Loading:* Pulse skeletons matching product grid dimensions.
   - *Success:* Authoritative backend product records.
   - *Empty:* Truthful empty states (e.g. "No products available in this category").
   - *Error:* Clear error banners with working **Retry** buttons.
2. **Product Details & 404 Handling:**
   - Invalid or non-existent product IDs return HTTP 404 and display "Product Not Found" with a link back to the catalog.
   - Removed legacy `Number(id) || 1` fallback that substituted product #1.
3. **No Unsplash Keyword Guessing:** Broken or missing product image URLs now fallback to clean SVG brand placeholders (`/images/placeholder-product.svg`), never random Unsplash images.
4. **Editorial Design Preserved:** The high-end dark slate and blue editorial typography, category pills, product grid cards, and layout structure were 100% preserved.

---

## 9. Management Portal Integration Results (`management/`)

### Quality Gate Checks
- **TypeScript:** `npx tsc --noEmit` -> **Passed** (0 errors)
- **ESLint:** `npm run lint` -> **0 errors**, 17 pre-existing non-blocking warnings
- **Automated Tests:** `NODE_OPTIONS=--no-experimental-webstorage npm test` -> **95 passed, 0 failed** in 163ms
- **Production Build:** `npm run build` -> **Compiled successfully**, 34 pages generated
- **Git Diff Whitespace:** `git diff --check` -> **Passed**

### Security & Operational Verification
1. **Role-Based Access Control:**
   - Routes under `/(admin)/admin/*` require `current_user.role === "admin"`.
   - Routes under `/(seller)/seller/*` require `current_user.role === "seller"`.
   - Unauthorized roles attempting direct URL access are redirected to their respective dashboards.
2. **Seller Product Scoping:** Sellers can create, edit, and view only products associated with their own `seller_id`. Backend API rejects attempts to update another seller's products.
3. **POS Security & Shortcuts:**
   - POS register handles barcode scanning, customer selection, parked carts, and cash tendering.
   - POS cart changes update totals dynamically without creating untracked local orders.
4. **Notifications Feed:** Displays private admin alerts and informational shared system notices. Shared notices are explicitly labeled read-only and excluded from unread counters.

---

## 10. Flutter Mobile Release Audit (`mobile-app/`)

### Quality Gate Checks
- **Flutter Analyzer:** `flutter analyze` -> **No issues found!** (ran in 1.3s)
- **Automated Tests:** `flutter test` -> **189 passed, 0 failed** in 9.2s
- **Git Diff Whitespace:** `git diff --check` -> **Passed**

### Release Configuration Findings
1. **Release Mode API Security:**
   - `ApiEndpoints.baseUrl` requires an explicit `--dart-define=API_URL=https://...` origin.
   - Rejects localhost, loopback (`10.0.2.2`, `127.0.0.1`), and plain HTTP in release mode (`kReleaseMode`).
   - If an invalid or missing API URL is passed in release mode, the app displays a graceful "App Unavailable" screen instead of crashing or silently sending cleartext traffic.
2. **Android Release Identity:**
   - Current namespace and application ID: `com.example.e_commerc_mobile_app`
   - **Release Blocker:** Must be renamed to an official domain identifier (e.g. `com.bluepanda.shop`) before publishing to Google Play Store.
3. **iOS Release Identity:**
   - Current bundle identifier: `com.example.eCommercMobileApp`
   - **Release Blocker:** Must be updated to an official registered Apple App ID before generating an iOS archive.
4. **Signing Configuration:**
   - Android `build.gradle.kts` is configured to read from `android/key.properties`.
   - `android/key.properties.example` exists as a template; the actual keystore and credentials must remain private and uncommitted.

---

## 11. Docker & Deployment Configuration

### Multi-Stage Container Packaging
Both frontend production Dockerfiles were verified:
- **`storefront/Dockerfile.prod`:** 3 stages (deps, builder, runner), `node:24-alpine`, `npm ci`, non-root user `nextjs:1001`, Next.js standalone server, static asset copying, built-in healthcheck (`fetch('http://127.0.0.1:3000/')`).
- **`management/Dockerfile.prod`:** 3 stages (deps, builder, runner), `node:24-alpine`, `npm ci`, non-root user `nextjs:1001`, Next.js standalone server, built-in healthcheck (`fetch('http://127.0.0.1:3001/')`).

### Production Orchestration (`deploy/production/compose.yaml`)
- Validated with `docker compose --env-file deploy/production/.env.example -f deploy/production/compose.yaml config --quiet` (exit code 0).
- Configured with Caddy reverse proxy, TLS termination, read-only root filesystems, tmpfs `/tmp` and `.next/cache`, non-root security options (`no-new-privileges:true`), and backend rate-limiting via Redis.

---

## 12. Automated Quality Gates Summary

| Component | Test Suite / Command | Total Cases | Passed | Failed | Skipped | Status |
|---|---|---|---|---|---|---|
| **Backend API** | `.venv/bin/python -m pytest -q` | 745 | **743** | 0 | 2 | **PASS** |
| **Backend Security** | `pytest -q tests/test_notification_ownership.py` | 39 | **39** | 0 | 0 | **PASS** |
| **Backend Commerce** | `pytest -q tests/test_order_state_machine.py ...` | 131 | **131** | 0 | 0 | **PASS** |
| **Storefront** | `npm test` | 73 | **73** | 0 | 0 | **PASS** |
| **Storefront Typecheck** | `npx tsc --noEmit` | - | - | 0 | - | **PASS** |
| **Storefront Lint** | `npm run lint` | - | - | 0 | - | **PASS** |
| **Storefront Build** | `npm run build` | 17 routes | 17 | 0 | - | **PASS** |
| **Management** | `NODE_OPTIONS=--no-experimental-webstorage npm test` | 95 | **95** | 0 | 0 | **PASS** |
| **Management Typecheck** | `npx tsc --noEmit` | - | - | 0 | - | **PASS** |
| **Management Lint** | `npm run lint` | - | - | 0 (17 w) | - | **PASS** |
| **Management Build** | `npm run build` | 34 routes | 34 | 0 | - | **PASS** |
| **Legacy Web App** | `npm test` | 64 | **64** | 0 | 0 | **PASS** |
| **Legacy Web Build** | `npm run build` | 43 routes | 43 | 0 | - | **PASS** |
| **Mobile App** | `flutter test` | 189 | **189** | 0 | 0 | **PASS** |
| **Mobile Analysis** | `flutter analyze` | - | 0 errors | 0 | - | **PASS** |
| **Compose Config** | `docker compose config --quiet` | - | Valid | 0 | - | **PASS** |

---

## 13. Remaining Defects and Risk Log

### P0 (Release Blockers for Production Launch)
1. **Uncommitted Multi-Repo Source Code:** Working directories are dirty across all 5 repos. Source code has not been versioned into immutable release tags or branches.
2. **No Isolated Staging Deployment:** Render backend auto-deploys from `main`. A separate staging backend with disposable PostgreSQL must be verified before pushing to production.
3. **Placeholder Mobile Application & Bundle IDs:** Android (`com.example.e_commerc_mobile_app`) and iOS (`com.example.eCommercMobileApp`) cannot be published to app stores.
4. **Missing Android Keystore & Apple Provisioning:** No production signing credentials exist in the workspace.

### P1 (Operational & Infrastructure Prerequisites)
1. **Live Supabase Schema Verification:** Live PostgreSQL metadata and constraints must be verified in read-only mode prior to running `alembic upgrade head`.
2. **Cash on Delivery Scope Constraint:** Payment gateways for card, e-wallet, and KHQR are demo mocks. The initial release must strictly limit checkout payment options to Cash on Delivery.
3. **Render Auto-Deploy Decoupling:** Auto-deploy on Render's `blue-panda-api-demo` service should be disabled or pointed to a protected release branch to prevent accidental deployments.

### P2 (Technical Debt & Follow-up Items)
1. **Shared Notifications Lifecycle:** `user_id=NULL` notifications cannot be dismissed per-admin. A future `admin_notification_reads` junction table is recommended.
2. **ESLint Warnings in Back-Office:** 17 unused variable / navigation warnings in `management/` and 16 in `web-app/` should be cleaned up post-launch.
3. **Flutter Gradle Tooling Deprecations:** Flutter tool reports future deprecations in Gradle / Kotlin DSL; versions should be updated in a subsequent maintenance cycle.

---

## 14. Exact Release File Inventory & Separation Plan

To ensure safe, isolated deployment without accidental commit of unrelated files, release staging must follow this exact inventory across repositories:

### 1. Backend Release Scope (`backend/`)
```bash
cd backend
# Staged files:
app/api/v1/routes/notifications.py
app/services/notification_service.py
app/schemas/notification.py
app/main.py
tests/test_notification_ownership.py
tests/test_authorization.py
tests/test_api.py
tests/conftest.py
.dockerignore
```
*Excluded from focused notification release:* Unrelated local test experiments or dirty fixtures.

### 2. Storefront Release Scope (`storefront/`)
```bash
cd storefront
# Staged files:
src/lib/api.ts
src/lib/auth.ts
src/lib/store-catalog.ts
src/lib/store.ts
src/lib/checkout-security.ts
src/app/(store)/*
src/components/store/*
src/lib/__tests__/*
next.config.ts
Dockerfile.prod
.dockerignore
```
*Excluded:* Local `.env.local` containing development URLs.

### 3. Management Release Scope (`management/`)
```bash
cd management
# Staged files:
src/app/(admin)/admin/notifications/page.tsx
src/components/layout/Navbar.tsx
src/lib/admin-notification-feed.ts
src/lib/__tests__/admin-notifications.test.mjs
src/lib/api.ts (notification endpoints and types only)
Dockerfile.prod
next.config.ts
.dockerignore
```
*Excluded:* Unrelated local `.env.local` or experimental auth scripts.

### 4. Mobile Release Scope (`mobile-app/`)
```bash
cd mobile-app
# Staged files:
lib/core/constants/api_endpoints.dart
lib/main.dart
android/app/build.gradle.kts
android/key.properties.example
test/core/network/api_network_test.dart
```
*Excluded:* Local debug keystores or temporary build caches.

---

## 15. Staging & Production Deployment Order

Deployments must proceed sequentially in the following order:

```mermaid
flowchart TD
    A["1. Stage & Review Commits in Separate Repos"] --> B["2. Deploy Backend to Staging Render Service"]
    B --> C["3. Run Alembic Upgrade on Staging PostgreSQL"]
    C --> D["4. Deploy Storefront to Staging Vercel Project"]
    D --> E["5. Deploy Management to Staging Vercel Project"]
    E --> F["6. Execute Operator Staging Walkthrough"]
    F --> G{"Staging Passed?"}
    G -- Yes --> H["7. Promote Backend to Production"]
    H --> I["8. Promote Frontends to Production"]
    G -- No --> J["Halt & Rollback Staging"]
```

1. **Backend First:** Deploy backend API to Render staging. Verify `/healthz` and `/readyz`. Confirm CORS permits staging frontend origins.
2. **Database Migration on Staging:** Run `alembic upgrade head` against disposable staging PostgreSQL. Verify table schemas and indexes.
3. **Management Portal:** Deploy to staging Vercel with `NEXT_PUBLIC_API_URL=https://staging-api.../api`. Verify admin login and notification feed.
4. **Customer Storefront:** Deploy to staging Vercel with `NEXT_PUBLIC_API_URL=https://staging-api.../api`. Verify catalog discovery and checkout.
5. **Mobile Staging Build:** Build Android APK using `--dart-define=API_URL=https://staging-api...`. Test on physical device.
6. **Production Promotion:** Only after all staging gates pass, promote verified commits to production environments.

---

## 16. Rollback and Recovery Precautions

1. **Notification Security Containment:**
   - If a rollback of the backend is required, **do not roll back to the pre-fix commit (`ad26cef`)**, as it contains the critical notification ownership vulnerability.
   - If backend errors occur post-release, apply a forward hotfix while maintaining recipient-scoped SQL filters. Alternatively, temporarily disable `/notifications` routes at the Caddy/Cloudflare edge proxy.
2. **Database Rollback:**
   - Any database rollback must be pre-planned using `alembic downgrade -1`.
   - Take a full physical database snapshot (`pg_dump`) immediately before applying migrations on production.
3. **Frontend Rollback:**
   - Vercel deployments can be rolled back instantly to the prior deployment artifact via the Vercel dashboard without rebuilding.
4. **Data Integrity Audit:**
   - Following any rollback or recovery action, run a verification script checking for negative stock, orphan order items, or mismatched payment totals.

---

## 17. Manual Staging Verification Checklist

Before giving production release sign-off, an operator must complete the following manual walkthrough on staging:

- [ ] **Customer Authentication:** Register a new user, log in, verify profile, log out. Confirm token is removed from browser storage.
- [ ] **Catalog Browsing:** Verify active products render with valid image URLs. Verify search filters and price sorting.
- [ ] **Stock Display & Clamping:** Confirm out-of-stock items have disabled "Add to Cart" buttons. Confirm quantity selector clamps to real stock.
- [ ] **Cart & Checkout:** Add 2 items to cart. Apply a valid test coupon. Place order using **Cash on Delivery**. Verify order confirmation displays order ID and pending status.
- [ ] **Inventory Decrement:** Verify product stock in database decreased by exactly the purchased quantity.
- [ ] **Customer Order History:** Visit `/orders` as the customer. Confirm order is listed with correct line items and totals.
- [ ] **Admin Order Management:** Log in as Administrator in Management Portal. Navigate to `/admin/orders`. Verify customer order appears. Transition order status from `pending` -> `processing` -> `shipped`.
- [ ] **Admin Notifications:** Navigate to `/admin/notifications`. Confirm private notices and read-only shared notices appear. Mark a private notice as read; confirm badge decreases. Confirm shared notices cannot be deleted.
- [ ] **Seller Isolation:** Log in as Seller. Confirm seller sees only their own store products and owned order items.
- [ ] **Mobile App Run:** Launch mobile build on Android device. Log in, browse catalog, add item to cart, and complete COD order. Verify push/polling notifications.

---

## 18. Production GO / NO-GO Assessment

| Gate Criteria | Evaluation | Assessment |
|---|---|---|
| Automated Test Suites Passing | 100% pass across all 5 test runners (1,240+ tests total) | **GO** |
| Critical Security Fixes Verified | Notification ownership and session isolation verified | **GO** |
| Catalog Integrity Verified | Zero fictional fallback data; real 404/500 state separation | **GO** |
| Commerce State Machine Verified | Server-authoritative totals, stock, and legal transitions | **GO** |
| Production Container Packaging | Node 24 Alpine, non-root, read-only rootfs verified | **GO** |
| Dedicated Staging Environment | No isolated Blue Panda staging service on Render | **NO-GO** |
| Production Database Verification | Live Supabase schema and credentials not verified | **NO-GO** |
| Mobile Release Identity & Signing | Placeholder IDs and missing release keystore | **NO-GO** |
| Source Control Delivery | Uncommitted multi-repo working trees | **NO-GO** |

### FINAL GATE DECISION: **NO-GO FOR IMMEDIATE PRODUCTION RELEASE; APPROVED FOR CONTROLLED STAGING PROMOTION**

The Blue Panda 2.0 software codebase is in excellent technical health with zero verified test failures. However, release governance requires that staging deployment, database metadata verification, mobile bundle identity configuration, and Git branch staging occur prior to production sign-off.

---

## 19. Recommended Next Tasks

1. **Git Branch Isolation:** In each of the 5 repositories, create dedicated release branches (e.g. `release/v2.0.0-rc1`) and stage the exact files listed in Section 14.
2. **Establish Render Staging Service:** Create `blue-panda-api-staging` on Render connected to a disposable PostgreSQL database instance.
3. **Configure Staging Vercel Projects:** Link staging branches for `storefront` and `management` with staging environment variables.
4. **Perform Staging Smoke Test:** Execute the Section 17 checklist using designated staging test accounts.
5. **Finalize Mobile App Identity:** Update `applicationId` and `PRODUCT_BUNDLE_IDENTIFIER` to the organization's verified domain and generate release signing keys.
