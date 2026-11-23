from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_roles
from app.db.database import get_db
from app.models.user import User
from app.schemas.inventory import (
    PurchaseOrderCreate,
    PurchaseOrderReceiveRequest,
    StockAdjustmentRequest,
    WarehouseCreate,
    WarehouseTransferCreate,
    WarehouseUpdate,
)
from app.services.inventory_service import InventoryService

router = APIRouter(prefix="/inventory", tags=["Inventory & Warehouses"])


@router.get("/warehouses", status_code=status.HTTP_200_OK)
def list_warehouses(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    warehouses = InventoryService.list_warehouses(db)
    return {
        "success": True,
        "message": "Warehouses retrieved successfully.",
        "data": [w.model_dump() for w in warehouses],
    }


@router.post("/warehouses", status_code=status.HTTP_201_CREATED)
def create_warehouse(
    payload: WarehouseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    wh = InventoryService.create_warehouse(db, payload)
    return {
        "success": True,
        "message": "Warehouse created successfully.",
        "data": wh.model_dump(),
    }


@router.put("/warehouses/{warehouse_id}", status_code=status.HTTP_200_OK)
def update_warehouse(
    warehouse_id: int,
    payload: WarehouseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    wh = InventoryService.update_warehouse(db, warehouse_id, payload)
    return {
        "success": True,
        "message": "Warehouse updated successfully.",
        "data": wh.model_dump(),
    }


@router.get("/stocks", status_code=status.HTTP_200_OK)
def list_stocks(
    warehouse_id: int | None = Query(None, gt=0),
    product_id: int | None = Query(None, gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    stocks = InventoryService.list_warehouse_stocks(
        db, warehouse_id=warehouse_id, product_id=product_id
    )
    return {
        "success": True,
        "message": "Warehouse stocks retrieved successfully.",
        "data": [s.model_dump() for s in stocks],
    }


@router.get("/products/{product_id}/stocks", status_code=status.HTTP_200_OK)
def get_product_stocks(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    stocks = InventoryService.list_warehouse_stocks(db, product_id=product_id)
    return {
        "success": True,
        "message": "Product warehouse breakdown retrieved successfully.",
        "data": [s.model_dump() for s in stocks],
    }


@router.post("/adjustments", status_code=status.HTTP_201_CREATED)
def create_stock_adjustment(
    payload: StockAdjustmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    entry = InventoryService.create_adjustment(db, payload, actor_user_id=current_user.id)
    return {
        "success": True,
        "message": "Stock adjustment recorded in double-entry inventory ledger.",
        "data": entry.model_dump(),
    }


@router.get("/ledger", status_code=status.HTTP_200_OK)
def list_inventory_ledger(
    product_id: int | None = Query(None, gt=0),
    warehouse_id: int | None = Query(None, gt=0),
    entry_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    ledger = InventoryService.list_ledger(
        db,
        product_id=product_id,
        warehouse_id=warehouse_id,
        entry_type=entry_type,
        page=page,
        limit=limit,
    )
    return {
        "success": True,
        "message": "Inventory ledger retrieved successfully.",
        "data": ledger.model_dump(),
    }


@router.get("/purchase-orders", status_code=status.HTTP_200_OK)
def list_purchase_orders(
    status_filter: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    rows = InventoryService.list_purchase_orders(db, status_filter=status_filter)
    return {
        "success": True,
        "message": "Purchase orders retrieved successfully.",
        "data": [row.model_dump() for row in rows],
    }


@router.post("/purchase-orders", status_code=status.HTTP_201_CREATED)
def create_purchase_order(
    payload: PurchaseOrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    po = InventoryService.create_purchase_order(db, payload, actor_user_id=current_user.id)
    return {
        "success": True,
        "message": "Purchase order created successfully.",
        "data": po.model_dump(),
    }


@router.post("/purchase-orders/{po_id}/order", status_code=status.HTTP_200_OK)
def order_purchase_order(
    po_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    po = InventoryService.mark_purchase_order_ordered(db, po_id)
    return {
        "success": True,
        "message": "Purchase order marked as ordered.",
        "data": po.model_dump(),
    }


@router.post("/purchase-orders/{po_id}/receive", status_code=status.HTTP_200_OK)
def receive_purchase_order(
    po_id: int,
    payload: PurchaseOrderReceiveRequest = PurchaseOrderReceiveRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    po = InventoryService.receive_purchase_order(
        db, po_id, payload, actor_user_id=current_user.id
    )
    return {
        "success": True,
        "message": "Purchase order stock received and posted to inventory ledger.",
        "data": po.model_dump(),
    }


@router.post("/purchase-orders/{po_id}/cancel", status_code=status.HTTP_200_OK)
def cancel_purchase_order(
    po_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    po = InventoryService.cancel_purchase_order(db, po_id)
    return {
        "success": True,
        "message": "Purchase order cancelled.",
        "data": po.model_dump(),
    }


@router.get("/transfers", status_code=status.HTTP_200_OK)
def list_warehouse_transfers(
    status_filter: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    rows = InventoryService.list_transfers(db, status_filter=status_filter)
    return {
        "success": True,
        "message": "Warehouse transfers retrieved successfully.",
        "data": [row.model_dump() for row in rows],
    }


@router.post("/transfers", status_code=status.HTTP_201_CREATED)
def create_warehouse_transfer(
    payload: WarehouseTransferCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    transfer = InventoryService.create_transfer(db, payload, actor_user_id=current_user.id)
    return {
        "success": True,
        "message": "Warehouse transfer created successfully.",
        "data": transfer.model_dump(),
    }


@router.post("/transfers/{transfer_id}/dispatch", status_code=status.HTTP_200_OK)
def dispatch_warehouse_transfer(
    transfer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    transfer = InventoryService.dispatch_transfer(
        db, transfer_id, actor_user_id=current_user.id
    )
    return {
        "success": True,
        "message": "Warehouse transfer dispatched to in-transit ledger account.",
        "data": transfer.model_dump(),
    }


@router.post("/transfers/{transfer_id}/complete", status_code=status.HTTP_200_OK)
def complete_warehouse_transfer(
    transfer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    transfer = InventoryService.complete_transfer(
        db, transfer_id, actor_user_id=current_user.id
    )
    return {
        "success": True,
        "message": "Warehouse transfer completed at destination.",
        "data": transfer.model_dump(),
    }


@router.post("/transfers/{transfer_id}/cancel", status_code=status.HTTP_200_OK)
def cancel_warehouse_transfer(
    transfer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    transfer = InventoryService.cancel_transfer(
        db, transfer_id, actor_user_id=current_user.id
    )
    return {
        "success": True,
        "message": "Warehouse transfer cancelled.",
        "data": transfer.model_dump(),
    }
