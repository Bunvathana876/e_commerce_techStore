"""Tests for independent Suppliers CRUD, Refund accounting ledger, and executive/inventory reports."""

from decimal import Decimal
import pytest
from sqlalchemy import func, select

from app.db.database import SessionLocal
from app.models.product import Product
from app.models.refund import RefundLedgerEntry
from app.models.seller import Seller


def test_dedicated_suppliers_are_independent_of_sellers(client, admin_headers, headers):
    # Seller & customer cannot access suppliers endpoints
    assert client.get("/api/v1/suppliers", headers=headers(2)).status_code == 403
    assert client.get("/api/v1/suppliers", headers=headers(4)).status_code == 403

    with SessionLocal() as db:
        sellers_before = db.scalar(select(func.count(Seller.id)))

    create_res = client.post(
        "/api/v1/suppliers",
        headers=admin_headers,
        json={
            "name": "Indochina Hardware Wholesale",
            "contact_name": "Vanna Meas",
            "email": "vanna@indochinawholesale.com",
            "phone": "+85512000111",
            "payment_terms": "Net 45",
            "lead_time_days": 10,
        },
    )
    assert create_res.status_code == 201, create_res.text
    supplier = create_res.json()["data"]
    sid = supplier["id"]
    assert supplier["code"].startswith("SUP-")

    with SessionLocal() as db:
        sellers_after = db.scalar(select(func.count(Seller.id)))
        assert sellers_after == sellers_before

    # Update supplier (valid status) & reject unsupported status
    bad_status = client.put(
        f"/api/v1/suppliers/{sid}",
        headers=admin_headers,
        json={"status": "On Hold"},
    )
    assert bad_status.status_code == 400

    upd_res = client.put(
        f"/api/v1/suppliers/{sid}",
        headers=admin_headers,
        json={"payment_terms": "Net 60", "status": "Inactive"},
    )
    assert upd_res.status_code == 200
    assert upd_res.json()["data"]["payment_terms"] == "Net 60"
    assert upd_res.json()["data"]["status"] == "Inactive"

    # Inactive supplier cannot receive new POs (409), re-activate before creating PO
    wh_id = client.get("/api/inventory/warehouses", headers=admin_headers).json()["data"][0]["id"]
    inactive_po = client.post(
        "/api/inventory/purchase-orders",
        headers=admin_headers,
        json={
            "supplier_id": sid,
            "warehouse_id": wh_id,
            "items": [{"product_id": 1, "quantity_ordered": 5, "unit_cost": "10.00"}],
        },
    )
    assert inactive_po.status_code == 409

    assert (
        client.put(
            f"/api/v1/suppliers/{sid}",
            headers=admin_headers,
            json={"status": "Active"},
        ).status_code
        == 200
    )

    # Supplier linked to a PO cannot be deleted
    po_res = client.post(
        "/api/inventory/purchase-orders",
        headers=admin_headers,
        json={
            "supplier_id": sid,
            "warehouse_id": wh_id,
            "items": [{"product_id": 1, "quantity_ordered": 5, "unit_cost": "10.00"}],
        },
    )
    assert po_res.status_code == 201

    del_blocked = client.delete(f"/api/v1/suppliers/{sid}", headers=admin_headers)
    assert del_blocked.status_code in (400, 409)

    # Unlinked supplier can be deleted
    sup2_id = client.post(
        "/api/v1/suppliers",
        headers=admin_headers,
        json={
            "name": "Temp Vendor",
            "contact_name": "Test Contact",
            "email": "temp@vendor.com",
        },
    ).json()["data"]["id"]
    del_ok = client.delete(f"/api/v1/suppliers/{sup2_id}", headers=admin_headers)
    assert del_ok.status_code == 200


