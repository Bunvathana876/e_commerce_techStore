# Blue Panda notification security release readiness

Prepared locally on 2026-11-16. **No commit, push, migration, production data change, or deployment was performed. Production is not yet fixed.** The backend, management portal, storefront, and legacy web application were inspected as separate worktrees. Existing uncommitted changes were preserved.

## Existing implementation and root cause

The earlier uncommitted backend fix removed six admin paths that passed `user_id=None` into a service where `None` meant an unfiltered notification query: personal list, unread count, single read, read all, single delete, and clear all. That could expose or mutate another recipient's notifications, including through an admin bulk delete. The existing fix made personal endpoints use the authenticated ID, added `/notifications/admin` routes guarded by `require_roles("admin")`, and rejected a missing recipient in the service. Both `/api` and `/api/v1` register these routes.

The management API client already had uncommitted changes selecting `/notifications/admin`, but its page and navbar still used optimistic local state and silently ignored failed writes. The page could display a shared notice as personally unread, then call an admin mutation that changed the one database row for every administrator. It also persisted read/deleted/cleared notification IDs in browser storage, which could mask the server's state across sessions.

## Shared-notification lifecycle

The `notifications` model has one nullable `user_id` and one `read` flag per row. A `user_id=NULL` row has **global** read and delete state; there is no per-admin or per-recipient state table. This release treats these rows as read-only shared admin notices:

- The admin feed shows the admin's private rows plus shared rows. No customer- or seller-private row is included.
- Admin unread counts and `unread_only=true` include only the admin's private rows. The portal displays shared rows as informational and excludes them from unread badges.
- Personal and admin single/bulk mutations affect only rows whose `user_id` is the authenticated user. A shared or foreign ID returns 404 and is not changed. The portal hides mutation controls for shared notices.
- Shared rows remain until a separately designed retention or per-recipient lifecycle exists. An administrator may create a shared row through the existing authorized create route, but cannot globally mark or delete it through the notification feed.

No model column, table, index, or migration was added. The create schema description was clarified. Existing shared rows retain their stored `read` value; the portal treats that value as inapplicable to a per-admin unread badge.

## Backend files for a focused release

| File | Include | Reason |
| --- | --- | --- |
| `backend/app/api/v1/routes/notifications.py` | Whole notification diff | Personal recipient scoping and explicit admin routes; admin mutations are now personal-only. |
| `backend/app/services/notification_service.py` | Whole notification diff | Fail-closed recipient filter, shared rows in read-only lists, personal-only mutations and counts. |
| `backend/app/schemas/notification.py` | One description hunk | Clarifies that a null recipient creates a read-only shared admin notice. No wire-format change. |
| `backend/tests/test_notification_ownership.py` | New file | Customer, seller, admin, shared lifecycle, missing-recipient, and dual-prefix regression tests. |
| `backend/tests/test_authorization.py` | Notification assertion hunk only | Aligns the authorization test with separate personal and admin feeds. |

The backend's unrelated uncommitted `app/main.py`, `tests/test_config_security.py`, and `tests/test_cors_security.py` changes must be excluded from this focused release. CORS was not changed by this task; staging must verify the deployed management origin is permitted by the selected backend release.

## Management files for a focused release

| File | Include | Reason |
| --- | --- | --- |
| `management/src/lib/api.ts` | Notification endpoint and notification response-type hunks only | Uses `/notifications/admin`, types required unread counts and the delete response accurately, and preserves bearer attachment. The unrelated password-change hunk must be excluded. |
| `management/src/lib/admin-notification-feed.ts` | New file | Validates the admin recipient, handles loading/ready/error results, blocks shared/foreign mutations, rejects stale sessions, and refreshes after success. |
| `management/src/app/(admin)/admin/notifications/page.tsx` | Whole notification diff | Uses the admin feed, shows personal and shared rows correctly, limits actions to personal rows, rejects stale account responses, refreshes from the server, and shows retry/success/error states. Linked cards wait for a successful read before navigation. Live activity summaries remain visible as explicitly read-only fallback content when the saved feed fails. |
| `management/src/components/layout/Navbar.tsx` | Whole notification diff | Uses admin counts/feed, treats shared rows as informational, avoids optimistic false success, and clears or rejects stale notification state on same-tab and cross-tab account changes. |
| `management/src/lib/__tests__/admin-notifications.test.mjs` | New file | Endpoint/method/bearer, feed state, recipient mismatch, shared guard, mutation failure, refresh, and authorization regression tests. |

Exclude unrelated management changes in `src/components/layout/Sidebar.tsx`, `src/components/seller/SellerSidebar.tsx`, `src/lib/auth.ts`, `Dockerfile.prod`, and `src/lib/__tests__/server-logout.test.mjs`. The storefront and legacy `web-app` were inspected but not edited. The root report file is release documentation and is not required to run either application.

## Compatibility

- The management API base must end in `/api` or `/api/v1`; it appends `/notifications/admin`. Its `ApiNotification`, required `unread_count`, `updated_count`, `deleted_count`, and delete response without a `data` field match the backend's current response fields. The generic request wrapper attaches the management bearer token.
- The admin routes require the backend's exact `admin` role. Customer and seller tokens receive 403; missing credentials receive 401. Unknown, foreign, and shared mutation IDs receive 404. The management page treats these as errors and does not fabricate success.
- Storefront and mobile still call personal notification endpoints (`/api` and `/api/v1`, respectively). Those paths and response fields remain available and are recipient-scoped. The legacy `web-app` still has an old admin page that calls personal endpoints, but the active Compose stack uses `management/` and `storefront/`.
- No notification-specific CORS change was made. Backend `app/main.py` has a separate pre-existing CORS diff; it is outside this release scope.

