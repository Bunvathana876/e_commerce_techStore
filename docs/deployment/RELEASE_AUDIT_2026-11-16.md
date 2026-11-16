# Release audit — 2026-11-16

## Outcome

Verified and fixed release configuration, packaging, test coverage, and information-disclosure problems. This is not certification that every feature is correct or authorization to launch. No live database, migration, credentials, DNS, or app-store submission was changed. Existing staged and unstaged work was preserved.

## Changes made in this pass (complete file inventory)

| File | Reason |
| --- | --- |
| `backend/app/main.py` | Return a generic 503 on database readiness failure instead of exposing exception details. Existing CORS changes preserved. |
| `backend/tests/conftest.py` | Force test environment, disable seeding, and isolate rate-limiter resets from configured Redis. |
| `backend/tests/test_api.py` | Regressions for readiness confidentiality and in-memory test rate limiting. |
| `backend/.dockerignore` | Exclude private environment files and uploaded media from Docker context. |
| `storefront/next.config.ts` | Standalone packaging; reject missing/insecure production browser URLs and invalid API suffixes. |
| `storefront/Dockerfile.prod` | Node 24 matching package engines; deploy standalone server, public files, and static chunks. |
| `storefront/.dockerignore` | Exclude all private environment variants. |
| `management/next.config.ts` | Enable standalone packaging with serialized build configuration. |
| `management/Dockerfile.prod` | Node 24; deploy standalone runtime and static assets. |
| `management/.dockerignore` | Exclude all private environment variants. |
| `management/package.json` | Disable Node native web storage for tests so existing browser mocks work deterministically. |
| `deploy/production/compose.yaml` | Writable temporary Next.js cache in otherwise read-only frontend containers. |
| `web-app/package.json` | Run previously omitted TypeScript security tests with resolver; isolate browser storage mocks. |
| `web-app/src/app/(admin)/admin/pos/page.tsx` | Register shortcuts after handler declarations, refresh captured cart state each render, escape JSX quotes. |
| `mobile-app/lib/core/constants/api_endpoints.dart` | Validate API origins; require remote HTTPS URL in release; reject duplicate API paths and URL credentials. |
| `mobile-app/lib/main.dart` | Show an unavailable screen when release API configuration is invalid. |
| `mobile-app/test/core/network/api_network_test.dart` | Cover rejected release URLs and accepted development/production origins. |
| `mobile-app/android/app/build.gradle.kts` | Use private release signing configuration instead of debug signing. |
| `mobile-app/android/key.properties.example` | Placeholder-only signing configuration template. Actual signing files already ignored. |
| `mobile-app/android/gradle.properties` | Flutter build automatically added builtInKotlin/newDsl compatibility flags. |
| `docs/deployment/RELEASE_AUDIT_2026-11-16.md` | This evidence, file inventory, and handoff. |

## Verification

- Backend full isolated suite: **743 passed, 2 skipped**; skips initially required dedicated Redis. A subsequent focused run against a new disposable Redis container passed all four Redis tests, including both previously skipped cases. PostgreSQL migration/concurrency tests ran against disposable local PostgreSQL, not live data. Python on this machine is 3.14; production image specifies 3.12 and was not rebuilt in this pass.
- Storefront: **73 tests passed**, lint clean, production build passed.
- Management: **95 tests passed**, lint has 17 existing warnings and no errors, production build passed with placeholder HTTPS build variables. Local development `.env.local` intentionally fails its production URL guard.
- Preserved legacy web: **64 tests passed**, lint has 16 warnings and no errors, production build passed.
- Mobile: **189 tests passed**, analyzer clean, Android debug APK built. Flutter reports upcoming Gradle/AGP/Kotlin support deprecations; no versions were upgraded.
- Both production frontend Docker images built from lockfiles with Node 24. Read-only container HTTP checks passed for storefront `/`, `/shop`, `/checkout`, `/login` and management `/`, `/login`, `/admin/pos`, `/seller/products`. Twelve storefront and thirteen management static assets loaded. Security headers preserved, including management CSP API origin. These HTTP checks do not execute browser JavaScript or authenticate.
- Temporary audit containers were stopped after verification; local audit images and the debug APK remain available.
- Git diff whitespace checks passed for root and nested repositories.
- Both frontend production URL guards accepted HTTPS `/api` and rejected localhost HTTP, empty API URLs, and missing API suffixes.
- Production Compose placeholder configuration validated with `config --quiet`.
- npm production dependency audit: storefront zero findings; management three low findings in the SVGR/deepmerge chain. Management full Docker install reported three low and seven moderate findings including development dependencies. Dependency remediation needs a separately reviewed change; no automatic major downgrade was applied.
- Browser UI inspection was attempted but browser access host was unavailable. Narrow/wide, keyboard, and real purchase-flow checks remain unverified.
- Signed Android release, iOS archive, real hosted checkout, backups/restoration, production database migration, load testing, and full production infrastructure were not run. They require release identity/credentials, target hosting, or approved database operations.

