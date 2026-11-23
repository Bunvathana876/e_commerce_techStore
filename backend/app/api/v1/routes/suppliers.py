from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_roles
from app.db.database import get_db
from app.models.user import User
from app.schemas.supplier import SupplierCreate, SupplierUpdate
from app.services.supplier_service import SupplierService

router = APIRouter(prefix="/suppliers", tags=["Suppliers"])


@router.get("", status_code=status.HTTP_200_OK)
def list_suppliers(
    status_filter: str | None = Query(None, alias="status"),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    suppliers = SupplierService.list_suppliers(
        db, status_filter=status_filter, search=search
    )
    return {
        "success": True,
        "message": "Suppliers retrieved successfully.",
        "data": [s.model_dump() for s in suppliers],
    }


@router.get("/{supplier_id}", status_code=status.HTTP_200_OK)
def get_supplier(
    supplier_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    supplier = SupplierService.get_supplier(db, supplier_id)
    return {
        "success": True,
        "message": "Supplier retrieved successfully.",
        "data": supplier.model_dump(),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_supplier(
    payload: SupplierCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    supplier = SupplierService.create_supplier(db, payload)
    return {
        "success": True,
        "message": "Supplier created successfully.",
        "data": supplier.model_dump(),
    }


@router.put("/{supplier_id}", status_code=status.HTTP_200_OK)
def update_supplier(
    supplier_id: int,
    payload: SupplierUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    supplier = SupplierService.update_supplier(db, supplier_id, payload)
    return {
        "success": True,
        "message": "Supplier updated successfully.",
        "data": supplier.model_dump(),
    }


@router.delete("/{supplier_id}", status_code=status.HTTP_200_OK)
def delete_supplier(
    supplier_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    SupplierService.delete_supplier(db, supplier_id)
    return {
        "success": True,
        "message": f"Supplier #{supplier_id} deleted successfully.",
        "data": None,
    }
