# Blue Panda — Phase 1 Security Audit

Date: 2026-10-30. **Task 0 only; no fixes implemented.**

This is a static inspection of current source, starting from `PROJECT_CONTEXT.md` and checking the older `PROJECT_UI_UX_ANALYSIS.md`. Current source takes precedence. Findings describe reachable code paths, not a penetration test or verified deployment incident. No app imports, database connections, migrations, server startup, dependency installations, or database-writing tests were performed. Private environment file contents are not included.

## 1. Workspace and architecture

The root and the nested `backend/`, `web-app/`, and `mobile-app/` Git repositories are on `main`. Existing changes were present before this task:

- Root: modified README, `.DS_Store`, and nested repository references; untracked `.vscode/`, `AGENTS.md`, and `PROJECT_CONTEXT.md`.
- Backend: an untracked generated product image under `uploads/products/`.
- Web: modified admin/auth/layout/API files; deleted old root page; untracked storefront pages, components, catalog/state modules, images, and local instruction documents.
- Mobile: many modified networking, auth, catalog, cart, checkout, orders, notification, profile, review, theme, and shared-widget files.

These changes must be preserved. This task adds only this report to the workspace.

Blue Panda has a FastAPI/Python backend, PostgreSQL through synchronous SQLAlchemy 2, Pydantic schemas, Alembic migrations, bcrypt passwords, and JWT bearer authentication. Next.js 16/React 19 uses App Router, TypeScript, Tailwind 4 and Zustand. Flutter uses Provider/ChangeNotifier, HTTP services, and SharedPreferences.

Data flow: web pages/API wrapper or Flutter screens/providers/services → FastAPI route → service → SQLAlchemy session → PostgreSQL. Most backend responses use `{success, message, data}`. Users/stats and uploads have logic directly in route modules.

Every feature router is registered under **both `/api` and `/api/v1`** in `backend/app/api/v1/__init__.py`. Web defaults to `/api`; Flutter endpoint constants include `/api/v1`. Protect both aliases without breaking either client.

| Location | Responsibility / configuration |
|---|---|
| `backend/app/main.py` | App, CORS, routers, uploads, health/debug routes, import-time schema creation and seeding |
| `backend/app/core/` | Settings, password/JWT helpers, current-user dependencies |
| `backend/app/api/v1/routes/`, `services/`, `models/`, `schemas/` | HTTP, business logic, persistence, validation respectively |
| `backend/app/db/`, `backend/alembic/` | Engine/session, initialization/seed logic, migrations |
| `backend/.env`, `backend/.env.example` | Private settings location and existing example; private values not inspected |
| `web-app/.env.local`, `web-app/.env.example` | Local client API configuration and example; private values not inspected |
| `web-app/src/lib/{api,auth,store,store-catalog}.ts` | API, session, persisted shopping state, live/demo catalog |
| `mobile-app/lib/core/constants/api_endpoints.dart` | API host override and endpoint constants |
| `docker-compose.yml`, `run.sh`, `pgadmin/servers.json` | Development infrastructure and launch configuration |

There is no root `.env.example`. Compose defines `postgres`, `pgadmin`, `backend`, and `web`; host ports are 5433, 5050, 8000, and 3000. PostgreSQL/pgAdmin use named volumes. Backend/web use source bind mounts and development servers. Actual running containers and deployment configuration were not queried. Existing backend/web private env files were not listed as tracked by their nested repositories; that does not prove secrets have never appeared in Git history.

## 2. Authentication and existing protections

