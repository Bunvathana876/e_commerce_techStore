# Blue Panda E-Commerce — Project Context

> Code audit date: 2026-10-30  
> Scope: root workspace, FastAPI backend, Next.js web application, Flutter mobile application, Docker/pgAdmin configuration, tests, and existing documentation.  
> Audit method: static inspection of the current workspace. No existing source code, database schema, dependencies, or business logic were changed. Runtime tests were not executed during this audit because the backend suite writes to the configured database and upload directory. Secret values are intentionally omitted.

## 1. Project Overview

The project is a full-stack, multi-client e-commerce platform branded **Blue Panda**. It combines:

- A public customer storefront and an admin/merchant interface in one Next.js application.
- A Flutter customer application for Android, iOS, web, and desktop-capable Flutter targets.
- A FastAPI REST backend using PostgreSQL through SQLAlchemy.
- Docker Compose infrastructure for PostgreSQL, pgAdmin, the backend, and the web application.

The intended business domain is a multi-seller marketplace with product discovery, carts, favorites, coupons, checkout, orders, reviews, notifications, catalog administration, seller management, inventory views, reporting, and point-of-sale operations.

The repository README calls the system “production-ready.” The current code is a strong development/demo application, but it is **not production-ready** because critical backend authorization is missing, several payment and operational flows are simulations or derived views, development credentials are committed in configuration/documentation, and the database migration history does not describe the current schema.

### Verified application types

| Area | Type | Primary users |
|---|---|---|
| `web-app/` storefront | Responsive website | Customers and guests |
| `web-app/` admin | Web dashboard and POS | Admins and sellers, although server-side role enforcement is missing |
| `mobile-app/` | Flutter mobile application | Customers |
| `backend/` | REST API and business layer | Both clients |
| PostgreSQL/pgAdmin | Data store and development administration | Developers/operators |

## 2. Tech Stack

### Languages

- Python for the backend.
- TypeScript and TSX for the web application.
- Dart for the Flutter application.
- SQL generated and managed through SQLAlchemy/Alembic.
- Bash/shell for launch and container entrypoint scripts.
- CSS through Tailwind CSS and a global stylesheet.
- YAML for Docker Compose and Flutter configuration.

### Backend

- Python 3.12 container runtime.
- FastAPI 0.141.1 and Uvicorn 0.53.0.
- SQLAlchemy 2.0.54 with synchronous sessions.
- PostgreSQL via `psycopg2-binary`.
- Pydantic 2 and `pydantic-settings`.
- Alembic 1.20.0.
- `bcrypt` for password hashing.
- PyJWT for bearer access tokens.
- `python-multipart` for uploads.
- Pytest and FastAPI `TestClient` for integration tests.
- Additional installed tooling includes FastAPI CLI/cloud packages, Sentry SDK, and PyMySQL. No MySQL runtime path or Sentry initialization was found, so these appear unnecessary or unfinished.

### Web

- Next.js 16.3.4 using the App Router.
- React and React DOM 19.2.8.
- TypeScript with strict mode enabled.
- Tailwind CSS 4.
- Zustand 5 with persisted client state.
- Lucide React and React Icons.
- `clsx` and `tailwind-merge`.
- Next/font with Plus Jakarta Sans.
- ESLint 9 and the React compiler plugin.
- SVGR support through custom webpack configuration.

No web test framework or web test files were found.

### Mobile

- Flutter with Dart SDK constraint `^3.11.1`.
- Material 3.
- Provider/ChangeNotifier for state management.
- `http` for REST requests.
- `shared_preferences` for session, theme, notification, and order cache data.
- Google Fonts using Plus Jakarta Sans.
- `flutter_animate`, `shimmer`, and `smooth_page_indicator` for interaction and loading effects.
- `flutter_launcher_icons` for app icons.
- Flutter lint configuration through `flutter_lints`.

### Infrastructure

- Docker Compose.
- PostgreSQL 16 Alpine.
- pgAdmin 4.
- Backend and web development containers.
- Named volumes for PostgreSQL and pgAdmin data.

No Redis, Celery, message queue, payment provider SDK, email provider, push notification service, shipping provider, or analytics service integration was verified.

## 3. Folder Structure

```text
e-commerce/
├── backend/
│   ├── app/
│   │   ├── api/v1/routes/       # FastAPI route handlers
│   │   ├── core/                # Settings, JWT/password helpers, auth dependencies
│   │   ├── db/                  # SQLAlchemy session, table initialization, seed data
│   │   ├── models/              # SQLAlchemy models
│   │   ├── schemas/             # Pydantic request/response schemas
│   │   ├── services/            # Business and persistence logic
│   │   └── main.py              # FastAPI application entry point
│   ├── alembic/                 # Migration configuration and one initial migration
│   ├── tests/test_api.py        # Database-backed integration flow
│   ├── uploads/products/        # Locally served uploaded product images
│   ├── Dockerfile
│   ├── docker-entrypoint.sh
│   └── requirements.txt
├── mobile-app/
│   ├── lib/
│   │   ├── app/                 # MaterialApp and named routes
│   │   ├── core/                # API client, endpoints, theme, validators, transitions
│   │   ├── features/            # Feature-first screens, models, providers, services, widgets
│   │   ├── shared/widgets/      # Reusable branding, controls, banners, navigation
│   │   └── main.dart            # Flutter entry point and provider registration
│   ├── test/                    # Unit and widget tests
│   ├── android/, ios/, web/     # Platform runners and configuration
│   └── pubspec.yaml
├── web-app/
│   ├── public/                  # Static brand and product imagery
│   ├── src/
│   │   ├── app/
│   │   │   ├── (store)/         # Customer storefront routes
│   │   │   ├── (admin)/admin/   # Admin, seller, reporting, and POS routes
│   │   │   ├── (auth)/          # Login and registration
│   │   │   ├── globals.css
│   │   │   └── layout.tsx       # Root layout and metadata
│   │   ├── components/
│   │   │   ├── layout/          # Admin shell, sidebar, top navigation
│   │   │   └── store/           # Store navbar, footer, cards, dialogs, toasts
│   │   └── lib/                 # API client/types, auth storage, catalog fallback, Zustand store
│   ├── Dockerfile
│   ├── next.config.ts
│   └── package.json
├── pgadmin/servers.json         # pgAdmin server registration
├── docker-compose.yml           # Four-service development stack
├── run.sh                       # One-click Docker launcher
├── README.md                    # Root documentation; contains outdated claims
├── PROJECT_UI_UX_ANALYSIS.md    # Older analysis; does not match all current code
└── PROJECT_CONTEXT.md           # This verified project handover
```

