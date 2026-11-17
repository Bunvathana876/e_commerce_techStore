from fastapi import APIRouter

from app.api.v1.routes.addresses import router as address_router
from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.cart import router as cart_router
from app.api.v1.routes.categories import router as category_router
from app.api.v1.routes.coupons import router as coupon_router
from app.api.v1.routes.favorites import router as favorite_router
from app.api.v1.routes.notifications import router as notification_router
from app.api.v1.routes.orders import router as order_router
from app.api.v1.routes.pos import router as pos_router
from app.api.v1.routes.products import router as product_router
from app.api.v1.routes.reviews import router as review_router
from app.api.v1.routes.seller import router as seller_self_router
from app.api.v1.routes.sellers import router as seller_router
from app.api.v1.routes.stats import router as stats_router
from app.api.v1.routes.upload import router as upload_router
from app.api.v1.routes.users import router as user_router

all_routers = [
    auth_router,
    category_router,
    product_router,
    cart_router,
    favorite_router,
    notification_router,
    address_router,
    order_router,
    pos_router,
    coupon_router,
    review_router,
    seller_self_router,
    seller_router,
    stats_router,
    user_router,
    upload_router,
]

api_router = APIRouter(prefix="/api")
for r in all_routers:
    api_router.include_router(r)

api_v1_router = APIRouter(prefix="/api/v1")
for r in all_routers:
    api_v1_router.include_router(r)