- `routes/auth.py` exposes registration/login, current profile, profile edit, password change, and logout.
- `services/auth_service.py` hashes passwords with bcrypt and issues signed JWTs. Public registration explicitly creates a **customer**, not a client-selected role.
- `core/security.py` verifies JWT signature/expiry with the configured algorithm. The default algorithm is HS256 and the default access lifetime is seven days. No refresh rotation or revocation implementation was found.
- `core/dependencies.py:get_current_user` returns 401 for missing/invalid credentials and resolves the database user; inactive accounts return 403. There is no role/permission dependency. Optional authentication returns `None` even for invalid tokens.
- Registration has no password length constraint; `name` and `full_name` can both be omitted, but the service calls `data.name.strip()`. Password change enforces only six characters. Boundary tests should include missing/blank names and bcrypt's password byte limit.
- `PUT /auth/me` accepts the broad `UserUpdate` schema, but its service updates only name, phone, and avatar. **This path currently does not assign roles**; the public `/users` CRUD endpoints are the privilege-escalation path.
- Backend logout returns success without invalidating the token. Password change also leaves already-issued tokens valid.
- Web login/register submit real API requests and save the returned session; no fabricated login fallback was found in `AuthForm.tsx`. Its demo-fill controls contain known development credentials. `auth.ts` uses localStorage and client expiry parsing; the admin layout checks login only, not role. This is not server-side authorization.
- Flutter stores tokens/users in SharedPreferences. Mock auth paths and social actions can enter authenticated UI without a real server session. Such fake tokens do not themselves bypass correctly protected backend routes.
- Cart, address, and favorite services normally filter by authenticated user ID. Order list/create use the current user. These working controls should be preserved and tested.

Roles are free-form strings. Seed/auth code uses `admin`, `seller`, and `customer`; employee/roles web pages also reference `employee`, `staff`, and `super_admin`. These UI references do not establish working backend permissions or prove those roles exist in the current database.

## 3. Route inventory

Each endpoint below is relative to **both** `/api` and `/api/v1`. Inventory was extracted from route decorators/signatures without importing the application and checked against services. There is no global or router-level role guard in the registration code.

Required access is a **proposed policy for Task 1**, not an implemented control. “Own seller” means `Seller.user_id == current_user.id` and `Product.seller_id == Seller.id`; never trust a supplied seller ID alone. Staff privileges remain undecided; default-deny unrecognized roles. Public seller/product/review output needs a deliberately limited public schema.