Generated/vendor folders such as `node_modules`, Flutter tool output, and build output are not architecture sources.

## 4. Application Architecture

### Overall data flow

```text
Flutter screens ──> ChangeNotifier providers ──> Dart services/ApiClient ─┐
                                                                         ├─> FastAPI routes
Next.js pages/components ──> Zustand/component state ──> web API client ─┘
                                                                               │
                                                            service classes ──> SQLAlchemy ──> PostgreSQL
```

### Backend pattern

The backend mostly uses a layered route/service/model pattern:

1. Route modules in `app/api/v1/routes/` validate requests through Pydantic schemas and inject a database session.
2. Service classes implement catalog, cart, order, coupon, review, seller, address, favorite, POS, notification, and authentication logic.
3. SQLAlchemy models define persistence and relationships.
4. Responses normally use a `{ success, message, data }` envelope.

Exceptions to the pattern exist: the users and stats routes contain database logic directly, and upload handling writes files directly in the route.

Every router is registered twice, under both `/api` and `/api/v1`. This supports the current clients but doubles the public API surface and makes versioning ambiguous.

### Web pattern

The web application uses Next.js route groups:

- `(store)` provides the public commerce experience.
- `(auth)` provides login and registration.
- `(admin)` provides the back office and POS.

Most pages are client components. They call the browser-side API wrapper in `src/lib/api.ts`. Authentication is stored in `localStorage`. Store cart, wishlist, recently viewed products, local orders, dialogs, and toasts are managed by a persisted Zustand store in `src/lib/store.ts`.

The storefront has a dual live/demo architecture. Fetch helpers call the backend, but an empty response or network error returns hardcoded `SHOWCASE_*` products, categories, sellers, coupons, and reviews. This produces a polished demo but can show invented commerce data when the real system is unavailable.

### Mobile pattern

The Flutter app follows a feature-first structure. `main.dart` registers eight ChangeNotifier providers:

- `AuthProvider`
- `ProductProvider`
- `CartProvider`
- `OrderProvider`
- `CategoryProvider`
- `ReviewProvider`
- `NotificationProvider`
- `ThemeProvider`

Screens observe providers, providers call feature services, and services use the shared `ApiClient`. The API base URL is platform-aware and can be overridden through `--dart-define=API_URL=...` or at runtime.

Production catalog/category/review providers generally show loading, empty, or connection-error states instead of test product data. However, authentication still contains production-reachable mock fallbacks, social sign-in creates fake local sessions, coupons have local fallbacks, and checkout can create local orders after API failure.

### Module communication

- Both clients use REST JSON and bearer JWTs.
- The web default API base is `http://localhost:8000/api`.
- The mobile endpoint constants use `/api/v1/...`; its base URL must therefore be the host only, without another `/api` suffix.
- The backend uses a required `DATABASE_URL` setting to create a synchronous SQLAlchemy engine.
- Uploaded images are stored under `backend/uploads/products` and served from `/uploads` by FastAPI.
- There is no event bus, WebSocket channel, background worker, or third-party commerce integration.

## 5. Existing Features

Status meanings:

- **Implemented**: a working code path and data model/service are present.
- **Partial**: meaningful code exists, but the behavior is simulated, incomplete, insecure, or not represented by its own backend domain.
- **Missing**: no supporting production implementation was found.

### Customer features

| Feature | Status | Evidence and limitations |
|---|---|---|
| Email/password registration and login | Partial | FastAPI issues JWTs and both clients persist sessions. Backend registration does not enforce a password length. Mobile can fall back to mock accounts after failures. |
| Social authentication | Missing/unsafe demo | Mobile Google/Apple/Facebook/X actions save fabricated tokens and users. No OAuth provider SDK or backend OAuth flow exists. |
| Logout | Partial | Clients clear local tokens. The backend logout endpoint does not revoke a JWT, and there is no token deny-list. |
| Profile and password updates | Implemented | `/auth/me` and `/auth/change-password` exist; web and mobile screens expose related actions. Password reset email is UI-only. |
| Product catalog and details | Implemented | Pagination, search, category/seller filters, price/rating filters, sorting, stock, discounts, images, and ratings exist. Storefront may replace failures with showcase data. |
| Categories and seller stores | Implemented | Backend read APIs and customer pages exist. Public product listing does not default to active-only. |
| Cart | Implemented with limitations | Authenticated server cart and optimistic local client carts exist. Variant selections are client-only because the backend cart has no variant field. |
| Wishlist/favorites | Implemented | Authenticated backend favorites plus optimistic/persisted local state. Logout does not consistently clear all per-user web store state. |
| Coupons | Partial | Server validation and default coupons exist. Clients also validate local showcase coupons during network failures. No usage limits, redemption history, per-user limits, or admin coupon CRUD exists. |
| Address book | Implemented | User-owned address create/update/delete/default behavior exists. |
| Checkout/order creation | Partial | The backend safely recalculates product prices, validates stock, applies coupons, deducts stock, snapshots items, and clears the server cart. Both clients can create local “confirmed” orders if the backend is unavailable. |
| Payments | Missing/unsafe demo | Card, KHQR, Apple Pay, QR, and other choices are labels/simulations. No gateway, webhook, signature verification, or settlement model exists. Local orders can be marked paid without provider proof. |
| Order history and status timeline | Partial | Real order records and four-step status visualization exist. No carrier integration, tracking number model, delivery events, or real-time tracking exists. |
| Reviews | Partial | Authenticated submission, moderation status, replies, and rating recalculation exist. Purchase ownership is not verified; web fallback reviews are invented; the public web fetch does not request only approved reviews. |
| Notifications | Partial | Database notifications, unread counts, filters, and client interactions exist. They are pull-based, not push or real-time. API ownership/auth rules are unsafe. |
| Theme preferences | Implemented on mobile | Light/dark mode persists through SharedPreferences. The admin web UI is primarily light-only. |
| Newsletter, support, returns promises | UI-only | Newsletter state is only local. No support or return-request service backs the storefront claims. |

### Admin and merchant features

