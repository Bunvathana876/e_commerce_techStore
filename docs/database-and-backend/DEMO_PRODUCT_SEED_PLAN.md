# Blue Panda demo catalog insertion plan

Prepared 2026-11-06. Status: **read-only validation complete; awaiting explicit user approval for database-owner maintenance**.

## Verified target and current data

- The explicit `.env.supabase` target is the Supabase session pooler, host `aws-0-ap-southeast-2.pooler.supabase.com`, database `postgres`, schema `public`.
- The normal `.env` points to local `ecommerce_db`. The seed tool ignores that file and the process `DATABASE_URL` when selecting its target.
- A read-only connection confirmed PostgreSQL identity, encrypted client-to-pooler transport, and migration revision `a1b2c3d4e5f6`. No migrations were run.
- Supabase currently contains **0 categories, 0 products, 0 sellers, and 0 users**.
- Both public `GET /api/products?limit=100` and `GET /api/categories` returned HTTP 200 with empty data from `https://blue-panda-api-demo.onrender.com`.
- Matching empty responses are consistent with this target, but public responses alone do not conclusively identify Render's private database connection. The public API check after approved insertion will verify that the live API exposes the inserted catalog.
- The existing authenticated database role owns both catalog tables and has catalog SELECT/INSERT and sequence USAGE privileges. Catalog RLS is disabled. There are no custom catalog triggers. The proposed method is an explicitly approved operation by that database owner; it does not impersonate an application admin or invoke protected application endpoints without authentication.

## Models, constraints, and visibility

`products` requires `category_id`, `name` (up to 200 characters), `price` (`NUMERIC(10,2)`), `stock`, `rating` (`NUMERIC(3,2)`), `is_active`, and timestamps. IDs and timestamps have database defaults. `seller_id`, description, discount price, and image URL are nullable. Foreign keys reference `categories.id` and `sellers.id`; stock must be nonnegative. Product names have no database uniqueness constraint.

`categories` requires a unique name (up to 100 characters), `is_active`, and timestamps. Description and image are optional. The proposed categories are all active.

There is no separate product visibility column. The public product service exposes active products to guests. Positive stock makes the proposed listings available for the storefront's stock checks.

The product API requires an authenticated admin or an authorized seller; category creation requires an admin. Admin-created products may have `seller_id=NULL`. Sellers require a real name, owner name, email, status, counters, rating, and timestamps; creating a fabricated seller is unnecessary and prohibited by this plan.

The admin API is unavailable for this task because the database has no application users. The existing `ProductService.create_category` commits each category; `create_product` commits each product and separately updates a seller counter when assigned. The maintenance script therefore reuses the existing `CategoryCreate` and `ProductCreate` schemas, then uses parameterized SQLAlchemy Core inserts inside one encompassing transaction. It authenticates with the existing configured Supabase database connection and verifies ownership and insert privileges. It requires explicit approval for this database-maintenance method. It does not create tokens, assume an application identity, or change permissions. No seller or application account is required by the database schema for these sellerless listings.

## Exact proposed rows

Insert these **7 rows into `public.categories`** if they are still absent: Accessories, Audio, Gaming, Laptops, Monitors, Smartphones, Tablets. Each new description starts with `[Blue Panda demonstration content v1]`, `is_active=true`, and `image=NULL`.

Insert these **8 rows into `public.products`** if they are still absent:

| Product | Demo price (USD) | Category | Demo stock |
| --- | ---: | --- | ---: |
| MacBook Air M3 | 999.00 | Laptops | 12 |
| Sony WH-1000XM5 | 299.00 | Audio | 20 |
| Logitech MX Master 3S | 99.00 | Accessories | 30 |
| Samsung Galaxy S24 | 699.00 | Smartphones | 15 |
| iPad Air | 599.00 | Tablets | 18 |
| Keychron K2 Mechanical Keyboard | 89.00 | Accessories | 25 |
| Dell UltraSharp 27-inch Monitor | 399.00 | Monitors | 10 |
| HyperX Cloud III Headset | 99.00 | Gaming | 22 |

Every product uses:

