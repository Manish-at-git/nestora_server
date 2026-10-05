"""Database access for event passes. The caller owns the transaction."""

import uuid
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class EventPassRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def one(self, sql: str, **params: object) -> dict | None:
        row = (await self.session.execute(text(sql), params)).mappings().first()
        return dict(row) if row else None

    async def many(self, sql: str, **params: object) -> list[dict]:
        rows = (await self.session.execute(text(sql), params)).mappings().all()
        return [dict(row) for row in rows]

    async def execute(self, sql: str, **params: object) -> None:
        await self.session.execute(text(sql), params)

    async def pass_by_id(self, pass_id: str, *, lock: bool = False) -> dict | None:
        suffix = " FOR UPDATE" if lock else ""
        return await self.one(
            "SELECT * FROM event_passes WHERE id=:pass_id" + suffix, pass_id=pass_id
        )

    async def booked_count(self, event_id: str) -> int:
        row = await self.one(
            "SELECT COALESCE(SUM(total_passes),0) total FROM event_passes "
            "WHERE event_id=:event_id AND shared_from_pass_id IS NULL AND status <> 'Cancelled'",
            event_id=event_id,
        )
        return int(row["total"] or 0)

    async def buyer_count(self, event_id: str, account_id: str) -> int:
        row = await self.one(
            "SELECT COALESCE(SUM(total_passes),0) total FROM event_passes "
            "WHERE event_id=:event_id AND account_id=:account_id "
            "AND shared_from_pass_id IS NULL AND status <> 'Cancelled'",
            event_id=event_id, account_id=account_id,
        )
        return int(row["total"] or 0)

    async def primary_buyer_pass(self, event_id: str, account_id: str) -> dict | None:
        return await self.one(
            "SELECT * FROM event_passes WHERE event_id=:event_id AND account_id=:account_id "
            "AND shared_from_pass_id IS NULL AND status <> 'Cancelled' "
            "ORDER BY created_at ASC LIMIT 1 FOR UPDATE",
            event_id=event_id,
            account_id=account_id,
        )

    async def buyer(self, account_id: str) -> dict | None:
        return await self.one(
            "SELECT COALESCE(ud.name, a.email) name, ud.contact_number mobile "
            "FROM accounts a LEFT JOIN user_details ud ON ud.user_id=a.user_id "
            "WHERE a.account_id=:account_id", account_id=account_id,
        )

    async def recipient(self, mobile: str) -> dict | None:
        return await self.one(
            "SELECT a.account_id, COALESCE(ud.name,a.email) name FROM accounts a "
            "JOIN user_details ud ON ud.user_id=a.user_id "
            "WHERE RIGHT(REPLACE(REPLACE(REPLACE(ud.contact_number,' ',''),'-',''),'+',''),10)=:mobile "
            "AND a.status='active' LIMIT 1", mobile=mobile,
        )

    async def insert_pass(self, values: dict) -> None:
        await self.execute(
            "INSERT INTO event_passes "
            "(id,event_id,account_id,buyer_name,buyer_mobile,total_passes,remaining_passes,"
            "pass_code,qr_data,amount_paid,payment_method,payment_status,status,"
            "shared_from_pass_id,shared_to_mobile,checked_in_passes) "
            "VALUES (:id,:event_id,:account_id,:buyer_name,:buyer_mobile,:total_passes,"
            ":remaining_passes,:pass_code,:qr_data,:amount_paid,:payment_method,"
            ":payment_status,:status,:shared_from_pass_id,:shared_to_mobile,0)",
            **values,
        )

    async def add_to_pass(self, pass_id: str, count: int, amount: Decimal) -> None:
        await self.execute(
            "UPDATE event_passes SET total_passes=total_passes+:count, "
            "remaining_passes=remaining_passes+:count, amount_paid=amount_paid+:amount, "
            "status='Active', updated_at=NOW() WHERE id=:pass_id",
            pass_id=pass_id,
            count=count,
            amount=amount,
        )

    async def my_passes(self, event_id: str, account_id: str) -> list[dict]:
        return await self.many(
            "SELECT * FROM event_passes WHERE event_id=:event_id AND account_id=:account_id "
            "ORDER BY created_at DESC", event_id=event_id, account_id=account_id,
        )

    async def transfers(self, pass_id: str) -> list[dict]:
        return await self.many(
            "SELECT new_pass_id,recipient_mobile,recipient_name,count,created_at "
            "FROM event_pass_transfers WHERE original_pass_id=:pass_id ORDER BY created_at DESC",
            pass_id=pass_id,
        )

    async def admin_passes(self, event_id: str) -> list[dict]:
        return await self.many(
            "SELECT p.*, a.email user_email FROM event_passes p "
            "JOIN accounts a ON a.account_id=p.account_id "
            "WHERE p.event_id=:event_id ORDER BY p.created_at DESC", event_id=event_id,
        )

    async def scan_match(self, event_id: str, query: str, mobile: str | None) -> dict | None:
        row = await self.one(
            "SELECT * FROM event_passes WHERE id=:query OR pass_code=:query LIMIT 1", query=query,
        )
        if row or not mobile:
            return row
        return await self.one(
            "SELECT * FROM event_passes WHERE event_id=:event_id AND "
            "RIGHT(REPLACE(REPLACE(buyer_mobile,' ',''),'-',''),10)=:mobile "
            "ORDER BY created_at DESC LIMIT 1", event_id=event_id, mobile=mobile,
        )

    async def checkins(self, pass_id: str) -> list[dict]:
        return await self.many(
            "SELECT id,admitted_count,checked_in_by_name,checked_in_at,notes "
            "FROM event_pass_checkins WHERE pass_id=:pass_id ORDER BY checked_in_at DESC",
            pass_id=pass_id,
        )

    async def wallet(self, account_id: str) -> dict | None:
        return await self.one(
            "SELECT id,balance,security_pin FROM wallets WHERE account_id=:account_id "
            "AND COALESCE(is_deleted,0)=0 FOR UPDATE", account_id=account_id,
        )

    async def debit_wallet(self, wallet_id: str, amount: Decimal, title: str) -> None:
        await self.execute(
            "UPDATE wallets SET balance=balance-:amount WHERE id=:wallet_id",
            amount=amount, wallet_id=wallet_id,
        )
        await self.execute(
            "INSERT INTO wallet_transactions "
            "(id,wallet_id,type,amount,status,description,is_deleted) "
            "VALUES (:id,:wallet_id,'Debit',:amount,'Completed',:description,0)",
            id=str(uuid.uuid4()), wallet_id=wallet_id, amount=amount,
            description=f"Event Pass: {title}",
        )

    async def record_upi_payment(self, wallet_id: str, amount: Decimal, title: str) -> None:
        await self.execute(
            "INSERT INTO wallet_transactions "
            "(id,wallet_id,type,amount,status,description,is_deleted) "
            "VALUES (:id,:wallet_id,'UPI',:amount,'Completed',:description,0)",
            id=str(uuid.uuid4()), wallet_id=wallet_id, amount=amount,
            description=f"Event Pass: {title}",
        )
