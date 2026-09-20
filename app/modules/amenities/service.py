"""Authorization and transactional amenity workflows."""

import uuid
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleCode
from app.modules.amenities.constants import (
    AMENITY_BOOKING_REPORT_ROLES,
    AMENITY_MANAGER_ROLES,
    AmenityPaymentMethod,
)
from app.modules.amenities.messages import AmenityMessage as Messages
from app.modules.amenities.models import Amenity, AmenityBooking
from app.modules.amenities.repository import AmenityRepository
from app.modules.amenities.schemas import AmenityBookingRequest, AmenityCreateRequest, AmenityStatusRequest
from app.modules.auth.models import Account


class AmenityService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = AmenityRepository(session)

    @staticmethod
    def role_code(account: Account) -> RoleCode:
        if account.role is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, Messages.FORBIDDEN)
        try:
            return RoleCode(account.role.code)
        except ValueError as exc:
            raise HTTPException(status.HTTP_403_FORBIDDEN, Messages.FORBIDDEN) from exc

    async def list_admin(self, association_id: str, account: Account) -> list[dict]:
        await self._require_manager_association(account, association_id)
        return await self.repository.list_amenities([association_id])

    async def list_active(self, association_id: str, account: Account) -> list[dict]:
        await self._require_association_member(account, association_id)
        return await self.repository.list_amenities([association_id], active_only=True)

    async def create(self, association_id: str, payload: AmenityCreateRequest, account: Account) -> str:
        await self._require_manager_association(account, association_id)
        amenity = Amenity(
            id=str(uuid.uuid4()),
            association_id=association_id,
            name=payload.name,
            charges=payload.charges,
            status=payload.status,
            is_deleted=False,
        )
        self.repository.add_amenity(amenity)
        await self.repository.session.flush()
        return amenity.id

    async def update_status(
        self, association_id: str, amenity_id: str, payload: AmenityStatusRequest, account: Account
    ) -> None:
        await self._require_manager_association(account, association_id)
        amenity = await self.repository.amenity_model(amenity_id)
        if amenity is None or amenity.association_id != association_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, Messages.NOT_FOUND)
        amenity.status = payload.status
        await self.repository.session.flush()

    async def delete(self, association_id: str, amenity_id: str, account: Account) -> None:
        await self._require_manager_association(account, association_id)
        amenity = await self.repository.amenity_model(amenity_id)
        if amenity is None or amenity.association_id != association_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, Messages.NOT_FOUND)
        amenity.is_deleted = True
        await self.repository.session.flush()

    async def association_bookings(self, association_id: str, account: Account) -> list[dict]:
        role_code = self.role_code(account)
        if role_code not in AMENITY_BOOKING_REPORT_ROLES:
            raise HTTPException(status.HTTP_403_FORBIDDEN, Messages.FORBIDDEN)
        if association_id == "ALL":
            if role_code == RoleCode.SUPER_ADMIN:
                return await self.repository.bookings()
            if role_code == RoleCode.ADMIN:
                return await self.repository.bookings(await self.repository.association_ids_for_admin(account.id))
            else:
                raise HTTPException(status.HTTP_403_FORBIDDEN, Messages.FORBIDDEN)
        await self._require_association_access(account, association_id)
        return await self.repository.bookings([association_id])

    async def month_slots(self, amenity_id: str, month: str, account: Account) -> list[dict]:
        amenity = await self.repository.amenity_model(amenity_id)
        if amenity is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, Messages.NOT_FOUND)
        await self._require_association_member(account, amenity.association_id)
        if len(month) != 7 or month[4] != "-":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Month must use YYYY-MM format")
        return await self.repository.month_slots(amenity_id, month)

    async def my_bookings(self, account: Account) -> list[dict]:
        unit = await self.repository.account_unit(account)
        if unit is None:
            return await self.repository.bookings(user_id=account.id)
        # The legacy workflow shows the account's reservations plus reservations
        # made by residents in the same unit.
        rows = await self.repository.bookings(user_id=account.id)
        sibling_rows = []
        if unit.get("unit_number") and unit.get("association_id"):
            sibling_rows = await self.repository.bookings(
                unit_number=unit["unit_number"], unit_association_id=unit["association_id"]
            )
        seen = {row["id"] for row in rows}
        rows.extend(row for row in sibling_rows if row["id"] not in seen)
        rows.sort(key=lambda row: (row.get("booking_date"), row.get("start_time")), reverse=True)
        return rows

    async def book(self, amenity_id: str, payload: AmenityBookingRequest, account: Account) -> str:
        amenity = await self.repository.amenity_model(amenity_id)
        if amenity is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, Messages.NOT_FOUND)
        if not amenity.status:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, Messages.INACTIVE)
        await self._require_association_member(account, amenity.association_id)
        if await self.repository.overlapping_booking(
            amenity.id, payload.booking_date, payload.start_time, payload.end_time
        ):
            raise HTTPException(status.HTTP_409_CONFLICT, Messages.SLOT_BOOKED)

        unit = await self.repository.account_unit(account)
        amount = (Decimal(amenity.charges or 0) * payload.duration_hours).quantize(Decimal("0.01"))
        wallet = await self.repository.wallet_for_update(account.id)
        if wallet is None and payload.payment_method == AmenityPaymentMethod.UPI:
            # UPI does not require a pre-existing wallet balance or PIN, but the
            # transaction ledger still needs a wallet row as its foreign key.
            wallet = await self.repository.create_wallet(account.id)
        if wallet is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, Messages.WALLET_NOT_FOUND)
        if payload.payment_method == AmenityPaymentMethod.WALLET:
            if not wallet.get("security_pin") or wallet["security_pin"] != payload.pin:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, Messages.INVALID_PIN)
            if Decimal(wallet.get("balance") or 0) < amount:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, Messages.INSUFFICIENT_BALANCE)
            await self.repository.debit_wallet(wallet["id"], amount)
            payment_type = "Debit"
        else:
            payment_type = "UPI"
        await self.repository.add_wallet_transaction(wallet["id"], payment_type, amount, f"Amenity Booking: {amenity.name}")
        booking = AmenityBooking(
            id=str(uuid.uuid4()),
            amenity_id=amenity.id,
            user_id=account.id,
            association_id=amenity.association_id,
            unit_number=unit.get("unit_number") if unit else "",
            homeowner_name=(getattr(account, "name", None) or (unit.get("name") if unit else None) or account.email),
            amount=amount,
            booking_date=payload.booking_date,
            payment_status="Confirmed",
            start_time=payload.start_time,
            end_time=payload.end_time,
            duration_hours=payload.duration_hours,
            is_deleted=False,
        )
        self.repository.add_booking(booking)
        await self.repository.session.flush()
        return booking.id

    async def _require_manager_association(self, account: Account, association_id: str) -> None:
        role_code = self.role_code(account)
        if role_code not in AMENITY_MANAGER_ROLES:
            raise HTTPException(status.HTTP_403_FORBIDDEN, Messages.FORBIDDEN)
        if not await self.repository.association_exists(association_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, Messages.INVALID_ASSOCIATION)
        if role_code == RoleCode.ADMIN:
            allowed = await self.repository.association_ids_for_admin(account.id)
            if association_id not in allowed:
                raise HTTPException(status.HTTP_403_FORBIDDEN, Messages.FORBIDDEN)

    async def _require_association_member(self, account: Account, association_id: str) -> None:
        if not await self.repository.association_exists(association_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, Messages.INVALID_ASSOCIATION)
        if self.role_code(account) == RoleCode.SUPER_ADMIN:
            return
        await self._require_association_access(account, association_id)

    async def _require_association_access(self, account: Account, association_id: str) -> None:
        if not await self.repository.association_exists(association_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, Messages.INVALID_ASSOCIATION)
        role_code = self.role_code(account)
        if role_code == RoleCode.SUPER_ADMIN:
            return
        if role_code == RoleCode.ADMIN:
            if association_id not in await self.repository.association_ids_for_admin(account.id):
                raise HTTPException(status.HTTP_403_FORBIDDEN, Messages.FORBIDDEN)
            return
        if await self.repository.member_association_id(account) != association_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, Messages.FORBIDDEN)