| Method | Endpoint | Current Access | Required Access | Risk |
|---|---|---|---|---|
| GET | `/products` | Public; inactive records possible | Public active catalog; privileged inventory query separately | High: hidden inventory exposure |
| GET | `/products/featured` | Public | Public active catalog | Medium: verify visibility filter |
| GET | `/products/search` | Public | Public active catalog | High: visibility bypass |
| GET | `/products/{product_id}` | Public | Public active item; owner/admin for hidden item | High: inactive/private seller fields |
| POST | `/products` | Public | Admin or own seller | Critical: arbitrary catalog writes |
| PUT | `/products/{product_id}` | Public | Admin or own seller; prevent reassignment | Critical: price/stock manipulation |
| DELETE | `/products/{product_id}` | Public | Admin or own seller, retention policy | Critical: deletion |
| GET | `/categories` | Public; active filter optional | Public active categories | Medium: visibility |
| GET | `/categories/{category_id}` | Public | Public active category | Medium: visibility |
| GET | `/categories/{category_id}/products` | Public | Public active products/category | High: alternate catalog path |
| POST | `/categories` | Public | Admin | Critical: mutation |
| PUT | `/categories/{category_id}` | Public | Admin | Critical: mutation |
| DELETE | `/categories/{category_id}` | Public | Admin, retention review | Critical: cascading deletion |
| GET | `/users` | Public | Admin | Critical: identity data disclosure |
| GET | `/users/{user_id}` | Public | Admin; self via `/auth/me` | High: identity data disclosure |
| POST | `/users` | Public, arbitrary role | Admin with role allow-list | Critical: privilege escalation |
| PUT | `/users/{user_id}` | Public, role/password editable | Admin with role allow-list | Critical: account takeover |
| DELETE | `/users/{user_id}` | Public | Admin, retention review | Critical: account/order deletion |
| GET | `/sellers` | Public, full seller response | Public limited active storefronts; admin full data | High: contact/financial fields |
| GET | `/sellers/{seller_id}` | Public, full seller response | Public limited profile; owner/admin full data | High: private seller data |
| POST | `/sellers` | Public; may create user | Admin, explicit identity assignment | Critical: account/store creation |
| PUT | `/sellers/{seller_id}` | Public | Admin; owner only allow-listed profile fields | Critical: seller/metric tampering |
| DELETE | `/sellers/{seller_id}` | Public | Admin | Critical: deletion |
| GET | `/orders/all` | Public | Admin; no full-order seller access | Critical: customer/order disclosure |
| GET | `/orders` | Authenticated, own orders | Authenticated owner | Controlled; preserve scope |
| POST | `/orders` | Authenticated, own cart | Authenticated owner, transaction safeguards | High: race/partial commit |
| GET | `/orders/{order_id}` | Public; optional service scope unused | Owner or admin | Critical: customer/order disclosure |
| PUT | `/orders/{order_id}/status` | Public | Admin, valid transitions and payment evidence | Critical: forged payment/status |
| DELETE | `/orders/{order_id}` | Public | Admin, retention decision | Critical: commerce record deletion |
| GET | `/reviews` | Public; any moderation status | Public approved/redacted; admin moderation view | High: email/pending review disclosure |
| GET | `/reviews/{review_id}` | Public | Approved/redacted public; owner/admin otherwise | High: review/email disclosure |
| POST | `/reviews/product/{product_id}` | Authenticated; purchase unchecked | Authenticated owner; verified purchase if promised | Medium: forged purchase association |
| PUT | `/reviews/{review_id}/status` | Public | Admin moderator | High: moderation tampering |
| PUT | `/reviews/{review_id}/reply` | Public | Admin or seller owning reviewed product | High: impersonated replies |
| DELETE | `/reviews/{review_id}` | Public | Admin; own-review removal only if agreed | High: deletion/rating manipulation |
| GET | `/notifications` | Optional auth; anonymous query unfiltered | Authenticated recipient; authorized broadcasts | Critical: private notifications leak |
| GET | `/notifications/unread-count` | Optional auth; anonymous count unfiltered | Authenticated recipient | Medium: information leak |
| POST | `/notifications` | Public; client chooses recipient | Admin/trusted server operation | High: forged messages |
| PATCH | `/notifications/{notification_id}/read` | Public, no ownership | Authenticated recipient | High: cross-user modification |
| POST | `/notifications/read-all` | Optional auth; anonymous updates all | Authenticated recipient | Critical: global modification |
| DELETE | `/notifications/{notification_id}` | Public, no ownership | Recipient; admin by explicit policy | High: deletion |
| DELETE | `/notifications` | Optional auth; anonymous deletes all | Recipient-scoped; no public bulk operation | Critical: global deletion |
| POST | `/coupons/validate` | Public; may seed/commit | Public quote, rate-limited; authoritative checkout validation | High: transaction side effects |
| GET | `/coupons/available` | Public; may seed/commit | Public intended active/unexpired offers; read-only | Medium: mutation during read |
| POST | `/upload/image` | Public | Admin or authorized seller, validated content/size | Critical: unrestricted upload |
| POST | `/pos/checkout` | Any authenticated user | Admin initially; explicit staff/seller policy later | High: privileged sale path; currently broken |
| GET | `/pos/summary` | Any authenticated user, global data | Admin; scoped staff/seller if supported | High: business data exposure |
| GET | `/pos/customers` | Any authenticated user; all active roles searchable | Authorized cashier; limited customer fields | High: identity disclosure |
| GET | `/stats/overview` | Public | Admin; separate seller-scoped view if needed | High: business data/revenue misstatement |
| POST | `/auth/register` | Public; fixed customer role | Public, validated/rate-limited | High: weak validation/abuse |
| POST | `/auth/login` | Public | Public, rate-limited | Medium: brute force protection absent |
| GET | `/auth/me` | Authenticated self | Authenticated self | Controlled |
| PUT | `/auth/me` | Authenticated self, restricted service fields | Authenticated self, dedicated schema | Low: overly broad request contract |
| PUT | `/auth/change-password` | Authenticated self/current password | Same plus policy/session handling | Medium: weak policy/no revocation |
| POST | `/auth/logout` | Authenticated, acknowledgment only | Session termination consistent with token design | Medium: token remains usable |
| GET | `/cart` | Authenticated owner | Authenticated owner | Controlled |
| POST | `/cart`, `/cart/items` | Authenticated owner | Authenticated owner | Controlled; validate stock |
| PUT | `/cart/{item_id}`, `/cart/items/{item_id}` | Authenticated owner; ambiguous ID matching | Owner, unambiguous item identifier | Medium: wrong own item changed |
| DELETE | `/cart/{item_id}`, `/cart/items/{item_id}` | Authenticated owner; ambiguous ID matching | Owner, unambiguous item identifier | Medium: wrong own item deleted |
| DELETE | `/cart` | Authenticated owner | Authenticated owner | Controlled |
| GET | `/favorites` | Authenticated owner | Authenticated owner | Controlled |
| POST | `/favorites/{product_id}` | Authenticated owner | Authenticated owner | Controlled |
| DELETE | `/favorites/{product_id}` | Authenticated owner | Authenticated owner | Controlled |
| POST | `/favorites/{product_id}/toggle` | Authenticated owner | Authenticated owner | Controlled |
| GET | `/addresses` | Authenticated owner | Authenticated owner | Controlled |
| POST | `/addresses` | Authenticated owner | Authenticated owner | Controlled |
| PUT | `/addresses/{address_id}` | Authenticated owner | Authenticated owner | Controlled |
| DELETE | `/addresses/{address_id}` | Authenticated owner | Authenticated owner | Controlled |
| PUT | `/addresses/{address_id}/default` | Authenticated owner | Authenticated owner | Controlled |