## Verification results

| Check | Result |
| --- | --- |
| Backend focused: `.venv/bin/python -m pytest -q tests/test_notification_ownership.py` | 39 passed, 2 deprecation warnings. |
| Backend full: `.venv/bin/python -m pytest -q` | 741 passed, 2 skipped, 2 deprecation warnings. |
| Management: `npx tsc --noEmit` | Passed. |
| Management: `npm run lint` | Passed, 0 errors and 17 pre-existing warnings outside the touched notification files. |
| Management: `NODE_OPTIONS=--no-experimental-webstorage npm test` | 95 passed, 0 failed. |
| Management production build | Passed with non-secret `https://api.example.com/api` and `https://store.example.com` build-time placeholders. The first attempt using localhost URLs was rejected as expected by `next.config.ts` production validation. |
| `git diff --check` in backend and management | Passed. |

The local machine supplied Node 25.8.0; Node 24.x was not found. Tests used the backend's temporary SQLite fixture and temporary uploads, not production PostgreSQL. No browser session or staging deployment was run.

## Required staging validation before production

1. In separate clean release branches or worktrees for **each** Git repository, select only the backend and management files/hunks listed above. Review the staged diff, including `src/lib/api.ts`'s partial hunk, before making any future commit. Do not stage the dirty root, storefront, or legacy worktrees wholesale.
2. Deploy the backend release branch to an isolated staging Render service or equivalent, without changing backend `main`. Confirm the staging service has the intended CORS origin and uses a disposable database. No migration is needed for these notification changes.
3. Build the management release branch with the actual staging HTTPS `NEXT_PUBLIC_API_URL` (including `/api` or `/api/v1`) and `NEXT_PUBLIC_STOREFRONT_URL`, then deploy it only to staging. Do not reuse the placeholder build artifact from local verification.
4. With separate customer A, customer B, seller, and two administrator accounts, create personal and shared test notices. On both API prefixes verify 401/403/404 behavior, personal read/delete/read-all/clear-all counts, admin feed contents, and that shared and foreign rows never change. Inspect the database rows before and after bulk actions.
5. In the staging management portal, verify narrow and wide layouts, keyboard controls, loading/empty/error/retry states, read/delete success and failure, refresh after mutation, the navbar badge, account switching, and shared read-only labels. Confirm storefront and mobile personal notification flows still work.

## Production release instructions — approval required

1. Obtain explicit approval for the exact reviewed backend and management release commits. Keep them in their separate repositories. Review `rtk git status --short`, `rtk proxy git diff --check`, the staged diff, and the test results immediately before release.
2. Release the **backend first**. The backend Render service deploys from its repository's `main`; merging or pushing the approved backend commit to `main` may deploy automatically. Wait for a healthy Render deployment and record the previous deployment/commit for comparison only. Its pre-fix version is not a safe rollback target. Do not run a migration for this change.
3. Verify production API behavior using authorized, non-destructive reads first: admin and personal feeds, unread counts, 401/403/404 boundaries, and both prefixes. Use disposable designated test accounts for any mutation verification; inspect recipient-scoped counts and confirm unrelated rows remain intact. Never test bulk deletion on production customer data.
4. Only after backend verification, release the approved management artifact built with the real production HTTPS origins. Verify `/admin/notifications` and the navbar with an admin account, including shared read-only display and personal mutation success/error states. Verify storefront and mobile still use personal endpoints.
5. If backend behavior is wrong, stop the management rollout. Do not restore the current pre-fix Render deployment: it contains the notification ownership vulnerability. Contain the affected notification routes at the edge while preparing a forward hotfix that retains recipient scoping. If management behavior is wrong after its rollout, restore its prior artifact while keeping the secured backend deployed. Recheck feeds and counts after containment or rollback; never force-push or reset `main`.

## Known limitations and remaining risks

- Shared notices cannot be individually dismissed or deleted per administrator without a reviewed schema and migration. They may accumulate; a future retention policy needs a separate design and approval.
- Existing null-recipient seed notices may contain mixed demo or operational content. They are visible in the admin feed but remain immutable through notification actions.
- The backend's SQLite tests do not prove PostgreSQL migration compatibility or concurrency. Staging against PostgreSQL remains required.
- The management page's live activity summaries depend on other admin APIs and appear only when the saved notification feed fails; they are labeled read-only. Browser storage still holds display preferences, but no longer overrides persisted read/delete state.
- The legacy `web-app` admin page still calls personal endpoints. It is not in the active Compose stack; if deployed independently, it requires its own integration before use as an admin notification manager.
- The production build succeeded with placeholder public URLs and Node 25.8.0. Rebuild with the actual approved production URLs and declared Node 24.x runtime during release preparation.
- The accessible Render workspace has no Blue Panda staging service; staging validation is outstanding. The current production backend service auto-deploys from `main` and still runs the pre-fix committed HEAD.
- The untracked `management/Dockerfile.prod` uses Node 20 in all stages while `management/package.json` declares Node 24.x. If that Dockerfile is the chosen management release path, resolve and validate the runtime mismatch before release.
