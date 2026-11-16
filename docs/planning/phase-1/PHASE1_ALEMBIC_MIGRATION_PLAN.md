# Blue Panda — Phase 1, Task 5 (Part 3A): Alembic Migration & Baseline Plan (S18)

Last Updated: 2026-10-31  
Target: Alembic Migration Consolidation & Baseline Plan for PostgreSQL  
Finding Reference: S18 (Alembic migration drift, missing tables, and ad-hoc startup schema mutations)

---

## 1. Current Migration Revision History

Inspection of the `backend/alembic/` directory confirms that Alembic contains **exactly one** migration revision:

- **Revision ID:** `f904b613102f`
- **Filename:** `backend/alembic/versions/f904b613102f_create_initial_ecommerce_tables.py`
- **Revises:** `None` (Base initial revision)
- **Current Head:** `f904b613102f`
- **Branch Labels:** `None`
- **Depends On:** `None`

### Tables Created by Revision `f904b613102f`:
The initial revision only creates **8 tables**:
1. `users` (id, name, email, password_hash, phone, avatar, role, is_active, created_at, updated_at)
2. `categories` (id, name, description, image, is_active, created_at, updated_at)
3. `products` (id, category_id, name, description, price, discount_price, stock, image_url, rating, is_active, created_at, updated_at)
4. `addresses` (id, user_id, full_name, phone, address_line, city, province, postal_code, is_default, created_at, updated_at)
5. `orders` (id, user_id, status, subtotal, shipping_fee, total, payment_method, payment_status, shipping_address, created_at, updated_at)
6. `cart_items` (id, user_id, product_id, quantity, created_at, updated_at)
7. `favorites` (id, user_id, product_id, created_at)
8. `order_items` (id, order_id, product_id, product_name, price, quantity, subtotal, created_at)

---

## 2. Current SQLAlchemy Model Inventory

All models in the application are defined under `backend/app/models/` and registered with `Base` in `backend/app/models/__init__.py`:

| # | Model Class | Table Name | Defined In | Foreign Key Dependencies |
|---|-------------|------------|------------|--------------------------|
| 1 | `User` | `users` | `backend/app/models/user.py` | None |
| 2 | `Category` | `categories` | `backend/app/models/category.py` | None |
| 3 | `Product` | `products` | `backend/app/models/product.py` | `categories.id`, `sellers.id` |
| 4 | `Address` | `addresses` | `backend/app/models/address.py` | `users.id` |
| 5 | `Order` | `orders` | `backend/app/models/order.py` | `users.id` |
| 6 | `OrderItem` | `order_items` | `backend/app/models/order.py` | `orders.id`, `products.id` |
| 7 | `CartItem` | `cart_items` | `backend/app/models/cart.py` | `users.id`, `products.id` |
| 8 | `Favorite` | `favorites` | `backend/app/models/favorite.py` | `users.id`, `products.id` |
| 9 | `Seller` | `sellers` | `backend/app/models/seller.py` | `users.id` |
| 10 | `Coupon` | `coupons` | `backend/app/models/coupon.py` | None |
| 11 | `Notification` | `notifications` | `backend/app/models/notification.py` | `users.id` |
| 12 | `Review` | `reviews` | `backend/app/models/review.py` | `products.id`, `users.id`, `orders.id` |

*Note on POS models:* There are no separate POS database tables. The POS module (`PosService` and `/api/v1/pos`) records transactions directly as standard `orders` and `order_items` rows with `user_id` set to the cashier/admin user.

---

## 3. Confirmed Schema Differences (Drift)

A line-by-line comparison between `f904b613102f` and the current SQLAlchemy models confirms the following discrepancies:

### A. 4 Entirely Missing Tables
1. **`sellers`**: Defined in `app.models.seller.Seller`, completely absent from Alembic revisions.
2. **`coupons`**: Defined in `app.models.coupon.Coupon` (including `usage_limit` and `used_count` from S11), completely absent from Alembic revisions.
3. **`notifications`**: Defined in `app.models.notification.Notification`, completely absent from Alembic revisions.
4. **`reviews`**: Defined in `app.models.review.Review`, completely absent from Alembic revisions.

### B. Missing Columns on Existing Tables
1. **`products.seller_id`**:
   - Model has `seller_id: Mapped[int | None] = mapped_column(ForeignKey("sellers.id", ondelete="SET NULL"), nullable=True, index=True)`.
   - Migration `f904b613102f` has no `seller_id` column.
2. **`orders.discount_amount`**:
   - Model has `discount_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))`.
   - Migration `f904b613102f` has no `discount_amount` column.
3. **`orders.coupon_code`**:
   - Model has `coupon_code: Mapped[str | None] = mapped_column(String(50), nullable=True)`.
   - Migration `f904b613102f` has no `coupon_code` column.

