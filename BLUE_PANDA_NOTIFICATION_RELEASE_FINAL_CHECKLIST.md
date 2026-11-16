# Blue Panda notification security final checklist

Prepared 2026-11-16. **Status: local release candidate verified; production deployment is blocked pending staging and a verified management deployment path.** No commit, staging, push, migration, production data operation, or deployment occurred during this check. The backend and management repositories still contain unrelated uncommitted work.

## Security behavior verified locally

- [x] Personal list, unread count, mark read, mark all read, delete, and clear all use the authenticated user's ID. A missing service recipient raises `ValueError` before a query or mutation.
- [x] `/notifications/admin` routes require the backend `admin` role. Unauthenticated requests get 401; customer and seller tokens get 403.
- [x] The admin feed contains the current admin's private rows and `user_id=NULL` shared rows. Foreign customer and seller private rows are excluded. Both `/api` and `/api/v1` are covered.
- [x] Admin and personal mutations affect only the authenticated user's private rows. A foreign or shared ID returns 404. Bulk actions cannot use a null recipient to update or delete all rows.
- [x] Shared notices are read-only in the admin feed. The model has one global `read` bit per null-recipient row, so a per-admin dismissal cannot be represented safely. Shared rows do not contribute to admin unread counts or the `unread_only` feed.
- [x] Management API paths, methods, bearer attachment, response fields, and exact `admin` role policy match the backend. Storefront and mobile remain on the personal API paths.
- [x] The management page labels shared and fallback summary rows as read-only, shows loading/empty/error/retry/success states, waits for a successful read before navigating from a linked card, and refreshes after successful writes. The navbar skips shared mutations and reports fetch or write failures.
- [x] The page and navbar discard late responses when the session epoch, token, or user ID changes. The page clears private feed state and immediately reloads for the new account on same-tab auth changes and cross-tab credential storage events.
- [x] No notification model or Alembic file changed. The only schema edit is a request-field description. **No database migration is required for this release.**

## Required release files and exclusions

The lists below are the complete **notification** scope at the time of this check. Reinspect status immediately before staging; do not use `git add .` or stage the root repository wholesale.

| Repository | Include |
| --- | --- |
| `backend/` | `app/api/v1/routes/notifications.py`; `app/services/notification_service.py`; `app/schemas/notification.py`; `tests/test_notification_ownership.py` (currently untracked); the notification-only diff in `tests/test_authorization.py`. |
| `management/` | `src/app/(admin)/admin/notifications/page.tsx`; `src/components/layout/Navbar.tsx`; `src/lib/admin-notification-feed.ts` (currently untracked); `src/lib/__tests__/admin-notifications.test.mjs` (currently untracked); **only the notification hunks** in `src/lib/api.ts`. |

| Repository | Exclude from this focused release |
| --- | --- |
| `backend/` | `app/main.py`, `tests/test_config_security.py`, `tests/test_cors_security.py`; all other existing local changes. |
| `management/` | `src/components/layout/Sidebar.tsx`, `src/components/seller/SellerSidebar.tsx`, `src/lib/auth.ts`, `Dockerfile.prod`, `src/lib/__tests__/server-logout.test.mjs`; the unrelated `authApi.changePassword` hunk in `src/lib/api.ts`. |
| Root, storefront, legacy web app, mobile | All pre-existing edits and untracked files. The root release reports are documentation; they are not runtime dependencies. |

The release depends on existing management auth helpers, but this notification change does not require the unrelated auth diff to be staged. If a separate release already includes it, review that release independently.

## Actual checks run