def test_refund_workflow_accounting_ledger_and_restock(client, headers, admin_headers):
    # Create & settle a COD order first
    order_res = client.post(
        "/api/v1/orders",
        headers=headers(2),
        json={
            "shipping_address": "123 Norodom Blvd, Phnom Penh",
            "payment_method": "Cash on Delivery",
            "items": [{"product_id": 1, "quantity": 2}],  # $40 + shipping
        },
    )
    assert order_res.status_code == 201
    order = order_res.json()["data"]
    oid = order["id"]
    order_total = Decimal(str(order["total"]))

    with SessionLocal() as db:
        assert db.get(Product, 1).stock == 18

    # Unpaid order cannot be refunded (409)
    unpaid_ref = client.post(
        "/api/v1/refunds",
        headers=admin_headers,
        json={
            "order_id": oid,
            "amount": "5.00",
            "refund_method": "Cash on Delivery",
            "reason": "Before payment",
        },
    )
    assert unpaid_ref.status_code == 409

    # Deliver & mark COD order as paid
    assert client.put(f"/api/v1/orders/{oid}/status", headers=admin_headers, json={"status": "processing"}).status_code == 200
    assert client.put(f"/api/v1/orders/{oid}/status", headers=admin_headers, json={"status": "shipped"}).status_code == 200
    assert client.put(
        f"/api/v1/orders/{oid}/status",
        headers=admin_headers,
        json={"status": "delivered", "payment_status": "paid", "reason": "Cash collected"},
    ).status_code == 200

    # Over-refund attempt rejected (409)
    over_res = client.post(
        "/api/v1/refunds",
        headers=admin_headers,
        json={
            "order_id": oid,
            "amount": float(order_total + Decimal("10.00")),
            "refund_method": "Cash on Delivery",
            "reason": "Over-refund test",
        },
    )
    assert over_res.status_code == 409

    # Deprecated refund method rejected
    bad_method_res = client.post(
        "/api/v1/refunds",
        headers=admin_headers,
        json={
            "order_id": oid,
            "amount": "10.00",
            "refund_method": "ABA / KHQR",
            "reason": "Unsupported refund method",
        },
    )
    assert bad_method_res.status_code == 400

    # Create valid full refund with restock_items=True
    ref_res = client.post(
        "/api/v1/refunds",
        headers=admin_headers,
        json={
            "order_id": oid,
            "refund_method": "Cash on Delivery",
            "reason": "Damaged in transit",
            "restock_items": True,
        },
    )
    assert ref_res.status_code == 201, ref_res.text
    refund = ref_res.json()["data"]
    ref_num = refund["refund_number"]
    assert refund["status"] == "requested"

    # Approve refund -> posts Dr 4100 / Cr 2100 accrual entries
    app_res = client.post(f"/api/v1/refunds/{ref_num}/approve", headers=admin_headers)
    assert app_res.status_code == 200
    app_data = app_res.json()["data"]
    assert app_data["status"] == "approved"
    assert len(app_data["ledger_entries"]) == 2
    assert {e["account_code"] for e in app_data["ledger_entries"]} == {"4100", "2100"}

    # Process refund -> posts Dr 2100 / Cr 1010 clearing, marks order refunded & restocks
    proc_res = client.post(f"/api/v1/refunds/{ref_num}/process", headers=admin_headers)
    assert proc_res.status_code == 200
    proc_data = proc_res.json()["data"]
    assert proc_data["status"] == "processed"
    assert proc_data["restocked"] is True
    assert proc_data["order_payment_status"] == "refunded"
    assert len(proc_data["ledger_entries"]) == 4
    assert {e["account_code"] for e in proc_data["ledger_entries"]} == {"4100", "2100", "1010"}

    with SessionLocal() as db:
        # Stock restored from 18 back to 20
        assert db.get(Product, 1).stock == 20

    # Trial balance across refund GL must match
    gl_res = client.get("/api/v1/refunds/ledger", headers=admin_headers)
    assert gl_res.status_code == 200
    tb = gl_res.json()["data"]["trial_balance"]
    assert tb["balanced"] is True
    assert Decimal(str(tb["total_debits"])) == Decimal(str(tb["total_credits"]))