### C. Constraint and Index Discrepancies
1. **`categories.name`**:
   - Model specifies `name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)`.
   - Initial migration `f904b613102f` created non-unique index `op.create_index(op.f('ix_categories_name'), 'categories', ['name'], unique=False)`.
2. **Missing Check Constraints**:
   - Neither the migration nor the models enforce `products.stock >= 0`.
   - Neither enforces `coupons.used_count >= 0`.
   - Neither enforces `reviews.rating >= 1 AND reviews.rating <= 5`.

### D. Ad-Hoc Runtime Workarounds Currently in Code
To compensate for these migration omissions, the project currently relies on runtime band-aids:
1. `backend/app/main.py` lines 27-29:
   ```python
   if settings.AUTO_INIT_DB:
       Base.metadata.create_all(bind=engine)
   ```
2. `backend/app/db/init_db.py` lines 7-22:
   ```python
   Base.metadata.create_all(bind=engine)
   with engine.begin() as conn:
       try:
           conn.execute(text("ALTER TABLE orders ADD COLUMN discount_amount NUMERIC(10, 2) NOT NULL DEFAULT 0.00"))
       except Exception: pass
       try:
           conn.execute(text("ALTER TABLE orders ADD COLUMN coupon_code VARCHAR(50) NULL"))
       except Exception: pass
   ```
3. `backend/docker-entrypoint.sh` lines 10-18:
   Swallows Alembic errors with `alembic upgrade head || { echo "Warning..."; }` and then calls `python -m app.db.init_db`.

---

## 4. Proposed Migration Revision Sequence

We will establish a clean, linear, two-revision Alembic sequence:

```
[f904b613102f] (Initial 8 Tables)
      │
      ▼
[a1b2c3d4e5f6] (Consolidate Missing Models, Columns, Constraints & Indexes)  <-- HEAD
```

### Proposed New Migration:
`backend/alembic/versions/<timestamp_hash>_consolidate_ecommerce_schema.py`
- **Revises:** `f904b613102f`
- **Down Revision:** `f904b613102f`
- **Execution Order in `upgrade()`**:
  1. Create `sellers` table (depends only on `users.id`).
  2. Add `seller_id` column and foreign key index to `products` table.
  3. Add `discount_amount` (with server default `0.00`) and `coupon_code` (nullable) to `orders` table.
  4. Create `coupons` table with `code` unique index, `usage_limit`, and `used_count`.
  5. Create `notifications` table with `user_id` foreign key.
  6. Create `reviews` table with `product_id`, `user_id`, and `order_id` foreign keys.
  7. Add unique constraint / index on `categories.name`.
  8. Add safe check constraints: `products.stock >= 0`, `coupons.used_count >= 0`, and `reviews.rating BETWEEN 1 AND 5`.

---

## 5. Data-Preserving Upgrade Strategy

To avoid destroying records or failing when upgrading existing databases (where tables or columns were already partially generated by `Base.metadata.create_all()`), the upgrade script will be **idempotent and introspective**:

```python
def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    # 1. Sellers
    if "sellers" not in existing_tables:
        op.create_table("sellers", ...)
    
    # 2. Products -> seller_id
    product_cols = {c["name"] for c in inspector.get_columns("products")}
    if "seller_id" not in product_cols:
        op.add_column("products", sa.Column("seller_id", sa.Integer(), nullable=True))
        op.create_foreign_key("fk_products_seller_id", "products", "sellers", ["seller_id"], ["id"], ondelete="SET NULL")
        op.create_index("ix_products_seller_id", "products", ["seller_id"])

    # 3. Orders -> discount_amount & coupon_code
    order_cols = {c["name"] for c in inspector.get_columns("orders")}
    if "discount_amount" not in order_cols:
        op.add_column("orders", sa.Column("discount_amount", sa.Numeric(10, 2), nullable=False, server_default="0.00"))
    if "coupon_code" not in order_cols:
        op.add_column("orders", sa.Column("coupon_code", sa.String(50), nullable=True))

    # 4. Coupons
    if "coupons" not in existing_tables:
        op.create_table("coupons", ...)

    # 5. Notifications
    if "notifications" not in existing_tables:
        op.create_table("notifications", ...)

    # 6. Reviews
    if "reviews" not in existing_tables:
        op.create_table("reviews", ...)

    # 7. Categories uniqueness
    # Check if unique constraint already exists before adding
    cat_indexes = {idx["name"]: idx for idx in inspector.get_indexes("categories")}
    if "uq_categories_name" not in cat_indexes and "ix_categories_name" in cat_indexes:
        # Safely upgrade or add unique index if no duplicates exist
        op.create_unique_constraint("uq_categories_name", "categories", ["name"])
```