| Check | Result |
| --- | --- |
| Backend focused `rtk proxy .venv/bin/python -m pytest -q tests/test_notification_ownership.py` | **39 passed**, 2 deprecation warnings. |
| Backend full `rtk proxy .venv/bin/python -m pytest -q` | **741 passed, 2 skipped**, 2 deprecation warnings. |
| Management `rtk proxy env NODE_OPTIONS=--no-experimental-webstorage npm test` | **95 passed**, 0 failed/skipped. Includes cross-tab account-switch guard tests. |
| Management `rtk proxy npx tsc --noEmit` | Passed. |
| Management `rtk proxy npm run lint` | Passed with 0 errors and 17 existing warnings outside the notification edits. |
| Management production build with placeholder HTTPS public URLs | Passed; `/admin/notifications` was generated. This does **not** validate real deployment URLs or a container image. |
| `rtk proxy git diff --check` in backend and management | Passed. |

The backend fixture sets a temporary SQLite database, temporary uploads, a generated test JWT secret, and `AUTO_INIT_DB=false` before app import. Tests did not touch production data. Local Node was 25.8.0, while management declares `24.x`. No authenticated browser walkthrough, staging PostgreSQL run, real-origin CORS check, or container build was performed.

## Open release gates

1. **Staging is unavailable in the accessible Render workspace.** Read-only inspection found `blue-panda-api-demo` on `main` with auto-deploy enabled and no Blue Panda staging service. The live backend commit is `ad26cefb3dae4d0a24d1b53c8cdb5f494ac602cf`, which matches the local committed backend HEAD; the notification fix is uncommitted and not live. A separate, disposable PostgreSQL-backed staging service and staging management portal must be identified and validated before production approval.
2. **Management deployment path is unverified.** `deploy/production/` is explicitly a configuration skeleton, not a launch-ready deployment. Its untracked `management/Dockerfile.prod` uses Node 20 in all stages, while `management/package.json` requires Node 24.x. If that Dockerfile is selected, resolve the runtime mismatch and validate its image separately. Do not include that unrelated Dockerfile in this focused notification staging set without its own review.
3. **Browser behavior needs staging QA.** Node tests exercise feed rules and API requests; they do not render the actual TSX page or navbar at phone and desktop widths. Check focus, loading/empty/error/retry, linked-card navigation after failed read, 401 redirect, 403 denial, account switching between tabs, and network failure with a staging browser session.
4. **PostgreSQL remains untested for this release candidate.** SQLite isolation tests do not prove production concurrency or migration history. No notification migration is needed, but the project's broader migration chain remains incomplete.
5. **Shared notices have no per-admin lifecycle.** They remain visible and immutable until a separate retention or per-recipient-state design is approved. Existing null-recipient seed content may be demo-like; do not treat it as a real customer notification.

## Git staging instructions — future approved release work only

Coordinate with owners of the dirty worktrees and use dedicated release branches. The following commands are **instructions, not actions performed**. Run each block from its own repository after rechecking the diff and confirming that the listed files still contain only the reviewed notification changes.

### Backend repository

```bash
cd /Users/bunvathana/Documents/Code/Project/e-commerce/backend
rtk git status --short
rtk proxy git diff -- app/api/v1/routes/notifications.py app/services/notification_service.py app/schemas/notification.py tests/test_authorization.py
rtk proxy git add -- app/api/v1/routes/notifications.py app/services/notification_service.py app/schemas/notification.py tests/test_authorization.py tests/test_notification_ownership.py
rtk proxy git diff --cached --check
rtk proxy git diff --cached --name-status
rtk proxy git diff --cached
```

The staged name list must contain exactly the five backend files above. Confirm `app/main.py` and the config/CORS tests are absent. If `tests/test_authorization.py` gains unrelated edits before staging, use `rtk proxy git add -p -- tests/test_authorization.py` and accept only the notification hunk.

### Management repository

```bash
cd /Users/bunvathana/Documents/Code/Project/e-commerce/management
rtk git status --short
rtk proxy git diff -- src/app/'(admin)'/admin/notifications/page.tsx src/components/layout/Navbar.tsx src/lib/api.ts
rtk proxy git add -- src/app/'(admin)'/admin/notifications/page.tsx src/components/layout/Navbar.tsx src/lib/admin-notification-feed.ts src/lib/__tests__/admin-notifications.test.mjs
rtk proxy git add -p -- src/lib/api.ts
rtk proxy git diff --cached --check
rtk proxy git diff --cached --name-status
rtk proxy git diff --cached
```