| Feature | Status | Evidence and limitations |
|---|---|---|
| Dashboard KPIs | Partial | Counts and revenue/stock figures load from backend stats. Stats are public, and revenue falls back to all orders when no paid orders exist. |
| Product/category management | Implemented but unsecured | CRUD pages and APIs exist, including image upload. Backend write routes do not require authentication or roles. |
| Inventory | Partial | Product stock can be viewed/edited. There is no stock movement ledger, purchase order, warehouse, or concurrency-safe reservation system. |
| Order administration | Implemented but unsecured | Listing, detail, status/payment updates, and deletion exist. Administrative routes are public and lack ownership/role checks. |
| Customer/employee management | Implemented but critically unsecured | User CRUD and role edits exist. Endpoints are public, allowing data exposure and privilege changes. |
| Seller management | Partial | Seller records and CRUD exist. Seller/admin client restrictions are cosmetic because the server does not enforce them. Seller data is not consistently scoped to the logged-in seller. |
| Suppliers | Partial/misnamed | Supplier pages reuse the seller API and model. There is no separate supplier entity or procurement workflow. |
| Review moderation | Implemented but unsecured | Approve/reject/reply/delete paths exist without admin/seller authorization. |
| Notifications center | Partial | Combines backend data with generated operational items and localStorage read/deleted/settings state. Mutation routes are not properly protected. |
| POS | Partial | Product selection, customer lookup, discounts/tax, cash calculations, parked carts, receipts, print styles, checkout, and summaries exist. Any authenticated user can call the POS API; no staff role check exists. |
| Payments/transactions/refunds | Partial/derived | Pages transform order fields into payment, transaction, and refund rows. There are no dedicated payment, transaction, refund, or return models/workflows. |
| Reports/analytics | Partial | Views calculate summaries from products, orders, users, and stats. There is no reporting service, immutable finance ledger, export job, or audit trail. |
| Roles and permissions | Missing | Role cards and user counts exist, but there is no permission model, policy engine, or enforced RBAC. |
| Store settings | UI-only | Save uses timers and component state; values are not persisted to the backend. |

### Navigation and routing

- Mobile starts at an auth welcome screen unless a locally stored token/user is present. Its main shell has five IndexedStack tabs: Home, Categories, Favorites, Cart, and Profile.
- Web storefront routes include `/`, `/shop`, `/categories`, `/deals`, `/stores`, `/wishlist`, `/account`, `/cart`, `/checkout`, `/orders`, and `/product/[id]`.
- Web authentication routes are `/login` and `/register`.
- Admin routes cover dashboard, analytics, categories, customers, employees, inventory, notifications, orders, payments, POS, products, profile, refunds, reports, reviews, roles, sellers, settings, suppliers, and transactions.
- `/admin` redirects to `/admin/dashboard`.
- Admin route protection only checks whether a local token appears valid; it does not require an admin or seller role.

### Error handling and validation

- Mobile has typed network exceptions for 400/401/403/404/409/5xx, timeouts, socket failures, and invalid data. Providers expose loading/error state, although some services swallow errors and return empty values.
- Web API calls throw parsed errors, but numerous empty `catch` blocks intentionally hide synchronization failures.
- Backend relies on FastAPI defaults and service-level `HTTPException`; no shared application error envelope or structured logging middleware was found.
- Pydantic validates emails and several numeric ranges, but key fields such as registration password length, role values, statuses, payment methods, and review moderation statuses are largely unconstrained strings.

## 6. Frontend and UI/UX Overview

### Shared visual direction

The current interfaces already have a recognizable Blue Panda identity: Plus Jakarta Sans, blue primary actions, slate surfaces, rounded cards, soft borders, responsive grids, badges, and restrained shadows. The customer web storefront is the most cohesive surface. The mobile application has a strong Material 3 light/dark theme and polished loading states.

### Web storefront

Strengths:

- Clear navigation and strong customer-oriented visual hierarchy.
- Responsive Tailwind layouts across common breakpoints.
- Consistent product cards, quick view, search dialog, cart drawer, toasts, and footer.
- Useful empty states, filters, free-shipping feedback, and checkout autofill attributes.
- Global reduced-motion handling is present.
- Many product and logo images include alternative text.

Problems:

- It silently substitutes showcase products, reviews, sellers, and coupons when live data fails. Users cannot reliably tell real inventory from demo inventory.
- Guest/offline checkout displays confirmation and can mark non-COD payment methods paid without a real transaction.
- Marketing text promises verified merchants, authentic products, returns, support, live tracking, and synchronized data beyond what the backend proves.
- Most pages fetch on the client after hydration and request large catalogs for client-side filtering. This reduces SEO/server-rendering benefits and causes unnecessary loading/fallback transitions.
- Raw `<img>` usage and an unrestricted remote image configuration weaken Next.js image optimization and security.

### Admin web interface

Strengths:

- Broad feature coverage, clear sidebar grouping, readable tables, responsive stacking, and consistent card layouts.
- Loading, success, empty, and error presentations exist on many data pages.
- POS has touch-oriented controls and print-specific receipt styling.

Problems:

- The interface exposes many unfinished concepts as if they were live, including settings, permissions, payments, refunds, suppliers, and financial reporting.
- `#7699F0` is repeatedly hardcoded instead of being a shared design token and is likely too light for normal text on white at WCAG AA contrast levels.
- Repeated table, filter, status badge, form, confirmation, and notification implementations create subtle inconsistencies.
- Large side navigation and many destinations increase cognitive load; seller and admin experiences are not cleanly separated.
- Admin is primarily light theme, while the storefront and mobile product support a stronger modern theme system.
- Large tables rely on horizontal scrolling on small screens; mobile admin workflows are technically usable but not optimized.

### Flutter mobile interface

Strengths:

- Consistent Material 3 theme, light/dark mode, Plus Jakarta Sans, rounded surfaces, and strong touch target sizing.
- Five-tab navigation makes cart and favorites discoverable.
- Shimmer loading, pull-to-refresh, empty cart/wishlist/order states, network error states, form validation, and checkout feedback are present.
- SafeArea, scrolling, keyboard insets, and responsive size checks are used throughout.
- Reusable widgets exist for branding, text fields, product cards, category cards, promo banners, and animated buttons.

Problems:

- Several screens are extremely large: product detail is over 2,000 lines; home, checkout, profile, and cart are each over 1,200 lines. This makes consistent UI refinement risky.
- Decorative gradients, glass effects, animations, badges, and long promotional copy are sometimes denser than the user’s requested clean, real-world style.
- Social login and KHQR look authentic but are simulations, creating a trust problem.
- Accessibility semantics are sparse outside selected cards. Custom gesture/button wrappers and icon-only controls need explicit labels, focus behavior, and screen-reader testing.
- There is no verified tablet/large-screen information architecture; most layout decisions target phone screens.
- Settings such as language, currency, and notification preferences are largely local UI state rather than real application preferences.

### Layout consistency and component reuse

- Mobile has a central theme, but many screens still hardcode colors and custom card/input styles.
- Web storefront components are reasonably reusable; admin pages duplicate many page patterns.
- Web and mobile share branding but do not share formal design tokens or content rules.
- The project would benefit from a small cross-platform design specification for color roles, spacing, radii, typography, state messages, and truthful demo labeling.

