from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_roles
from app.db.database import get_db
from app.models.user import User
from app.services.reporting_service import ReportingService

router = APIRouter(prefix="/reports", tags=["Administrative Reporting"])


@router.get("/executive", status_code=status.HTTP_200_OK)
def get_executive_report(
    days: int = Query(30, ge=1, le=3650),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    report = ReportingService.get_executive_report(db, days=days)
    return {
        "success": True,
        "message": "Executive report retrieved successfully.",
        "data": report.model_dump(),
    }


@router.get("/inventory", status_code=status.HTTP_200_OK)
def get_inventory_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    report = ReportingService.get_inventory_report(db)
    return {
        "success": True,
        "message": "Inventory report retrieved successfully.",
        "data": report.model_dump(),
    }


@router.get("/ledger-export", status_code=status.HTTP_200_OK)
def export_ledger_csv(
    ledger: str = Query(..., description="inventory or refunds"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    csv_body = ReportingService.export_ledger_csv(db, ledger)
    clean_name = "inventory" if ledger.strip().lower() == "inventory" else "refunds"
    return Response(
        content=csv_body,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{clean_name}-ledger.csv"',
            "Cache-Control": "no-store",
        },
    )
