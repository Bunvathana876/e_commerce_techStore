from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.address import AddressCreate, AddressUpdate
from app.services.address_service import AddressService

router = APIRouter(prefix="/addresses", tags=["Addresses"])


@router.get("", status_code=status.HTTP_200_OK)
def list_addresses(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    addresses = AddressService.get_addresses(db, current_user.id)
    return {
        "success": True,
        "message": "Addresses retrieved successfully.",
        "data": [a.model_dump() for a in addresses],
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_address(
    request: AddressCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    address = AddressService.create_address(db, current_user.id, request)
    return {
        "success": True,
        "message": "Address created successfully.",
        "data": address.model_dump(),
    }


@router.put("/{address_id}", status_code=status.HTTP_200_OK)
def update_address(
    address_id: int,
    request: AddressUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    address = AddressService.update_address(db, current_user.id, address_id, request)
    return {
        "success": True,
        "message": "Address updated successfully.",
        "data": address.model_dump(),
    }


@router.delete("/{address_id}", status_code=status.HTTP_200_OK)
def delete_address(
    address_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    AddressService.delete_address(db, current_user.id, address_id)
    return {
        "success": True,
        "message": "Address deleted successfully.",
    }


@router.put("/{address_id}/default", status_code=status.HTTP_200_OK)
def set_default_address(
    address_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    address = AddressService.set_default(db, current_user.id, address_id)
    return {
        "success": True,
        "message": "Default address updated.",
        "data": address.model_dump(),
    }

