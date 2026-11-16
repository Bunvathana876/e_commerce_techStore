# Blue Panda Repository Instructions

Read `PROJECT_CONTEXT.md` first for the verified project audit. Treat it as orientation, then inspect the current files relevant to the task because the code may have changed.

Follow `/Users/bunvathana/.codex/RTK.md`: prefix shell commands with `rtk`.

## Project Purpose and Stack

Blue Panda is a development-stage, multi-client e-commerce marketplace:

- `backend/`: Python 3.12, FastAPI, synchronous SQLAlchemy 2, Pydantic 2, Alembic, PostgreSQL, bcrypt, and JWT bearer auth.
- `web-app/`: Next.js 16 App Router, React 19, strict TypeScript, Tailwind CSS 4, Zustand, and Plus Jakarta Sans.
- `mobile-app/`: Flutter/Dart, Material 3, Provider/ChangeNotifier, `http`, SharedPreferences, and Plus Jakarta Sans.
- Root infrastructure: Docker Compose runs PostgreSQL 16, pgAdmin, the backend, and the web app.

This is not yet production-ready. Do not describe simulated payments, social login, showcase data, local orders, role UI, or status timelines as production integrations.

## Architecture and Folder Conventions

### Backend

- Entry point: `backend/app/main.py`.
- HTTP routes: `backend/app/api/v1/routes/`.
- Business logic: `backend/app/services/`.
- Persistence: `backend/app/models/` and `backend/app/db/`.
- Request/response contracts: `backend/app/schemas/`.
- Migrations: `backend/alembic/versions/`.
- Tests: `backend/tests/`.
- Keep the route -> service -> model/schema separation. Do not place substantial new business logic in route handlers.
- API responses normally use `{ "success", "message", "data" }`; preserve this contract unless a coordinated API migration is requested.
- Routes are currently exposed under both `/api` and `/api/v1`. Web defaults to `/api`; mobile endpoints use `/api/v1`. Account for both clients when changing an endpoint.
- Authorization must be enforced on the backend. Client-side role checks are never sufficient.

### Web

- Root shell and global design: `web-app/src/app/layout.tsx` and `web-app/src/app/globals.css`.
- Storefront routes: `web-app/src/app/(store)/`.
- Authentication routes: `web-app/src/app/(auth)/`.
- Admin/POS routes: `web-app/src/app/(admin)/admin/`.
- Reusable UI: `web-app/src/components/store/` and `web-app/src/components/layout/`.
- API types/client: `web-app/src/lib/api.ts`.
- Store state: `web-app/src/lib/store.ts`; auth helpers: `web-app/src/lib/auth.ts`.
- Store fixtures/fallbacks: `web-app/src/lib/store-catalog.ts`.
- Prefer server components unless browser APIs, events, hooks, or persisted client state require `"use client"`.
- The nested `web-app/AGENTS.md` is mandatory and more specific: read the relevant installed Next.js documentation in `web-app/node_modules/next/dist/docs/` before modifying Next.js code.

### Mobile

- Entry/provider registration: `mobile-app/lib/main.dart`.
- App and named routes: `mobile-app/lib/app/`.
- Shared networking, endpoints, themes, and utilities: `mobile-app/lib/core/`.
- Feature code: `mobile-app/lib/features/<feature>/{models,providers,screens,services,widgets}/`.
- Cross-feature widgets: `mobile-app/lib/shared/widgets/`.
- Tests mirror features under `mobile-app/test/`.
- Keep screens focused on presentation, providers on reactive state, services on I/O, and models on serialization/domain data.
- Add a new top-level provider only when state is genuinely app-wide.

## Coding Style and Naming

- Follow the style already used in the edited file; do not reformat unrelated code.
- Python: 4-space indentation, `snake_case` modules/functions/variables, `PascalCase` classes/schemas, type hints, and small service methods. Use SQLAlchemy 2-style queries and Pydantic models already present.
- TypeScript/React: strict types, 2-space indentation, double quotes, semicolons, `PascalCase` components/types, `camelCase` functions/state, and the `@/` import alias. Avoid new `any` when a useful type can be expressed.
- Dart/Flutter: standard `dart format`, 2-space indentation, `snake_case.dart` filenames, `PascalCase` types/widgets, `lowerCamelCase` members, `const` where practical, and immutable widget inputs.
- Prefer existing shared components, models, API helpers, providers, tokens, and utilities before creating duplicates.
- Keep comments focused on non-obvious intent or constraints; do not narrate straightforward code.
- When a file is already very large, prefer extracting a focused component/service instead of extending a monolith, provided the extraction remains a small behavior-preserving change.

## Existing Development Patterns

- Backend uses synchronous FastAPI handlers and SQLAlchemy sessions from `get_db`.
- Web authentication and commerce state are currently persisted in browser storage; Zustand performs optimistic cart/wishlist synchronization.
- Mobile uses a singleton `ApiClient`, Provider/ChangeNotifier, typed API exceptions, and SharedPreferences persistence.
- Storefront showcase data and some mobile mock/demo paths exist. Do not expand silent fake-data behavior. Test fixtures should remain test-only or be enabled by an explicit, visibly labeled demo mode.
- Checkout totals, stock, authorization, payment status, and ownership decisions must be validated server-side, not trusted from a client.
- Uploaded media is currently served by FastAPI from `backend/uploads/`; avoid committing generated uploads.
- Database schema handling currently mixes Alembic, `create_all`, and compatibility ALTER statements. Do not add more ad hoc schema mutation; schema changes require a reviewed Alembic migration plan.
- Preserve loading, empty, error, offline, success, and disabled states when changing user-facing flows.