### Why this preserves all data:
- Zero `DROP TABLE` or `DROP COLUMN` calls.
- Adds columns with safe `nullable=True` or explicit `server_default`.
- Detects already existing tables and keeps all rows intact.

---

## 6. Fresh Database Initialization Strategy

For a brand-new PostgreSQL database:
1. Container starts with an empty PostgreSQL database.
2. `alembic upgrade head` runs:
   - Revision 1 (`f904b613102f`) creates initial 8 tables.
   - Revision 2 (`consolidate_ecommerce_schema`) creates `sellers`, adds `products.seller_id`, adds `orders` discount columns, and creates `coupons`, `notifications`, `reviews`, plus constraints.
3. Database reaches `head` cleanly and deterministically.
4. If demo seeding is enabled (`SEED_DEMO_DATA=true` in development), seeds categories, products, demo users, sellers, and sample notifications.

---

## 7. Existing Database Baseline Strategy

For existing developer or deployed databases that were initialized under older workflows:
1. The database currently has `alembic_version` recorded as `f904b613102f` (or unversioned if `alembic upgrade` failed previously).
2. If `alembic_version` is missing, running `alembic stamp f904b613102f` establishes the initial baseline.
3. Running `alembic upgrade head` executes Revision 2.
4. Because Revision 2 uses introspective checks, any table already created by `create_all()` is preserved without errors or table locks.
5. Missing columns (`seller_id`, `discount_amount`, `coupon_code`) and missing constraints are applied seamlessly.
6. The `alembic_version` table is updated to Revision 2 head.

---

## 8. Backup and Rollback Considerations

1. **Pre-Migration Backup Procedure:**
   Before running migration in staging or production environments, execute a physical or logical snapshot:
   ```bash
   pg_dump -U postgres -d ecommerce -Fc -f /backups/ecommerce_pre_s18_$(date +%Y%m%d%H%M%S).dump
   ```
2. **Downgrade Functionality (`downgrade()` in Revision 2):**
   - Drops `reviews`, `notifications`, `coupons`.
   - Drops `products.seller_id` column and index.
   - Drops `orders.discount_amount` and `orders.coupon_code`.
   - Drops `sellers` table.
   - Returns schema strictly to `f904b613102f`.
3. **Safety Warning:**
   Downgrades should only be used in non-production rollbacks, as dropping tables/columns inevitably discards data in those specific fields.

---

## 9. Constraints and Indexes to Add

The following constraints and indexes will be explicitly added in Revision 2:

1. **Check Constraints:**
   - `CHECK (stock >= 0)` on `products` table.
   - `CHECK (used_count >= 0)` on `coupons` table.
   - `CHECK (usage_limit IS NULL OR usage_limit >= 0)` on `coupons` table.
   - `CHECK (rating >= 1 AND rating <= 5)` on `reviews` table.
2. **Foreign Keys:**
   - `fk_products_seller_id`: `products.seller_id` -> `sellers.id` (ON DELETE SET NULL).
   - `fk_reviews_product_id`: `reviews.product_id` -> `products.id` (ON DELETE CASCADE).
   - `fk_reviews_user_id`: `reviews.user_id` -> `users.id` (ON DELETE CASCADE).
   - `fk_reviews_order_id`: `reviews.order_id` -> `orders.id` (ON DELETE SET NULL).
   - `fk_notifications_user_id`: `notifications.user_id` -> `users.id` (ON DELETE CASCADE).
3. **Indexes:**
   - Index on `products.seller_id`.
   - Index on `reviews.product_id`, `reviews.user_id`, `reviews.order_id`, and `reviews.status`.
   - Index on `notifications.user_id` and `notifications.read`.
   - Unique index on `coupons.code`.
   - Unique index / constraint on `categories.name`.

---

## 10. Required PostgreSQL Tests

In Part 3B, we will verify the migration against PostgreSQL using an isolated test harness:
1. **Fresh Database Test:**
   - Create an empty isolated PostgreSQL test database (`bluepanda_mig_fresh`).
   - Run `alembic upgrade head`.
   - Assert all 12 tables exist.
   - Assert all foreign keys, check constraints, and indexes exist.
   - Run `alembic downgrade -1` and verify clean rollback to `f904b613102f`.
2. **Existing Database Upgrade Test:**
   - Create an isolated PostgreSQL database (`bluepanda_mig_existing`).
   - Run `f904b613102f`.
   - Simulate previous behavior by running `Base.metadata.create_all()` and inserting test rows into `users`, `products`, `orders`, `sellers`, and `coupons`.
   - Run `alembic upgrade head`.
   - Assert migration succeeds with exit code 0.
   - Assert test rows in `sellers`, `coupons`, and `orders` remain completely intact.
