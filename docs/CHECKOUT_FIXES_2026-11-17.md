# Checkout fixes — 2026-11-17

The four issues from the project review are fixed locally. This is not a deployment or production-readiness sign-off. Existing unrelated changes, including backend checkout/migration work, were preserved. No dependency or database schema changes were made in this pass.

## Behavior changes

1. Mobile checkout fetches the authenticated account and its saved addresses from the backend. Customers without an address can add one through a validated form. Loading, empty, failure, retry and save-failure states are explicit. Checkout sends the selected address ID and full contact/address snapshot; no hardcoded customer addresses remain in the screen.
2. Mobile cart and checkout use the backend's standard shipping rule: $2 below a $100 subtotal, free at or above $100, before discounts. Express is visibly unavailable and cannot add a surcharge or imply express fulfillment.
3. Mobile saves an original checkout request and random idempotency key before sending it. The record is scoped by API origin and verified customer ID, persists across screen/process recreation and logout, and is removed after confirmed consumption or a definitive validation/inventory rejection. An unresolved retry resends the exact original payload. A pending request does not silently become a new order when the cart changes. Replaying a previous order does not clear a newly edited cart. Stale account responses cannot update the next account's checkout.
4. Storefront and legacy web preserve server-settled COD `paid` status in order history and checkout replays. Mobile also preserves server COD settlement on replay. Pending, failed and refunded states remain distinct. Electronic demo methods still cannot establish a paid transaction; mobile now blocks their real-order submission, matching the web's COD-only flow.
5. The storefront unused-import lint warning is removed. Narrow-screen checkout headings wrap with enlarged text.

## Files changed in this pass

Paths below are relative to the root workspace. Some files were already dirty; their full Git diffs also contain earlier work.

| File | Why |
| --- | --- |
| `mobile-app/lib/core/constants/api_endpoints.dart` | Add the existing addresses API path |
| `mobile-app/lib/core/network/api_client.dart` | Expose the authentication epoch for stale-response rejection |
| `mobile-app/lib/features/cart/providers/cart_provider.dart` | Match the backend shipping fee |
| `mobile-app/lib/features/checkout/models/address_model.dart` | Parse saved addresses and preserve province, postal code and contact fields |
| `mobile-app/lib/features/checkout/providers/checkout_provider.dart` | Own checkout/address loading, selection, account isolation, submission and retry state |
| `mobile-app/lib/features/checkout/services/address_service.dart` | Fetch/create real addresses and verify returned ownership |
| `mobile-app/lib/features/checkout/services/checkout_attempt_store.dart` | Persist and serialize per-account checkout retry records |
| `mobile-app/lib/features/checkout/widgets/checkout_address_section.dart` | Render real addresses, selection, errors and the address form |
| `mobile-app/lib/features/checkout/screens/checkout_screen.dart` | Integrate the checkout provider, remove hardcoded addresses, disable express, recover pending orders and preserve settled COD status |
| `mobile-app/lib/features/orders/services/order_api_service.dart` | Send the optional saved address ID with existing atomic checkout/idempotency fields |
| `mobile-app/test/support/checkout_api_fixture.dart` | Supply explicit test-only identity/address API fixtures |
| `mobile-app/test/features/cart/cart_and_checkout_modernization_test.dart` | Verify corrected totals, disabled express and real API address selection |
| `mobile-app/test/features/checkout/checkout_security_test.dart` | Verify COD-only submission and durable retry after screen recreation |
| `mobile-app/test/features/checkout/checkout_reliability_test.dart` | Cover persistence, ownership, late responses, lost responses, concurrency, stock conflicts and shipping boundaries |
| `mobile-app/test/features/checkout/checkout_address_widget_test.dart` | Cover loading/retry, form validation, save failure, light/dark themes and 320px layout with enlarged text |
| `storefront/src/lib/checkout-security.ts` | Preserve backend-confirmed COD settlement |
| `storefront/src/lib/__tests__/checkout-security.test.ts` | Add settlement regressions and remove the unused import |
| `web-app/src/lib/checkout-security.ts` | Apply the same settlement correction in legacy web |
| `web-app/src/lib/__tests__/checkout-security.test.ts` | Add legacy settlement regressions |
| `docs/CHECKOUT_FIXES_2026-11-17.md` | Record scope, evidence, limitations and reproduction steps |

## Verification

- Full Flutter suite: **204 passed**.
- Flutter analyzer: **no issues**.
- Storefront: **91 tests passed**, lint clean, production build passed.
- Legacy web: **82 tests passed**, lint clean, production build passed.
- Backend focused suite: **382 passed** using the isolated pytest configuration. Command: `rtk proxy .venv/bin/python -m pytest -q tests/test_checkout_reliability.py tests/test_order_state_machine.py tests/test_authorization.py` from `backend/`.
- Diff whitespace checks passed for the root and application repositories.
- Existing Node module/storage test warnings and backend dependency deprecation warnings remain; no dependency changes were introduced to suppress them.

The backend full suite, PostgreSQL concurrency tests, management build and production Compose validation were not repeated in this fix pass because their source/configuration was not changed by this pass. They were checked in the preceding review. Live production orders, migrations, deployment, signed mobile builds and real payment integrations were not exercised. Widget tests use mocked HTTP, while backend tests use isolated databases; they do not establish live network or hosting readiness.

## Safe user verification

Use a disposable staging account and test products, not a real customer's order.

1. **Addresses:** Sign in on mobile and open checkout. Confirm the displayed recipient matches the saved account address. Select a different saved address and confirm that the submitted order uses it. With a new account, select Add address, try saving empty fields, then enter a complete test address and save. Simulate an address API failure and verify Retry/save retry retains input and never selects a fabricated address.
2. **Shipping:** Use a $45 product, quantity one, with no coupon. Cart and checkout should show $2 shipping and $47 total. At $100 subtotal shipping should be free. Express should say Unavailable and leave the total unchanged. Check both themes at a narrow width.
3. **Lost response/restart:** From `mobile-app/`, run `rtk flutter test test/features/checkout/checkout_security_test.dart test/features/checkout/checkout_reliability_test.dart`. These simulate a server commit followed by a lost response, recreate the checkout state, and assert the same request/key returns one order. For staging fault injection, drop the order response after backend commit, leave/reopen checkout and choose Retry pending order. Confirm one order and one stock deduction. Switching accounts must not show or submit the other account's pending request.
4. **COD settlement:** In staging, advance a test COD order through supported fulfillment states and record authorized cash settlement with a reason. Open order history in storefront and legacy web: it must show Paid. A delivered order whose payment remains pending must still show Unpaid (Cash on Delivery). Refunded/failed orders must keep their corresponding payment labels.
5. **Unsupported payments:** Select a mobile electronic demo method and attempt checkout. It must explain that online payments are unavailable, preserve the cart and create no order.

## Remaining operational limits

- Pending retry records deliberately survive logout under their original account's storage key. They use the project's existing SharedPreferences storage, contain the original delivery snapshot, and are removed after confirmation or definitive rejection; they contain no bearer token.
- Corrupt retry state or attempts older than 23 hours fail closed and direct the customer to check order history/support. The backend may prune completed idempotency records after 24 hours, so blindly resending older attempts could create a duplicate. Do not erase unresolved retry state as routine cleanup.
- The existing idempotency migration must already be reviewed/applied in the target environment before deploying clients that rely on it. This pass did not apply migrations.
- Manual browser/physical-device verification against staging remains a release check. Automated widget coverage does not replace that target-environment check.
