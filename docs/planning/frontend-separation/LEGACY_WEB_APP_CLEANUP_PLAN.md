# Blue Panda E-Commerce — Legacy `web-app/` Cleanup & Decommission Plan

**Document Version:** 1.0  
**Date:** 2026-10-31  
**Status:** DRAFT — Awaiting User Approval before execution  
**Rule:** DO NOT delete, rename, or archive `web-app/` until explicit approval is granted.

---

## 1. Migration Completeness Audit

A 100% complete migration of all routes, features, and assets from `web-app/` into `storefront/` and `management/` has been verified.

### Route Migration Status

| Original Route in `web-app/` | New Location | Status | Notes |
| :--- | :--- | :--- | :--- |
| `/(store)` (11 routes) | `storefront/src/app/*` | **Migrated** | Independent customer storefront app on `:3000` |
| `/(admin)/admin/*` (24 routes) | `management/src/app/(admin)/admin/*` | **Migrated** | Full admin suite with POS & reports on `:3001` |
| `/(seller)/seller/*` (4 routes) | `management/src/app/(seller)/seller/*` | **Migrated** | Seller Center suite with store profile on `:3001` |
| `/(auth)/login`, `register` | Both apps | **Migrated** | Split customer login (:3000) vs admin/seller (:3001) |
| `/_not-found` | Both apps | **Migrated** | Dedicated 404 page in each application |

### Components & State Migration Status

| Original Artifact in `web-app/` | New Location | Status | Notes |
| :--- | :--- | :--- | :--- |
| `components/store/*` | `storefront/src/components/store/*` | **Migrated** | CartDrawer, ProductCard, StoreNavbar, StoreFooter, QuickViewDialog |
| `components/layout/*` | `management/src/components/layout/*` | **Migrated** | AdminSidebar, DashboardLayout, Navbar |
| `components/seller/*` | `management/src/components/seller/*` | **Migrated** | SellerNavbar, SellerSidebar, SellerLayout |
| `lib/store.ts` | `storefront/src/lib/store.ts` | **Migrated** | Zustand cart/wishlist client store (excluded from management) |
| `lib/store-catalog.ts` | `storefront/src/lib/store-catalog.ts` | **Migrated** | Showcase mock catalog fallback (excluded from management) |
| `lib/checkout-security.ts` | `storefront/src/lib/checkout-security.ts` | **Migrated** | Frontend checkout validation and security safeguards |
| `lib/auth.ts` | Both apps | **Migrated & Isolated** | Namespaced keys (`storefront_*` vs `mgmt_*`), role routing guards |
| `lib/api.ts` | Both apps | **Migrated** | Dedicated API clients with app-specific 401 recovery |

### Public Assets & Branding

| Asset | `storefront/public` | `management/public` | Status |
| :--- | :--- | :--- | :--- |
| `images/logo_panda_blue.png` | Present | Present | **Migrated** |
| `icons/icon.svg` | Not required | Present | **Migrated** |
| `robots.txt` | Present (SEO ready) | Present (`Disallow: /`) | **Configured** |

---

## 2. Dependency Audit

Neither new application depends on `web-app/`:
- **Code imports**: `grep -r "web-app" storefront/src management/src` returns **zero occurrences**.
- **Docker Compose**: `docker-compose.yml` defines `storefront` (context `./storefront`) and `management` (context `./management`). The legacy `web` service was retired and removed.
- **Node Modules / Packages**: Both `storefront` and `management` have independent `package.json` and `node_modules` trees.

---

## 3. Residual Items Not Migrated (Intentional Exclusions)

The following items were intentionally excluded from specific targets to enforce proper separation of concerns:
1. **Zustand (`zustand`)**:
   - Included in `storefront/` for client-side shopping cart, wishlist, and drawer state.
   - **Excluded from `management/`**: Management uses server data and local React state; Zustand shopping state is irrelevant for admin/seller workflows.
2. **Showcase Mock Catalog (`store-catalog.ts`)**:
   - Preserved in `storefront/` as client-side fallback when API is offline.
   - **Excluded from `management/`**: Management dashboards strictly reflect real backend data; zero fake data fallbacks are permitted for administration.
3. **Customer Commerce Routes in Management**:
   - `/shop`, `/product/[id]`, `/cart`, `/checkout`, `/account` are not hosted on port 3001.

---

## 4. Decommissioning Procedure (Post-Approval Only)

When explicit approval is given to decommission `web-app/`, the following safe procedure should be followed:

### Step 1: Backup / Archive
Create a compressed archive of `web-app/` before removal:
```bash
rtk tar -czf web-app-backup-$(date +%Y%m%d).tar.gz web-app/
```

### Step 2: Update Repository Documentation
Update remaining documentation references:
- [`README.md`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/README.md): Update architecture tree and developer setup commands to reference `storefront` and `management`.
- [`AGENTS.md`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/AGENTS.md): Update web directory instructions.

### Step 3: Remove Directory
Remove `web-app/`:
```bash
rtk rm -rf web-app/
```

### Step 4: Verify Clean Git Status & Builds
Verify that deleting `web-app/` does not break any builds or tests:
```bash
cd storefront && npm test && npm run build
cd ../management && npm test && npm run build
cd ../backend && .venv/bin/pytest tests/
docker compose config --quiet
```

---

## 5. Current Recommendation

**Keep `web-app/` in place until Checkpoint 6 final review and sign-off.**  
Do not delete until the product owner confirms all user journeys are satisfactory.