### Accessibility assessment

Accessibility is **partially implemented**:

- Positive: reduced-motion CSS, visible focus styles in many web inputs, image alt text, large mobile controls, semantic HTML in portions of the storefront.
- Gaps: incomplete icon-button labels, weak label/input associations in repeated admin forms, possible low-contrast blue text, limited Flutter `Semantics`, no documented keyboard-only audit, no screen-reader test suite, and no automated accessibility tests.

## 7. Backend and API Architecture

### Route groups

The backend exposes both `/api/...` and `/api/v1/...` variants for:

- Authentication
- Categories
- Products
- Cart
- Favorites
- Notifications
- Addresses
- Orders
- POS
- Coupons
- Reviews
- Sellers
- Dashboard stats
- Users
- Uploads

Swagger UI and ReDoc are exposed at `/docs` and `/redoc`. Health and database test endpoints exist at `/health` and `/db-test`.

### Business logic strengths

- Passwords are hashed with bcrypt.
- JWT signatures and expiration are verified for protected dependencies.
- Cart/address/favorite services scope normal customer operations to the authenticated user.
- Order creation recalculates prices server-side, checks active products and stock, applies server coupon logic, deducts stock, snapshots order items, clears the cart, and creates an order notification in one database commit path.
- Product queries support pagination and useful filters.
- Reviews recalculate product ratings after moderation changes.
- SQLAlchemy relationships and select-in loading are used to return nested data.

### API design limitations

- Authorization policies are not centralized and are absent from most administrative routes.
- Status, role, and payment fields use free-form strings rather than enums or constrained values.
- Users, sellers, all orders, stats, and several other lists are not consistently paginated.
- API v1 and unversioned endpoints are exact duplicates.
- Some response shapes vary, forcing defensive parsing in the clients.
- Synchronous route functions and database access are acceptable for a small application, but scaling depends on worker configuration and query discipline.
- Uploads are written to local container storage, which is not a durable production media architecture.

## 8. Database Structure

### Verified tables and relationships

| Table | Main responsibility | Relationships |
|---|---|---|
| `users` | Customer/admin/seller identity and profile | Owns addresses, cart items, favorites, orders, reviews; optional seller record |
| `categories` | Product grouping | Has many products |
| `sellers` | Marketplace store profile and denormalized metrics | Optional user; has many products |
| `products` | Catalog, price, discount, stock, image, rating | Belongs to category and optional seller; used by cart, favorites, order items, reviews |
| `addresses` | User shipping addresses | Belongs to user |
| `cart_items` | Authenticated user cart | Unique user/product pair |
| `favorites` | Authenticated wishlist | Unique user/product pair |
| `coupons` | Discount rules | Standalone; no redemption relationship |
| `orders` | Checkout header, totals, status, payment labels, address snapshot | Belongs to user; has many order items |
| `order_items` | Historical product/price/quantity snapshot | Belongs to order; optional product reference |
| `reviews` | Product rating/comment/moderation/reply | Belongs to user and product; optional order reference |
| `notifications` | User-specific or global messages | Optional user reference |

### Schema risks

- The single Alembic migration creates only the original eight tables. It does not include sellers, reviews, notifications, coupons, `products.seller_id`, or all newer order columns.
- Startup runs Alembic, then `Base.metadata.create_all`, then manual `ALTER TABLE` statements whose exceptions are ignored. `app.main` also calls `create_all` during import. This hides migration gaps and makes environments difficult to reproduce.
- Role, order status, payment status, seller status, notification type, and coupon type lack database constraints.
- Seller product/order/revenue counters are denormalized. Product counts are updated in some product flows, but the audit did not find a complete mechanism maintaining all seller metrics.
- User deletion cascades to orders, which can remove historical commerce records and conflict with financial/audit retention requirements.
- Stock deduction does not lock product rows. Concurrent checkouts can race and oversell.
- There are no payment transaction, refund, return, inventory movement, shipment, audit-log, permission, or coupon-redemption tables.

## 9. Authentication and Security

### Implemented controls

- Bcrypt password hashing.
- Signed JWT bearer tokens with expiry.
- Active-user checks for routes that use `get_current_user`.
- Ownership filters for customer addresses, cart operations, and favorites.
- Email validation through Pydantic.
- Client-side token expiry checks in the web application.

### Critical security findings

1. **Administrative authorization is missing.** Product, category, seller, user, order-administration, stats, upload, review-moderation, and notification mutation routes are public or insufficiently protected. POS requires a login but not a staff role.
2. **Public user management permits privilege escalation.** The user creation/update schemas accept arbitrary role strings, and the routes require no authorization.
3. **Sensitive business/customer data can be exposed.** Public users and all-orders endpoints return identity/order information; individual order access does not enforce ownership.
4. **Admin page protection is only client-side and role-blind.** Any locally authenticated customer can enter `/admin`, and client checks cannot replace server authorization.
5. **Development credentials and default secrets are committed.** Docker Compose, seed code, the root README, launch output, and web demo-fill controls contain known development credentials. Values are intentionally not repeated here. They must never be used outside an isolated local environment.
6. **CORS includes a wildcard while credentials are enabled.** This must be replaced with explicit environment-specific origins.
7. **Web access tokens are stored in localStorage.** An XSS vulnerability could steal them. Mobile uses SharedPreferences rather than secure platform keychain/keystore storage.
8. **Registration password validation is weak on the server.** The public register schema does not enforce a minimum length or strength.
9. **No brute-force/rate limiting, refresh rotation, revocation, MFA, email verification, reset-token flow, or security audit log was found.**
10. **Uploads are unsafe for production.** The endpoint is public, trusts extension/request MIME, allows SVG, does not enforce its declared size limit, writes synchronously to local disk, and returns raw exception text.
11. **Next image hosts are unrestricted.** `next.config.ts` allows arbitrary HTTP and HTTPS hosts, increasing unwanted remote fetch/SSRF exposure through image optimization paths.
12. **Mobile social login is fabricated.** It stores fake tokens and enters authenticated UI without a backend identity.

### Additional authorization/content issues

- Notification optional authentication treats unauthenticated access as access to global notifications; mutation ownership is not verified.
- Review moderation is public, and the web customer review fetch can display non-approved reviews.
- Seller UI hides some controls by role, but server endpoints do not enforce seller ownership.
- Logout is local only; existing JWTs remain valid until expiration.
- The seven-day default access token lifetime increases the impact of token theft.

## 10. State Management

### Flutter

