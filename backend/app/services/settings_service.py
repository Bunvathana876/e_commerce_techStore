from decimal import Decimal
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.store_setting import StoreSetting
from app.models.user import User
from app.schemas.settings import (
    AdminSettingsResponse,
    InfrastructureStatusResponse,
    PublicStoreSettingsResponse,
    RoleDefinitionResponse,
    RolePermissionGroup,
    RoleUserSummary,
    StoreSettingsData,
    StoreSettingsUpdate,
)
from app.services.email_service import EmailService
from app.services.payment_service import PaymentService
from app.services.storage_service import StorageService


ROLE_CATALOG: list[dict] = [
    {
        "id": "admin",
        "name": "Admin",
        "description": "Full platform control across catalog, orders, inventory ledgers, refunds, settings, and users.",
        "is_system": True,
        "permission_groups": [
            {"module": "Catalog & Merchandising", "permissions": ["products.manage", "categories.manage", "reviews.moderate", "coupons.manage"]},
            {"module": "Orders, POS & Refunds", "permissions": ["orders.read_all", "orders.update_status", "orders.cancel", "pos.checkout", "refunds.approve_process"]},
            {"module": "Inventory & Procurement", "permissions": ["warehouses.manage", "inventory.adjust", "purchase_orders.manage", "transfers.manage", "suppliers.manage"]},
            {"module": "Platform & Users", "permissions": ["users.manage", "sellers.manage", "reports.view", "settings.manage"]},
        ],
    },
    {
        "id": "seller",
        "name": "Seller",
        "description": "Merchant portal access for managing store profile, owned products, fulfillment tracking, and seller orders.",
        "is_system": False,
        "permission_groups": [
            {"module": "Seller Storefront", "permissions": ["seller_profile.read", "seller_profile.update", "upload.store_media"]},
            {"module": "Catalog Ownership", "permissions": ["own_products.read", "own_products.create", "own_products.update", "own_products.delete"]},
            {"module": "Order Fulfillment", "permissions": ["own_orders.read", "own_orders.advance_shipping", "own_orders.update_tracking", "own_reviews.reply"]},
        ],
    },
    {
        "id": "customer",
        "name": "Customer",
        "description": "Storefront & mobile shopping account for cart sync, checkout, order history, tracking, and verified reviews.",
        "is_system": True,
        "permission_groups": [
            {"module": "Shopping & Checkout", "permissions": ["catalog.browse", "cart.manage", "favorites.manage", "addresses.manage", "orders.create"]},
            {"module": "Post-Purchase", "permissions": ["own_orders.read", "own_orders.track", "reviews.submit_verified", "notifications.manage"]},
        ],
    },
    {
        "id": "staff",
        "name": "Staff",
        "description": "Operational support account tier reserved for scoped warehouse/store workflows.",
        "is_system": False,
        "permission_groups": [
            {"module": "General", "permissions": ["account.authenticated_access"]},
        ],
    },
    {
        "id": "employee",
        "name": "Employee",
        "description": "Internal employee account tier reserved for scoped operational workflows.",
        "is_system": False,
        "permission_groups": [
            {"module": "General", "permissions": ["account.authenticated_access"]},
        ],
    },
]


