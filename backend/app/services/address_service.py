from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.address import Address
from app.schemas.address import AddressCreate, AddressResponse, AddressUpdate


class AddressService:
    @staticmethod
    def get_addresses(db: Session, user_id: int) -> list[AddressResponse]:
        addresses = list(
            db.scalars(
                select(Address)
                .where(Address.user_id == user_id)
                .order_by(Address.is_default.desc(), Address.created_at.desc())
            ).all()
        )
        return [AddressResponse.model_validate(a) for a in addresses]

    @staticmethod
    def create_address(db: Session, user_id: int, data: AddressCreate) -> AddressResponse:
        existing_count = db.scalar(
            select(Address).where(Address.user_id == user_id)
        )

        is_default = data.is_default
        # If this is the user's first address, make it default automatically
        if existing_count is None:
            is_default = True

        if is_default:
            # Unset default on other addresses
            db.execute(
                update(Address)
                .where(Address.user_id == user_id)
                .values(is_default=False)
            )

        new_address = Address(
            user_id=user_id,
            full_name=data.full_name.strip(),
            phone=data.phone.strip(),
            address_line=data.address_line.strip(),
            city=data.city.strip(),
            province=data.province.strip() if data.province else None,
            postal_code=data.postal_code.strip() if data.postal_code else None,
            is_default=is_default,
        )

        db.add(new_address)
        db.commit()
        db.refresh(new_address)

        return AddressResponse.model_validate(new_address)

    @staticmethod
    def update_address(
        db: Session,
        user_id: int,
        address_id: int,
        data: AddressUpdate,
    ) -> AddressResponse:
        address = db.scalar(
            select(Address).where(Address.id == address_id, Address.user_id == user_id)
        )

        if not address:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Address not found.",
            )

        update_dict = data.model_dump(exclude_unset=True)

        if update_dict.get("is_default") is True:
            db.execute(
                update(Address)
                .where(Address.user_id == user_id)
                .values(is_default=False)
            )

        for key, value in update_dict.items():
            setattr(address, key, value)

        db.commit()
        db.refresh(address)
        return AddressResponse.model_validate(address)

    @staticmethod
    def delete_address(db: Session, user_id: int, address_id: int) -> None:
        address = db.scalar(
            select(Address).where(Address.id == address_id, Address.user_id == user_id)
        )

        if not address:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Address not found.",
            )

        was_default = address.is_default
        db.delete(address)
        db.commit()

        # If deleted address was default, make the latest one default
        if was_default:
            first_left = db.scalar(
                select(Address)
                .where(Address.user_id == user_id)
                .order_by(Address.created_at.desc())
            )
            if first_left:
                first_left.is_default = True
                db.commit()

    @staticmethod
    def set_default(db: Session, user_id: int, address_id: int) -> AddressResponse:
        address = db.scalar(
            select(Address).where(Address.id == address_id, Address.user_id == user_id)
        )

        if not address:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Address not found.",
            )

        db.execute(
            update(Address)
            .where(Address.user_id == user_id)
            .values(is_default=False)
        )

        address.is_default = True
        db.commit()
        db.refresh(address)
        return AddressResponse.model_validate(address)

