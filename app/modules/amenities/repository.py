"""SQL access for amenity catalogues, reservations, and wallet debits."""

import uuid
from collections.abc import Iterable
from datetime import date, time, timedelta
from decimal import Decimal

from sqlalchemy import bindparam, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.amenities.models import Amenity, AmenityBooking
from app.modules.auth.models import Account


class AmenityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _normalize_time(value: time | timedelta | None) -> time | None:
        """Convert MySQL TIME values returned as timedeltas into API time values."""
        if not isinstance(value, timedelta):
            return value
        total_seconds = int(value.total_seconds()) % (24 * 60 * 60)
        return time(total_seconds // 3600, (total_seconds % 3600) // 60, total_seconds % 60)

    async def association_ids_for_admin(self, account_id: str) -> list[str]:
        result = await self.session.scalars(
            text("SELECT association_id FROM admin_associations WHERE admin_id = :account_id"),
            {"account_id": account_id},
        )
        return list(result.all())

    async def member_association_id(self, account: Account) -> str | None:
        if not account.user_id:
            return None
        return await self.session.scalar(
            text(
                "SELECT COALESCE(ud.association_id, b.association_id) FROM user_details ud "
                "LEFT JOIN units u ON u.id = ud.unit_id LEFT JOIN blocks b ON b.id = u.block_id "
                "WHERE ud.user_id = :user_id AND ud.is_deleted = 0 LIMIT 1"
            ),
            {"user_id": account.user_id},
        )

    async def association_exists(self, association_id: str) -> bool:
        return bool(
            await self.session.scalar(
                text("SELECT id FROM associations WHERE id = :id AND is_deleted = 0 LIMIT 1"),
                {"id": association_id},
            )
        )

    async def list_amenities(self, association_ids: Iterable[str] | None, active_only: bool = False) -> list[dict]:
        query = (
            "SELECT a.id, a.association_id, assoc.name AS association_name, a.name, a.charges, "
            "a.status, a.created_at FROM amenities a JOIN associations assoc ON assoc.id = a.association_id "
            "WHERE a.is_deleted = 0 AND assoc.is_deleted = 0"
        )
        params: dict = {}
        if active_only:
            query += " AND a.status = 1"
        if association_ids is not None:
            ids = tuple(dict.fromkeys(association_ids))
            if not ids:
                return []
            query += " AND a.association_id IN :association_ids"
            params["association_ids"] = ids
        statement = text(query + " ORDER BY a.name")
        if association_ids is not None:
            statement = statement.bindparams(bindparam("association_ids", expanding=True))
        result = await self.session.execute(statement, params)
        return [dict(row) for row in result.mappings().all()]

    async def amenity_model(self, amenity_id: str) -> Amenity | None:
        return await self.session.scalar(
            select(Amenity).where(Amenity.id == amenity_id, Amenity.is_deleted.is_(False))
        )

    async def active_amenity_in_association(self, amenity_id: str, association_id: str) -> Amenity | None:
        return await self.session.scalar(
            select(Amenity).where(
                Amenity.id == amenity_id,
                Amenity.association_id == association_id,
                Amenity.status.is_(True),
                Amenity.is_deleted.is_(False),
            )
        )

    async def bookings(
        self,
        association_ids: Iterable[str] | None = None,
        user_id: str | None = None,
        unit_number: str | None = None,
        unit_association_id: str | None = None,
    ) -> list[dict]:
        query = (
            "SELECT b.id, b.amenity_id, a.name AS amenity_name, b.association_id, assoc.name AS association_name, "
            "b.user_id, b.homeowner_name, b.unit_number, ud.contact_number AS contact_no, b.amount, "
            "b.booking_date, b.payment_status, b.start_time, b.end_time, b.duration_hours, b.created_at, "
            "COALESCE(NULLIF(b.homeowner_name, ''), ud.name, acc.email) AS computed_homeowner_name, "
            "COALESCE(NULLIF(b.unit_number, ''), u.unit_number) AS computed_unit_number "
            "FROM amenity_bookings b JOIN amenities a ON a.id = b.amenity_id "
            "JOIN associations assoc ON assoc.id = b.association_id "
            "LEFT JOIN accounts acc ON b.user_id = acc.account_id "
            "LEFT JOIN user_details ud ON acc.user_id = ud.user_id LEFT JOIN units u ON ud.unit_id = u.id "
            "WHERE b.is_deleted = 0 AND a.is_deleted = 0 AND assoc.is_deleted = 0"
        )
        params: dict = {}
        if association_ids is not None:
            ids = tuple(dict.fromkeys(association_ids))
            if not ids:
                return []
            query += " AND b.association_id IN :association_ids"
            params["association_ids"] = ids
        if user_id is not None:
            query += " AND b.user_id = :user_id"
            params["user_id"] = user_id
        if unit_number is not None and unit_association_id is not None:
            query += " AND b.unit_number = :unit_number AND b.association_id = :unit_association_id"
            params["unit_number"] = unit_number
            params["unit_association_id"] = unit_association_id
        statement = text(query + " ORDER BY b.booking_date DESC, b.start_time DESC")
        if association_ids is not None:
            statement = statement.bindparams(bindparam("association_ids", expanding=True))
        result = await self.session.execute(statement, params)
        rows = []
        for row in result.mappings().all():
            item = dict(row)
            item["start_time"] = self._normalize_time(item["start_time"])
            item["end_time"] = self._normalize_time(item["end_time"])
            item["homeowner_name"] = item["homeowner_name"] or item.pop("computed_homeowner_name")
            item["unit_number"] = item["unit_number"] or item.pop("computed_unit_number")
            rows.append(item)
        return rows

    async def month_slots(self, amenity_id: str, month: str) -> list[dict]:
        result = await self.session.execute(
            text(
                "SELECT DISTINCT booking_date, start_time, end_time, duration_hours, homeowner_name, unit_number "
                "FROM amenity_bookings WHERE amenity_id = :amenity_id AND payment_status = 'Confirmed' "
                "AND is_deleted = 0 AND DATE_FORMAT(booking_date, '%Y-%m') = :month "
                "ORDER BY booking_date, start_time"
            ),
            {"amenity_id": amenity_id, "month": month},
        )
        rows = []
        for row in result.mappings().all():
            item = dict(row)
            item["start_time"] = self._normalize_time(item["start_time"])
            item["end_time"] = self._normalize_time(item["end_time"])
            rows.append(item)
        return rows

    async def overlapping_booking(self, amenity_id: str, booking_date: date, start_time: time, end_time: time) -> bool:
        return bool(
            await self.session.scalar(
                text(
                    "SELECT id FROM amenity_bookings WHERE amenity_id = :amenity_id "
                    "AND booking_date = :booking_date AND is_deleted = 0 AND payment_status = 'Confirmed' "
                    "AND start_time < :end_time AND end_time > :start_time LIMIT 1"
                ),
                {
                    "amenity_id": amenity_id,
                    "booking_date": booking_date,
                    "start_time": start_time,
                    "end_time": end_time,
                },
            )
        )

    async def account_unit(self, account: Account) -> dict | None:
        if not account.user_id:
            return None
        result = await self.session.execute(
            text(
                "SELECT ud.unit_id, ud.name, u.unit_number, COALESCE(ud.association_id, b.association_id) AS association_id "
                "FROM user_details ud LEFT JOIN units u ON u.id = ud.unit_id LEFT JOIN blocks b ON b.id = u.block_id "
                "WHERE ud.user_id = :user_id AND ud.is_deleted = 0 LIMIT 1"
            ),
            {"user_id": account.user_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def wallet_for_update(self, account_id: str) -> dict | None:
        result = await self.session.execute(
            text("SELECT id, balance, security_pin FROM wallets WHERE account_id = :account_id FOR UPDATE"),
            {"account_id": account_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def create_wallet(self, account_id: str) -> dict:
        wallet_id = str(uuid.uuid4())
        await self.session.execute(
            text(
                "INSERT INTO wallets (id, account_id, balance, reward_points) "
                "VALUES (:id, :account_id, 0, 0)"
            ),
            {"id": wallet_id, "account_id": account_id},
        )
        return {"id": wallet_id, "balance": Decimal("0"), "security_pin": None}

    async def debit_wallet(self, wallet_id: str, amount: Decimal) -> None:
        await self.session.execute(
            text("UPDATE wallets SET balance = balance - :amount WHERE id = :wallet_id"),
            {"amount": amount, "wallet_id": wallet_id},
        )

    async def add_wallet_transaction(self, wallet_id: str, payment_type: str, amount: Decimal, description: str) -> None:
        await self.session.execute(
            text(
                "INSERT INTO wallet_transactions (id, wallet_id, type, amount, status, description) "
                "VALUES (:id, :wallet_id, :type, :amount, 'Completed', :description)"
            ),
            {
                "id": str(uuid.uuid4()),
                "wallet_id": wallet_id,
                "type": payment_type,
                "amount": amount,
                "description": description,
            },
        )

    def add_amenity(self, amenity: Amenity) -> None:
        self.session.add(amenity)

    def add_booking(self, booking: AmenityBooking) -> None:
        self.session.add(booking)
