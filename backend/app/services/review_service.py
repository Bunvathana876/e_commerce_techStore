from datetime import datetime
from decimal import Decimal
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.order import Order, OrderItem
from app.models.product import Product
from app.models.review import Review
from app.schemas.review import ReviewCreateRequest, ReviewResponse


class ReviewService:
    @staticmethod
    def _recalculate_product_rating(db: Session, product_id: int) -> None:
        avg_rating = db.scalar(
            select(func.avg(Review.rating)).where(
                Review.product_id == product_id,
                Review.status == "approved",
            )
        )
        product = db.scalar(select(Product).where(Product.id == product_id))
        if product:
            product.rating = Decimal(str(round(avg_rating, 2))) if avg_rating else Decimal("0.00")
            db.commit()

    @staticmethod
    def list_reviews(
        db: Session,
        status_filter: str | None = None,
        rating_filter: int | None = None,
        product_id: int | None = None,
    ) -> list[ReviewResponse]:
        query = select(Review).options(
            selectinload(Review.user),
            selectinload(Review.product),
        )

        if status_filter and status_filter.lower() != "all":
            query = query.where(Review.status == status_filter.lower())

        if rating_filter:
            query = query.where(Review.rating == rating_filter)

        if product_id:
            query = query.where(Review.product_id == product_id)

        query = query.order_by(Review.created_at.desc())

        reviews = list(db.scalars(query).all())
        return [ReviewResponse.model_validate(r) for r in reviews]

    @staticmethod
    def get_review_by_id(db: Session, review_id: int) -> ReviewResponse:
        review = db.scalar(
            select(Review)
            .options(
                selectinload(Review.user),
                selectinload(Review.product),
            )
            .where(Review.id == review_id)
        )
        if not review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Review #{review_id} not found.",
            )
        return ReviewResponse.model_validate(review)

    @staticmethod
    def create_review(
        db: Session,
        user_id: int,
        product_id: int,
        request: ReviewCreateRequest,
    ) -> ReviewResponse:
        product = db.scalar(select(Product).where(Product.id == product_id))
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product #{product_id} not found.",
            )

        if request.order_id is not None:
            owned_order = db.scalar(select(Order.id).join(OrderItem).where(
                Order.id == request.order_id, Order.user_id == user_id,
                OrderItem.product_id == product_id,
            ))
            if owned_order is None:
                raise HTTPException(status_code=404, detail="Order item not found.")

        new_review = Review(
            product_id=product_id,
            user_id=user_id,
            order_id=request.order_id,
            rating=request.rating,
            comment=request.comment.strip(),
            status="pending",
        )
        db.add(new_review)
        db.commit()
        db.refresh(new_review)

        try:
            from app.models.notification import Notification
            notif = Notification(
                type="review",
                title=f"New {new_review.rating}★ Review Submitted ⭐",
                message=f"Review on {product.name}: '{new_review.comment[:80]}'",
                link=f"/admin/reviews",
                read=False,
            )
            db.add(notif)
            db.commit()
        except Exception:
            pass

        loaded_review = db.scalar(
            select(Review)
            .options(
                selectinload(Review.user),
                selectinload(Review.product),
            )
            .where(Review.id == new_review.id)
        )
        return ReviewResponse.model_validate(loaded_review)

    @staticmethod
    def update_review_status(
        db: Session,
        review_id: int,
        new_status: str,
    ) -> ReviewResponse:
        allowed = ["pending", "approved", "rejected"]
        if new_status.lower() not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status '{new_status}'. Allowed statuses: {', '.join(allowed)}",
            )

        review = db.scalar(
            select(Review)
            .options(
                selectinload(Review.user),
                selectinload(Review.product),
            )
            .where(Review.id == review_id)
        )
        if not review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Review #{review_id} not found.",
            )

        review.status = new_status.lower()
        db.commit()
        db.refresh(review)

        # Recalculate average rating of the associated product
        ReviewService._recalculate_product_rating(db, review.product_id)

        return ReviewResponse.model_validate(review)

    @staticmethod
    def reply_review(
        db: Session,
        review_id: int,
        admin_reply_text: str,
    ) -> ReviewResponse:
        review = db.scalar(
            select(Review)
            .options(
                selectinload(Review.user),
                selectinload(Review.product),
            )
            .where(Review.id == review_id)
        )
        if not review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Review #{review_id} not found.",
            )

        review.admin_reply = admin_reply_text.strip()
        review.admin_replied_at = datetime.now()
        db.commit()
        db.refresh(review)

        return ReviewResponse.model_validate(review)

    @staticmethod
    def delete_review(db: Session, review_id: int) -> None:
        review = db.scalar(select(Review).where(Review.id == review_id))
        if not review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Review #{review_id} not found.",
            )

        product_id = review.product_id
        db.delete(review)
        db.commit()

        # Recalculate average rating after deletion
        ReviewService._recalculate_product_rating(db, product_id)