At the `src/lib/api.ts` patch prompt, **reject** the `authApi.changePassword` hunk and **accept** the notification endpoint/type hunks. The staged name list must contain exactly the five management files above. Review the staged `api.ts` diff explicitly before any future commit. Do not commit or push from this checklist task.

## Staging and production order — after separate approval

1. Establish a disposable Blue Panda staging backend and management deployment with staging HTTPS origins, isolated PostgreSQL, test accounts, and auto-deploy disabled unless deliberately approved. Build management with the actual staging `NEXT_PUBLIC_API_URL` ending in `/api` or `/api/v1` and `NEXT_PUBLIC_STOREFRONT_URL`. Confirm backend `CORS_ORIGINS` permits the exact management origin. Do not use production credentials or data.
2. Deploy the selected backend notification commit to staging, then management. On **both** API prefixes, use customer A, customer B, seller, and two admins to verify feed contents, 401/403/404 responses, bearer handling, personal read/delete/read-all/clear-all, shared immutability, and unchanged foreign rows. Run browser QA from gate 3. Re-run backend and management checks on the exact release commits.
3. Obtain explicit approval for the staged commit IDs and production build configuration. Record the currently live Render deployment and a **secure containment plan** before touching `main`. A push to the backend repository's `main` automatically deploys `blue-panda-api-demo`; do not push until staging passes and the release window is approved.
4. Release backend first. Confirm health, both route prefixes, admin and personal feed response shapes, exact role denials, and read-only shared behavior with safe read requests. Use designated disposable production test accounts for any write checks; never run bulk deletion against real customer data.
5. Release the verified management artifact only after backend checks pass. Confirm the page, navbar, account switches, failures, and refresh behavior. Check storefront and mobile personal notification calls remain functional.

Required production environment classes: backend `DATABASE_URL`, high-entropy `JWT_SECRET_KEY`, exact HTTPS `CORS_ORIGINS`, `AUTO_INIT_DB=false`, and demo seeding disabled; management build-time `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_STOREFRONT_URL` with real HTTPS origins. `NEXT_PUBLIC_*` values are compiled into the client bundle. Review values through the approved secret process without printing them. No notification migration command belongs in this release.

## Recovery and containment

- **Never roll the backend back to the currently live pre-fix commit or deployment** after the secure release. That would restore the authorization vulnerability. If backend notification behavior is unsafe, immediately block both `/api/notifications*` and `/api/v1/notifications*` at the approved edge or ingress, verify the block, and prepare a forward hotfix that retains authenticated recipient filters and admin role checks. This temporarily disables notifications while preserving other API routes. Re-enable only after isolated tests and a staged verification of the hotfix.
- If only management fails, keep the secured backend in place and restore the prior management artifact through its verified deployment platform. Old personal-endpoint calls will then receive recipient-scoped backend responses. Recheck API denials and notification counts.
- If data integrity is suspected, stop notification writes at the edge, preserve logs and a database snapshot through the approved backup process, and investigate before any repair. Do not run ad hoc SQL cleanup or migrations as rollback.

## Post-release checks to record

- [ ] Backend deployment ID, immutable commit, health, and CORS response from the approved management origin.
- [ ] `/api` and `/api/v1` personal/admin response shapes and 401/403/404 boundaries.
- [ ] Designated test-account before/after row counts showing no cross-user mutation and no shared-row mutation.
- [ ] Management page and navbar loading, empty, shared, read/delete, failure/retry, and cross-tab switch behavior at narrow and wide widths.
- [ ] Storefront and mobile personal notification list/count/read/delete flows.
- [ ] Error-rate and notification-route logs during the release window; no unexpected customer notification changes.
- [ ] Final approved commit IDs, management artifact ID, operator, timestamp, and the containment decision recorded outside source control.
