# Deployment fix progress — 2026-11-17

Status: active work; production readiness is not yet established. No deployment,
remote push, production migration, dependency upgrade, or credential change was
performed in this pass. Existing checkout/migration changes were already present
when work began and were preserved.

## Verified defects fixed

1. A slow checkout could lose exclusive ownership of an expired idempotency
   record. A PostgreSQL regression test reproduced two workers creating orders
   for the same key. Acquisition now holds transaction-scoped advisory and row
   locks until the order commits or rolls back. New keys and abandoned records
   are covered. SQLite test transactions now begin before inserting a savepoint,
   so failed checkout does not leave a committed retry record.
2. Checkout performed an unnecessary second idempotency write after committing
   the order. The order ID is already persisted atomically with the order, so
   that second write was removed. Rollback no longer deletes a retry record
   another worker could have acquired. Cleanup excludes processing records.
3. Cancellation and cash settlement could both succeed from stale snapshots.
   Four PostgreSQL regression cases reproduced this for both cancellation API
   paths and both execution orders. Conditional updates now validate both
   fulfillment and payment state; the losing action returns HTTP 409 without
   restoring inventory or overwriting the successful action.
4. Root Git submodule references lacked `.gitmodules`, causing `git submodule
   status` to fail. All five mappings now match the existing repository origins.
   Nested changes still need release commits and published references before a
   fresh clone can include them.
5. The README claimed production readiness and real integrations that were not
   established, listed the wrong active website locations, and provided unsafe
   setup guidance. It now describes current applications, supported COD checkout,
   limitations, test isolation, and deployment gates without embedded passwords.
6. Web checkout retry handling lost its idempotency key on browser reload because
   the key lived only in a component ref. A durable `sessionStorage`-backed helper
   now caches the pending key tied to the cart item signature. Retrying after page
   reload or network failure sends the exact same idempotency key; modifying cart
   contents invalidates stale keys; and confirmed checkout clears the key.
7. Mobile checkout did not pass atomic cart items or an idempotency key to the
   backend API. `OrderApiService.createOrder` and `CheckoutScreen` now track
   `_checkoutIdempotencyKey` and items payload, reusing the identical key across
   retries upon network glitches or server 5xx responses, and resetting upon success.
8. `ordersApi.delete` in `management` and `storefront` was out of sync with the
   backend contract and `web-app`, expecting `ApiResponse<null>` rather than the
   cancelled order response. They now support optional `reason` and return
   `ApiResponse<ApiOrder | null>`, with admin toast copy updated to reflect
   cancellation/archival rather than hard table deletion.

## Files changed in this pass

| File | Purpose |
| --- | --- |
| `.gitmodules` | Restore nested repository URL/path mappings |
| `README.md` | Correct setup, feature, and readiness documentation |
| `backend/app/services/idempotency_service.py` | Keep retry ownership tied to transactions and preserve rollback |
| `backend/app/services/order_service.py` | Remove post-commit retry writes and protect payment/cancellation races |
| `backend/tests/test_stock_concurrency.py` | Add seven PostgreSQL concurrency and rollback regressions |
| `storefront/src/lib/checkout-security.ts` | Add durable sessionStorage checkout key tied to cart signature |
| `storefront/src/app/(store)/checkout/page.tsx` | Use durable key across checkout lifecycle and reload |
| `storefront/src/lib/api.ts` | Sync `ordersApi.delete` signature with backend contract |
| `storefront/src/lib/__tests__/checkout-security.test.ts` | Regressions for reload persistence and cart invalidation |
| `web-app/src/lib/checkout-security.ts` | Add durable sessionStorage checkout key tied to cart signature |
| `web-app/src/app/(store)/checkout/page.tsx` | Use durable key across checkout lifecycle and reload |
| `web-app/src/app/(admin)/admin/orders/page.tsx` | Truthful cancellation/archival notification copy |
| `web-app/src/lib/__tests__/checkout-security.test.ts` | Regressions for reload persistence and cart invalidation |
| `management/src/lib/api.ts` | Sync `ordersApi.delete` signature with backend contract |
| `management/src/app/(admin)/admin/orders/page.tsx` | Truthful cancellation/archival notification copy |
| `mobile-app/lib/features/orders/services/order_api_service.dart` | Support atomic items and idempotency key/header in `createOrder` |
| `mobile-app/lib/features/checkout/screens/checkout_screen.dart` | Track and persist `_checkoutIdempotencyKey` across retry |
| `mobile-app/test/features/checkout/checkout_security_test.dart` | Regression for retry key reuse and confirmed cart clearing |
| `docs/deployment/DEPLOYMENT_FIX_PROGRESS_2026-11-17.md` | Record evidence, testing steps, and remaining work |

