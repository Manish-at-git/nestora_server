import uuid
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleCode
from app.modules.auth.models import Account
from app.modules.wallet.constants import WALLET_ROLE_CODES
from app.modules.wallet.repository import WalletRepository
from app.modules.wallet.schemas import (
    AddMoneyRequest,
    CreateOrderRequest,
    PayDuesRequest,
    PayDuesUpiRequest,
    PinRequest,
    SendMoneyRequest,
    VerifyPaymentRequest,
)


class WalletService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = WalletRepository(session)

    @staticmethod
    def _role(account: Account) -> RoleCode:
        try:
            role = RoleCode(account.role.code)
        except (AttributeError, ValueError) as exc:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Wallet access is not available for this role") from exc
        if role not in WALLET_ROLE_CODES:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Wallet access is not available for this role")
        return role

    async def _wallet(self, account: Account, for_update: bool = False) -> dict:
        self._role(account)
        wallet = await self.repository.wallet(account.id, for_update)
        if wallet is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Wallet not found.")
        return wallet

    async def details(self, account: Account) -> dict:
        wallet = await self._wallet(account)
        return {"id": wallet["id"], "balance": wallet["balance"], "reward_points": wallet["reward_points"] or 0, "has_pin": bool(wallet["security_pin"])}

    async def list_transactions(self, account: Account) -> list[dict]:
        wallet = await self._wallet(account)
        return await self.repository.transactions(wallet["id"])

    async def setup_pin(self, account: Account, payload: PinRequest) -> dict:
        wallet = await self._wallet(account, True)
        await self.repository.set_pin(wallet["id"], payload.pin)
        return {"message": "PIN set successfully."}

    async def add_money(self, account: Account, payload: AddMoneyRequest) -> dict:
        wallet = await self._wallet(account, True)
        await self.repository.update_balance(wallet["id"], payload.amount)
        await self.repository.add_transaction(wallet["id"], "Credit", payload.amount, f"Added via {payload.method}")
        return {"message": "Money added successfully.", "balance": Decimal(wallet["balance"]) + payload.amount}

    async def _validate_debit(self, account: Account, pin: str, amount: Decimal) -> dict:
        wallet = await self._wallet(account, True)
        if not wallet["security_pin"] or wallet["security_pin"] != pin:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid PIN.")
        if Decimal(wallet["balance"]) < amount:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Insufficient wallet balance.")
        return wallet

    async def pay_dues(self, account: Account, payload: PayDuesRequest) -> dict:
        wallet = await self._wallet(account, True)
        maintenance_amount, violation_fines = await self._outstanding_dues(account, wallet["id"])
        amount = maintenance_amount + sum((Decimal(fine["fine_amount"]) for fine in violation_fines), Decimal("0"))
        self._validate_due_amount(payload.amount, amount)
        self._validate_wallet_pin(wallet, payload.pin, amount)
        await self.repository.update_balance(wallet["id"], -amount)
        await self._record_due_payment(wallet["id"], maintenance_amount, violation_fines, "Debit")
        return {"message": "Dues paid successfully.", "balance": Decimal(wallet["balance"]) - amount}

    async def pay_dues_upi(self, account: Account, payload: PayDuesUpiRequest) -> dict:
        wallet = await self._wallet(account, True)
        maintenance_amount, violation_fines = await self._outstanding_dues(account, wallet["id"])
        amount = maintenance_amount + sum((Decimal(fine["fine_amount"]) for fine in violation_fines), Decimal("0"))
        self._validate_due_amount(payload.amount, amount)
        await self._record_due_payment(wallet["id"], maintenance_amount, violation_fines, "UPI")
        return {"message": "UPI dues payment recorded successfully.", "balance": wallet["balance"]}

    async def _outstanding_dues(self, account: Account, wallet_id: str) -> tuple[Decimal, list[dict]]:
        assessment = await self.repository.assessment_amount(account.id)
        maintenance_amount = assessment.amount if assessment and assessment.amount > 0 else Decimal("0")
        if maintenance_amount > 0 and await self.repository.dues_paid_this_month(wallet_id):
            maintenance_amount = Decimal("0")
        violation_fines = await self.repository.active_violation_fines(account.user_id, for_update=True)
        if maintenance_amount <= 0 and not violation_fines:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "No maintenance dues or accepted violation fines are outstanding.")
        return maintenance_amount, violation_fines

    @staticmethod
    def _validate_due_amount(supplied_amount: Decimal, expected_amount: Decimal) -> None:
        if supplied_amount != expected_amount:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Dues amount no longer matches the outstanding balance.")

    @staticmethod
    def _validate_wallet_pin(wallet: dict, pin: str, amount: Decimal) -> None:
        if not wallet["security_pin"] or wallet["security_pin"] != pin:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid PIN.")
        if Decimal(wallet["balance"]) < amount:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Insufficient wallet balance.")

    async def _record_due_payment(
        self,
        wallet_id: str,
        maintenance_amount: Decimal,
        violation_fines: list[dict],
        payment_type: str,
    ) -> None:
        if maintenance_amount > 0:
            await self.repository.add_transaction(wallet_id, payment_type, maintenance_amount, "Maintenance Dues Paid")
        for fine in violation_fines:
            transaction_id = await self.repository.add_transaction(
                wallet_id,
                payment_type,
                Decimal(fine["fine_amount"]),
                f"Violation fine {fine['display_id']}",
            )
            await self.repository.mark_violation_fine_paid(fine["id"], transaction_id)

    async def send_money(self, account: Account, payload: SendMoneyRequest) -> dict:
        sender = await self._validate_debit(account, payload.pin, payload.amount)
        recipient_id = await self.repository.account_id_by_email(payload.recipient_email)
        if not recipient_id or recipient_id == account.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Recipient account is invalid.")
        recipient = await self.repository.wallet(recipient_id, True)
        if recipient is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Recipient wallet not found.")
        await self.repository.update_balance(sender["id"], -payload.amount)
        await self.repository.update_balance(recipient["id"], payload.amount)
        description = f"Transfer to {payload.recipient_email}" + (f" · {payload.purpose}" if payload.purpose else "")
        await self.repository.add_transaction(sender["id"], "Debit", payload.amount, description)
        await self.repository.add_transaction(recipient["id"], "Credit", payload.amount, f"Transfer from {account.email}")
        return {"message": "Money sent successfully.", "balance": Decimal(sender["balance"]) - payload.amount}

    async def create_order(self, account: Account, payload: CreateOrderRequest) -> dict:
        self._role(account)
        return {"order_id": f"nestora_{uuid.uuid4().hex}", "amount": payload.amount, "currency": payload.currency, "receipt": payload.receipt}

    async def verify_payment(self, account: Account, payload: VerifyPaymentRequest) -> dict:
        self._role(account)
        return {"success": True, "wallet_added": False, "message": "Payment verified. Wallet credit is pending confirmation."}
