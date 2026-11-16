# Task 1 — Authorization and Ownership

Date: 2026-10-31. Task 1 only; Tasks 2–6 have not been implemented.

## Outcome and policy

Backend role guards now protect sensitive reads and administrative writes under both `/api` and `/api/v1`. Roles are resolved from the database on each authenticated request; a role claim in a JWT cannot grant privileges. Missing/invalid authentication returns 401, disallowed roles return 403, and another user's private resource generally returns 404.

| Operation | Admin | Seller | Customer, staff, employee |
|---|---|---|---|
| Public active catalog and approved reviews | Yes | Yes | Yes, including guests |
| User/role, category, seller administration | Yes | No | No |
| Product create/update/delete | All | Only assigned active seller stores | No |
| Product reassignment | All | Only another active store owned by the same user; cannot unlink | No |
| Private orders | All | Own purchases only | Own purchases only |
| All orders/status/delete, POS, global stats | Yes | No | No |
| Review moderation/delete | Yes | No | No |
| Review replies | All | Reviewed product must belong to an owned active store | No |
| Notifications | All; can create | Own recipient records | Own recipient records |
| Upload | Yes | Requires an active linked seller store | No |

`staff` and `employee` are accepted role values but have no administrative privileges. Unknown roles, including the old UI-only `super_admin` alias, receive no privileged access. No database roles were renamed or migrated. Seller fulfillment permissions and staff/cashier policies remain intentionally unimplemented until defined.

Public registration continues to force `customer`; profile updates cannot assign roles. Administrative create/update schemas now reject unsupported role values. Seller creation and account association are admin-only. Seller ownership checks support multiple linked stores and deny unlinked/suspended accounts.

Customers cannot read another customer's order. Existing address/cart/favorite ownership was retained and tested. Reviews cannot reference an order item belonging to another user. This does not implement a delivered-purchase requirement for every review: order association remains optional.

Public seller responses omit account linkage, owner contact details and financial metrics; the seller owner and admin retain full seller details. Nested product seller summaries omit owner/contact fields. Public review lists return approved reviews only and omit email/order linkage; owners can retrieve their own pending review by ID. Admins retain moderation visibility.

Notifications with no recipient include operational messages and are now admin-only. Customer read/delete/bulk actions cannot modify those shared records or another recipient's records. Per-user read state for public broadcasts would require a separate design; it was not simulated.

## Files changed

All paths below are relative to the project root. Pre-existing work was preserved.

| Files | Reason |
|---|---|
| `backend/app/core/dependencies.py` | Reusable role guard, database-derived identity, strict handling of invalid optional credentials, malformed subject handling |
| `backend/app/services/authorization_service.py` (new) | Central admin/active-seller/product ownership predicates |
| `backend/app/api/v1/routes/users.py` | Admin-only identity and role management |
| `backend/app/api/v1/routes/orders.py` | Admin-only global operations; owner/admin order detail |
| `backend/app/api/v1/routes/products.py` | Seller/admin mutations and private product visibility |
| `backend/app/api/v1/routes/categories.py` | Admin mutations and active public category visibility |
| `backend/app/api/v1/routes/sellers.py` | Admin mutations and limited public seller data |
| `backend/app/api/v1/routes/reviews.py` | Moderator/reply policies, approved public visibility, private-field filtering |
| `backend/app/api/v1/routes/notifications.py` | Required authentication and recipient/admin scope |
| `backend/app/api/v1/routes/pos.py`, `backend/app/api/v1/routes/stats.py` | Admin-only global POS/statistics operations |
| `backend/app/api/v1/routes/upload.py` | Admin/active-seller upload authorization and configurable upload root |
| `backend/app/schemas/user.py` | Role allow-list |
| `backend/app/schemas/product.py` | Remove private seller fields from nested product summaries |
| `backend/app/services/product_service.py` | Public active products and owner/admin hidden-product visibility across catalog aliases |
| `backend/app/services/notification_service.py` | Required explicit recipient scope; scoped single and bulk queries |
| `backend/app/services/review_service.py` | Check supplied order association against authenticated purchaser and product |
| `backend/app/core/config.py`, `backend/app/main.py` | `AUTO_INIT_DB` switch and `UPLOAD_DIR` setting for safe test imports; normal defaults preserved |
| `backend/tests/conftest.py` (new) | Temporary database/uploads, generated test signing key, synthetic fixtures and isolation checks before app import |
| `backend/tests/test_authorization.py` (new) | Role denial/allowance, owner isolation, public privacy, token and seller edge cases on both prefixes |
| `backend/tests/test_api.py` | Existing integration flow now uses authorized admin cleanup/upload; root JSON explicitly requested |
| `web-app/src/app/(admin)/admin/layout.tsx` | Redirect non-admin/non-seller accounts out of admin UI and clear readiness on logout; backend remains the security boundary |
| `web-app/src/lib/api.ts` | Types account for redacted seller/review responses |
| `web-app/src/app/(admin)/admin/sellers/page.tsx`, `web-app/src/app/(admin)/admin/sellers/[id]/page.tsx` | Safely handle optional private seller fields |
| `web-app/src/app/(store)/stores/page.tsx` | Do not show an empty owner label when private data is omitted |
| `AGENTS.md` | Replace obsolete unsafe-test warning with the new isolation requirements |
| `TASK1_AUTHORIZATION_REPORT.md` (new) | Policy, verification, compatibility changes and checkpoint handoff |

