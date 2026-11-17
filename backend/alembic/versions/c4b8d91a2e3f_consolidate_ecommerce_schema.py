"""consolidate_ecommerce_schema

Revision ID: c4b8d91a2e3f
Revises: f904b613102f
Create Date: 2026-10-31 14:35:00.000000

Consolidates the full 12-table SQLAlchemy schema into Alembic.
Adds missing tables (sellers, coupons, notifications, reviews), missing columns
(products.seller_id, orders.discount_amount, orders.coupon_code), indexes,
foreign keys, and data-integrity check constraints.

Supports both fresh database migrations and existing databases without
destroying existing records.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4b8d91a2e3f'
down_revision: Union[str, Sequence[str], None] = 'f904b613102f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    # =========================================================================
    # 1. Table: sellers
    # =========================================================================
    if 'sellers' not in existing_tables:
        op.create_table(
            'sellers',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=True),
            sa.Column('name', sa.String(length=150), nullable=False),
            sa.Column('owner_name', sa.String(length=100), nullable=False),
            sa.Column('email', sa.String(length=255), nullable=False),
            sa.Column('phone', sa.String(length=50), nullable=True),
            sa.Column('address', sa.String(length=255), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('logo', sa.String(length=500), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='Active'),
            sa.Column('rating', sa.Numeric(precision=3, scale=2), nullable=False, server_default='5.00'),
            sa.Column('products_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('orders_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('total_revenue', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_sellers_name'), 'sellers', ['name'], unique=False)
        op.create_index(op.f('ix_sellers_email'), 'sellers', ['email'], unique=False)
        op.create_index(op.f('ix_sellers_user_id'), 'sellers', ['user_id'], unique=False)
    else:
        # Table exists: verify columns and indexes
        existing_cols = {c['name'] for c in inspector.get_columns('sellers')}
        if 'user_id' in existing_cols:
            existing_fks = inspector.get_foreign_keys('sellers')
            fk_targets = {tuple(fk['referred_columns']) for fk in existing_fks if fk['referred_table'] == 'users'}
            if ('id',) not in fk_targets:
                # Check orphan seller user_id
                res = conn.execute(sa.text(
                    "SELECT COUNT(*) FROM sellers WHERE user_id IS NOT NULL AND user_id NOT IN (SELECT id FROM users)"
                )).scalar()
                if res and res > 0:
                    raise RuntimeError(
                        f"Cannot add foreign key on sellers.user_id: {res} orphan record(s) reference non-existent users."
                    )
                op.create_foreign_key('fk_sellers_user_id', 'sellers', 'users', ['user_id'], ['id'], ondelete='SET NULL')

    # =========================================================================
    # 2. Table: products -> add seller_id
    # =========================================================================
    product_cols = {c['name'] for c in inspector.get_columns('products')}
    if 'seller_id' not in product_cols:
        op.add_column('products', sa.Column('seller_id', sa.Integer(), nullable=True))
        op.create_foreign_key('fk_products_seller_id', 'products', 'sellers', ['seller_id'], ['id'], ondelete='SET NULL')
        op.create_index(op.f('ix_products_seller_id'), 'products', ['seller_id'], unique=False)
    else:
        # Column exists: ensure FK constraint is present
        prod_fks = inspector.get_foreign_keys('products')
        seller_fk = any(fk['referred_table'] == 'sellers' for fk in prod_fks)
        if not seller_fk:
            res = conn.execute(sa.text(
                "SELECT COUNT(*) FROM products WHERE seller_id IS NOT NULL AND seller_id NOT IN (SELECT id FROM sellers)"
            )).scalar()
            if res and res > 0:
                raise RuntimeError(
                    f"Cannot add foreign key on products.seller_id: {res} orphan product(s) reference non-existent sellers."
                )
            op.create_foreign_key('fk_products_seller_id', 'products', 'sellers', ['seller_id'], ['id'], ondelete='SET NULL')
        
        prod_indexes = {idx['name'] for idx in inspector.get_indexes('products')}
        if 'ix_products_seller_id' not in prod_indexes:
            op.create_index(op.f('ix_products_seller_id'), 'products', ['seller_id'], unique=False)

    # =========================================================================
    # 3. Table: orders -> add discount_amount and coupon_code
    # =========================================================================
    order_cols = {c['name'] for c in inspector.get_columns('orders')}
    if 'discount_amount' not in order_cols:
        op.add_column(
            'orders',
            sa.Column('discount_amount', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0.00'),
        )
    if 'coupon_code' not in order_cols:
        op.add_column(
            'orders',
            sa.Column('coupon_code', sa.String(length=50), nullable=True),
        )

    # =========================================================================
    # 4. Table: coupons
    # =========================================================================
    if 'coupons' not in existing_tables:
        op.create_table(
            'coupons',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('code', sa.String(length=50), nullable=False),
            sa.Column('description', sa.String(length=255), nullable=True),
            sa.Column('discount_type', sa.String(length=20), nullable=False, server_default='percent'),
            sa.Column('discount_value', sa.Numeric(precision=10, scale=2), nullable=False),
            sa.Column('min_order_amount', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0.00'),
            sa.Column('max_discount_amount', sa.Numeric(precision=10, scale=2), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('expires_at', sa.DateTime(), nullable=True),
            sa.Column('usage_limit', sa.Integer(), nullable=True),
            sa.Column('used_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_coupons_code'), 'coupons', ['code'], unique=True)
    else:
        # Table exists: verify code uniqueness
        coupon_indexes = {idx['name'] for idx in inspector.get_indexes('coupons')}
        if 'ix_coupons_code' not in coupon_indexes:
            # Check duplicate coupon codes
            dupes = conn.execute(sa.text(
                "SELECT code, COUNT(*) FROM coupons GROUP BY code HAVING COUNT(*) > 1"
            )).fetchall()
            if dupes:
                raise RuntimeError(
                    f"Cannot create unique index on coupons.code: duplicate codes found: {dupes}. "
                    "Please resolve duplicate coupon codes before migrating."
                )
            op.create_index(op.f('ix_coupons_code'), 'coupons', ['code'], unique=True)

    # =========================================================================
    # 5. Table: notifications
    # =========================================================================
    if 'notifications' not in existing_tables:
        op.create_table(
            'notifications',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=True),
            sa.Column('type', sa.String(length=50), nullable=False, server_default='system'),
            sa.Column('title', sa.String(length=255), nullable=False),
            sa.Column('message', sa.Text(), nullable=False),
            sa.Column('link', sa.String(length=255), nullable=True),
            sa.Column('read', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_notifications_user_id'), 'notifications', ['user_id'], unique=False)
    else:
        # Table exists: verify user_id FK
        notif_fks = inspector.get_foreign_keys('notifications')
        user_fk = any(fk['referred_table'] == 'users' for fk in notif_fks)
        if not user_fk:
            res = conn.execute(sa.text(
                "SELECT COUNT(*) FROM notifications WHERE user_id IS NOT NULL AND user_id NOT IN (SELECT id FROM users)"
            )).scalar()
            if res and res > 0:
                raise RuntimeError(
                    f"Cannot add foreign key on notifications.user_id: {res} orphan record(s) reference non-existent users."
                )
            op.create_foreign_key('fk_notifications_user_id', 'notifications', 'users', ['user_id'], ['id'], ondelete='CASCADE')

    # =========================================================================
    # 6. Table: reviews
    # =========================================================================
    if 'reviews' not in existing_tables:
        op.create_table(
            'reviews',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('product_id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('order_id', sa.Integer(), nullable=True),
            sa.Column('rating', sa.Integer(), nullable=False, server_default='5'),
            sa.Column('comment', sa.Text(), nullable=False),
            sa.Column('status', sa.String(length=30), nullable=False, server_default='pending'),
            sa.Column('admin_reply', sa.Text(), nullable=True),
            sa.Column('admin_replied_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
            sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_reviews_order_id'), 'reviews', ['order_id'], unique=False)
        op.create_index(op.f('ix_reviews_product_id'), 'reviews', ['product_id'], unique=False)
        op.create_index(op.f('ix_reviews_status'), 'reviews', ['status'], unique=False)
        op.create_index(op.f('ix_reviews_user_id'), 'reviews', ['user_id'], unique=False)
    else:
        # Table exists: verify foreign keys
        review_fks = inspector.get_foreign_keys('reviews')
        ref_tables = {fk['referred_table'] for fk in review_fks}
        if 'products' not in ref_tables:
            res = conn.execute(sa.text(
                "SELECT COUNT(*) FROM reviews WHERE product_id NOT IN (SELECT id FROM products)"
            )).scalar()
            if res and res > 0:
                raise RuntimeError(
                    f"Cannot add foreign key on reviews.product_id: {res} orphan record(s) reference non-existent products."
                )
            op.create_foreign_key('fk_reviews_product_id', 'reviews', 'products', ['product_id'], ['id'], ondelete='CASCADE')
        if 'users' not in ref_tables:
            res = conn.execute(sa.text(
                "SELECT COUNT(*) FROM reviews WHERE user_id NOT IN (SELECT id FROM users)"
            )).scalar()
            if res and res > 0:
                raise RuntimeError(
                    f"Cannot add foreign key on reviews.user_id: {res} orphan record(s) reference non-existent users."
                )
            op.create_foreign_key('fk_reviews_user_id', 'reviews', 'users', ['user_id'], ['id'], ondelete='CASCADE')
        if 'orders' not in ref_tables:
            res = conn.execute(sa.text(
                "SELECT COUNT(*) FROM reviews WHERE order_id IS NOT NULL AND order_id NOT IN (SELECT id FROM orders)"
            )).scalar()
            if res and res > 0:
                raise RuntimeError(
                    f"Cannot add foreign key on reviews.order_id: {res} orphan record(s) reference non-existent orders."
                )
            op.create_foreign_key('fk_reviews_order_id', 'reviews', 'orders', ['order_id'], ['id'], ondelete='SET NULL')

    # =========================================================================
    # 7. Uniqueness Constraint: categories.name
    # =========================================================================
    cat_indexes = inspector.get_indexes('categories')
    has_unique_name = any(idx['unique'] and 'name' in idx['column_names'] for idx in cat_indexes)
    cat_uqs = inspector.get_unique_constraints('categories')
    has_uq_name = any('name' in uq['column_names'] for uq in cat_uqs)

    if not (has_unique_name or has_uq_name):
        # Validate that no duplicate category names exist before applying unique constraint
        dupes = conn.execute(sa.text(
            "SELECT name, COUNT(*) FROM categories GROUP BY name HAVING COUNT(*) > 1"
        )).fetchall()
        if dupes:
            dupe_names = [d[0] for d in dupes]
            raise RuntimeError(
                f"Cannot add unique constraint on categories.name: duplicate categories found: {dupe_names}. "
                "Manual deduplication required before applying constraint."
            )
        # Drop non-unique index if it exists under ix_categories_name
        ix_names = {idx['name'] for idx in cat_indexes}
        if 'ix_categories_name' in ix_names:
            op.drop_index('ix_categories_name', table_name='categories')
        op.create_unique_constraint('uq_categories_name', 'categories', ['name'])

    # =========================================================================
    # 8. Data-Integrity Check Constraints
    # =========================================================================
    # 8a. products: stock >= 0
    prod_checks = {ck['name'] for ck in inspector.get_check_constraints('products')}
    if 'ck_products_stock_non_negative' not in prod_checks:
        res = conn.execute(sa.text("SELECT COUNT(*) FROM products WHERE stock < 0")).scalar()
        if res and res > 0:
            raise RuntimeError(
                f"Cannot add check constraint ck_products_stock_non_negative: found {res} product(s) with negative stock. "
                "Inventory correction required before applying constraint."
            )
        op.create_check_constraint('ck_products_stock_non_negative', 'products', 'stock >= 0')

    # 8b. coupons: used_count >= 0
    coupon_checks = {ck['name'] for ck in inspector.get_check_constraints('coupons')}
    if 'ck_coupons_used_count_non_negative' not in coupon_checks:
        res = conn.execute(sa.text("SELECT COUNT(*) FROM coupons WHERE used_count < 0")).scalar()
        if res and res > 0:
            raise RuntimeError(
                f"Cannot add check constraint ck_coupons_used_count_non_negative: found {res} coupon(s) with used_count < 0. "
                "Coupon counter correction required before applying constraint."
            )
        op.create_check_constraint('ck_coupons_used_count_non_negative', 'coupons', 'used_count >= 0')

    if 'ck_coupons_usage_limit_valid' not in coupon_checks:
        res = conn.execute(sa.text("SELECT COUNT(*) FROM coupons WHERE usage_limit IS NOT NULL AND usage_limit < 0")).scalar()
        if res and res > 0:
            raise RuntimeError(
                f"Cannot add check constraint ck_coupons_usage_limit_valid: found {res} coupon(s) with negative usage_limit. "
                "Correction required before applying constraint."
            )
        op.create_check_constraint('ck_coupons_usage_limit_valid', 'coupons', 'usage_limit IS NULL OR usage_limit >= 0')

    # 8c. reviews: rating BETWEEN 1 AND 5
    review_checks = {ck['name'] for ck in inspector.get_check_constraints('reviews')}
    if 'ck_reviews_rating_range' not in review_checks:
        res = conn.execute(sa.text("SELECT COUNT(*) FROM reviews WHERE rating < 1 OR rating > 5")).scalar()
        if res and res > 0:
            raise RuntimeError(
                f"Cannot add check constraint ck_reviews_rating_range: found {res} review(s) with rating outside 1..5. "
                "Correction required before applying constraint."
            )
        op.create_check_constraint('ck_reviews_rating_range', 'reviews', 'rating >= 1 AND rating <= 5')


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    # 1. Drop check constraints
    if 'reviews' in existing_tables:
        review_checks = {ck['name'] for ck in inspector.get_check_constraints('reviews')}
        if 'ck_reviews_rating_range' in review_checks:
            op.drop_constraint('ck_reviews_rating_range', 'reviews', type_='check')

    if 'coupons' in existing_tables:
        coupon_checks = {ck['name'] for ck in inspector.get_check_constraints('coupons')}
        if 'ck_coupons_usage_limit_valid' in coupon_checks:
            op.drop_constraint('ck_coupons_usage_limit_valid', 'coupons', type_='check')
        if 'ck_coupons_used_count_non_negative' in coupon_checks:
            op.drop_constraint('ck_coupons_used_count_non_negative', 'coupons', type_='check')

    if 'products' in existing_tables:
        prod_checks = {ck['name'] for ck in inspector.get_check_constraints('products')}
        if 'ck_products_stock_non_negative' in prod_checks:
            op.drop_constraint('ck_products_stock_non_negative', 'products', type_='check')

    # 2. Revert categories uniqueness constraint
    if 'categories' in existing_tables:
        cat_uqs = {uq['name'] for uq in inspector.get_unique_constraints('categories')}
        if 'uq_categories_name' in cat_uqs:
            op.drop_constraint('uq_categories_name', 'categories', type_='unique')
            op.create_index(op.f('ix_categories_name'), 'categories', ['name'], unique=False)

    # 3. Drop tables in reverse foreign key order
    if 'reviews' in existing_tables:
        op.drop_table('reviews')

    if 'notifications' in existing_tables:
        op.drop_table('notifications')

    if 'coupons' in existing_tables:
        op.drop_table('coupons')

    # 4. Remove columns from orders
    if 'orders' in existing_tables:
        order_cols = {c['name'] for c in inspector.get_columns('orders')}
        if 'coupon_code' in order_cols:
            op.drop_column('orders', 'coupon_code')
        if 'discount_amount' in order_cols:
            op.drop_column('orders', 'discount_amount')

    # 5. Remove seller_id from products
    if 'products' in existing_tables:
        product_cols = {c['name'] for c in inspector.get_columns('products')}
        if 'seller_id' in product_cols:
            prod_fks = {fk['name']: fk for fk in inspector.get_foreign_keys('products')}
            if 'fk_products_seller_id' in prod_fks:
                op.drop_constraint('fk_products_seller_id', 'products', type_='foreignkey')
            prod_indexes = {idx['name'] for idx in inspector.get_indexes('products')}
            if 'ix_products_seller_id' in prod_indexes:
                op.drop_index('ix_products_seller_id', table_name='products')
            op.drop_column('products', 'seller_id')

    # 6. Drop sellers table
    if 'sellers' in existing_tables:
        op.drop_table('sellers')