class SettingsService:
    """Persisted Store Settings, live infrastructure inspection, and authoritative RBAC role catalog."""

    @staticmethod
    def get_effective_settings(db: Session) -> StoreSetting:
        """Return persisted store settings or transient defaults without mutating the current transaction."""
        row = db.scalar(select(StoreSetting).where(StoreSetting.key == "default"))
        if row is not None:
            return row
        return StoreSetting(
            key="default",
            store_name="Blue Panda",
            store_email="support@bluepanda.com",
            currency="USD",
            language="en",
            timezone="Asia/Phnom_Penh",
            theme="light",
            primary_color="#245BE7",
            sidebar_style="default",
            free_shipping_min=Decimal("100.00"),
            standard_shipping_fee=Decimal("2.00"),
            express_shipping_fee=Decimal("12.00"),
            estimated_delivery_days="1-3",
            enable_card_payment=True,
            enable_cod_payment=True,
            notify_new_order=True,
            notify_low_stock=True,
            notify_customer_message=True,
            notify_weekly_report=False,
        )

    @staticmethod
    def get_or_create_settings(db: Session) -> StoreSetting:
        row = db.scalar(select(StoreSetting).where(StoreSetting.key == "default"))
        if row is not None:
            return row

        row = StoreSetting(key="default")
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    @staticmethod
    def get_infrastructure_status(db: Session) -> InfrastructureStatusResponse:
        bind = db.get_bind()
        dialect = bind.dialect.name if bind is not None else "unknown"
        db_connected = False
        table_names: list[str] = []
        try:
            db.execute(text("SELECT 1"))
            db_connected = True
        except Exception:
            db_connected = False

        if bind is not None:
            try:
                table_names = sorted(
                    t for t in inspect(bind).get_table_names() if t != "alembic_version"
                )
            except Exception:
                table_names = []

        return InfrastructureStatusResponse(
            database_dialect=dialect,
            database_connected=db_connected,
            table_count=len(table_names),
            table_names=table_names,
            upload_storage_backend=StorageService.resolve_backend(settings),
            email_provider=EmailService.resolve_provider(settings),
            card_gateway_configured=PaymentService.is_stripe_configured(),
        )

    @staticmethod
    def get_public_settings(db: Session) -> PublicStoreSettingsResponse:
        row = SettingsService.get_or_create_settings(db)
        return PublicStoreSettingsResponse(
            store_name=row.store_name,
            store_email=row.store_email,
            store_phone=row.store_phone,
            store_logo_url=row.store_logo_url,
            currency=row.currency,
            free_shipping_min=row.free_shipping_min,
            standard_shipping_fee=row.standard_shipping_fee,
            express_shipping_fee=row.express_shipping_fee,
            estimated_delivery_days=row.estimated_delivery_days,
            enable_card_payment=row.enable_card_payment,
            enable_cod_payment=row.enable_cod_payment,
        )

    @staticmethod
    def get_admin_settings(db: Session) -> AdminSettingsResponse:
        row = SettingsService.get_or_create_settings(db)
        return AdminSettingsResponse(
            settings=StoreSettingsData.model_validate(row),
            infrastructure=SettingsService.get_infrastructure_status(db),
        )

    @staticmethod
    def update_admin_settings(
        db: Session,
        payload: StoreSettingsUpdate,
        actor: User,
    ) -> AdminSettingsResponse:
        row = SettingsService.get_or_create_settings(db)
        for field, value in payload.model_dump().items():
            setattr(row, field, value)
        row.updated_by_user_id = actor.id
        db.commit()
        db.refresh(row)
        return AdminSettingsResponse(
            settings=StoreSettingsData.model_validate(row),
            infrastructure=SettingsService.get_infrastructure_status(db),
        )

    @staticmethod
    def list_roles(db: Session) -> list[RoleDefinitionResponse]:
        users = list(db.scalars(select(User).order_by(User.id.asc())).all())
        users_by_role: dict[str, list[RoleUserSummary]] = {}
        for u in users:
            role_key = (u.role or "customer").strip().lower()
            users_by_role.setdefault(role_key, []).append(
                RoleUserSummary(
                    id=u.id,
                    name=u.name,
                    email=u.email,
                    is_active=u.is_active,
                )
            )

        roles_out: list[RoleDefinitionResponse] = []
        for template in ROLE_CATALOG:
            groups = [RolePermissionGroup(**g) for g in template["permission_groups"]]
            perm_count = sum(len(g.permissions) for g in groups)
            assigned = users_by_role.get(template["id"], [])
            roles_out.append(
                RoleDefinitionResponse(
                    id=template["id"],
                    name=template["name"],
                    description=template["description"],
                    is_system=template["is_system"],
                    permissions_count=perm_count,
                    permission_groups=groups,
                    users_count=len(assigned),
                    users=assigned,
                )
            )
        return roles_out