Non-prefixed surfaces in `app/main.py`: public `/`, `/health`, `/db-test`, `/docs`, `/redoc`, OpenAPI, and static `/uploads`. A minimal health endpoint can remain public; `/db-test` should be development-only or privileged. Public docs alone are not an authorization flaw. Static uploads require safe content handling. `/health` currently does not verify database readiness.

## 4. Confirmed findings and recommended fixes

Severity: **Critical** means unauthenticated destructive access, account compromise, or broad private-data exposure. **High** means serious confidentiality, integrity, transaction, or trust failures. **Medium** means narrower exposure, validation gaps, or operational risk. Conditions below distinguish confirmed code defects from untested runtime consequences.

| ID / Severity | Evidence and impact | Minimal recommended approach / compatibility risk |
|---|---|---|
| S01 Critical | `routes/users.py` and `schemas/user.py`: public create/update/delete, arbitrary role and password replacement | Protect all user management; allow-list supported roles. Keep public registration customer-only. Admin UI and current test cleanup must send authorized credentials. |
| S02 Critical | `routes/orders.py`, `services/order_service.py`: public all/detail/delete/status; status/payment fields assigned without transition checks | Enforce owner/admin queries and validated transitions; payment state needs trusted evidence. Seller access cannot expose another seller's lines or customer data through the whole order. |
| S03 Critical | `routes/products.py`, `categories.py`, `sellers.py`: public writes; no seller scope | Central role dependency plus ownership predicates. Sellers cannot reassign products to others or choose arbitrary account associations. Public reads must remain available with limited output. |
| S04 Critical | `routes/notifications.py`, `services/notification_service.py`: `None` user ID removes filtering; invalid tokens become anonymous; public single-item writes | Require authentication; scope every query/mutation. Global notifications have one shared `read` flag: customer actions must not mark/delete broadcasts for everyone. Per-recipient broadcast state needs a separate design decision. |
| S05 Critical | `routes/upload.py`: no auth, client-controlled MIME/extension, SVG accepted, size constant unused; `main.py` serves files | Authorize uploads, cap streamed bytes, validate real image content, disallow unsafe SVG, return generic failures. UUID filenames are already good; preserve them. Existing SVG assets and fake-byte upload tests may need updating. Exploitability of active content depends on rendering/deployment context. |
| S06 High | Flutter `auth/services/auth_service.dart`, `auth/screens/login_screen.dart`, `sign_up_screen.dart`: mock credential fallback, email-triggered mock registration, fabricated social sessions | Remove automatic fallback from production; use injected test doubles or explicit labeled demo mode. Disable unsupported OAuth actions. Existing UI tests may depend on these paths. |
| S07 High | Web `(store)/checkout/page.tsx`; Flutter `checkout/screens/checkout_screen.dart`: local orders after failure, success navigation/cart clearing, non-cash local orders marked paid | Preserve cart/draft on failure; require real order response; payment remains pending unless trusted verification exists. Guest checkout currently has no backend-supported guest-order flow; do not silently replace it. |
| S08 High | `core/config.py`, Compose, seed/launch/docs and web demo fill contain default credentials/secret dependencies; seller service has a fixed fallback password | Environment-driven secrets, explicit opt-in seed/demo mode, safe examples. Do not change private env files or rotate real deployments automatically. Any reused credentials require operator rotation. Actual deployed values are unknown. |
| S09 High | `main.py`, `db/init_db.py`, entrypoint, Alembic: incomplete migrations and silent schema recovery | Review additive migration/baseline strategy against disposable PostgreSQL first. Stop swallowing migration errors; separate app import, migrations, seeding. Existing volumes require inspection before any stamp/upgrade. |
| S10 High | `order_service.py` and `pos_service.py`: read/check/decrement stock without row locks; no request idempotency | Use a defined transaction boundary, ordered locks or atomic conditional updates, plus idempotency where justified. Test simultaneous requests in PostgreSQL, not only SQLite. |
| S11 High | `coupon_service.py:_seed_coupons_if_needed` commits/rolls back the caller session; checkout has already changed stock before calling it | Move seeding outside request validation. With an empty coupon table, seed commit can persist stock deductions even if coupon/address validation later fails. Preserve atomic order/cart/stock changes and test this exact sequence. |
| S12 High | `pos_service.py` passes `is_read=False` to `Notification`; model defines only `read` | Constructor mismatch is a static defect expected to raise before sale commit; runtime not executed. Fix with a focused regression test when authorized. Do not mistake this failure for a security control: POS lacks role checks and trusts price overrides/discounts, and intends to mark sales paid without validating tender/provider evidence. |
| S13 High | Public review schemas include user email; seller/product seller summaries include owner/contact data; seller response includes revenue. Inactive products and unapproved reviews are queryable | Separate public projection/filtering from admin views, check detail/search/category paths too. Limit seller disclosure intentionally. Moderation status validation exists in the service, but authorization does not. |
| S14 High | Web `auth.ts`, `store.ts`; Flutter auth/order providers: localStorage/SharedPreferences sessions and unpartitioned commerce caches | Clear/partition per-user state, handle expired sessions centrally. Plan secure platform storage and browser HttpOnly/session changes separately; they require coordinated architecture work. Do not discard guest carts without a defined merge policy. |
| S15 Medium | `auth` schemas/service: missing name/password bounds; `product` schemas: unconstrained price/stock; order/payment strings unrestricted | Add focused API validation and actionable 4xx errors. Preserve legitimate payload formats; test both clients. Public register already fixes the role, and profile service ignores role updates. |
| S16 Medium | `coupon` model uses timezone-naive expiry; service compares with aware UTC | Normalize datetime storage/comparison deliberately. Test expired and valid dated coupons; current defaults have no expiry and may conceal the problem. |
| S17 Medium | `stats.py` replaces zero paid revenue with all orders; review service commits review and notification separately and swallows errors | Report only truthful metrics; define transactional versus best-effort side effects, rollback failed sessions, use safe logging. Existing dashboard values may decrease. |
| S18 Medium | CORS wildcard plus credentials; unrestricted HTTP(S) image patterns in `web-app/next.config.ts`; raw upload/startup exceptions | Explicit environment origins/media allow-list and sanitized errors. Do not assert a proven SSRF exploit without testing framework/network defenses. CORS is not a substitute for authentication. |
| S19 Medium | Cart service matches either row ID or product ID in one query | Choose explicit identifiers while coordinating mobile (product ID) and web (cart row ID). Current ownership filtering prevents cross-user access, but colliding IDs can select the wrong item within one cart. |
| S20 High | `backend/tests/test_api.py` imports real app, seeds/creates tables, writes real upload path, creates orders and deducts stock | Isolate environment before app import, temporary uploads, dedicated disposable DB and dependency overrides. Build this minimum foundation during Task 1; do not wait until Task 6 to make security tests safe. |