def test_refund_rejection_and_orm_immutability_guard(client, headers, admin_headers):
    from app.models.order import Order

    order_res = client.post(
        "/api/orders",
        headers=headers(2),
        json={
            "shipping_address": "123 Norodom Blvd, Phnom Penh",
            "payment_method": "Credit / Debit Card",
            "items": [{"product_id": 1, "quantity": 1}],
        },
    )
    oid = order_res.json()["data"]["id"]
    with SessionLocal() as db:
        order = db.get(Order, oid)
        order.payment_status = "paid"
        db.commit()

    # Create & reject a refund
    r1 = client.post(
        "/api/refunds",
        headers=admin_headers,
        json={
            "order_id": oid,
            "amount": "5.00",
            "refund_method": "Credit / Debit Card",
            "reason": "Minor scratch claim",
        },
    ).json()["data"]
    rej_res = client.post(
        f"/api/refunds/{r1['refund_number']}/reject",
        headers=admin_headers,
        json={"reason": "Out of warranty"},
    )
    assert rej_res.status_code == 200
    assert rej_res.json()["data"]["status"] == "rejected"

    # Approve a second refund to populate RefundLedgerEntry and test ORM immutability
    r2 = client.post(
        "/api/refunds",
        headers=admin_headers,
        json={
            "order_id": oid,
            "amount": "5.00",
            "refund_method": "Credit / Debit Card",
            "reason": "Partial credit",
        },
    ).json()["data"]
    assert client.post(f"/api/refunds/{r2['refund_number']}/approve", headers=admin_headers).status_code == 200

    with SessionLocal() as db:
        entry = db.scalar(select(RefundLedgerEntry))
        assert entry is not None
        entry.memo = "Tampered memo"
        with pytest.raises(ValueError, match="immutable"):
            db.flush()
        db.rollback()

        db.delete(entry)
        with pytest.raises(ValueError, match="immutable"):
            db.flush()
        db.rollback()


def test_executive_and_inventory_reports_and_csv_exports(
    client, headers, admin_headers
):
    # Non-admin denied
    assert client.get("/api/v1/reports/executive", headers=headers(2)).status_code == 403

    # Create an order & a settled refund
    order_res = client.post(
        "/api/v1/orders",
        headers=headers(2),
        json={
            "shipping_address": "123 Norodom Blvd",
            "payment_method": "Cash on Delivery",
            "items": [{"product_id": 1, "quantity": 2}],
        },
    )
    oid = order_res.json()["data"]["id"]
    client.put(f"/api/v1/orders/{oid}/status", headers=admin_headers, json={"status": "processing"})
    client.put(f"/api/v1/orders/{oid}/status", headers=admin_headers, json={"status": "shipped"})
    client.put(
        f"/api/v1/orders/{oid}/status",
        headers=admin_headers,
        json={"status": "delivered", "payment_status": "paid", "reason": "Cash collected"},
    )

    ref_num = client.post(
        "/api/v1/refunds",
        headers=admin_headers,
        json={"order_id": oid, "amount": "10.00", "refund_method": "Cash", "reason": "Partial credit"},
    ).json()["data"]["refund_number"]
    client.post(f"/api/v1/refunds/{ref_num}/approve", headers=admin_headers)
    client.post(f"/api/v1/refunds/{ref_num}/process", headers=admin_headers)

    exec_res = client.get("/api/v1/reports/executive?days=30", headers=admin_headers)
    assert exec_res.status_code == 200
    exec_data = exec_res.json()["data"]
    assert Decimal(str(exec_data["settled_refunds_total"])) >= Decimal("10.00")
    assert Decimal(str(exec_data["net_revenue"])) == Decimal(str(exec_data["gross_paid_revenue"])) - Decimal(str(exec_data["settled_refunds_total"]))

    inv_res = client.get("/api/v1/reports/inventory", headers=admin_headers)
    assert inv_res.status_code == 200
    inv_data = inv_res.json()["data"]
    assert inv_data["ledger_balanced"] is True
    assert inv_data["total_warehouses"] >= 1

    inv_csv = client.get("/api/v1/reports/ledger-export?ledger=inventory", headers=admin_headers)
    assert inv_csv.status_code == 200
    assert "text/csv" in inv_csv.headers["content-type"]
    assert "entry_number" in inv_csv.text

    ref_csv = client.get("/api/v1/reports/ledger-export?ledger=refunds", headers=admin_headers)
    assert ref_csv.status_code == 200
    assert "journal_ref" in ref_csv.text