No application models/migrations, private env files, real database records, credentials, Flutter source, or packages were changed. The test harness creates and resets only its own temporary schema; it does not repair or exercise migration history.

## Verification

Executed from the relevant package directory:

| Command / check | Result |
|---|---|
| Backend: `rtk proxy .venv/bin/python -m pytest -q -p no:cacheprovider` | **320 passed**, 2 dependency deprecation warnings; temporary SQLite DB/uploads, no normal database connection |
| Web: `rtk npm run build` | Passed, including TypeScript and page generation |
| Web: `rtk npm run lint` | Failed: 5 errors and 11 warnings; errors in the unchanged POS page |
| Web: focused ESLint on the five changed TS/TSX files | Passed with one existing API-client navigation warning |
| Mobile: `rtk flutter test test/core/network/api_network_test.dart test/features/reviews/review_test.dart` | 19 passed; initial sandbox run blocked Flutter SDK cache write, approved retry succeeded |
| Backend/web `rtk git diff --check` | Passed |
| Hash comparison against audit snapshot | POS and all Flutter application source unchanged |

The final backend run passed all 320 cases. Tests cover denied administrative operations for anonymous/customer/staff/employee/unknown-role callers, seller restrictions, valid admin and seller operations, customer order/address/cart/favorite ownership, notification single/bulk scope, hidden inventory, review privacy, role injection, expired/invalid/inactive sessions, upload access, and the existing customer purchase flow.

The standalone TypeScript check initially found four optional-field errors after privacy changes; these were corrected, and the subsequent production build passed. The full lint failure is not hidden or treated as a successful check. Existing FastAPI/Starlette test-client dependencies emit two deprecation warnings; no package changes were made.

Not executed: PostgreSQL migration/concurrency tests, live database probes, full Flutter suite/analyzer, browser/device manual walkthroughs. This task establishes authorization correctness in isolated API tests; it does not certify production readiness or all client workflows.

## How to verify locally

1. From `backend/`, run `rtk proxy .venv/bin/python -m pytest -q -p no:cacheprovider`. The conftest sets isolation before app import; do not import/run test files directly. Synthetic fixtures are created automatically and removed with the temporary directory.
2. From `web-app/`, run `rtk npm run build`. For changed-file lint, run:

   ```bash
   rtk proxy ./node_modules/.bin/eslint 'src/app/(admin)/admin/layout.tsx' 'src/app/(admin)/admin/sellers/page.tsx' 'src/app/(admin)/admin/sellers/[id]/page.tsx' 'src/app/(store)/stores/page.tsx' src/lib/api.ts
   ```

3. In a disposable seeded development environment, browse products/stores as a guest; private fields should be absent. Sign in as a customer and open `/admin`: the UI redirects to `/account`, and direct admin API calls return 403. Guests receive 401 for protected APIs.
4. With two synthetic sellers, verify one can edit its assigned product but cannot edit/delete/reassign the other's product. With two customers, verify cross-account order/address/notification requests fail and bulk notification actions leave the other account untouched. The automated suite performs these mutations only in its temporary database.
5. From `mobile-app/`, rerun the two focused test files above. Manually check real authenticated order and notification loading against a disposable API environment; fake auth/checkout behavior is still pending Task 2.

## Remaining risks and compatibility changes

- Previously public admin operations now require an admin bearer token. Existing clients/scripts relying on unauthenticated mutation must be updated, not exempted.
- Seller dashboards may still link to global orders/POS/stats/user pages; those APIs now return 403. No seller order-partition or staff permission model was invented. Navigation redesign is outside this task.
- Public seller contact/revenue and review email/order fields are intentionally omitted. API envelopes and both prefixes remain; clients must tolerate omitted private fields. Some notification "broadcasts" disappear for customers because they have no authenticated recipient.
- Fake production authentication, checkout/payment success, known development credentials/defaults, upload content/size validation, migrations, stock concurrency, coupon transaction behavior, and general error handling remain for later tasks.
- Admin POS still has the audited notification constructor bug. Its authorization is secured; successful POS business processing is not claimed. Privileged payment/status changes still need evidence and transition rules in subsequent work.
- `AUTO_INIT_DB` defaults to the existing behavior for compatibility. Tests explicitly disable it; authoritative migrations and removing import-time initialization belong to Task 4.
- SQLite tests prove authorization/query behavior, not PostgreSQL locking or migration correctness. Browser role checks are convenience only; the backend enforces all actual permissions.

## Checkpoint

Task 1 authorization is implemented with isolated positive and negative tests. Stop here. The next recommended task is **Task 2: remove production-reachable fake authentication and order/payment success**. Do not start it until instructed.
