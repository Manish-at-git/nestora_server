"""SQL access and association scoping for documents."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleCode


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def scoped_associations(self, account_id: str, role_code: str, user_id: str | None) -> list[str] | None:
        if role_code == RoleCode.SUPER_ADMIN.value:
            return None
        if role_code in {RoleCode.ADMIN.value, RoleCode.ACCOUNTANT.value}:
            rows = await self.session.scalars(
                text("SELECT association_id FROM admin_associations WHERE admin_id=:account_id"),
                {"account_id": account_id},
            )
            return list(rows.all())
        if role_code == RoleCode.BOARD_MEMBER.value:
            rows = await self.session.scalars(
                text("SELECT association_id FROM board_members WHERE account_id=:account_id AND status='active' AND is_deleted=0"),
                {"account_id": account_id},
            )
            values = list(rows.all())
            if values:
                return values
        if not user_id:
            return []
        association_id = await self.session.scalar(
            text(
                "SELECT COALESCE(ud.association_id,b.association_id) FROM user_details ud "
                "LEFT JOIN units u ON u.id=ud.unit_id LEFT JOIN blocks b ON b.id=u.block_id "
                "WHERE ud.user_id=:user_id AND ud.is_deleted=0 LIMIT 1"
            ),
            {"user_id": user_id},
        )
        return [association_id] if association_id else []

    @staticmethod
    def _scope_sql(scoped: list[str] | None, column: str) -> tuple[str, dict]:
        if scoped is None:
            return "", {}
        if not scoped:
            return " AND 1=0", {}
        return f" AND {column} IN :association_ids", {"association_ids": tuple(scoped)}

    async def list_documents(self, scoped: list[str] | None) -> list[dict]:
        scope, params = self._scope_sql(scoped, "d.association_id")
        # SQLAlchemy expands tuple parameters only when explicitly marked; use one
        # bound parameter per association to keep this compatible with MySQL.
        if scoped is not None and scoped:
            marks = ",".join(f":association_{i}" for i in range(len(scoped)))
            scope = f" AND d.association_id IN ({marks})"
            params = {f"association_{i}": value for i, value in enumerate(scoped)}
        result = await self.session.execute(
            text(
                "SELECT d.*, a.name association_name FROM documents d "
                "JOIN associations a ON a.id=d.association_id AND a.is_deleted=0 "
                "WHERE d.is_deleted=0" + scope + " ORDER BY d.created_at DESC"
            ),
            params,
        )
        return [dict(row) for row in result.mappings().all()]

    async def get_document(self, document_id: str) -> dict | None:
        result = await self.session.execute(
            text("SELECT * FROM documents WHERE id=:id AND is_deleted=0"), {"id": document_id}
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def create_document(self, values: dict) -> str:
        await self.session.execute(text("""INSERT INTO documents
            (id, association_id, title, document_number, document_type, category, file_name, file_url,
             file_type, file_size_kb, department, related_module, visibility, allow_download, issue_date,
             expiry_date, reminder_before_expiry_days, status, keywords, remarks, is_deleted)
            VALUES (:id,:association_id,:title,:document_number,:document_type,:category,:file_name,:file_url,
             :file_type,:file_size_kb,:department,:related_module,:visibility,:allow_download,:issue_date,
             :expiry_date,:reminder_before_expiry_days,:status,:keywords,:remarks,0)"""), values)
        return values["id"]

    async def update_document(self, document_id: str, values: dict) -> bool:
        values["id"] = document_id
        result = await self.session.execute(text("""UPDATE documents SET title=:title,
            document_number=:document_number, document_type=:document_type, category=:category,
            department=:department, related_module=:related_module, visibility=:visibility,
            allow_download=:allow_download, issue_date=:issue_date, expiry_date=:expiry_date,
            reminder_before_expiry_days=:reminder_before_expiry_days, status=:status, keywords=:keywords,
            remarks=:remarks WHERE id=:id AND is_deleted=0"""), values)
        return bool(result.rowcount)

    async def delete_document(self, document_id: str) -> bool:
        result = await self.session.execute(
            text("UPDATE documents SET is_deleted=1 WHERE id=:id AND is_deleted=0"), {"id": document_id}
        )
        return bool(result.rowcount)

    async def list_unit_documents(self, scoped: list[str] | None, account_id: str, can_manage: bool) -> list[dict]:
        scope, params = self._scope_sql(scoped, "ud.association_id")
        if scoped is not None and scoped:
            marks = ",".join(f":association_{i}" for i in range(len(scoped)))
            scope = f" AND ud.association_id IN ({marks})"
            params = {f"association_{i}": value for i, value in enumerate(scoped)}
        if not can_manage:
            scope += " AND (ud.user_id=:account_id OR ud.unit_id=(SELECT unit_id FROM user_details WHERE user_id=(SELECT user_id FROM accounts WHERE account_id=:account_id) LIMIT 1))"
            params["account_id"] = account_id
        result = await self.session.execute(
            text(
                "SELECT ud.*, a.name association_name, u.unit_number, "
                "COALESCE(udetail.name, acc.email) user_name FROM unit_documents ud "
                "JOIN associations a ON a.id=ud.association_id AND a.is_deleted=0 "
                "LEFT JOIN units u ON u.id=ud.unit_id "
                "JOIN accounts acc ON acc.account_id=ud.user_id "
                "LEFT JOIN user_details udetail ON udetail.user_id=acc.user_id "
                "WHERE ud.is_deleted=0" + scope + " ORDER BY ud.created_at DESC"
            ),
            params,
        )
        return [dict(row) for row in result.mappings().all()]

    async def get_unit_document(self, document_id: str) -> dict | None:
        result = await self.session.execute(
            text("SELECT * FROM unit_documents WHERE id=:id AND is_deleted=0"), {"id": document_id}
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def create_unit_document(self, values: dict) -> str:
        await self.session.execute(text("""INSERT INTO unit_documents
            (id, association_id, unit_id, user_id, name, type, description, file_url, file_name, file_type,
             file_size_kb, is_deleted) VALUES (:id,:association_id,:unit_id,:user_id,:name,:type,:description,
             :file_url,:file_name,:file_type,:file_size_kb,0)"""), values)
        return values["id"]

    async def update_unit_document(self, document_id: str, values: dict) -> bool:
        values["id"] = document_id
        result = await self.session.execute(
            text("UPDATE unit_documents SET name=:name, type=:type, description=:description WHERE id=:id AND is_deleted=0"),
            values,
        )
        return bool(result.rowcount)

    async def delete_unit_document(self, document_id: str) -> bool:
        result = await self.session.execute(
            text("UPDATE unit_documents SET is_deleted=1 WHERE id=:id AND is_deleted=0"), {"id": document_id}
        )
        return bool(result.rowcount)

    async def list_units(self, association_id: str) -> list[dict]:
        result = await self.session.execute(
            text(
                "SELECT u.id, u.unit_number, b.name block_name FROM units u "
                "LEFT JOIN blocks b ON b.id=u.block_id "
                "WHERE b.association_id=:association_id "
                "AND u.is_deleted=0 ORDER BY b.name, u.unit_number"
            ),
            {"association_id": association_id},
        )
        return [dict(row) for row in result.mappings().all()]