- The category ID generated for or reused from its category row.
- A clear, product-specific description beginning with `[Blue Panda demonstration content v1]`, explicitly identifying the price and inventory as sample data for storefront testing.
- `seller_id=NULL`, `discount_price=NULL`, `image_url=NULL`, `rating=0.00`, and `is_active=true`.
- Database-generated IDs and timestamps; exact IDs will be known after insertion.

Only category and product rows will be inserted. Their ID sequences advance on insertion; PostgreSQL sequence allocations may leave gaps after a rollback. No existing record will be updated or deleted. No users, sellers, orders, payments, reviews, coupons, or other records will be inserted. No schema, hosting configuration, or automatic startup seed changes are included.

The storefront already resolves empty images to its current fallback images, which may be generic or unrelated to these products. This plan adds no image URLs and makes no claim that the fallback depicts the exact product.

## Idempotency and transaction safeguards

The script checks trimmed, case-insensitive names across existing products and categories. It reuses an active matching category, skips a product only when all proposed values already match, and stops on conflicting listings, duplicate names, or inactive categories. It never rewrites an existing listing to fit the demo.

Insertion acquires short-lived catalog write locks, rechecks the exact reviewed plan, and uses one transaction for all category and product inserts. The locks also exclude ordinary concurrent API writes while the duplicate checks and inserts run. This protects seed retries and concurrent seed execution without changing the schema; it cannot prevent unrelated writers from adding duplicate names later because the application has no unique product-name constraint. Failure rolls back the pending inserts. Lock and statement timeouts limit waiting.

The tool is not imported by app startup. It never imports `app.main`, runs Alembic, invokes the old seed (which creates fabricated accounts), or changes environment files. SQLAlchemy logging is disabled and error details are withheld to protect credentials. No application tokens are used. Connection credentials are read only from the explicit Supabase environment file and are never printed or copied into this document.

## Commands and approval sequence

Read-only preview, from `backend/`:

```bash
rtk proxy .venv/bin/python -m scripts.seed_demo_products
```

The full preview prints proposed descriptions, fields, counts, database ownership/privilege checks, and a SHA-256 digest. This command was run successfully against Supabase and inserted no rows.

Current reviewed plan SHA-256: `1e9d2689cc1e1dbd4b8d67723d3922ccbec65fe9a62a83762b03462b987c08b3`. This identifies the prepared plan; it is not user approval.

Before any insertion:

1. Review the read-only report, including the verified Supabase target, counts, ownership checks, and digest.
2. Obtain the user's explicit final confirmation for **7 category inserts and 8 product inserts through the existing Supabase database-owner connection**, with no new accounts and no updates to existing rows.
3. If the data, target, or code changes before execution, prepare and review a fresh plan and obtain approval again.
4. Only after confirmation, run the following with the reviewed digest:

```bash
rtk proxy .venv/bin/python -m scripts.seed_demo_products --apply --approved-plan <reviewed-plan-sha256>
```

The tool requires an interactive terminal and the confirmation phrase `INSERT BLUE PANDA DEMO`. It rechecks database ownership and privileges before insertion. Never paste connection credentials into chat, command arguments, or this document. No insertion has been approved or attempted.

After an approved commit, the script checks every listing through public `/api/products` searches, including exact product data, price, stock, rating, active status, category links, and duplicate results. A public verification failure is reported separately from a committed transaction and never triggers automatic deletion.

Then open the user's actual Vercel storefront, refresh, verify all eight product cards and category filters, and open a product detail page. The storefront's live URL still needs to be identified for that final UI check. No storefront deployment or code changes are part of this seed.

## Verification performed

`rtk proxy .venv/bin/python -m pytest tests/test_demo_product_seed.py -q`: **11 passed** in the temporary SQLite database established by `tests/conftest.py`. Coverage includes dry-run behavior, repeated insertion, correct category links, preservation of existing records and identities, conflicting product names, duplicate/inactive categories, transaction rollback, database ownership authorization denial, empty application-admin setup, local-target rejection, and SSL enforcement.

Read-only Supabase inspection confirmed live columns, nullability, database defaults, foreign keys, category uniqueness, stock constraint, migration revision, ownership, permissions, absence of custom catalog triggers, and row counts. PostgreSQL write locks and actual inserts have not been exercised against Supabase because the user has not approved insertion. API and storefront verification after insertion remain pending.