## Remaining launch gates

1. Confirm intended hosting/domain names and Android/iOS targets. Actual DNS, TLS, secrets, durable upload storage, backup retention, monitoring, and restore rehearsal still need verification on that environment.
2. Choose permanent Android application ID and Apple bundle identity; current Android application ID is `com.example.e_commerc_mobile_app`. Configure private upload signing and Apple provisioning. Do not publish the debug APK.
3. Resolve source delivery: backend, mobile-app, and web-app are Git links with substantial uncommitted changes; storefront, management, and deployment files are untracked in the root. A clean remote checkout is not proven to reproduce this workspace. No Git restructuring or commits were performed.
4. Keep launch scope to cash on delivery unless a real electronic payment integration is independently implemented and tested. Existing KHQR/card/wallet demo controls do not prove payment settlement. A real gateway is not inherently required for a COD-only launch.
5. Complete interactive staging tests below, plus light/dark mobile and small-screen checks. Local automated success does not establish public production readiness.
6. Review dependency audit findings and tooling deprecations with approval before upgrading dependencies.

## Exact operator retest steps

### API failure and test isolation

From `backend/`, run `rtk .venv/bin/python -m pytest -q tests/test_api.py`. The readiness failure test substitutes an unavailable database and asserts HTTP 503 contains no connection details. The isolation test confirms an in-memory limiter. Do not stop a live database to test this.

### Frontend packaging and configuration

From the repository root, build with your actual HTTPS URLs (the examples below deliberately use non-live placeholders):

```sh
rtk docker build -f storefront/Dockerfile.prod --build-arg NEXT_PUBLIC_API_URL=https://api.example.com/api --build-arg NEXT_PUBLIC_MANAGEMENT_URL=https://manage.example.com -t blue-panda-storefront:verify ./storefront
rtk docker build -f management/Dockerfile.prod --build-arg NEXT_PUBLIC_API_URL=https://api.example.com/api --build-arg NEXT_PUBLIC_STOREFRONT_URL=https://shop.example.com -t blue-panda-management:verify ./management
rtk docker compose --env-file deploy/production/.env.example -f deploy/production/compose.yaml config --quiet
```

Use real target origins before release; public variables are compiled into bundles. Start isolated staging containers with the cache tmpfs declared in Compose. Visit `/shop`, `/checkout`, `/login`, and `/admin/pos`; confirm CSS/images load, no hydration errors, and intended API origin in browser Network. Disconnect staging API during checkout: confirm no successful order/payment is invented and cart is preserved.

### Legacy POS shortcuts and tests

From `web-app/`, run `rtk npm test`, `rtk npm run lint`, and `rtk npm run build`. In staging `/admin/pos`, add an item, change its quantity without changing the number of cart rows, then press F4. Resume the parked cart and confirm the updated quantity. Press F9 and confirm the current total, F8 for summary, and Escape to close. Use a staging staff account.

### Mobile release configuration and signing

From `mobile-app/`, run `rtk flutter analyze` and `rtk flutter test`. For device tests, use `rtk flutter run --dart-define=API_URL=https://YOUR_API_HOST`; no `/api` suffix. On a release build without a valid API origin, confirm the unavailable screen rather than localhost requests. A valid signed staging release should allow login, catalog, cart and COD checkout; test offline failures, back navigation, keyboard, light/dark, and account switching.

Copy `android/key.properties.example` to the ignored `android/key.properties` locally and supply your existing upload key details. Configure permanent app identity before `rtk flutter build appbundle --release --dart-define=API_URL=https://YOUR_API_HOST`. Release signing follows [Flutter Android release instructions](https://docs.flutter.dev/deployment/android). Never send or commit keystore passwords. No signing key was generated in this pass.
