"""Tests for multi-warehouse inventory, PO lifecycle, transfers, and immutable double-entry ledger."""

import pytest
from sqlalchemy import select

from app.db.database import SessionLocal
from app.models.inventory import (
    InventoryJournalEntry,
    InventoryLedgerLine,
)
from app.models.product import Product


def _create_supplier(client, admin_headers) -> int:
    res = client.post(
        "/api/v1/suppliers",
        headers=admin_headers,
        json={
            "name": "Mekong Tech Distributors",
            "contact_name": "Dara Sok",
            "email": "dara@mekongtech.com",
            "payment_terms": "Net 30",
            "lead_time_days": 5,
        },
    )
    assert res.status_code == 201, res.text
    return res.json()["data"]["id"]


def test_inventory_admin_rbac_enforced(client, headers):
    for customer_or_seller in (headers(2), headers(4)):
        assert (
            client.get("/api/v1/inventory/warehouses", headers=customer_or_seller).status_code
            == 403
        )
        assert (
            client.post(
                "/api/v1/inventory/adjustments",
                headers=customer_or_seller,
                json={"product_id": 1, "quantity_delta": 5, "reason": "Unauthorized edit"},
            ).status_code
            == 403
        )


def test_warehouse_crud_and_scoped_double_entry_adjustments(client, admin_headers):
    # Ensure default WH-MAIN is provisioned + create WH-EAST
    wh_list_res = client.get("/api/inventory/warehouses", headers=admin_headers)
    assert wh_list_res.status_code == 200
    warehouses = wh_list_res.json()["data"]
    assert any(w["code"] == "WH-MAIN" and w["is_default"] for w in warehouses)
    wh_main_id = next(w["id"] for w in warehouses if w["code"] == "WH-MAIN")

    east_res = client.post(
        "/api/inventory/warehouses",
        headers=admin_headers,
        json={"code": "WH-EAST", "name": "East Fulfillment Center", "location": "Sen Sok"},
    )
    assert east_res.status_code == 201
    wh_east_id = east_res.json()["data"]["id"]

    # Duplicate code fails
    dup_res = client.post(
        "/api/inventory/warehouses",
        headers=admin_headers,
        json={"code": "WH-EAST", "name": "Another Hub"},
    )
    assert dup_res.status_code in (400, 409)

    # Zero delta rejected by validator (422)
    zero_res = client.post(
        "/api/inventory/adjustments",
        headers=admin_headers,
        json={"product_id": 1, "warehouse_id": wh_main_id, "quantity_delta": 0, "reason": "Zero test"},
    )
    assert zero_res.status_code == 422

    # Positive adjustment into WH-MAIN (+5 -> product stock 20 -> 25)
    pos_res = client.post(
        "/api/inventory/adjustments",
        headers=admin_headers,
        json={
            "product_id": 1,
            "warehouse_id": wh_main_id,
            "quantity_delta": 5,
            "unit_cost": "12.00",
            "reason": "Cycle count surplus",
        },
    )
    assert pos_res.status_code == 201
    lines = pos_res.json()["data"]["lines"]
    assert sum(l["debit_qty"] for l in lines) == 5
    assert sum(l["credit_qty"] for l in lines) == 5

    # Cannot deduct more stock from WH-EAST (currently 0) than available
    over_res = client.post(
        "/api/inventory/adjustments",
        headers=admin_headers,
        json={
            "product_id": 1,
            "warehouse_id": wh_east_id,
            "quantity_delta": -2,
            "reason": "Shrinkage test",
        },
    )
    assert over_res.status_code == 409

    with SessionLocal() as db:
        assert db.get(Product, 1).stock == 25

    ledger_res = client.get("/api/inventory/ledger?product_id=1", headers=admin_headers)
    assert ledger_res.status_code == 200
    tb = ledger_res.json()["data"]["trial_balance"]
    assert tb["balanced"] is True
    assert tb["total_debits"] == tb["total_credits"]


def test_purchase_order_partial_and_full_receipt_updates_warehouse_and_ledger(
    client, admin_headers
):
    supplier_id = _create_supplier(client, admin_headers)
    wh_res = client.post(
        "/api/v1/inventory/warehouses",
        headers=admin_headers,
        json={"code": "WH-NORTH", "name": "North Hub"},
    )
    wh_north_id = wh_res.json()["data"]["id"]

    po_res = client.post(
        "/api/v1/inventory/purchase-orders",
        headers=admin_headers,
        json={
            "supplier_id": supplier_id,
            "warehouse_id": wh_north_id,
            "notes": "Restock fixture product",
            "items": [{"product_id": 1, "quantity_ordered": 12, "unit_cost": "10.00"}],
        },
    )
    assert po_res.status_code == 201
    po_data = po_res.json()["data"]
    po_id = po_data["id"]
    item_id = po_data["items"][0]["id"]
    assert po_data["status"] == "draft"
    assert float(po_data["total_cost"]) == 120.0

    # Order PO
    order_res = client.post(
        f"/api/v1/inventory/purchase-orders/{po_id}/order", headers=admin_headers
    )
    assert order_res.status_code == 200
    assert order_res.json()["data"]["status"] == "ordered"

    # Partial receipt (4 units)
    part_res = client.post(
        f"/api/v1/inventory/purchase-orders/{po_id}/receive",
        headers=admin_headers,
        json={"items": [{"item_id": item_id, "quantity_received": 4}]},
    )
    assert part_res.status_code == 200
    assert part_res.json()["data"]["status"] == "partially_received"

    # Remaining receipt (8 units)
    full_res = client.post(
        f"/api/v1/inventory/purchase-orders/{po_id}/receive",
        headers=admin_headers,
        json={},
    )
    assert full_res.status_code == 200
    assert full_res.json()["data"]["status"] == "received"

    with SessionLocal() as db:
        assert db.get(Product, 1).stock == 32  # 20 + 12

    stocks_res = client.get(
        f"/api/v1/inventory/stocks?warehouse_id={wh_north_id}&product_id=1",
        headers=admin_headers,
    )
    assert stocks_res.status_code == 200
    assert stocks_res.json()["data"][0]["quantity"] == 12

    # Cancelled PO cannot be received
    po2_res = client.post(
        "/api/v1/inventory/purchase-orders",
        headers=admin_headers,
        json={
            "supplier_id": supplier_id,
            "warehouse_id": wh_north_id,
            "items": [{"product_id": 1, "quantity_ordered": 5, "unit_cost": "10.00"}],
        },
    )
    po2_id = po2_res.json()["data"]["id"]
    assert (
        client.post(f"/api/v1/inventory/purchase-orders/{po2_id}/cancel", headers=admin_headers).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/inventory/purchase-orders/{po2_id}/receive",
            headers=admin_headers,
            json={},
        ).status_code
        == 409
    )


