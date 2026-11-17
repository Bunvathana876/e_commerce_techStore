from fastapi import APIRouter, Depends, File, Query, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_roles
from app.db.database import get_db
from app.models.user import User
from app.services.upload_service import UploadService

router = APIRouter(prefix="/upload", tags=["Upload"])


@router.post("/image", status_code=status.HTTP_201_CREATED)
async def upload_image(
    request: Request,
    file: UploadFile = File(...),
    product_id: int | None = Query(None, ge=1),
    seller_id: int | None = Query(None, ge=1),
    current_user: User = Depends(require_roles("admin", "seller")),
    db: Session = Depends(get_db),
):
    """
    Upload a validated product raster image (JPEG, PNG, or WebP) to the server.
    Returns the static URL to access the uploaded image.
    """
    try:
        UploadService.authorize_upload(
            db=db,
            current_user=current_user,
            product_id=product_id,
            seller_id=seller_id,
        )
        unique_filename = UploadService.validate_and_store_product_image(file)
    finally:
        await file.close()

    relative_path = f"/uploads/products/{unique_filename}"
    base_url = str(request.base_url).rstrip("/")
    if "0.0.0.0" in base_url:
        base_url = base_url.replace("0.0.0.0", "localhost")

    full_url = f"{base_url}{relative_path}"

    return {
        "success": True,
        "message": "Image uploaded successfully.",
        "data": {
            "filename": unique_filename,
            "url": full_url,
            "relative_url": relative_path,
        },
    }
