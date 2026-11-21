"""Guard read costs with fresh sessions so the identity map cannot hide N+1s."""
from contextlib import contextmanager
from decimal import Decimal

import pytest
from sqlalchemy import event

from app.db.database import SessionLocal, engine
from app.models.cart import CartItem
from app.models.favorite import Favorite
from app.models.product import Product
from app.models.seller import Seller
from app.schemas.product import ProductResponse
from app.services.cart_service import CartService
from app.services.favorite_service import FavoriteService
from app.services.product_service import ProductService


@contextmanager
def counted_selects():
    statements = []

    def capture(_conn, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", capture)


@pytest.fixture
def catalog():
    with SessionLocal() as db:
        for index in range(10, 22):
            db.add(Seller(id=index, name=f"Seller {index}", owner_name="Owner",
                          email=f"seller{index}@example.com"))
        db.flush()
        for index in range(10, 23):
            db.add(Product(id=index, category_id=1,
                           seller_id=index if index < 22 else None,
                           name=f"Product {index}", price=20, discount_price=15,
                           stock=10, is_active=True))
        db.flush()
        for index in range(10, 23):
            db.add(CartItem(user_id=2, product_id=index, quantity=2))
            db.add(Favorite(user_id=2, product_id=index))
        db.add(CartItem(user_id=3, product_id=1, quantity=1))
        db.add(Favorite(user_id=3, product_id=1))
        db.add(Favorite(user_id=2, product_id=2))  # Inactive remains hidden.
        db.commit()


def test_product_page_uses_two_queries(catalog):
    with SessionLocal() as db, counted_selects() as queries:
        result = ProductService.get_products(db, limit=100)
        assert result.total == 14
        assert len(result.items) == 14
        assert all(product.is_active for product in result.items)
        assert next(p for p in result.items if p.id == 22).seller is None
        assert next(p for p in result.items if p.id == 10).seller.name == "Seller 10"
        assert len(queries) == 2


def test_product_detail_uses_one_query(catalog):
    with SessionLocal() as db, counted_selects() as queries:
        result = ProductResponse.model_validate(ProductService.get_product_by_id(db, 10))
        assert result.category.name == "Fixture category"
        assert result.seller.name == "Seller 10"
        assert len(queries) == 1


def test_cart_query_cost_is_constant_and_preserves_totals_and_owner(catalog):
    with SessionLocal() as db, counted_selects() as queries:
        result = CartService.get_cart(db, 2)
        assert len(result.items) == 13
        assert result.total_items == 26
        assert result.subtotal == Decimal("390.00")
        assert {item.product_id for item in result.items} == set(range(10, 23))
        assert next(i for i in result.items if i.product_id == 10).product.seller.name == "Seller 10"
        assert len(queries) == 1


def test_favorites_query_cost_is_constant_and_preserves_visibility(catalog):
    with SessionLocal() as db, counted_selects() as queries:
        result = FavoriteService.get_favorites(db, 2)
        assert {item.product_id for item in result} == set(range(10, 23))
        assert next(i for i in result if i.product_id == 10).product.seller.name == "Seller 10"
        assert len(queries) == 1
