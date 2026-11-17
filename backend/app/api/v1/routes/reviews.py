from app.services.authorization_service import AuthorizationService
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_roles, get_optional_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.review import (
    ReviewCreateRequest,
    ReviewResponse,
    ReviewReplyRequest,
    ReviewStatusUpdateRequest,
)
from app.services.review_service import ReviewService

router = APIRouter(prefix="/reviews", tags=["Reviews"])


@router.get("", status_code=status.HTTP_200_OK)
def list_reviews(
    status: str | None = None,
    rating: int | None = None,
    product_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    if not AuthorizationService.is_admin(current_user):
        status = "approved"
    reviews = ReviewService.list_reviews(
        db, status_filter=status, rating_filter=rating, product_id=product_id
    )
    return {
        "success": True,
        "message": "Reviews retrieved successfully.",
        "data": [_review_response(r, current_user) for r in reviews],
    }


@router.get("/{review_id}", status_code=status.HTTP_200_OK)
def get_review_by_id(
    review_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    review = ReviewService.get_review_by_id(db, review_id=review_id)
    if not AuthorizationService.is_admin(current_user) and review.status != "approved":
        if current_user is None or review.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Review not found.")
    return {
        "success": True,
        "message": "Review details retrieved successfully.",
        "data": _review_response(review, current_user),
    }


@router.post("/product/{product_id}", status_code=status.HTTP_201_CREATED)
def create_review(
    product_id: int,
    request: ReviewCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    review = ReviewService.create_review(
        db, user_id=current_user.id, product_id=product_id, request=request
    )
    return {
        "success": True,
        "message": "Review submitted successfully and pending moderation.",
        "data": _review_response(review, current_user),
    }


@router.put("/{review_id}/status", status_code=status.HTTP_200_OK)
def update_review_status(
    review_id: int,
    request: ReviewStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    updated = ReviewService.update_review_status(
        db, review_id=review_id, new_status=request.status
    )
    return {
        "success": True,
        "message": f"Review #{review_id} status updated to '{request.status}'.",
        "data": _review_response(updated, current_user),
    }


@router.put("/{review_id}/reply", status_code=status.HTTP_200_OK)
def reply_to_review(
    review_id: int,
    request: ReviewReplyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "seller")),
):
    review = ReviewService.get_review_by_id(db, review_id)
    AuthorizationService.require_product(db, current_user, review.product_id)
    updated = ReviewService.reply_review(
        db, review_id=review_id, admin_reply_text=request.admin_reply
    )
    return {
        "success": True,
        "message": f"Reply added to review #{review_id}.",
        "data": _review_response(updated, current_user),
    }


@router.delete("/{review_id}", status_code=status.HTTP_200_OK)
def delete_review(
    review_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    ReviewService.delete_review(db, review_id=review_id)
    return {
        "success": True,
        "message": f"Review #{review_id} deleted successfully.",
        "data": None,
    }


def _review_response(review: ReviewResponse, user: User | None) -> dict:
    data = review.model_dump()
    if not AuthorizationService.is_admin(user):
        if data.get("user"):
            data["user"].pop("email", None)
        data.pop("order_id", None)
    return data