## 5. Fake-success behavior: both clients

| Flow | Next.js | Flutter |
|---|---|---|
| Login | Real auth request; errors shown; demo-fill credentials are not fabricated JWT issuance | Specific demo credentials return a fabricated session after remote failure, not restricted to tests |
| Registration | Real request, no mock success found | Remote failure can become success for test/mock/example email patterns even outside tests |
| Social authentication | No real provider integration verified | Login/signup social handlers directly store fabricated tokens/users |
| Checkout/order | Guests, recognized network failures, or missing order data can create a local confirmed order; ordinary business errors are rethrown | Any caught order failure or unauthenticated flow can create a local order and navigate to success |
| Payment | Local non-COD order marked paid; no provider verification | Local non-cash order marked paid; KHQR modal has a simulated confirmation action |
| Coupons | Local validation after selected network error messages | Local validation after remote failure, including errors that should remain failures |
| Catalog/reviews | Empty/error responses activate showcase fixtures; missing product may be replaced by matching fixture ID | Do not infer universal offline mocks from old report; current catalog sample paths are generally test-gated |

Affected web paths: `src/app/(auth)/components/AuthForm.tsx`, `src/app/(store)/checkout/page.tsx`, `src/lib/store.ts`, `src/lib/store-catalog.ts`. Affected Flutter paths: `lib/features/auth/{services,providers,screens}/`, `lib/features/checkout/screens/checkout_screen.dart`, `lib/features/cart/providers/cart_provider.dart`, `lib/features/orders/providers/order_provider.dart`.