def test_warehouse_transfer_dispatch_complete_and_cancel_restores_source(
    client, admin_headers
):
    wh_list = client.get("/api/inventory/warehouses", headers=admin_headers).json()["data"]
    wh_main_id = next(w["id"] for w in wh_list if w["code"] == "WH-MAIN")
    wh_dest_id = client.post(
        "/api/inventory/warehouses",
        headers=admin_headers,
        json={"code": "WH-SOUTH", "name": "South Branch"},
    ).json()["data"]["id"]

    # Ensure WH-MAIN has product stock synced via opening/adjustment
    client.post(
        "/api/inventory/adjustments",
        headers=admin_headers,
        json={"product_id": 1, "warehouse_id": wh_main_id, "quantity_delta": 5, "reason": "Init hub"},
    )
    # Product stock is 25, WH-MAIN has 25

    # Same warehouse transfer rejected
    same_wh = client.post(
        "/api/inventory/transfers",
        headers=admin_headers,
        json={
            "source_warehouse_id": wh_main_id,
            "destination_warehouse_id": wh_main_id,
            "items": [{"product_id": 1, "quantity": 2}],
        },
    )
    assert same_wh.status_code == 400

    # Transfer 7 units from WH-MAIN -> WH-SOUTH
    tr1 = client.post(
        "/api/inventory/transfers",
        headers=admin_headers,
        json={
            "source_warehouse_id": wh_main_id,
            "destination_warehouse_id": wh_dest_id,
            "items": [{"product_id": 1, "quantity": 7}],
        },
    )
    assert tr1.status_code == 201
    tr1_id = tr1.json()["data"]["id"]

    disp_res = client.post(
        f"/api/inventory/transfers/{tr1_id}/dispatch", headers=admin_headers
    )
    assert disp_res.status_code == 200
    assert disp_res.json()["data"]["status"] == "in_transit"

    comp_res = client.post(
        f"/api/inventory/transfers/{tr1_id}/complete", headers=admin_headers
    )
    assert comp_res.status_code == 200
    assert comp_res.json()["data"]["status"] == "completed"

    # Second transfer dispatched and then cancelled -> stock returns to WH-MAIN
    tr2_id = client.post(
        "/api/inventory/transfers",
        headers=admin_headers,
        json={
            "source_warehouse_id": wh_main_id,
            "destination_warehouse_id": wh_dest_id,
            "items": [{"product_id": 1, "quantity": 3}],
        },
    ).json()["data"]["id"]
    assert (
        client.post(f"/api/inventory/transfers/{tr2_id}/dispatch", headers=admin_headers).status_code
        == 200
    )
    cancel_res = client.post(
        f"/api/inventory/transfers/{tr2_id}/cancel", headers=admin_headers
    )
    assert cancel_res.status_code == 200
    assert cancel_res.json()["data"]["status"] == "cancelled"

    prod_stocks = client.get("/api/inventory/products/1/stocks", headers=admin_headers).json()["data"]
    qty_by_wh = {s["warehouse_id"]: s["quantity"] for s in prod_stocks}
    assert qty_by_wh[wh_main_id] == 18  # 25 - 7 (tr2's 3 returned)
    assert qty_by_wh[wh_dest_id] == 7

    ledger_res = client.get("/api/inventory/ledger", headers=admin_headers).json()["data"]
    assert ledger_res["trial_balance"]["balanced"] is True


def test_inventory_ledger_orm_immutability_guard(client, admin_headers):
    client.post(
        "/api/inventory/adjustments",
        headers=admin_headers,
        json={"product_id": 1, "quantity_delta": 2, "reason": "Immutable entry test"},
    )

    with SessionLocal() as db:
        entry = db.scalar(select(InventoryJournalEntry))
        line = db.scalar(select(InventoryLedgerLine))
        assert entry is not None and line is not None

        entry.reason = "Tampered reason"
        with pytest.raises(ValueError, match="immutable"):
            db.flush()
        db.rollback()

        db.delete(line)
        with pytest.raises(ValueError, match="immutable"):
            db.flush()
        db.rollback()