## UI/UX Principles

- Keep Blue Panda modern, clean, professional, and easy to understand.
- Use the existing blue/slate identity, Plus Jakarta Sans, Material 3 on mobile, restrained shadows, rounded surfaces, and clear hierarchy.
- Prefer semantic design tokens and shared theme values over new hardcoded colors.
- Use concise, truthful copy. Never present demos, local-only actions, simulated payments, or unsupported guarantees as real services.
- Prioritize product information, price, stock, delivery details, and the next action over decoration.
- Avoid excessive gradients, badges, glass effects, animations, and dense text.
- Support phone and desktop breakpoints where applicable; consider tablet/large mobile layouts for Flutter changes.
- Maintain accessible contrast, keyboard/focus behavior, semantic labels, form label associations, touch targets, scalable text, and reduced-motion behavior.
- Every data view should handle loading, empty, failure, retry, and success states intentionally.
- Check both light and dark themes for mobile changes. Admin web is mainly light today; do not introduce isolated dark styling.

## Important Commands

Run commands from the indicated directory. Do not install or upgrade dependencies unless the task requires it and the user approves the dependency change.

### Full development stack

```bash
rtk ./run.sh
rtk docker compose up --build -d
rtk docker compose ps
```

Services normally use web `:3000`, backend `:8000`, pgAdmin `:5050`, and PostgreSQL host port `:5433`.

### Backend

```bash
cd backend
rtk uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
rtk pytest
```

`backend/tests/conftest.py` now sets a temporary SQLite database, upload directory, generated test JWT secret, and `AUTO_INIT_DB=false` before importing the application. Run backend tests through pytest so this isolation is applied; never import the test module directly against normal settings. SQLite authorization tests do not verify PostgreSQL migrations or concurrency. Preserve the isolation checks before adding database-writing tests.

### Web

```bash
cd web-app
rtk npm run dev
rtk npm run lint
rtk npm run build
```

There is currently no web test script.

### Mobile

```bash
cd mobile-app
rtk flutter analyze
rtk flutter test
rtk flutter run
```

For an explicit API host, use `rtk flutter run --dart-define=API_URL=http://localhost:8000`. Existing endpoint constants already include `/api/v1`; do not append `/api` to this mobile base URL.

## Rules for Safe Changes

1. Read `PROJECT_CONTEXT.md`, then inspect the relevant current implementation, callers, models/types, tests, and nearby patterns before editing.
2. Preserve the route/service/model, App Router/component/state, and Flutter feature/provider/service architectures.
3. Make the smallest focused change that solves the request. Do not opportunistically refactor unrelated files.
4. Preserve existing working behavior and compatibility across backend, web, and mobile when a shared contract changes.
5. Do not add packages when existing code or platform APIs can solve the problem. Ask before introducing a dependency, major abstraction, or new infrastructure service.
6. Ask before major architecture changes, database schema changes, data migrations, broad API breaking changes, destructive operations, or removal of user data/features.
7. Never expose, copy, log, or commit secrets or real `.env` values. Use placeholders in documentation and examples.
8. Do not overwrite or discard unrelated work. The repository may already be dirty; inspect `git status` and preserve user changes.
9. Do not run destructive Git/database/filesystem commands without explicit approval. Avoid deleting uploads, volumes, caches, records, or migrations as cleanup.
10. Do not modify generated/vendor output such as `node_modules`, `.next`, Flutter build output, or `.dart_tool` unless a tool normally regenerates it as part of an approved task.
11. Treat authentication, authorization, ownership, totals, stock, uploads, and payment/order status as security-sensitive. Add denial and failure-path coverage when changing them.
12. Keep application behavior truthful: a network failure must not silently become a successful real order, payment, review, or authentication event.

## Verification and Handoff

Use verification proportional to the change:

- Inspect `rtk git diff --check`, `rtk git diff`, and `rtk git status --short`; confirm only intended files changed.
- Backend: run focused tests in an isolated environment, then broader tests if safe. Verify response shape, status codes, authentication, role/ownership denial, validation, and transaction rollback paths.
- Web: run `rtk npm run lint` and `rtk npm run build`. Manually check affected routes at narrow and wide widths, keyboard navigation, loading/empty/error states, and API failure behavior.
- Mobile: run `rtk flutter analyze` and focused/full `rtk flutter test`. Manually check light/dark themes, small screens, keyboard insets, back navigation, loading/empty/error states, and screen-reader semantics where relevant.
- Shared API changes: verify both `web-app/src/lib/api.ts` and mobile services/models against backend schemas and test `/api` plus `/api/v1` compatibility where still required.
- Documentation-only changes: verify headings, commands, paths, links, and that no secret values were copied.

In the final handoff:

- State the outcome first.
- List every changed file and why it changed.
- Report checks run and their results; clearly state checks not run and why.
- Give exact user testing steps for each behavior changed.
- Mention remaining risks, assumptions, or follow-up work without implementing unrequested improvements.
