"""SQL access for marketplace listings, engagement, and chat."""

import uuid
from collections.abc import Iterable

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleCode


class MarketplaceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def association_ids_for_admin(self, account_id: str) -> list[str]:
        result = await self.session.scalars(
            text("SELECT association_id FROM admin_associations WHERE admin_id=:account_id"),
            {"account_id": account_id},
        )
        return list(result.all())

    async def member_association_ids(self, account_id: str, user_id: str | None) -> list[str]:
        result = await self.session.scalars(
            text("SELECT association_id FROM board_members WHERE account_id=:account_id AND status='active' AND is_deleted=0"),
            {"account_id": account_id},
        )
        values = list(result.all())
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

    async def association_exists(self, association_id: str) -> bool:
        return bool(
            await self.session.scalar(
                text("SELECT id FROM associations WHERE id=:id AND is_deleted=0 LIMIT 1"),
                {"id": association_id},
            )
        )

    async def categories(self) -> list[dict]:
        result = await self.session.execute(
            text("SELECT id,name,created_at FROM marketplace_categories WHERE is_deleted=0 ORDER BY name")
        )
        return [dict(row) for row in result.mappings().all()]

    async def _items_with_images(self, rows: list[dict]) -> list[dict]:
        if not rows:
            return []
        ids = [row["id"] for row in rows]
        marks = ",".join(f":item_{index}" for index in range(len(ids)))
        result = await self.session.execute(
            text(f"SELECT item_id,image_url FROM marketplace_images WHERE is_deleted=0 AND item_id IN ({marks}) ORDER BY created_at"),
            {f"item_{index}": value for index, value in enumerate(ids)},
        )
        images: dict[str, list[str]] = {}
        for row in result.mappings():
            images.setdefault(row["item_id"], []).append(row["image_url"])
        for row in rows:
            row["images"] = images.get(row["id"], [])
            row["is_saved"] = bool(row.get("is_saved"))
        return rows

    async def list_items(
        self, account_id: str, association_ids: Iterable[str] | None, filters: dict, mine_only: bool = False
    ) -> list[dict]:
        query = (
            "SELECT i.*, COALESCE(ac.account_id, legacy_ac.account_id) owner_account_id, "
            "c.name category_name, COALESCE(ud.name,ac.email,legacy_ac.email) seller_name, "
            "(SELECT COUNT(*) FROM marketplace_favorites f WHERE f.item_id=i.id AND f.user_id=:account_id AND f.is_deleted=0) is_saved, "
            "(SELECT COUNT(*) FROM marketplace_favorites f WHERE f.item_id=i.id AND f.is_deleted=0) saves_count, "
            "(SELECT COUNT(*) FROM marketplace_views v WHERE v.item_id=i.id AND v.is_deleted=0) views_count "
            "FROM marketplace_items i LEFT JOIN marketplace_categories c ON c.id=i.category_id AND c.is_deleted=0 "
            "LEFT JOIN accounts ac ON ac.account_id=i.user_id "
            "LEFT JOIN accounts legacy_ac ON legacy_ac.user_id=i.user_id "
            "LEFT JOIN user_details ud ON ud.user_id=COALESCE(ac.user_id,legacy_ac.user_id) "
            "WHERE i.is_deleted=0"
        )
        params: dict = {"account_id": account_id}
        if association_ids is not None:
            values = tuple(dict.fromkeys(association_ids))
            if not values:
                return []
            query += " AND i.association_id IN :association_ids"
            params["association_ids"] = values
        if mine_only:
            query += " AND i.user_id=:account_id"
        for field, expression in (
            ("category_id", "i.category_id=:category_id"),
            ("condition", "i.condition_state=:condition"),
            ("min_price", "i.price>=:min_price"),
            ("max_price", "i.price<=:max_price"),
            ("is_negotiable", "i.is_negotiable=:is_negotiable"),
            ("status", "i.status=:status"),
        ):
            if filters.get(field) is not None and filters.get(field) != "":
                query += f" AND {expression}"
                params[field] = filters[field]
        query += " ORDER BY i.created_at ASC" if filters.get("sort") == "Oldest" else " ORDER BY i.created_at DESC"
        statement = text(query)
        if association_ids is not None:
            statement = statement.bindparams(bindparam("association_ids", expanding=True))
        result = await self.session.execute(statement, params)
        return await self._items_with_images([dict(row) for row in result.mappings().all()])

    async def get_item(self, item_id: str) -> dict | None:
        result = await self.session.execute(
            text(
                "SELECT i.*, COALESCE(ac.account_id, legacy_ac.account_id) owner_account_id "
                "FROM marketplace_items i "
                "LEFT JOIN accounts ac ON ac.account_id=i.user_id "
                "LEFT JOIN accounts legacy_ac ON legacy_ac.user_id=i.user_id "
                "WHERE i.id=:id AND i.is_deleted=0"
            ),
            {"id": item_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def create_item(self, values: dict, images: list[str]) -> str:
        await self.session.execute(
            text(
                "INSERT INTO marketplace_items (id,association_id,user_id,category_id,title,description,price,condition_state,brand,item_age,location,contact_number,is_negotiable,status,listing_type,is_deleted) "
                "VALUES (:id,:association_id,:user_id,:category_id,:title,:description,:price,:condition_state,:brand,:item_age,:location,:contact_number,:is_negotiable,:status,:listing_type,0)"
            ),
            values,
        )
        for image_url in images:
            await self.session.execute(
                text("INSERT INTO marketplace_images (id,item_id,image_url,is_deleted) VALUES (:id,:item_id,:image_url,0)"),
                {"id": str(uuid.uuid4()), "item_id": values["id"], "image_url": image_url},
            )
        return values["id"]

    async def update_item(self, item_id: str, values: dict, images: list[str] | None) -> bool:
        if values:
            values["id"] = item_id
            fields = ",".join(f"{key}=:{key}" for key in values if key != "id")
            result = await self.session.execute(
                text(f"UPDATE marketplace_items SET {fields} WHERE id=:id AND is_deleted=0"), values
            )
            if not result.rowcount:
                return False
        if images is not None:
            await self.session.execute(text("UPDATE marketplace_images SET is_deleted=1 WHERE item_id=:id AND is_deleted=0"), {"id": item_id})
            for image_url in images:
                await self.session.execute(
                    text("INSERT INTO marketplace_images (id,item_id,image_url,is_deleted) VALUES (:id,:item_id,:image_url,0)"),
                    {"id": str(uuid.uuid4()), "item_id": item_id, "image_url": image_url},
                )
        return True

    async def delete_item(self, item_id: str) -> bool:
        result = await self.session.execute(
            text("UPDATE marketplace_items SET is_deleted=1 WHERE id=:id AND is_deleted=0"), {"id": item_id}
        )
        return bool(result.rowcount)

    async def favorites(self, account_id: str) -> list[dict]:
        rows = await self.list_items(account_id, None, {"status": None}, False)
        result = await self.session.execute(
            text("SELECT item_id FROM marketplace_favorites WHERE user_id=:id AND is_deleted=0"), {"id": account_id}
        )
        ids = {row["item_id"] for row in result.mappings()}
        return [row for row in rows if row["id"] in ids]

    async def toggle_favorite(self, account_id: str, item_id: str) -> bool:
        row = await self.session.execute(
            text("SELECT id,is_deleted FROM marketplace_favorites WHERE user_id=:user_id AND item_id=:item_id LIMIT 1"),
            {"user_id": account_id, "item_id": item_id},
        )
        existing = row.mappings().first()
        if existing:
            saved = bool(existing["is_deleted"])
            await self.session.execute(
                text("UPDATE marketplace_favorites SET is_deleted=:deleted WHERE id=:id"),
                {"deleted": 0 if saved else 1, "id": existing["id"]},
            )
            return saved
        await self.session.execute(
            text("INSERT INTO marketplace_favorites (id,user_id,item_id,is_deleted) VALUES (:id,:user_id,:item_id,0)"),
            {"id": str(uuid.uuid4()), "user_id": account_id, "item_id": item_id},
        )
        return True

    async def add_report(self, item_id: str, reporter_id: str, reason: str) -> str:
        report_id = str(uuid.uuid4())
        await self.session.execute(
            text("INSERT INTO marketplace_reports (id,item_id,reporter_id,reason,is_deleted) VALUES (:id,:item_id,:reporter_id,:reason,0)"),
            {"id": report_id, "item_id": item_id, "reporter_id": reporter_id, "reason": reason},
        )
        return report_id

    async def chat_threads(self, item_id: str, owner_id: str) -> list[dict]:
        result = await self.session.execute(
            text(
                "SELECT buyer.account_id buyer_id,COALESCE(ud.name,buyer.email) buyer_name,buyer.email buyer_email,"
                "MAX(c.created_at) last_message_at,(SELECT message FROM marketplace_chat mc WHERE mc.item_id=:item_id AND mc.is_deleted=0 AND (mc.sender_id=buyer.account_id OR mc.receiver_id=buyer.account_id) ORDER BY mc.created_at DESC LIMIT 1) last_message "
                "FROM marketplace_chat c JOIN accounts buyer ON (buyer.account_id=c.sender_id OR buyer.account_id=c.receiver_id) AND buyer.account_id<>:owner_id "
                "LEFT JOIN user_details ud ON ud.user_id=buyer.user_id WHERE c.item_id=:item_id AND c.is_deleted=0 GROUP BY buyer.account_id,buyer_name,buyer.email ORDER BY last_message_at DESC"
            ),
            {"item_id": item_id, "owner_id": owner_id},
        )
        return [dict(row) for row in result.mappings().all()]

    async def chat(self, item_id: str, first_account_id: str, second_account_id: str) -> list[dict]:
        result = await self.session.execute(
            text(
                "SELECT c.*,ac.email,COALESCE(ud.name,ac.email) sender_name "
                "FROM marketplace_chat c JOIN accounts ac ON ac.account_id=c.sender_id LEFT JOIN user_details ud ON ud.user_id=ac.user_id "
                "WHERE c.item_id=:item_id AND c.is_deleted=0 AND ((c.sender_id=:first AND c.receiver_id=:second) OR (c.sender_id=:second AND c.receiver_id=:first)) ORDER BY c.created_at"
            ),
            {"item_id": item_id, "first": first_account_id, "second": second_account_id},
        )
        return [dict(row) for row in result.mappings().all()]

    async def chat_for_account(self, item_id: str, account_id: str) -> list[dict]:
        """Return all messages for an owner when no buyer thread is selected yet."""
        result = await self.session.execute(
            text(
                "SELECT c.*,ac.email,COALESCE(ud.name,ac.email) sender_name "
                "FROM marketplace_chat c JOIN accounts ac ON ac.account_id=c.sender_id "
                "LEFT JOIN user_details ud ON ud.user_id=ac.user_id "
                "WHERE c.item_id=:item_id AND c.is_deleted=0 "
                "AND (c.sender_id=:account_id OR c.receiver_id=:account_id) "
                "ORDER BY c.created_at"
            ),
            {"item_id": item_id, "account_id": account_id},
        )
        return [dict(row) for row in result.mappings().all()]

    async def latest_chat_peer(self, item_id: str, account_id: str) -> str | None:
        result = await self.session.execute(
            text(
                "SELECT CASE WHEN sender_id=:account_id THEN receiver_id ELSE sender_id END "
                "FROM marketplace_chat WHERE item_id=:item_id AND is_deleted=0 "
                "AND (sender_id=:account_id OR receiver_id=:account_id) "
                "ORDER BY created_at DESC LIMIT 1"
            ),
            {"item_id": item_id, "account_id": account_id},
        )
        return result.scalar()

    async def add_chat(self, item_id: str, sender_id: str, receiver_id: str, message: str) -> dict:
        message_id = str(uuid.uuid4())
        await self.session.execute(
            text("INSERT INTO marketplace_chat (id,item_id,sender_id,receiver_id,message,is_deleted) VALUES (:id,:item_id,:sender_id,:receiver_id,:message,0)"),
            {"id": message_id, "item_id": item_id, "sender_id": sender_id, "receiver_id": receiver_id, "message": message},
        )
        return {"id": message_id, "item_id": item_id, "sender_id": sender_id, "receiver_id": receiver_id, "message": message}

    async def record_view(self, item_id: str, user_id: str) -> None:
        result = await self.session.execute(
            text("SELECT id,is_deleted FROM marketplace_views WHERE item_id=:item_id AND user_id=:user_id LIMIT 1"),
            {"item_id": item_id, "user_id": user_id},
        )
        existing = result.mappings().first()
        if existing:
            if existing["is_deleted"]:
                await self.session.execute(text("UPDATE marketplace_views SET is_deleted=0 WHERE id=:id"), {"id": existing["id"]})
            return
        await self.session.execute(
            text("INSERT INTO marketplace_views (id,item_id,user_id,is_deleted) VALUES (:id,:item_id,:user_id,0)"),
            {"id": str(uuid.uuid4()), "item_id": item_id, "user_id": user_id},
        )
