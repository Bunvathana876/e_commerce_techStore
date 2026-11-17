# Blue Panda E-Commerce

Blue Panda is a multi-client marketplace with a FastAPI backend, separate Next.js
customer and management websites, and a Flutter customer app. Deployment readiness
is still being verified; passing local tests alone is not production sign-off.

## Applications

| Directory | Purpose | Local endpoint |
| --- | --- | --- |
| `backend/` | FastAPI, synchronous SQLAlchemy, Alembic, PostgreSQL | `http://localhost:8000` |
| `storefront/` | Next.js customer shopping website | `http://localhost:3000` |
| `management/` | Next.js administrator and seller portal | `http://localhost:3001` |
| `mobile-app/` | Flutter customer application | Platform-dependent |
| `web-app/` | Legacy combined Next.js application | Separate local run only |
| `deploy/production/` | Production Docker Compose configuration | Configured HTTPS domains |

The backend exposes compatible API prefixes at `/api` and `/api/v1`. Browser
clients use an API URL ending in `/api`. Mobile uses a host-only API URL because
its endpoint paths already contain `/api/v1`.

## Implemented scope and limitations

Core flows include email/password authentication, catalog browsing, customer carts,
favorites, addresses, server-validated coupons, orders, reviews, in-app
notifications, catalog administration, seller access, and POS. Backend
role/ownership checks enforce access independently of the interface.

Cash on Delivery is the supported customer checkout path. Card, KHQR, Apple Pay,
and other electronic payment interfaces are not integrated payment gateways.
Demo interfaces must not be interpreted as payment confirmation. Order status
screens do not provide carrier tracking, and in-app notifications are not mobile
push delivery. Social login and password-reset email require real provider
integrations before they can be offered as supported services.

Some administrative screens remain derived views or local UI. See the audit and
release documents below for their limitations; the presence of a screen does not
prove a complete payment, refund, supplier, or settings workflow.

## Source checkout

The root repository pins five independent repositories using Git submodules:

```bash
rtk git clone --recurse-submodules https://github.com/Bunvathana876/Full_mobile_web_App_backend_e_commerce.git
```

For a fresh checkout that omitted submodules, initialize them with
`rtk git submodule update --init --recursive`. Do not run an update over local
uncommitted work. Each application's changes must be committed in its own
repository and made available remotely before the root can pin that release.
Uncommitted nested edits are not included in a clone of the root repository.

## Local development

Use Docker Compose, or installed Python/Node/Flutter toolchains matching the
application manifests. The active Next.js applications declare Node 24.x.

Configure local settings using [`.env.example`](.env.example). Keep real `.env`
files, signing keys, database URLs, and JWT secrets out of source control. Use
unique credentials; there is no production default login.

The root Compose file is for development. By default it expects a database
configured through `DATABASE_URL`; the bundled PostgreSQL service is enabled only
with the `container-db` profile. For that profile, configure the backend database
host as `postgres:5432` and keep its credentials consistent with the database
service settings. Its host port is configurable through `POSTGRES_HOST_PORT`.

Schema initialization and demo seeding are disabled by default. Review the
migration plan before applying Alembic to an existing database. Do not point local
tests or development setup at production.

Once the database and configuration are ready:

```bash
rtk docker compose up --build -d
rtk docker compose ps
```

For the optional bundled database:

```bash
rtk docker compose --profile container-db up --build -d
```

The development pgAdmin interface uses port 5050. Obtain its login from your local
configuration. Do not expose this development stack as a production deployment.

To run a website directly, run `rtk npm run dev` from `storefront/` or
`management/` with its dependencies already installed and its public API URL set.

From `mobile-app/`:

```bash
rtk flutter run --dart-define=API_URL=http://localhost:8000
```

The standard Android emulator can use `http://10.0.2.2:8000`; a physical device
needs a reachable host. Release builds require the intended HTTPS API origin.
Do not append `/api` to the mobile `API_URL`.

## Verification

Run each command from its application's directory:

| Application | Checks |
| --- | --- |
| Backend | `rtk pytest -q` (or `rtk proxy .venv/bin/python -m pytest -q`) |
| Storefront | `rtk npm test`, `rtk npm run lint`, `rtk npm run build` |
| Management | `rtk npm test`, `rtk npm run lint`, `rtk npm run build` |
| Legacy web | `rtk npm test`, `rtk npm run lint`, `rtk npm run build` |
| Mobile | `rtk flutter analyze`, `rtk flutter test` |

Backend pytest configures a temporary SQLite database, upload directory, and test
secret before application imports. PostgreSQL migration and concurrency tests
use disposable socket-only clusters when `initdb` and `pg_ctl` are installed.
SQLite-only results cannot establish PostgreSQL concurrency or migration safety.
Optional Redis tests may be skipped when their test service is unavailable.

From the root, validate production Compose syntax without launching services or
printing expanded secrets:

```bash
rtk docker compose --env-file deploy/production/.env.example -f deploy/production/compose.yaml config --quiet
```

## Deployment

Use the production Dockerfiles and [production configuration](deploy/production/),
not development hot-reload images. Frontend `NEXT_PUBLIC_*` URLs are compiled at
build time and must point to the intended HTTPS services when building the images.

Before release, verify the actual target environment, schema revision, reviewed
migration plan, secrets, domains/TLS, uploads persistence, backups and restore,
and staging customer/admin/seller flows. Backend liveness and readiness endpoints
are `/health` and `/readyz`. Mobile distribution additionally needs final app
identifiers and signing/provisioning credentials.

The working tree includes an idempotency-table migration; it must be reviewed and
validated against the target database before deploying checkout code that uses
it. Application startup must not be used to apply production migrations.

No production deployment or migration is implied by these setup commands.

## Documentation

- [Deployment fix progress and current test evidence](docs/deployment/DEPLOYMENT_FIX_PROGRESS_2026-11-17.md)
- [Documentation index](docs/README.md)
- [Original project context](PROJECT_CONTEXT.md) — historical orientation;
  inspect current implementation before relying on its findings.
- [Staging and release gate](BLUE_PANDA_STAGING_AND_RELEASE_GATE.md) — earlier
  audit; its counts and release state are not current verification evidence.
- [VPS deployment runbook](docs/deployment/VPS_DEPLOYMENT_RUNBOOK.md)
- [Production deployment configuration](deploy/production/README.md)
- [Database operations scripts](deploy/scripts/README.md)
- [Administrator bootstrap plan](docs/database-and-backend/ADMIN_BOOTSTRAP_PLAN.md)