- Provider/ChangeNotifier is the main application state mechanism.
- Auth token/user, theme, order cache, and notification preferences/deletions use SharedPreferences.
- Product/category/review/notification providers model loading and error state.
- Cart and favorites update optimistically and attempt background synchronization.
- Some state is not cleared consistently on logout: orders are explicitly cleared by the profile UI, but cart/favorites/notification state is not centrally reset by the auth provider.

### Web

- Zustand persists cart, coupon, wishlist, recently viewed products, and local orders under one browser storage key.
- Auth token and serialized user are separately stored in localStorage.
- Most admin data uses page-local `useState`/`useEffect` and refetches on each page.
- Local store state remains useful for guests, but it is not partitioned by authenticated user. Switching accounts in one browser can mix cart, wishlist, and local-order data.
- Admin notification state and POS parked carts also use localStorage.
- There is no server-state library, normalized cache, request deduplication, or consistent invalidation layer.

### Backend

- The backend is stateless at the HTTP layer; JWTs identify users and PostgreSQL stores business state.
- There is no server-side session/revocation store or distributed cache.

## 11. Current Problems and Limitations

### Critical impact

- Missing backend RBAC and ownership checks allow unauthorized reads and mutations.
- Demo credentials/default JWT configuration are committed and auto-seeded.
- Fake/local order and payment confirmation can be mistaken for a real transaction.
- Mobile social auth creates fake authenticated sessions.
- Migration history does not represent the current database schema.
- Public upload and user/order endpoints create privacy, abuse, and storage risks.

### High impact

- Web store silently mixes live and showcase data.
- Payment, refund, transaction, return, shipment, supplier, permissions, and settings domains are not truly implemented.
- Stock updates are race-prone, and there is no inventory ledger.
- Client persistence is not isolated per user and is stored in insecure browser/device storage.
- Public product listings can include inactive products because `active_only` is not enabled by customer calls at the backend level.
- Reviews are not verified against purchased/delivered order items.
- Seller scope is not enforced.
- Backend tests run against the configured database and filesystem rather than an isolated test environment.

### Maintainability

- Very large Flutter screens and web pages combine UI, state, data transformation, and workflows.
- `src/lib/api.ts`, `store-catalog.ts`, the Zustand store, admin POS, and notifications are monolithic.
- Admin page UI patterns are duplicated instead of composed from shared data-table/form/state components.
- Backend business logic is split inconsistently between routes and services.
- Silent exception handlers conceal synchronization and persistence failures.
- Duplicate `/api` and `/api/v1` routes increase maintenance and testing work.
- Hardcoded demo data, marketing copy, styles, status lists, and endpoints are spread across clients.

### Performance

- Store pages fetch large catalogs client-side and filter locally.
- Showcase data ships in the web client bundle.
- Several admin endpoints return unpaginated collections.
- Large client components increase parsing and maintenance costs, especially the POS and mobile detail/checkout screens.
- Local disk uploads do not scale across multiple backend instances.
- Startup performs schema creation and seeding work in application import/start paths.

### Documentation

- Root README claims RBAC, production readiness, supplier/analytics paths, social/payment functionality, and seller routes that are not supported as described.
- Root setup documentation refers to an incorrect mobile API configuration filename and includes development credentials.
- Web README is mostly the default Next.js template and does not explain this application.
- Existing UI/UX analysis files describe an older four-tab mobile layout, older dependency versions/test counts, and broader offline mock behavior than the current catalog providers use.
- Runtime health, test counts, and successful builds could not be independently verified in this static audit.

## 12. Recommended Improvements

### Priority 1: Critical bugs, security, and broken functionality

#### 1. Enforce authentication, RBAC, and resource ownership on the backend

- **What:** Add reusable dependencies/policies for admin, seller, staff, and customer ownership. Protect every write and sensitive read endpoint.
- **Why:** Current APIs allow public catalog/user/order/admin mutations and customer data exposure.
- **Files:** `backend/app/core/dependencies.py`, all modules in `backend/app/api/v1/routes/`, seller/order/review/notification services, and web admin route handling.
- **Risks:** Existing UI calls that relied on public APIs will begin returning 401/403; seller scoping rules require a product decision.
- **Approach:** Define an explicit role matrix, implement `require_roles(...)`, enforce order/user/notification ownership in queries, add denial tests for every protected route, then update clients to handle 403 cleanly.

#### 2. Remove production-reachable fake authentication and order/payment success

- **What:** Limit mocks to injected test implementations or an explicit development flag. Never report a paid/confirmed order after a failed backend or payment call.
- **Why:** Users can believe an account, payment, or order exists when it does not.
- **Files:** `mobile-app/lib/features/auth/services/auth_service.dart`, mobile login/sign-up screens, mobile checkout, `web-app/src/app/(store)/checkout/page.tsx`, `web-app/src/lib/store-catalog.ts`, and `web-app/src/lib/store.ts`.
- **Risks:** Offline demos become less automatic; demo mode needs visible labeling.
- **Approach:** Introduce a clearly named development/demo configuration, show a persistent demo badge, store draft carts rather than confirmed orders offline, and require server/payment confirmation for success.

#### 3. Rotate/remove committed credentials and harden configuration

- **What:** Remove known credentials from tracked configuration/docs, require environment values, rotate any reused secrets, and disable automatic credential printing.
- **Why:** Known credentials and a default JWT key make unauthorized access trivial if reused.
- **Files:** `docker-compose.yml`, `backend/app/core/config.py`, `backend/app/db/seed_data.py`, `run.sh`, root `README.md`, web demo-fill UI, pgAdmin configuration, and environment templates.
- **Risks:** Local setup becomes slightly less convenient and existing volumes may retain old accounts.
- **Approach:** Use `.env.example` with non-secret placeholders, fail fast outside development, create demo accounts only through an explicit seed command, and document rotation/reset steps without committing real values.

#### 4. Make database migrations authoritative

- **What:** Create migrations for the full current schema and stop using `create_all`/silent ALTER statements as migration substitutes.
- **Why:** New and existing environments can have different columns/tables while appearing healthy.
- **Files:** `backend/alembic/versions/`, `backend/app/main.py`, `backend/app/db/init_db.py`, `backend/docker-entrypoint.sh`, model definitions.
- **Risks:** Existing databases may need careful baseline/stamp/data migration work.
- **Approach:** Compare a real current schema to models, create reviewed incremental migrations, test upgrade/downgrade on disposable databases, remove import-time schema changes, and keep seeding separate.

#### 5. Harden uploads and remote images