Backend customer checkout itself initializes payment as pending and recomputes prices; preserve that behavior. Public status mutation and POS are separate payment-integrity gaps. No working gateway/webhook/OAuth implementation was verified. Disabling a simulated action is preferable to pretending an external integration exists.

## 6. Migration and data integrity assessment

Static comparison found **12 model tables versus 8 migration-created tables** in the sole revision `backend/alembic/versions/f904b613102f_create_initial_ecommerce_tables.py`:

| Model schema not represented in initial revision | Required review |
|---|---|
| `sellers`, `reviews`, `notifications`, `coupons` | Add tables, indexes, constraints and FKs in dependency order |
| `products.seller_id` | Nullable seller FK/index; preserve unassigned products |
| `orders.discount_amount`, `orders.coupon_code` | Backfill/default policy for existing orders |

This is a source-level table/column comparison, not a complete live-schema diff. Types, defaults, indexes and constraints also require review. For example, the category-name migration index is non-unique while the model declares uniqueness.

`main.py` calls `create_all` and seeding at import. `db/init_db.py` repeats `create_all` and attempts two ALTER statements with swallowed exceptions. PostgreSQL errors can leave that shared transaction aborted. `docker-entrypoint.sh` continues after migration, initialization, and seed failures. `create_all` does not add missing columns to existing tables, so it cannot repair an old `products` table.

