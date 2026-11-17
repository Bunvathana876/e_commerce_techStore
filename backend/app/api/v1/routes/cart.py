from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.cart import (
    CartItemAddRequest,
    CartItemUpdateRequest,
    CartReconcileRequest,
)
from app.services.cart_service import CartService

router = APIRouter(prefix="/cart", tags=["Cart"])


@router.get("", status_code=status.HTTP_200_OK)
def get_cart(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cart = CartService.get_cart(db, current_user.id)
    return {
        "success": True,
        "message": "Cart retrieved successfully.",
        "data": cart.model_dump(),
    }


@router.post("", status_code=status.HTTP_200_OK)
@router.post("/items", status_code=status.HTTP_200_OK)
def add_to_cart(
    request: CartItemAddRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cart = CartService.add_item(db, current_user.id, request)
    return {
        "success": True,
        "message": "Item added to cart.",
        "data": cart.model_dump(),
    }


@router.put("/items/{item_id}", status_code=status.HTTP_200_OK)
def update_cart_item(
    item_id: int,
    request: CartItemUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cart = CartService.update_item(db, current_user.id, item_id, request)
    return {
        "success": True,
        "message": "Cart item updated.",
        "data": cart.model_dump(),
    }


@router.delete("/items/{item_id}", status_code=status.HTTP_200_OK)
def remove_cart_item(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cart = CartService.remove_item(db, current_user.id, item_id)
    return {
        "success": True,
        "message": "Item removed from cart.",
        "data": cart.model_dump(),
    }


@router.put("/products/{product_id}", status_code=status.HTTP_200_OK)
@router.put("/product/{product_id}", status_code=status.HTTP_200_OK)
def update_cart_item_by_product(
    product_id: int,
    request: CartItemUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cart = CartService.update_item_by_product_id(db, current_user.id, product_id, request)
    return {
        "success": True,
        "message": "Cart item updated.",
        "data": cart.model_dump(),
    }


@router.delete("/products/{product_id}", status_code=status.HTTP_200_OK)
@router.delete("/product/{product_id}", status_code=status.HTTP_200_OK)
def remove_cart_item_by_product(
    product_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cart = CartService.remove_item_by_product_id(db, current_user.id, product_id)
    return {
        "success": True,
        "message": "Item removed from cart.",
        "data": cart.model_dump(),
    }


@router.put("/{item_id}", status_code=status.HTTP_200_OK)
def update_cart_item_legacy(
    item_id: int,
    request: CartItemUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cart = CartService.update_item_resolved(db, current_user.id, item_id, request)
    return {
        "success": True,
        "message": "Cart item updated.",
        "data": cart.model_dump(),
    }


@router.delete("/{item_id}", status_code=status.HTTP_200_OK)
def remove_cart_item_legacy(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cart = CartService.remove_item_resolved(db, current_user.id, item_id)
    return {
        "success": True,
        "message": "Item removed from cart.",
        "data": cart.model_dump(),
    }


@router.delete("", status_code=status.HTTP_200_OK)
def clear_cart(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    CartService.clear_cart(db, current_user.id)
    return {
        "success": True,
        "message": "Cart cleared successfully.",
        "data": {
            "items": [],
            "total_items": 0,
            "subtotal": 0.0,
        },
    }


@router.put("", status_code=status.HTTP_200_OK)
@router.post("/reconcile", status_code=status.HTTP_200_OK)
def reconcile_cart(
    request: CartReconcileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cart = CartService.reconcile_cart(db, current_user.id, request.items)
    return {
        "success": True,
        "message": "Cart reconciled successfully.",
        "data": cart.model_dump(),
    }