- **What:** Require a privileged role, enforce byte limits, verify file signatures, reject or sanitize SVG, store media outside the app container, and restrict Next image hosts.
- **Why:** Current upload paths permit abuse, oversized/misleading files, persistent content risks, and unrestricted server-side remote image fetches.
- **Files:** `backend/app/api/v1/routes/upload.py`, `backend/app/main.py`, `web-app/next.config.ts`, product/category upload screens.
- **Risks:** Existing image URLs may require migration or allow-list updates.
- **Approach:** Stream with a hard size cap, decode/re-encode supported raster formats, use object storage with generated keys, and configure only trusted media hosts.

#### 6. Strengthen account security

- **What:** Add server password policy, rate limiting, short-lived access tokens with refresh rotation, revocation, secure reset/email verification, and secure client storage.
- **Why:** Current long-lived bearer tokens and weak registration validation are easy to abuse.
- **Files:** backend auth schemas/services/security/config, web auth/API middleware, mobile auth provider/storage.
- **Risks:** Token migration will log out existing sessions and requires coordinated client release.
- **Approach:** Start with password validation and rate limits, then implement refresh token records/rotation and HttpOnly cookie strategy for web; use keychain/keystore storage on mobile.

#### 7. Correct data visibility and commerce invariants

- **What:** Return only active products to customer endpoints, only approved reviews publicly, validate verified purchases, lock stock during checkout, and never infer revenue from unpaid orders.
- **Why:** These errors affect catalog truth, moderation, overselling, and financial reporting.
- **Files:** product/review/order/stats routes and services, review schemas, storefront fetch helpers.
- **Risks:** Visible product/review counts and current dashboard revenue may decrease.
- **Approach:** Split public/admin query methods, add transaction-level row locking or atomic stock updates, and cover concurrent checkout and moderation cases in tests.

### Priority 2: Code quality and architecture

#### 1. Break large client files into feature components and controllers

- **What:** Extract sections, dialogs, data hooks/controllers, and shared table/form components from monolithic screens.
- **Why:** Files above 1,000–2,000 lines are difficult to test and safely redesign.
- **Files:** mobile product detail/home/checkout/cart/profile; web admin POS/notifications; web API/store catalog/store modules.
- **Risks:** Refactors can introduce state or navigation regressions.
- **Approach:** First add behavior tests, then extract one stable section at a time without changing public behavior.

#### 2. Separate demo fixtures from production code

- **What:** Move showcase/test data to dedicated fixture modules and never activate it implicitly.
- **Why:** Live and fictional records are currently difficult to distinguish.
- **Files:** `web-app/src/lib/store-catalog.ts`, mobile product/category/review/notification providers, auth service, seed data.
- **Risks:** Visual development may require a new explicit seed/demo command.
- **Approach:** Use build-time environment flags and dependency injection; label all demo environments.

#### 3. Standardize API contracts and versioning

- **What:** Keep one versioned API, consistent response envelopes, generated/central types, and paginated collection conventions.
- **Why:** Defensive parsing and duplicate routes hide contract mismatches.
- **Files:** backend router registration/schemas, web `api.ts`, mobile `api_response.dart` and feature services.
- **Risks:** Coordinated client changes are required.
- **Approach:** Publish `/api/v1`, deprecate `/api`, define an OpenAPI-based contract, and add contract tests.

#### 4. Add real domain models for operational features

- **What:** Model permissions, suppliers, inventory movements, payments, refunds, returns, shipments, and store settings instead of deriving them from orders or local state.
- **Why:** Current admin screens imply workflows that cannot be audited or safely changed.
- **Files:** backend models/schemas/services/routes/migrations and corresponding web pages/API types.
- **Risks:** This is a broad data-design change; poor modeling can create migration debt.
- **Approach:** Implement one bounded context at a time, beginning with payments/refunds and inventory movements.

#### 5. Improve error handling and observability

- **What:** Replace empty catches with explicit recoverable-state handling and add structured logs, request IDs, error reporting, and health/readiness checks.
- **Why:** Silent failures make cart, favorites, notifications, and admin actions appear successful when they are not.
- **Files:** both client API/state layers, backend middleware/services, Docker health checks.
- **Risks:** More visible errors may initially reveal many existing synchronization problems.
- **Approach:** Define error categories and user messages, log technical details centrally, and add retry only to idempotent operations.

#### 6. Isolate tests and expand coverage

- **What:** Use a disposable test database/filesystem, add authorization/ownership/concurrency tests, and add web unit/component/E2E tests.
- **Why:** Current backend tests mutate configured state; the web has no tests; the highest-risk behaviors are uncovered.
- **Files:** backend test configuration/fixtures, route/service tests, web test setup, existing Flutter tests.
- **Risks:** CI and fixture work takes time before feature velocity improves.
- **Approach:** Containerize a test database, override FastAPI dependencies, use a temporary upload directory, then gate merges on backend, web, and Flutter checks.

### Priority 3: UI/UX improvements

#### 1. Establish one design system across web/admin/mobile

- **What:** Define semantic tokens for primary, surface, text, border, success/warning/error, spacing, radius, elevation, typography, and state patterns.
- **Why:** Hardcoded colors and repeated patterns create visual inconsistency and accessibility risks.
- **Files:** web `globals.css`, Tailwind usage and shared components; Flutter `app_theme.dart` and shared widgets.
- **Risks:** Broad visual changes can create regressions if done all at once.
- **Approach:** Begin with tokens and shared Button/Input/Card/Badge/Empty/Error/Loading components, then migrate screen-by-screen.

#### 2. Simplify navigation and separate roles

- **What:** Give admins and sellers different allowed navigation, group secondary tools, and hide unfinished modules until they are real.
- **Why:** The current admin sidebar is crowded and implies equal access to everything.
- **Files:** admin sidebar/layout, role policy, route definitions.
- **Risks:** Existing bookmarks may move.
- **Approach:** Base navigation on the server-defined permission matrix and keep core daily actions prominent.

#### 3. Make all demo/incomplete behavior truthful

- **What:** Label demo mode, disable unavailable payments/social providers, and replace unsupported marketing promises with verified copy.
- **Why:** Trust is central to commerce UX.
- **Files:** storefront footer/home/checkout/product pages, mobile auth/checkout, admin partial modules.
- **Risks:** The product may initially look less feature-rich.
- **Approach:** Use “Coming soon” disabled states or hide capabilities until backend support exists.

#### 4. Complete accessibility work

- **What:** Add accessible names, form associations, keyboard/dialog focus management, WCAG AA colors, Flutter semantics, scalable text testing, and automated checks.
- **Why:** Current custom controls are not consistently usable with assistive technology.
- **Files:** shared web/mobile controls and all icon-heavy navigation/forms.
- **Risks:** Some visual colors and compact controls will need changes.
- **Approach:** Audit reusable components first, add axe/Playwright checks for web, and add Flutter semantics/widget tests.