3. **Idempotency Test:**
   - Re-running `alembic upgrade head` is a no-op with 0 errors.

---

## 11. Potential Breaking Changes & Mitigations

1. **Category Name Uniqueness:**
   - If an existing database has duplicate category names, adding a `UNIQUE` constraint will fail.
   - *Mitigation:* The migration will check for duplicates before creating the unique constraint; if duplicates exist, it logs a warning without crashing or creates a non-unique index until duplicates are resolved.
2. **Stock Non-Negative Constraint (`stock >= 0`):**
   - If existing products have negative stock from earlier concurrency defects prior to S10, the check constraint would fail.
   - *Mitigation:* The migration can execute `UPDATE products SET stock = 0 WHERE stock < 0` before applying the `CHECK (stock >= 0)` constraint.
3. **Startup Race Conditions (`docker-entrypoint.sh`):**
   - If multiple backend replicas run `alembic upgrade head` simultaneously in Kubernetes or multi-container Docker, migrations could collide.
   - *Mitigation:* Alembic uses database-level locks on PostgreSQL (`pg_advisory_lock` or transaction locks). Ensuring `alembic upgrade head` runs as a dedicated init container or entrypoint step before launching Uvicorn prevents worker race conditions.

---

## 12. Implementation and Verification Status (Part 3B Complete)

- **Revision Created:** [`backend/alembic/versions/c4b8d91a2e3f_consolidate_ecommerce_schema.py`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/backend/alembic/versions/c4b8d91a2e3f_consolidate_ecommerce_schema.py)
  - Revision ID: `c4b8d91a2e3f`
  - Down Revision: `f904b613102f`
- **Runtime Modifications:**
  - [`backend/app/db/init_db.py`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/backend/app/db/init_db.py): Removed ad-hoc runtime `ALTER TABLE orders ADD COLUMN ...` statements.
  - [`backend/app/main.py`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/backend/app/main.py): Disabled `Base.metadata.create_all()` in production environments, requiring verified Alembic migrations.
  - [`backend/docker-entrypoint.sh`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/backend/docker-entrypoint.sh): Replaced swallowed error handling with strict `alembic upgrade head` execution (fail-fast).
  - [`backend/alembic/env.py`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/backend/alembic/env.py): Allowed explicit target URLs to take precedence for isolated programmatic migration runs.
- **Verification Suite:** [`backend/tests/test_migrations_postgres.py`](file:///Users/bunvathana/Documents/Code/Project/e-commerce/backend/tests/test_migrations_postgres.py)
  - All 12 PostgreSQL migration scenarios passed on disposable databases:
    1. Fresh database migration (`f904b613102f` -> `c4b8d91a2e3f`)
    2. Existing populated database preserves all records
    3. Existing database with runtime-created tables preserves data without errors
    4. Missing selected columns added cleanly
    5. Re-running migration on upgraded database is idempotent
    6. Duplicate category names block constraint with clear error
    7. Negative stock blocks constraint with clear error
    8. Invalid review ratings block constraint with clear error
    9. Negative coupon used_count blocks constraint with clear error
    10. Orphan foreign-key references block constraint with clear error
    11. Failed migrations roll back and do not advance version stamp
    12. Downgrade cleanly reverts to initial revision on disposable database

---

## 13. Safe Manual Deployment Procedure for Real Environments

**DO NOT apply migrations to real environments without following this procedure:**

1. **Perform Full Database Backup:**
   ```bash
   pg_dump -U postgres -d ecommerce -Fc -f /backups/ecommerce_pre_s18_$(date +%Y%m%d%H%M%S).dump
   ```
2. **Pre-Flight Data Health Audit (Read-Only):**
   Run the following verification queries prior to migration:
   ```sql
   -- Check duplicate categories
   SELECT name, COUNT(*) FROM categories GROUP BY name HAVING COUNT(*) > 1;

   -- Check negative inventory
   SELECT id, name, stock FROM products WHERE stock < 0;

   -- Check invalid review ratings
   SELECT id, rating FROM reviews WHERE rating < 1 OR rating > 5;

   -- Check invalid coupon counters
   SELECT id, code, used_count FROM coupons WHERE used_count < 0;

   -- Check orphan product seller IDs
   SELECT id, name, seller_id FROM products WHERE seller_id IS NOT NULL AND seller_id NOT IN (SELECT id FROM sellers);
   ```
   *If any queries return rows, resolve the data inconsistencies manually before running the migration.*
3. **Execute Migration:**
   ```bash
   alembic upgrade head
   ```
4. **Verify Schema Post-Migration:**
   ```sql
   SELECT version_num FROM alembic_version;
   -- Should return: c4b8d91a2e3f
   ```


