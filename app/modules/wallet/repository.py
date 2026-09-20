import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class WalletRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def wallet(self, account_id: str, for_update: bool = False) -> dict | None:
        query = (
            "SELECT id, balance, reward_points, security_pin FROM wallets "
            "WHERE account_id = :account_id AND COALESCE(is_deleted, 0) = 0"
        )
        if for_update:
            query += " FOR UPDATE"
        row = (await self.session.execute(text(query), {"account_id": account_id})).mappings().first()
        return dict(row) if row else None

    async def transactions(self, wallet_id: str) -> list[dict]:
        result = await self.session.execute(
            text(
                "SELECT id, type, amount, status, description, created_at FROM wallet_transactions "
                "WHERE wallet_id = :wallet_id AND COALESCE(is_deleted, 0) = 0 ORDER BY created_at DESC"
            ),
            {"wallet_id": wallet_id},
        )
        return [dict(row) for row in result.mappings().all()]

    async def account_id_by_email(self, email: str) -> str | None:
        return await self.session.scalar(
            text("SELECT account_id FROM accounts WHERE LOWER(email) = :email AND status = 'active' LIMIT 1"),
            {"email": email.lower()},
        )

    async def update_balance(self, wallet_id: str, amount: object) -> None:
        await self.session.execute(
            text("UPDATE wallets SET balance = balance + :amount WHERE id = :wallet_id"),
            {"wallet_id": wallet_id, "amount": amount},
        )

    async def set_pin(self, wallet_id: str, pin: str) -> None:
        await self.session.execute(
            text("UPDATE wallets SET security_pin = :pin WHERE id = :wallet_id"),
            {"wallet_id": wallet_id, "pin": pin},
        )

    async def add_transaction(self, wallet_id: str, payment_type: str, amount: object, description: str) -> None:
        await self.session.execute(
            text(
                "INSERT INTO wallet_transactions "
                "(id, wallet_id, type, amount, status, description, is_deleted) "
                "VALUES (:id, :wallet_id, :type, :amount, 'Completed', :description, 0)"
            ),
            {"id": str(uuid.uuid4()), "wallet_id": wallet_id, "type": payment_type, "amount": amount, "description": description},
        )

    async def dues_paid_this_month(self, wallet_id: str) -> bool:
        return bool(
            await self.session.scalar(
                text(
                    "SELECT id FROM wallet_transactions WHERE wallet_id = :wallet_id "
                    "AND type IN ('Debit', 'UPI') AND description = 'Maintenance Dues Paid' "
                    "AND COALESCE(is_deleted, 0) = 0 AND created_at >= DATE_FORMAT(CURRENT_DATE, '%Y-%m-01') LIMIT 1"
                ),
                {"wallet_id": wallet_id},
            )
        )
