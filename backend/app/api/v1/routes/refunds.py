from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_roles
from app.db.database import get_db
from app.models.user import User
from app.schemas.refund import (
    RefundApproveRequest,
    RefundCreateRequest,
    RefundProcessRequest,
    RefundRejectRequest,
)
from app.services.refund_service import RefundService

router = APIRouter(prefix="/refunds", tags=["Refunds & Accounting Ledger"])


@router.get("", status_code=status.HTTP_200_OK)
def list_refunds(
    status_filter: str | None = Query(None, alias="status"),
    search: str | None = Query(None),
    order_id: int | None = Query(None, gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    rows = RefundService.list_refunds(
        db, status_filter=status_filter, search=search, order_id=order_id
    )
    return {
        "success": True,
        "message": "Refund records retrieved successfully.",
        "data": [r.model_dump() for r in rows],
    }


@router.get("/ledger", status_code=status.HTTP_200_OK)
def list_refund_ledger(
    refund_id: int | None = Query(None, gt=0),
    account_code: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    ledger = RefundService.list_ledger(
        db,
        refund_id=refund_id,
        account_code=account_code,
        page=page,
        limit=limit,
    )
    return {
        "success": True,
        "message": "Refund accounting ledger retrieved successfully.",
        "data": ledger.model_dump(),
    }


@router.get("/{refund_identifier}", status_code=status.HTTP_200_OK)
def get_refund(
    refund_identifier: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    refund = RefundService.get_refund(db, refund_identifier)
    return {
        "success": True,
        "message": "Refund details retrieved successfully.",
        "data": refund.model_dump(),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_refund(
    payload: RefundCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    refund = RefundService.create_refund(db, payload, actor=current_user)
    return {
        "success": True,
        "message": "Refund request recorded.",
        "data": refund.model_dump(),
    }


@router.post("/{refund_identifier}/approve", status_code=status.HTTP_200_OK)
def approve_refund(
    refund_identifier: str,
    payload: RefundApproveRequest = RefundApproveRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    refund = RefundService.approve_refund(db, refund_identifier, payload, actor=current_user)
    return {
        "success": True,
        "message": "Refund approved and accrued in accounting ledger.",
        "data": refund.model_dump(),
    }


@router.post("/{refund_identifier}/process", status_code=status.HTTP_200_OK)
def process_refund(
    refund_identifier: str,
    payload: RefundProcessRequest = RefundProcessRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    refund = RefundService.process_refund(db, refund_identifier, payload, actor=current_user)
    return {
        "success": True,
        "message": "Refund processed and settled in accounting ledger.",
        "data": refund.model_dump(),
    }


@router.post("/{refund_identifier}/reject", status_code=status.HTTP_200_OK)
def reject_refund(
    refund_identifier: str,
    payload: RefundRejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    refund = RefundService.reject_refund(db, refund_identifier, payload, actor=current_user)
    return {
        "success": True,
        "message": "Refund rejected.",
        "data": refund.model_dump(),
    }
