# Blue Panda Production Deployment Skeleton

This directory is a **configuration skeleton, not a launch-ready deployment**. It must not be started until production images are built and tested, all placeholders are replaced through an approved secret process, DNS is intentionally configured, backups are verified, and an operator authorizes launch.

It does not modify or replace the root development `docker-compose.yml`.

## Architecture

- Caddy is the only service publishing host ports: TCP 80, TCP 443, and UDP 443 for HTTP/3.
- Storefront, management, and backend are reachable only by service name on the `proxy` network.
- PostgreSQL is reachable only by the backend on the Docker-internal `data` network and has no published port.
- pgAdmin is intentionally absent. Production database administration should use an approved SSH tunnel or direct CLI procedure, not a public web service.
- PostgreSQL, uploaded product images, and Caddy state use explicitly named volumes.
- No source-code directories are mounted. The only bind mount is the read-only Caddy configuration template.

## Safety properties

- The backend Compose command explicitly bypasses the current development image entrypoint. It starts Uvicorn without reload and cannot automatically run Alembic, `create_all`, or demo seeding.
- `AUTO_INIT_DB=false` and `SEED_DEMO_DATA=false` are forced in Compose.
- There is no migration or backup container in this phase. Migrations require a verified backup and explicit approval through a future operator-only procedure.
- Application containers are read-only apart from `/tmp` and the backend uploads volume.
- Application services use `expose`, not `ports`; only Caddy publishes ports.

## Environment variable classes

### Required secrets

- `POSTGRES_PASSWORD`
- `DATABASE_URL` (must use the same database credentials; URL-encode special characters)
- `JWT_SECRET_KEY` (unique high-entropy value of at least 32 characters)
- Future backup credentials/encryption material; do not put key contents in `.env`

Store these outside Git with permissions restricted to the deployment account. The example values are intentionally unusable placeholders.

### Build-time public variables

- Storefront: `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_MANAGEMENT_URL`
- Management: `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_STOREFRONT_URL`

`NEXT_PUBLIC_*` values are public and compiled into Next.js client bundles. CI must supply the intended HTTPS values during `next build`, tag the resulting images immutably, and record the build configuration. Setting these variables only when the container starts does not reliably change client-side code.

### Runtime configuration

- Approved immutable image references
- `SHOP_DOMAIN`, `MANAGE_DOMAIN`, `API_DOMAIN`, and `ACME_EMAIL`
- PostgreSQL database/user names
- JWT algorithm/expiry, explicit CORS origins, worker count, and trusted proxy range
- Upload and request-size limits

### Optional/future configuration

- Backup destination, retention, schedule, and host-side key-file path
- Monitoring, logging, and alert routing values in a later approved phase

## Placeholder-only validation

The safe validation command does not start or pull images:

```bash
rtk docker compose \
  --env-file deploy/production/.env.example \
  -f deploy/production/compose.yaml \
  config --quiet
```

Review the rendered configuration only in a controlled environment because it expands secret variables. Do not paste rendered production configuration into logs or tickets.

## Pre-launch blockers

1. Build non-root, multi-stage production images and replace the example image references with immutable tags or digests.
2. Confirm frontend images were built with the correct public HTTPS URLs.
3. Replace every placeholder using the approved secret process; never use `.env.example` as production credentials.
4. Validate Caddy against real, intentionally configured domains. Do not use insecure TLS or fake certificates.
5. Add and test readiness, rate limiting, trusted-host/proxy behavior, structured logging, and monitoring.
6. Create encrypted backups and complete a restore drill.
7. Approve and test a separate migration procedure. Never attach migrations to application startup.
8. Confirm only Cash on Delivery is presented until real electronic payments are implemented and approved.

## Operations explicitly excluded

This phase does not start containers, pull images, create databases/volumes, request certificates, change DNS, run migrations, seed data, configure backups, or deploy to a VPS.
