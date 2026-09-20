"""Bank account business rules, masking, and soft deletion."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.field_encryption import decrypt_field, mask_secret
# Encryption is intentionally paused for this module for now. Keep the helper
# available so it can be re-enabled when encrypted persistence is approved.
# from app.core.field_encryption import encrypt_field
from app.modules.bank.messages import BankMessage
from app.modules.bank.models import BankAccount
from app.modules.bank.repository import BankRepository
from app.modules.bank.schemas import BankAccountRequest


class BankService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = BankRepository(session)

    async def list(self, account_id: str, role_code: str, association_id: str | None = None):
        return [self.serialize(row) for row in await self.repository.list(account_id, role_code, association_id)]

    async def create(self, account_id: str, role_code: str, payload: BankAccountRequest) -> BankAccount:
        if not await self.repository.can_access_association(account_id, role_code, payload.association_id):
            raise HTTPException(status.HTTP_403_FORBIDDEN, BankMessage.UNAUTHORIZED_ASSOCIATION)
        account = BankAccount(
            id=str(uuid.uuid4()),
            association_id=payload.association_id,
            account_name=payload.account_name.strip(),
            account_holder_name=payload.account_holder_name.strip(),
            bank_name=payload.bank_name.strip(),
            account_number=payload.account_number.strip(),
            # account_number=encrypt_field(payload.account_number.strip()) or "",
            ifsc_code=payload.ifsc_code.strip().upper(),
            branch_name=payload.branch_name,
            account_type=payload.account_type,
            currency=payload.currency,
            upi_id=payload.upi_id,
            qr_code_url=payload.qr_code_url,
            gateway_provider=payload.gateway_provider,
            merchant_id=payload.merchant_id,
            api_key=payload.api_key,
            api_secret=payload.api_secret,
            webhook_secret=payload.webhook_secret,
            # api_key=encrypt_field(payload.api_key),
            # api_secret=encrypt_field(payload.api_secret),
            # webhook_secret=encrypt_field(payload.webhook_secret),
            is_default=payload.is_default,
            status=payload.status,
            created_by=account_id,
        )
        self.repository.add(account)
        await self.repository.session.flush()
        await self.repository.session.refresh(account)
        return account

    async def update(self, account_id: str, role_code: str, bank_id: str, payload: BankAccountRequest) -> None:
        account = await self.repository.get(account_id, role_code, bank_id)
        if account is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, BankMessage.NOT_FOUND)
        if not await self.repository.can_access_association(account_id, role_code, payload.association_id):
            raise HTTPException(status.HTTP_403_FORBIDDEN, BankMessage.UNAUTHORIZED_ASSOCIATION)
        account.association_id = payload.association_id
        account.account_name = payload.account_name.strip()
        account.account_holder_name = payload.account_holder_name.strip()
        account.bank_name = payload.bank_name.strip()
        account.ifsc_code = payload.ifsc_code.strip().upper()
        account.branch_name = payload.branch_name
        account.account_type = payload.account_type
        account.currency = payload.currency
        account.upi_id = payload.upi_id
        account.qr_code_url = payload.qr_code_url
        account.gateway_provider = payload.gateway_provider
        account.merchant_id = payload.merchant_id
        account.is_default = payload.is_default
        account.status = payload.status
        if payload.account_number and not payload.account_number.startswith("****"):
            account.account_number = payload.account_number.strip()
            # account.account_number = encrypt_field(payload.account_number.strip()) or account.account_number
        for field in ("api_key", "api_secret", "webhook_secret"):
            value = getattr(payload, field)
            if value and value != "****":
                setattr(account, field, value)
                # setattr(account, field, encrypt_field(value))
        account.updated_by = account_id
        await self.repository.session.flush()

    async def delete(self, account_id: str, role_code: str, bank_id: str) -> None:
        account = await self.repository.get(account_id, role_code, bank_id)
        if account is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, BankMessage.NOT_FOUND)
        account.is_deleted = True
        account.updated_by = account_id
        await self.repository.session.flush()

    @staticmethod
    def serialize(account: BankAccount) -> dict:
        # New records are currently plaintext; the decrypt fallback keeps
        # responses compatible with records created while encryption was enabled.
        decrypted_number = decrypt_field(account.account_number) or account.account_number
        return {
            "id": account.id,
            "association_id": account.association_id,
            "association_name": account.association.name if account.association else None,
            "account_name": account.account_name,
            "account_holder_name": account.account_holder_name,
            "bank_name": account.bank_name,
            "account_number": mask_secret(decrypted_number),
            "ifsc_code": account.ifsc_code,
            "branch_name": account.branch_name,
            "account_type": account.account_type,
            "currency": account.currency,
            "upi_id": account.upi_id,
            "qr_code_url": account.qr_code_url,
            "gateway_provider": account.gateway_provider,
            "merchant_id": account.merchant_id,
            "api_key": "****" if account.api_key else None,
            "api_secret": "****" if account.api_secret else None,
            "webhook_secret": "****" if account.webhook_secret else None,
            "is_default": account.is_default,
            "status": account.status,
            "created_at": account.created_at,
            "created_by": account.created_by,
            "updated_by": account.updated_by,
        }