The service and checkout files were already dirty at the start. Their overall
Git diffs include pre-existing work beyond this pass. No schema or migration file
was changed by this pass.

## Verification evidence

- Full backend suite: **783 passed, 2 skipped**, with two dependency deprecation
  warnings. PostgreSQL migration/concurrency tests ran in disposable clusters.
- Focused checkout, stock concurrency, deletion, and state-machine suites:
  **69 passed** after both fixes.
- Storefront: **79 tests passed** (including durable reload regressions), lint clean,
  production build passed.
- Management: **95 tests passed**, lint clean (0 errors, 0 warnings),
  production build passed.
- Legacy web: **70 tests passed** (including durable reload regressions), lint clean,
  production build passed.
- Flutter: **190 tests passed** (including mobile idempotency retry regression),
  analyzer reports no issues.
- Production image runtime check (`verify-local-runtime.py`): **PASSED** on disposable
  PostgreSQL 16 container, verifying migrations, non-root read-only runtime, auth/role
  denials, COD checkout, retry idempotency, cancellation 409, and CORS on both API prefixes.
- Production Compose placeholder validation: passed using `config --quiet`.
- Root and all five application repositories: `git diff --check` passed cleanly.
- Graphify knowledge graph: updated AST-only without error.

Backend tests used the installed Python 3.14 virtual environment; the production
Dockerfile uses Python 3.12, whose container runtime still needs verification.
Web builds used the current local configuration. This proves compilation, not
that production API URLs were supplied. No package versions were changed.

## Reproduce the changed behaviors safely

From `backend/`, use the existing isolated pytest environment:

```bash
rtk proxy .venv/bin/python -m pytest -q tests/test_stock_concurrency.py -k 'expired_checkout or postgres_checkout_failure or cash_settlement_and_cancellation'
rtk proxy .venv/bin/python -m pytest -q tests/test_checkout_reliability.py tests/test_order_deletion.py tests/test_order_state_machine.py
```

The first command needs installed `initdb` and `pg_ctl`. It creates a disposable
socket-only PostgreSQL cluster and proves:

1. Competing submissions with the same customer/key receive 409 while a slow
   checkout is live; retry after completion returns the original order and stock
   decreases only once. This covers new and previously abandoned records.
2. A failed checkout rolls back the order, stock, and new retry record; retrying
   with the same key succeeds, and a later retry returns that order.
3. Simultaneous cash settlement and cancellation cannot both succeed. If payment
   wins, stock stays deducted. If cancellation wins, payment stays pending and
   stock is restored exactly once. Both status-update and DELETE paths are tested.

The second command checks HTTP response compatibility across `/api` and
`/api/v1`, authorization, ownership, failed checkout, and cancellation behavior.
Do not point a manual replay/cancellation test at a real customer's order.

From the root, check the source mappings and configuration without changing data:

```bash
rtk git submodule status
rtk docker compose --env-file deploy/production/.env.example -f deploy/production/compose.yaml config --quiet
```

## Remaining work before a deployment claim

- Confirm target hosting (e.g., VPS with Caddy, Render, etc.) and environment credentials.
- Choose permanent Android application ID and Apple bundle identifier (currently `com.example.e_commerc_mobile_app`) and configure production signing keys before app store submission.
- Staging deployment dry-run: run migration script against target staging cluster, configure live CORS origins and SSL certificates.
- Two optional Redis integration tests require an external Redis instance; local in-memory fallback is fully verified.
- Commit release branches in nested repositories when remote push credentials are provided.

The historical audit documents remain orientation, not evidence that all release
gates are satisfied.
