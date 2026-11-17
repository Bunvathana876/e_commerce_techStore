import pytest
from decimal import Decimal
from sqlalchemy import select
from app.db.database import SessionLocal
from app.models.cart import CartItem
from app.models.product import Product


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_valid_cart_item_update(client, headers, prefix):
    """Customer can successfully update their own cart item quantity via /cart/items/{item_id}."""
    user_header = headers(2)

    # 1. Add product 1 to cart
    add_res = client.post(
        f"{prefix}/cart/items",
        json={"product_id": 1, "quantity": 2},
        headers=user_header,
    )
    assert add_res.status_code == 200

    cart_data = client.get(f"{prefix}/cart", headers=user_header).json()["data"]
    assert len(cart_data["items"]) == 1
    cart_item_id = cart_data["items"][0]["id"]
    assert cart_data["items"][0]["quantity"] == 2

    # 2. Update cart item quantity
    update_res = client.put(
        f"{prefix}/cart/items/{cart_item_id}",
        json={"quantity": 4},
        headers=user_header,
    )
    assert update_res.status_code == 200
    updated_data = update_res.json()["data"]
    assert updated_data["items"][0]["id"] == cart_item_id
    assert updated_data["items"][0]["quantity"] == 4
    assert updated_data["total_items"] == 4
    assert updated_data["subtotal"] == 80.0  # 4 * 20.00


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_valid_cart_item_deletion(client, headers, prefix):
    """Customer can successfully delete an item from their cart via /cart/items/{item_id}."""
    user_header = headers(2)

    # 1. Add product 1 to cart
    client.post(
        f"{prefix}/cart/items",
        json={"product_id": 1, "quantity": 2},
        headers=user_header,
    )

    cart_data = client.get(f"{prefix}/cart", headers=user_header).json()["data"]
    cart_item_id = cart_data["items"][0]["id"]

    # 2. Delete item
    del_res = client.delete(f"{prefix}/cart/items/{cart_item_id}", headers=user_header)
    assert del_res.status_code == 200
    res_data = del_res.json()["data"]
    assert len(res_data["items"]) == 0
    assert res_data["total_items"] == 0
    assert res_data["subtotal"] == 0.0


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_overlapping_product_and_cart_item_ids(client, headers, prefix):
    """
    CRITICAL REGRESSION TEST:
    Verifies that when a cart item's primary key ID equals another item's product_id,
    mutating via /cart/items/{item_id} deterministically targets CartItem.id
    and NEVER mutates the other item.
    """
    user_header = headers(2)

    # Create a secondary product with a specific ID to ensure overlap
    with SessionLocal() as db:
        prod10 = Product(
            id=10,
            category_id=1,
            seller_id=1,
            name="Product with ID 10",
            price=Decimal("15.00"),
            stock=50,
            is_active=True,
        )
        db.add(prod10)
        db.commit()

        # Seed overlapping cart items directly to guarantee explicit primary key IDs
        # CartItem 1: id=10, product_id=1 (quantity 2)
        # CartItem 2: id=20, product_id=10 (quantity 1) -> product_id matches CartItem 1's id!
        ci1 = CartItem(id=10, user_id=2, product_id=1, quantity=2)
        ci2 = CartItem(id=20, user_id=2, product_id=10, quantity=1)
        db.add_all([ci1, ci2])
        db.commit()

    # Verify both items exist in user's cart
    cart_res = client.get(f"{prefix}/cart", headers=user_header).json()["data"]
    item_map = {item["id"]: item for item in cart_res["items"]}
    assert 10 in item_map
    assert 20 in item_map
    assert item_map[10]["product_id"] == 1
    assert item_map[20]["product_id"] == 10

    # 1. Update CartItem 10 -> MUST update CartItem 10 (Product 1), NOT CartItem 20 (Product 10)
    upd_res = client.put(
        f"{prefix}/cart/items/10",
        json={"quantity": 7},
        headers=user_header,
    )
    assert upd_res.status_code == 200

    # Verify in DB: CartItem 10 has qty 7, CartItem 20 is completely UNTOUCHED (still qty 1)
    with SessionLocal() as db:
        ci10 = db.get(CartItem, 10)
        ci20 = db.get(CartItem, 20)
        assert ci10.quantity == 7, "CartItem #10 should be updated to 7"
        assert ci20.quantity == 1, "CartItem #20 must remain untouched with quantity 1"

    # 2. Update CartItem 20 -> MUST update CartItem 20, leaving CartItem 10 untouched
    upd_res2 = client.put(
        f"{prefix}/cart/items/20",
        json={"quantity": 4},
        headers=user_header,
    )
    assert upd_res2.status_code == 200
    with SessionLocal() as db:
        ci10 = db.get(CartItem, 10)
        ci20 = db.get(CartItem, 20)
        assert ci10.quantity == 7
        assert ci20.quantity == 4

    # 3. Delete CartItem 10 -> MUST delete CartItem 10, leaving CartItem 20 in cart
    del_res = client.delete(f"{prefix}/cart/items/10", headers=user_header)
    assert del_res.status_code == 200
    with SessionLocal() as db:
        assert db.get(CartItem, 10) is None, "CartItem #10 should be deleted"
        ci20_rem = db.get(CartItem, 20)
        assert ci20_rem is not None, "CartItem #20 must remain in cart"
        assert ci20_rem.quantity == 4


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_cross_user_cart_access_strictly_denied(client, headers, prefix):
    """A customer cannot update or delete cart items belonging to another customer."""
    user2_header = headers(2)
    user3_header = headers(3)

    # User 2 adds product 1
    client.post(
        f"{prefix}/cart/items",
        json={"product_id": 1, "quantity": 2},
        headers=user2_header,
    )
    cart2 = client.get(f"{prefix}/cart", headers=user2_header).json()["data"]
    item_id_user2 = cart2["items"][0]["id"]

    # User 3 attempts to update User 2's cart item -> 404 Not Found
    attack_upd = client.put(
        f"{prefix}/cart/items/{item_id_user2}",
        json={"quantity": 10},
        headers=user3_header,
    )
    assert attack_upd.status_code == 404
    assert attack_upd.json()["detail"] == "Cart item not found."

    # User 3 attempts to delete User 2's cart item -> 404 Not Found
    attack_del = client.delete(
        f"{prefix}/cart/items/{item_id_user2}",
        headers=user3_header,
    )
    assert attack_del.status_code == 404
    assert attack_del.json()["detail"] == "Cart item not found."

    # Verify User 2's cart item is completely unchanged
    cart2_after = client.get(f"{prefix}/cart", headers=user2_header).json()["data"]
    assert len(cart2_after["items"]) == 1
    assert cart2_after["items"][0]["id"] == item_id_user2
    assert cart2_after["items"][0]["quantity"] == 2


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_missing_cart_item_returns_404(client, headers, prefix):
    """Mutating non-existent cart items returns a clean 404 error."""
    user_header = headers(2)

    res_upd = client.put(
        f"{prefix}/cart/items/999999",
        json={"quantity": 1},
        headers=user_header,
    )
    assert res_upd.status_code == 404
    assert res_upd.json()["detail"] == "Cart item not found."

    res_del = client.delete(f"{prefix}/cart/items/999999", headers=user_header)
    assert res_del.status_code == 404
    assert res_del.json()["detail"] == "Cart item not found."


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_invalid_quantities_rejected(client, headers, prefix):
    """Quantities must be >= 1 and not exceed product stock."""
    user_header = headers(2)

    client.post(
        f"{prefix}/cart/items",
        json={"product_id": 1, "quantity": 1},
        headers=user_header,
    )
    cart = client.get(f"{prefix}/cart", headers=user_header).json()["data"]
    item_id = cart["items"][0]["id"]

    # 1. Quantity 0 rejected by schema (ge=1)
    res_zero = client.put(
        f"{prefix}/cart/items/{item_id}",
        json={"quantity": 0},
        headers=user_header,
    )
    assert res_zero.status_code == 422

    # 2. Negative quantity rejected by schema
    res_neg = client.put(
        f"{prefix}/cart/items/{item_id}",
        json={"quantity": -3},
        headers=user_header,
    )
    assert res_neg.status_code == 422

    # 3. Quantity exceeding available stock (stock=20 for product 1)
    res_exceed = client.put(
        f"{prefix}/cart/items/{item_id}",
        json={"quantity": 99},
        headers=user_header,
    )
    assert res_exceed.status_code == 400
    assert "Only 20 items available in stock" in res_exceed.json()["detail"]


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_dedicated_product_reference_routes(client, headers, prefix):
    """Dedicated /cart/products/{product_id} routes mutate explicitly by product reference."""
    user_header = headers(2)

    client.post(
        f"{prefix}/cart/items",
        json={"product_id": 1, "quantity": 1},
        headers=user_header,
    )

    # 1. Update by product reference
    upd_res = client.put(
        f"{prefix}/cart/products/1",
        json={"quantity": 5},
        headers=user_header,
    )
    assert upd_res.status_code == 200
    assert upd_res.json()["data"]["items"][0]["quantity"] == 5

    # Cross-user denial on product route
    cross_res = client.put(
        f"{prefix}/cart/products/1",
        json={"quantity": 2},
        headers=headers(3),
    )
    assert cross_res.status_code == 404

    # 2. Delete by product reference
    del_res = client.delete(f"{prefix}/cart/products/1", headers=user_header)
    assert del_res.status_code == 200
    assert len(del_res.json()["data"]["items"]) == 0


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_checkout_compatibility_after_cart_updates(client, headers, prefix):
    """Checkout correctly consumes updated cart items and clears the cart."""
    user_header = headers(2)

    # 1. Add item and update quantity
    client.post(
        f"{prefix}/cart/items",
        json={"product_id": 1, "quantity": 2},
        headers=user_header,
    )
    cart = client.get(f"{prefix}/cart", headers=user_header).json()["data"]
    item_id = cart["items"][0]["id"]

    client.put(
        f"{prefix}/cart/items/{item_id}",
        json={"quantity": 3},
        headers=user_header,
    )

    # 2. Place COD order
    order_res = client.post(
        f"{prefix}/orders",
        json={
            "shipping_address": "123 Test Street, Phnom Penh",
            "payment_method": "Cash on Delivery",
        },
        headers=user_header,
    )
    assert order_res.status_code in (200, 201)
    order_data = order_res.json()["data"]
    assert order_data["status"] == "pending"
    assert order_data["payment_status"] == "pending"
    assert len(order_data["items"]) == 1
    assert order_data["items"][0]["quantity"] == 3
    assert order_data["items"][0]["price"] == 20.0
    assert order_data["total"] == 62.0  # 3 * 20.00 = 60.00 + 2.00 shipping

    # 3. Cart should now be empty
    cart_after = client.get(f"{prefix}/cart", headers=user_header).json()["data"]
    assert len(cart_after["items"]) == 0
    assert cart_after["total_items"] == 0


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_legacy_endpoint_rejects_ambiguous_overlapping_requests(client, headers, prefix):
    """
    TASK 3 REGRESSION TEST:
    Verifies that the legacy route /cart/{identifier} REJECTS ambiguous requests with HTTP 409 Conflict
    when identifier matches both a CartItem.id and a different CartItem's product_id.
    This guarantees the backend NEVER silently selects or corrupts the wrong cart item.
    """
    user_header = headers(2)

    with SessionLocal() as db:
        prod10 = Product(
            id=10,
            category_id=1,
            seller_id=1,
            name="Product 10",
            price=Decimal("15.00"),
            stock=50,
            is_active=True,
        )
        db.add(prod10)
        db.commit()

        # Item 1: id=5, product_id=10, qty 1 (User has Product 10)
        # Item 2: id=10, product_id=1, qty 1 (User has Product 1, primary key is 10)
        ci1 = CartItem(id=5, user_id=2, product_id=10, quantity=1)
        ci2 = CartItem(id=10, user_id=2, product_id=1, quantity=1)
        db.add_all([ci1, ci2])
        db.commit()

    # 1. Calling legacy PUT /cart/10 is ambiguous -> MUST return 409 Conflict
    ambig_upd = client.put(
        f"{prefix}/cart/10",
        json={"quantity": 5},
        headers=user_header,
    )
    assert ambig_upd.status_code == 409
    assert "Ambiguous cart identifier '10'" in ambig_upd.json()["detail"]

    # 2. Calling legacy DELETE /cart/10 is ambiguous -> MUST return 409 Conflict
    ambig_del = client.delete(f"{prefix}/cart/10", headers=user_header)
    assert ambig_del.status_code == 409
    assert "Ambiguous cart identifier '10'" in ambig_del.json()["detail"]

    # 3. Explicit /cart/items/10 succeeds deterministically (targets CartItem #10)
    strict_item_upd = client.put(
        f"{prefix}/cart/items/10",
        json={"quantity": 3},
        headers=user_header,
    )
    assert strict_item_upd.status_code == 200

    # 4. Explicit /cart/product/10 succeeds deterministically (targets CartItem #5, Product 10)
    strict_prod_upd = client.put(
        f"{prefix}/cart/product/10",
        json={"quantity": 4},
        headers=user_header,
    )
    assert strict_prod_upd.status_code == 200

    # Verify both items reflect their explicit, unambiguous updates
    with SessionLocal() as db:
        item1 = db.get(CartItem, 5)
        item2 = db.get(CartItem, 10)
        assert item1.quantity == 4, "Product 10 (CartItem #5) should be updated to 4"
        assert item2.quantity == 3, "Product 1 (CartItem #10) should be updated to 3"


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_legacy_endpoint_unambiguous_backward_compatibility(client, headers, prefix):
    """
    Verifies that the legacy route /cart/{identifier} preserves backward compatibility
    when there is NO ambiguity (matches only CartItem.id or only Product.id).
    """
    user_header = headers(2)

    with SessionLocal() as db:
        prod10 = Product(
            id=10,
            category_id=1,
            seller_id=1,
            name="Product 10",
            price=Decimal("15.00"),
            stock=50,
            is_active=True,
        )
        db.add(prod10)
        db.commit()

        # User has only 1 item: id=5, product_id=10
        ci1 = CartItem(id=5, user_id=2, product_id=10, quantity=1)
        db.add(ci1)
        db.commit()

    # 1. Legacy update by product ID 10 (unambiguous, no item with id=10 exists)
    upd_by_prod = client.put(
        f"{prefix}/cart/10",
        json={"quantity": 3},
        headers=user_header,
    )
    assert upd_by_prod.status_code == 200
    assert upd_by_prod.json()["data"]["items"][0]["quantity"] == 3

    # 2. Legacy update by cart item ID 5 (unambiguous, no item with product_id=5 exists)
    upd_by_id = client.put(
        f"{prefix}/cart/5",
        json={"quantity": 6},
        headers=user_header,
    )
    assert upd_by_id.status_code == 200
    assert upd_by_id.json()["data"]["items"][0]["quantity"] == 6

    # 3. Legacy delete by product ID 10
    del_by_prod = client.delete(f"{prefix}/cart/10", headers=user_header)
    assert del_by_prod.status_code == 200
    assert len(del_by_prod.json()["data"]["items"]) == 0


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_multiple_items_in_cart_isolated_mutations(client, headers, prefix):
    """Multiple items in the same cart can be added, updated, and removed independently."""
    user_header = headers(2)

    with SessionLocal() as db:
        p3 = Product(id=3, category_id=1, seller_id=1, name="P3", price=Decimal("10.00"), stock=50, is_active=True)
        p4 = Product(id=4, category_id=1, seller_id=1, name="P4", price=Decimal("25.00"), stock=50, is_active=True)
        db.add_all([p3, p4])
        db.commit()

    # Add Product 1 (price 20, qty 2)
    client.post(f"{prefix}/cart/items", json={"product_id": 1, "quantity": 2}, headers=user_header)
    # Add Product 3 (price 10, qty 3)
    client.post(f"{prefix}/cart/items", json={"product_id": 3, "quantity": 3}, headers=user_header)
    # Add Product 4 (price 25, qty 1)
    client.post(f"{prefix}/cart/items", json={"product_id": 4, "quantity": 1}, headers=user_header)

    cart = client.get(f"{prefix}/cart", headers=user_header).json()["data"]
    assert cart["total_items"] == 6  # 2 + 3 + 1
    assert cart["subtotal"] == 95.0  # 40 + 30 + 25

    # Update Product 3 via explicit product endpoint to qty 5
    upd_p3 = client.put(f"{prefix}/cart/product/3", json={"quantity": 5}, headers=user_header)
    assert upd_p3.status_code == 200
    cart2 = upd_p3.json()["data"]
    assert cart2["total_items"] == 8  # 2 + 5 + 1
    assert cart2["subtotal"] == 115.0  # 40 + 50 + 25

    # Remove Product 1 via explicit product endpoint
    del_p1 = client.delete(f"{prefix}/cart/product/1", headers=user_header)
    assert del_p1.status_code == 200
    cart3 = del_p1.json()["data"]
    assert cart3["total_items"] == 6  # 5 + 1
    assert cart3["subtotal"] == 75.0  # 50 + 25
    remaining_pids = {i["product_id"] for i in cart3["items"]}
    assert remaining_pids == {3, 4}

    # Clear entire cart
    clear_res = client.delete(f"{prefix}/cart", headers=user_header)
    assert clear_res.status_code == 200
    cart_empty = client.get(f"{prefix}/cart", headers=user_header).json()["data"]
    assert len(cart_empty["items"]) == 0
    assert cart_empty["total_items"] == 0
    assert cart_empty["subtotal"] == 0.0