#### 5. Reduce visual and content noise

- **What:** Limit simultaneous badges, gradients, glass effects, decorative animation, and long promotional paragraphs; prioritize product, price, stock, delivery, and next action.
- **Why:** A clean real-world commerce experience should feel trustworthy and fast rather than like a feature showcase.
- **Files:** mobile home/product/checkout, web home/product/admin dashboard.
- **Risks:** Stakeholders may prefer the existing decorative style.
- **Approach:** Use a clear hierarchy: one primary action, one supporting message, consistent spacing, and progressive disclosure.

### Priority 4: Performance and optimization

#### 1. Move storefront data work toward server rendering and paginated queries

- **What:** Fetch public catalog data on the server where appropriate, use URL-driven filters, and request only needed pages.
- **Why:** Current client fetching ships showcase data and processes large catalogs in the browser.
- **Files:** storefront pages, store catalog helpers, backend product endpoints.
- **Risks:** Authentication-dependent widgets require client boundaries.
- **Approach:** Keep cart/account widgets client-side but render public catalog/category/product shells from server data with caching rules.

#### 2. Paginate and index admin queries

- **What:** Add server pagination/search to users, orders, sellers, reviews, notifications, and reports; review query indexes.
- **Why:** Full collections will become slow and memory-heavy as data grows.
- **Files:** backend routes/services/models/migrations and admin tables.
- **Risks:** UI pagination and totals must be coordinated.
- **Approach:** Standardize `{items,total,page,limit,total_pages}` and add indexes based on measured query plans.

#### 3. Use durable media storage and optimized delivery

- **What:** Move uploads to object storage/CDN, generate responsive variants, and use allow-listed optimized images.
- **Why:** Local volume storage and arbitrary remote images are unreliable and slow at scale.
- **Files:** upload service, product/category models, web image components, mobile URL handling.
- **Risks:** URL migration and cleanup tooling are required.
- **Approach:** Add a media service abstraction before changing storage provider.

#### 4. Reduce client component and state size

- **What:** Lazy-load heavy admin/POS sections, split dialogs, and avoid rebuilding large Flutter trees unnecessarily.
- **Why:** Large interactive files increase bundle, rebuild, and testing costs.
- **Files:** admin POS/notifications, mobile IndexedStack screens and large feature screens.
- **Risks:** Incorrect splitting can lose local state.
- **Approach:** Profile first, then extract stable subtrees with focused selectors and keys.

### Priority 5: Optional future features

#### 1. Real payment and KHQR integration

- **What:** Add a supported provider, signed webhooks, idempotency keys, payment intents, and reconciliation.
- **Why:** Required for trustworthy non-COD commerce.
- **Files:** new backend payment domain, checkout clients, admin finance pages.
- **Risks:** Financial, regulatory, security, refund, and failure-state complexity.
- **Approach:** Start with sandbox mode and COD fallback; never trust client-reported payment status.

#### 2. Shipping and fulfillment integration

- **What:** Add shipments, carrier/tracking identifiers, event history, delivery estimates, and webhook updates.
- **Why:** Current tracking is only a visual mapping of order status.
- **Files:** new shipment models/services/routes and both order UIs.
- **Risks:** Carrier API reliability and data normalization.
- **Approach:** Model carrier-neutral shipment events before adding a provider adapter.

#### 3. Email and push notifications

- **What:** Add verified transactional email and mobile push for account/order events.
- **Why:** Database-only notifications do not reach users outside the app.
- **Files:** backend event/worker layer, mobile platform configuration, user preference models.
- **Risks:** delivery, consent, retry, rate, and privacy concerns.
- **Approach:** Use queued jobs and preference-aware templates.

#### 4. Search, personalization, and merchandising

- **What:** Add dedicated search indexing, synonyms, recommendations, merchandising slots, and analytics.
- **Why:** Useful once catalog and traffic exceed simple SQL/client filtering.
- **Files:** product/search services and storefront discovery surfaces.
- **Risks:** Added operational cost and privacy requirements.
- **Approach:** Instrument real behavior first; do not invent recommendations without data.

## 13. Development Roadmap

### Phase A — Secure and stabilize

1. Freeze new public/admin features temporarily.
2. Define the role/ownership matrix.
3. Protect every backend route and add 401/403/ownership tests.
4. remove fake production auth/order/payment success.
5. rotate development secrets and make config environment-only.
6. build an authoritative migration chain and disposable test database.
7. harden uploads, public product/review visibility, and stock checkout concurrency.

**Exit condition:** an unauthenticated customer cannot access or mutate admin/customer-private data; all environments are reproducible from migrations; checkout cannot falsely confirm payment/order state.

### Phase B — Make the core purchase journey reliable

1. Partition/clear per-user client state correctly.
2. Standardize API contracts and client error behavior.
3. Make catalog, cart, coupon, address, checkout, order, review, and notification flows use real data or clearly labeled demo mode.
4. Add web tests and extend backend/mobile integration tests.
5. Add audit logging for admin changes.

**Exit condition:** registration through delivered order works consistently across web and mobile against one test environment, with clear failure recovery.

### Phase C — Clean architecture and UI

1. Establish design tokens and shared states/components.
2. Split large screens and admin modules.
3. Separate seller/admin navigation based on enforced permissions.
4. complete accessibility checks.
5. remove unsupported marketing and unfinished menu items.

**Exit condition:** the interface is consistent, accessible, truthful, and maintainable without changing core commerce behavior.

### Phase D — Add real operational domains

1. Payment and refund ledger.
2. Inventory movement and supplier/procurement model.
3. Shipment/tracking events.
4. Persisted store settings and permissions.
5. Background jobs, email, and push notifications.

### Phase E — Scale and optimize

1. Server-render/cache public catalog pages.
2. Paginate admin data and tune indexes.
3. Move media to durable object storage/CDN.
4. Add observability, deployment checks, backups, and recovery drills.
5. Add search/personalization only after measuring real demand.

## 14. Important Files and Their Responsibilities

### Root/infrastructure

| File | Responsibility |
|---|---|
| `README.md` | High-level project documentation; currently overstates several features and exposes dev setup credentials |
| `docker-compose.yml` | PostgreSQL, pgAdmin, backend, and web development services |
| `run.sh` | Builds/starts Compose, polls backend health, and prints service information |
| `pgadmin/servers.json` | Pre-registers the local PostgreSQL service in pgAdmin |

### Backend

