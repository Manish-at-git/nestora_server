"""Document authorization and transaction rules."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleCode
from app.modules.documents.repository import DocumentRepository
from app.modules.documents.schemas import (
    DocumentRequest,
    DocumentUpdateRequest,
    UnitDocumentRequest,
    UnitDocumentUpdateRequest,
)


MANAGER_ROLES = {RoleCode.SUPER_ADMIN, RoleCode.ADMIN, RoleCode.ACCOUNTANT, RoleCode.BOARD_MEMBER}
UNIT_DOCUMENT_MANAGER_ROLES = {RoleCode.SUPER_ADMIN, RoleCode.ADMIN}


class DocumentService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = DocumentRepository(session)

    async def _scope(self, account, role_code: RoleCode) -> list[str] | None:
        role_code = RoleCode(role_code)
        return await self.repository.scoped_associations(account.id, role_code.value, account.user_id)

    async def list(self, account, role_code: RoleCode, association_id: str | None = None) -> list[dict]:
        role_code = RoleCode(role_code)
        scoped = await self._scope(account, role_code)
        if association_id:
            if scoped is not None and association_id not in scoped:
                return []
            scoped = [association_id]
        rows = await self.repository.list_documents(scoped)
        if role_code in MANAGER_ROLES:
            return rows
        allowed = {"public", "residents"}
        if role_code == RoleCode.COMMITTEE_MEMBER:
            allowed.add("committee")
        if role_code == RoleCode.BOARD_MEMBER:
            allowed.add("board member")
        return [row for row in rows if any(token in (row.get("visibility") or "").lower() for token in allowed)]

    async def create(self, account, role_code: RoleCode, payload: DocumentRequest) -> str:
        role_code = RoleCode(role_code)
        if role_code not in MANAGER_ROLES:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only association managers can create board documents")
        scoped = await self._scope(account, role_code)
        if scoped is not None and payload.association_id not in scoped:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Unauthorized for this association")
        values = payload.model_dump()
        values["id"] = str(uuid.uuid4())
        return await self.repository.create_document(values)

    async def update(self, account, role_code: RoleCode, document_id: str, payload: DocumentUpdateRequest) -> None:
        role_code = RoleCode(role_code)
        if role_code not in MANAGER_ROLES:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only association managers can update board documents")
        row = await self.repository.get_document(document_id)
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
        scoped = await self._scope(account, role_code)
        if scoped is not None and row["association_id"] not in scoped:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Unauthorized for this association")
        values = payload.model_dump(exclude={"association_id", "file_url", "file_name", "file_type", "file_size_kb"})
        if not await self.repository.update_document(document_id, values):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")

    async def delete(self, account, role_code: RoleCode, document_id: str) -> None:
        role_code = RoleCode(role_code)
        if role_code not in MANAGER_ROLES:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only association managers can delete board documents")
        row = await self.repository.get_document(document_id)
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
        scoped = await self._scope(account, role_code)
        if scoped is not None and row["association_id"] not in scoped:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Unauthorized for this association")
        await self.repository.delete_document(document_id)

    async def list_unit(self, account, role_code: RoleCode, association_id: str | None = None) -> list[dict]:
        role_code = RoleCode(role_code)
        scoped = await self._scope(account, role_code)
        if association_id:
            if scoped is not None and association_id not in scoped:
                return []
            scoped = [association_id]
        return await self.repository.list_unit_documents(
            scoped, account.id, role_code in UNIT_DOCUMENT_MANAGER_ROLES
        )

    async def list_units(self, account, role_code: RoleCode, association_id: str) -> list[dict]:
        role_code = RoleCode(role_code)
        scoped = await self._scope(account, role_code)
        if scoped is not None and association_id not in scoped:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Unauthorized for this association")
        return await self.repository.list_units(association_id)

    async def create_unit(self, account, role_code: RoleCode, payload: UnitDocumentRequest) -> str:
        role_code = RoleCode(role_code)
        scoped = await self._scope(account, role_code)
        association_id = payload.association_id
        unit_id = payload.unit_id
        if role_code not in UNIT_DOCUMENT_MANAGER_ROLES:
            own_unit_id = await self.repository.session.scalar(
                text("SELECT unit_id FROM user_details WHERE user_id=:user_id AND is_deleted=0"),
                {"user_id": account.user_id},
            )
            association_id = await self.repository.session.scalar(
                text(
                    "SELECT COALESCE(ud.association_id, b.association_id) "
                    "FROM user_details ud LEFT JOIN units u ON u.id=ud.unit_id "
                    "LEFT JOIN blocks b ON b.id=u.block_id "
                    "WHERE ud.user_id=:user_id AND ud.is_deleted=0 LIMIT 1"
                ),
                {"user_id": account.user_id},
            )
            if not association_id:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "Your account is not assigned to an association")
            if unit_id and unit_id != own_unit_id:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only add documents to your own unit")
            unit_id = own_unit_id
        elif not association_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "association_id is required")

        if scoped is not None and association_id not in scoped:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Unauthorized for this association")
        values = payload.model_dump()
        values.update(
            {
                "id": str(uuid.uuid4()),
                "association_id": association_id,
                "user_id": account.id,
                "unit_id": unit_id,
            }
        )
        return await self.repository.create_unit_document(values)

    async def update_unit(self, account, role_code: RoleCode, document_id: str, payload: UnitDocumentUpdateRequest) -> None:
        role_code = RoleCode(role_code)
        row = await self.repository.get_unit_document(document_id)
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
        scoped = await self._scope(account, role_code)
        owns = row["user_id"] == account.id
        if scoped is not None and row["association_id"] not in scoped:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Unauthorized for this association")
        if role_code not in UNIT_DOCUMENT_MANAGER_ROLES and not owns:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")
        await self.repository.update_unit_document(document_id, payload.model_dump())

    async def delete_unit(self, account, role_code: RoleCode, document_id: str) -> None:
        role_code = RoleCode(role_code)
        row = await self.repository.get_unit_document(document_id)
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
        scoped = await self._scope(account, role_code)
        if scoped is not None and row["association_id"] not in scoped:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Unauthorized for this association")
        if role_code not in UNIT_DOCUMENT_MANAGER_ROLES and row["user_id"] != account.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")
        await self.repository.delete_unit_document(document_id)