Automatic seed logic creates demo users/catalog and example notifications; coupon reads can seed too. Seed behavior should become an explicit development operation, outside requests/imports. `User.orders` cascades deletion and `orders.user_id` uses database CASCADE; deleting a user can erase order history. Product seller assignments and seller counters are not a substitute for a durable order-line seller snapshot.

Recommended future procedure: identify a disposable PostgreSQL target, test fresh migration → inspect model/schema parity, then test upgrades from representative existing schemas with preserved rows. For real environments, inventory current tables and Alembic revision, back up, and choose an explicit baseline/upgrade plan. **Do not blindly stamp, reset volumes, drop tables, or run migrations against the normal configured database.** No such operation was performed here.

## 7. Proposed authorization decisions for Task 1

Start with existing `get_current_user` plus reusable `require_roles(...)`; perform resource ownership checks in services/queries. Keep 401 for missing/invalid authentication and 403 for authenticated but disallowed roles. A consistent 404 for another user's private resource avoids confirming its existence.

| Capability | Admin | Seller | Staff/employee | Customer |
|---|---|---|---|---|
| Public active catalog | Yes | Yes | Yes | Yes, including guests |
| All user/role/category/seller administration | Yes | No | Deny pending explicit policy | No |
| Product management | All | Own linked seller only | Deny pending explicit policy | No |
| Private customer orders | All by admin policy | Own purchases; seller fulfillment view needs design | Deny pending explicit policy | Own only |
| Reviews | Moderate | Reply only for own products if approved policy | Deny pending explicit policy | Submit as self |
| Notifications | Explicit admin operations | Own recipient scope | Own recipient scope | Own recipient scope |
| POS and global statistics | Yes | Deny until scope defined | Deny until cashier permissions defined | No |

This conservative proposal does not silently grant privileges to `staff`, `employee`, or `super_admin`. Decide supported aliases before applying role validation. `Seller.user_id` is nullable and not unique: code must handle unlinked/multiple stores without assuming one valid seller per account. Seller order access is especially sensitive because one order may contain several sellers and historical items can lose their product reference. Do not grant access to the entire order merely because one item belongs to a seller.

## 8. Required test cases and verification plan

First establish a disposable test database identity and temporary upload root **before importing `app.main`**. Dependency overrides alone do not prevent current import-time writes. Use synthetic users/products and an explicit test secret, with fixtures that cannot target the normal database. PostgreSQL is required for credible lock/concurrency/migration verification; SQLite-only passes would not prove those behaviors.

| Area | Required cases |
|---|---|
| Authentication | Missing/malformed/expired/invalid-signature token → 401; inactive user → 403; missing name/weak or oversized password rejected; registration cannot select role; profile cannot escalate role |
| Admin routes | Anonymous denial on every sensitive method, customer → 403, authorized admin success; test both API prefixes and alternate cart/catalog routes |
| Ownership | Customer A cannot read/change customer B's order, address, cart, favorite or notification; authorized owner succeeds |
| Sellers | Seller A cannot mutate seller B's products or reassign ownership; forged seller ID denied; unlinked/multiple seller records handled; no unrelated order fields leaked |
| Notifications | Anonymous/invalid-token list and bulk operations denied; counts scoped; recipient cannot change another user's record or shared broadcast state |
| Public responses | Inactive products and non-approved reviews unavailable through list/detail/search/category paths; no private user email or seller finance fields |
| Uploads | Unauthorized caller, oversize content, spoofed MIME/extension, unsafe SVG and non-image bytes rejected; valid image succeeds in temporary directory; no partial file after failure |
| Client auth | Offline/invalid login and failed registration never create a production session; disabled OAuth never saves a token; explicit demo state cannot masquerade as production |
| Checkout/payment | Failed request/malformed result preserves cart and shows failure; real server result required for confirmation; no client-selected paid status; unknown response outcome handled without blind duplicate retry |
| Transactions | Out of stock, invalid coupon/address, DB failure and empty coupon table leave stock/cart/orders unchanged; duplicate/concurrent checkout cannot oversell or duplicate orders |
| POS | Role denial, valid notification construction, safe price/tender policy, underpayment rejection, no unverified non-cash success, transaction rollback |
| Coupons/stats | Reads do not seed/commit; expired/timezone-boundary coupon handling; server rejection cannot become local approval; zero paid revenue remains zero |
| Migrations | Fresh DB and representative old-schema upgrade; all tables/columns/FKs/indexes expected; existing rows preserved; startup fails clearly when migrations fail |
| Client state | Logout/account switch clears or partitions private data; expired session yields reauthentication; errors retain useful recovery state |