| File/path | Responsibility |
|---|---|
| `backend/app/main.py` | FastAPI app, CORS, route registration, uploads mount, health/root endpoints, import-time table creation/seeding |
| `backend/app/api/v1/__init__.py` | Registers all routers under both `/api` and `/api/v1` |
| `backend/app/api/v1/routes/` | HTTP endpoints for every backend feature |
| `backend/app/core/config.py` | Environment settings, database URL, JWT and CORS defaults |
| `backend/app/core/security.py` | Password hashing/verification and JWT creation/decoding |
| `backend/app/core/dependencies.py` | Current and optional user resolution; lacks role policies |
| `backend/app/db/database.py` | SQLAlchemy engine, session factory, declarative base, request DB dependency |
| `backend/app/db/init_db.py` | `create_all` and manual compatibility ALTER statements |
| `backend/app/db/seed_data.py` | Automatic demo users, sellers, categories, and products |
| `backend/app/models/` | Current database schema definitions and relationships |
| `backend/app/schemas/` | Request/response validation and serialization |
| `backend/app/services/` | Main business logic |
| `backend/alembic/versions/` | Incomplete initial migration history |
| `backend/tests/test_api.py` | One stateful API integration flow against the configured DB/filesystem |
| `backend/docker-entrypoint.sh` | Runs migration/init/seed and launches reload-mode Uvicorn |

### Web

| File/path | Responsibility |
|---|---|
| `web-app/src/app/layout.tsx` | Root font, metadata, and HTML/body shell |
| `web-app/src/app/(store)/layout.tsx` | Store navigation, footer, cart/search/quick-view dialogs, toasts |
| `web-app/src/app/(store)/` | Customer pages and checkout/order/account flows |
| `web-app/src/app/(admin)/admin/layout.tsx` | Client-side admin login guard and dashboard shell |
| `web-app/src/app/(admin)/admin/` | Admin/merchant/POS pages |
| `web-app/src/app/(auth)/components/AuthForm.tsx` | Login, registration, and demo credential fill UI |
| `web-app/src/lib/api.ts` | API types and all backend request methods; nearly 1,000 lines |
| `web-app/src/lib/auth.ts` | localStorage auth/session helpers and client JWT expiry checks |
| `web-app/src/lib/store.ts` | Persisted Zustand commerce state and optimistic synchronization |
| `web-app/src/lib/store-catalog.ts` | Store image helpers, showcase fixtures, live/fallback fetchers, local coupon validation |
| `web-app/src/components/store/` | Reusable customer storefront components |
| `web-app/src/components/layout/` | Reusable admin layout and navigation components |
| `web-app/src/app/globals.css` | Tailwind import, global colors/animation/print rules, reduced motion |
| `web-app/next.config.ts` | SVGR and currently unrestricted remote image patterns |

### Mobile

| File/path | Responsibility |
|---|---|
| `mobile-app/lib/main.dart` | Flutter entry point and root providers |
| `mobile-app/lib/app/app.dart` | MaterialApp, theme selection, authenticated start screen |
| `mobile-app/lib/app/routes.dart` | Named routes |
| `mobile-app/lib/core/constants/api_endpoints.dart` | Platform-aware base URL and all API endpoint constants |
| `mobile-app/lib/core/network/api_client.dart` | Shared HTTP client, bearer header, parsing, timeout/error translation |
| `mobile-app/lib/core/theme/app_theme.dart` | Material 3 light/dark design theme |
| `mobile-app/lib/features/*/providers/` | Feature state and UI-facing operations |
| `mobile-app/lib/features/*/services/` | REST calls and, in auth, mock fallback logic |
| `mobile-app/lib/features/navigation/main_navigation_screen.dart` | Five-tab main application shell |
| `mobile-app/lib/features/checkout/screens/checkout_screen.dart` | Address/payment UI, order call, local fallback, simulated KHQR |
| `mobile-app/lib/features/auth/services/auth_service.dart` | Live auth wrapper with unsafe production-reachable mock fallback |
| `mobile-app/test/` | Broad Flutter unit/widget coverage for network, auth, catalog, cart, checkout, orders, notifications, reviews, profile, and shared widgets |

## 15. How to Run and Test the Project

### Prerequisites

- Docker Desktop with Docker Compose for the simplest backend/web/database setup.
- Flutter SDK compatible with Dart `^3.11.1` for mobile work.
- Node.js 20+ for local Next.js development.
- Python 3.12+ and PostgreSQL for non-Docker backend development.

### Environment configuration

- Backend requires `DATABASE_URL` and should receive a non-default JWT secret through environment configuration.
- Web optionally reads `NEXT_PUBLIC_API_URL`; the browser default is `http://localhost:8000/api`.
- Mobile accepts a host base through `--dart-define=API_URL=...`. Do not append `/api` when using the existing endpoint constants because they already include `/api/v1`.
- Keep real `.env` files untracked. The audit intentionally did not inspect or reproduce secret values.

### Run with Docker Compose

From the repository root:

```bash
docker compose up --build -d
docker compose ps
```

Or use:

```bash
./run.sh
```

Development services are configured for:

- Web: `http://localhost:3000`
- Backend: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- pgAdmin: `http://localhost:5050`
- PostgreSQL host port: `5433`

The current containers run Uvicorn and Next.js development servers, including reload behavior. They are not production deployment images.

### Run the backend locally

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Important: until the migration chain is repaired, `alembic upgrade head` alone does not create the full current model schema. The current app compensates with `create_all`, which should not be considered a production migration strategy.

### Run the web application locally

```bash
cd web-app
npm ci
npm run dev
```

Quality checks:

```bash
npm run lint
npm run build
```

No automated web test command exists in `package.json` at the time of this audit.

### Run the Flutter application

```bash
cd mobile-app
flutter pub get
flutter devices
flutter run --dart-define=API_URL=http://localhost:8000
```

For the standard Android emulator, the code automatically defaults to `http://10.0.2.2:8000`. A physical device needs a reachable LAN or hosted API address.

Quality checks:

```bash
flutter analyze
flutter test
```

### Backend tests

Current command:

```bash
cd backend
pytest
```

Warning: the existing suite imports the real app, triggers startup schema/seed behavior, writes an uploaded file, creates orders/users, modifies stock, and uses the configured database. Run it only against a disposable test database and temporary upload directory. A proper test dependency override and isolated fixture environment should be created before using it in CI.

### Recommended first task

Start with backend authorization, not visual redesign. Define the role/ownership matrix and protect users, orders, products, categories, sellers, reviews, notifications, stats, uploads, and POS. Add tests proving that guests and ordinary customers receive 401/403 for every forbidden operation. After that, remove fake authentication/order/payment success and repair migrations. These changes make later UI improvements safe and trustworthy.