Current backend suite has four tests in `backend/tests/test_api.py`, no isolated fixtures, and expects public user deletion and fake image upload to succeed. Its root test expects JSON without explicitly requesting JSON, while the root handler defaults to HTML. These are source observations; tests were **not executed**. Flutter has feature/unit/widget tests, but old reports' pass counts were not reverified. Web `package.json` has lint/build scripts but no test script/framework configured.

Safe checks performed for Task 0: Git branch/status in all four repositories; source-only route inventory using Python AST; source-only model/migration table/column comparison; configuration-location and test inspection. Documentation validation and source-hash comparison are recorded in the task handoff. No runtime vulnerability probe, build, Flutter test, pytest run, or migration was performed. Static findings are not claims that runtime tests passed.

## 9. Unverified assumptions and compatibility risks

- Deployment exposure, TLS/reverse-proxy defenses, actual environment values, secret reuse, database contents/revision, backups, and installed/running service health are unknown.
- No credential rotation or external service provisioning has been authorized/performed in Task 0. Report locations, never values.
- Staff/cashier permissions, seller fulfillment visibility, public contact fields, notification broadcast state, guest checkout, and order retention need explicit decisions before their behavior is changed.
- Adding backend guards will reveal UI paths that currently rely on public APIs. Admin navigation needs role-aware handling and 403 messages; both clients need accurate session-expiry behavior. Public browsing must continue to work.
- Preserve both API prefixes/envelopes during hardening. Avoid combining security work with API version retirement, large component refactors, or a visual redesign.
- Restricting uploads and mocks intentionally breaks tests that relied on unsafe behavior. Replace those assumptions with isolated fixtures, not production bypasses.
- Fixing POS notification construction alone would activate an otherwise unsafe privileged sale path; add authorization and payment/tender tests alongside the reliability repair.
- CORS wildcard and arbitrary image origins warrant hardening but are not evidence of a demonstrated deployment exploit. No dependency CVE audit was performed.
- The older UI report's Redis/offline behavior/test-count claims are not current evidence. The newer context also understates anonymous notification scope: current service logic exposes **all** notifications when user ID is absent, not merely global ones.

## 10. Recommended implementation order and checkpoint

1. **Task 1: backend authorization first**, beginning with public users/role/password changes, orders, notification bulk operations, catalog/seller writes, uploads, review moderation, stats and POS. Define the role matrix, then add reusable guards and ownership checks. Establish the minimum isolated test harness within this task so every protection has positive and denial tests.
2. **Task 2:** remove production fake authentication and order/payment success, make failure recovery truthful, and keep incomplete integrations unavailable.
3. **Task 3:** harden environment defaults, opt-in seeds, CORS/uploads, safe errors and session cleanup; document manual rotation of any reused real credentials.
4. **Task 4:** repair migrations using disposable PostgreSQL and reviewed preservation/baseline rules.
5. **Task 5:** fix transaction boundaries (especially coupon seeding), stock concurrency, retry/idempotency, validation, POS correctness and observable errors.
6. **Task 6:** expand the safe testing foundation across backend, web and Flutter, verify compatibility, then write the implementation report.

**Checkpoint 0 complete: audit and proposed implementation order are ready for review. No security fix is claimed as implemented. Stop here and wait for the instruction “Continue Task 1”.**
