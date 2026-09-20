"""SQL access for visitor passes, gate logs, requests, and deliveries."""

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class VisitorManagementRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def unit_for_user(self, user_id: str | None) -> str | None:
        if not user_id:
            return None
        return await self.session.scalar(
            text("SELECT unit_id FROM user_details WHERE user_id=:user_id AND is_deleted=0 LIMIT 1"),
            {"user_id": user_id},
        )

    async def find_visitor(self, mobile: str) -> dict | None:
        row = await self.session.execute(
            text("SELECT * FROM visitors WHERE mobile=:mobile AND is_deleted=0 ORDER BY created_at DESC LIMIT 1"),
            {"mobile": mobile},
        )
        value = row.mappings().first()
        return dict(value) if value else None

    async def save_visitor(self, values: dict) -> str:
        visitor = await self.find_visitor(values["mobile"])
        if visitor:
            await self.session.execute(
                text("UPDATE visitors SET name=:name, photo_url=COALESCE(:photo_url,photo_url), id_type=:id_type, id_number=:id_number WHERE id=:id AND is_deleted=0"),
                {**values, "id": visitor["id"]},
            )
            return visitor["id"]
        visitor_id = str(uuid.uuid4())
        await self.session.execute(
            text("INSERT INTO visitors (id,name,mobile,photo_url,id_type,id_number,is_deleted) VALUES (:id,:name,:mobile,:photo_url,:id_type,:id_number,0)"),
            {**values, "id": visitor_id},
        )
        return visitor_id

    async def create_visit(self, values: dict) -> str:
        visit_id = str(uuid.uuid4())
        await self.session.execute(
            text("INSERT INTO visitor_visits (id,visitor_id,unit_id,purpose,visitor_type,number_of_visitors,vehicle_number,notes,expected_duration,status,is_deleted) VALUES (:id,:visitor_id,:unit_id,:purpose,:visitor_type,:number_of_visitors,:vehicle_number,:notes,:expected_duration,'Pending',0)"),
            {**values, "id": visit_id},
        )
        return visit_id

    async def get_visit(self, visit_id: str, status_value: str | None = None) -> dict | None:
        query = "SELECT * FROM visitor_visits WHERE id=:id AND is_deleted=0"
        params = {"id": visit_id}
        if status_value:
            query += " AND status=:status"
            params["status"] = status_value
        row = await self.session.execute(text(query), params)
        value = row.mappings().first()
        return dict(value) if value else None

    async def pending_visits(self, unit_id: str) -> list[dict]:
        result = await self.session.execute(text("SELECT v.id visit_id,vis.name,vis.mobile,vis.photo_url,v.purpose,v.visitor_type,v.number_of_visitors,v.created_at FROM visitor_visits v JOIN visitors vis ON vis.id=v.visitor_id AND vis.is_deleted=0 WHERE v.unit_id=:unit_id AND v.status='Pending' AND v.is_deleted=0 ORDER BY v.created_at DESC"), {"unit_id": unit_id})
        return [dict(row) for row in result.mappings().all()]

    async def update_visit(self, visit_id: str, values: dict) -> None:
        fields = ",".join(f"{key}=:{key}" for key in values)
        await self.session.execute(text(f"UPDATE visitor_visits SET {fields} WHERE id=:id AND is_deleted=0"), {**values, "id": visit_id})

    async def preapproved_create(self, values: dict) -> str:
        pass_id = str(uuid.uuid4())
        await self.session.execute(text("INSERT INTO pre_approved_visitors (id,resident_id,unit_id,visitor_name,mobile,visitor_type,pass_code,otp,visit_date,start_time,end_time,number_of_visitors,vehicle_number,purpose,pass_type,status,created_by,is_deleted) VALUES (:id,:resident_id,:unit_id,:visitor_name,:mobile,:visitor_type,:pass_code,:otp,:visit_date,:start_time,:end_time,:number_of_visitors,:vehicle_number,:purpose,:pass_type,'Active',:created_by,0)"), {**values, "id": pass_id})
        return pass_id

    async def resident_preapproved(self, unit_id: str) -> list[dict]:
        result = await self.session.execute(text("SELECT p.*,un.unit_number,b.name block_name,(SELECT check_in FROM visitor_logs WHERE pre_approved_id=p.id AND is_deleted=0 ORDER BY check_in DESC LIMIT 1) last_check_in FROM pre_approved_visitors p LEFT JOIN units un ON un.id=p.unit_id LEFT JOIN blocks b ON b.id=un.block_id WHERE p.unit_id=:unit_id AND p.is_deleted=0 ORDER BY p.visit_date DESC,p.start_time DESC"), {"unit_id": unit_id})
        return [dict(row) for row in result.mappings().all()]

    async def get_pass(self, pass_id: str | None = None, pass_code: str | None = None) -> dict | None:
        condition = "id=:id" if pass_id else "pass_code=:pass_code"
        params = {"id": pass_id} if pass_id else {"pass_code": pass_code}
        row = await self.session.execute(text(f"SELECT * FROM pre_approved_visitors WHERE {condition} AND is_deleted=0 LIMIT 1"), params)
        value = row.mappings().first()
        return dict(value) if value else None

    async def cancel_pass(self, pass_id: str, unit_id: str) -> bool:
        result = await self.session.execute(text("UPDATE pre_approved_visitors SET status='Cancelled' WHERE id=:id AND unit_id=:unit_id AND is_deleted=0"), {"id": pass_id, "unit_id": unit_id})
        return bool(result.rowcount)

    async def passes(self, search: str | None = None, today: bool = False) -> list[dict]:
        query = "SELECT p.*,(SELECT id FROM visitor_logs WHERE pre_approved_id=p.id AND check_out IS NULL AND is_deleted=0 LIMIT 1) active_log_id,ud.name resident_name,un.unit_number,b.name block_name FROM pre_approved_visitors p JOIN user_details ud ON ud.user_id=p.resident_id LEFT JOIN units un ON un.id=p.unit_id LEFT JOIN blocks b ON b.id=un.block_id WHERE p.is_deleted=0"
        params: dict = {}
        if today:
            query += " AND p.visit_date=CURDATE() AND p.status IN ('Active','Used')"
        if search:
            query += " AND (p.mobile LIKE :query OR p.pass_code LIKE :query OR p.otp=:otp)"
            params.update({"query": f"%{search}%", "otp": search})
        query += " ORDER BY p.visit_date DESC,p.start_time ASC LIMIT 100"
        result = await self.session.execute(text(query), params)
        return [dict(row) for row in result.mappings().all()]

    async def create_log(self, values: dict) -> str:
        log_id = str(uuid.uuid4())
        await self.session.execute(text("INSERT INTO visitor_logs (id,pre_approved_id,gate,guard_id,visitor_photo_url,remarks,is_deleted) VALUES (:id,:pre_approved_id,:gate,:guard_id,:visitor_photo_url,:remarks,0)"), {**values, "id": log_id})
        return log_id

    async def active_log(self, pass_id: str) -> dict | None:
        row = await self.session.execute(text("SELECT * FROM visitor_logs WHERE pre_approved_id=:pass_id AND check_out IS NULL AND is_deleted=0 ORDER BY check_in DESC LIMIT 1"), {"pass_id": pass_id})
        value = row.mappings().first()
        return dict(value) if value else None

    async def close_log(self, log_id: str) -> bool:
        result = await self.session.execute(text("UPDATE visitor_logs SET check_out=CURRENT_TIMESTAMP WHERE id=:id AND check_out IS NULL AND is_deleted=0"), {"id": log_id})
        return bool(result.rowcount)

    async def get_log(self, log_id: str) -> dict | None:
        row = await self.session.execute(text("SELECT * FROM visitor_logs WHERE id=:id AND is_deleted=0 LIMIT 1"), {"id": log_id})
        value = row.mappings().first()
        return dict(value) if value else None

    async def visitor_queue(self, recent_hours: int | None = None) -> list[dict]:
        query = "SELECT l.id log_id,p.id pass_id,p.visitor_name,p.mobile,p.visitor_type,p.pass_type,p.pass_code,l.check_in,l.check_out,un.unit_number,b.name block_name FROM visitor_logs l JOIN pre_approved_visitors p ON p.id=l.pre_approved_id AND p.is_deleted=0 LEFT JOIN units un ON un.id=p.unit_id LEFT JOIN blocks b ON b.id=un.block_id WHERE l.is_deleted=0"
        if recent_hours is None:
            query += " AND l.check_out IS NULL"
        else:
            query += f" AND l.check_out IS NOT NULL AND l.check_out >= DATE_SUB(NOW(), INTERVAL {int(recent_hours)} HOUR)"
        query += " ORDER BY COALESCE(l.check_out,l.check_in) DESC LIMIT 100"
        result = await self.session.execute(text(query))
        return [dict(row) for row in result.mappings().all()]

    async def history(self) -> list[dict]:
        result = await self.session.execute(text("SELECT l.id visit_id,p.visitor_name,p.mobile,p.purpose,p.visitor_type,l.check_in,l.check_out,'Exited' status,un.unit_number,b.name block_name,'Pre-Approved' entry_type FROM visitor_logs l JOIN pre_approved_visitors p ON p.id=l.pre_approved_id AND p.is_deleted=0 LEFT JOIN units un ON un.id=p.unit_id LEFT JOIN blocks b ON b.id=un.block_id WHERE l.check_out IS NOT NULL AND l.is_deleted=0 UNION ALL SELECT v.id visit_id,vis.name visitor_name,vis.mobile,v.purpose,v.visitor_type,COALESCE(v.check_in_time,v.created_at) check_in,v.check_out_time check_out,v.status,un.unit_number,b.name block_name,'Regular' entry_type FROM visitor_visits v JOIN visitors vis ON vis.id=v.visitor_id AND vis.is_deleted=0 LEFT JOIN units un ON un.id=v.unit_id LEFT JOIN blocks b ON b.id=un.block_id WHERE v.status NOT IN ('Active','Entered','Pending','Checked-In') AND v.is_deleted=0 ORDER BY check_out DESC,check_in DESC LIMIT 100"))
        return [dict(row) for row in result.mappings().all()]

    async def create_delivery(self, values: dict) -> str:
        delivery_id = str(uuid.uuid4())
        await self.session.execute(text("INSERT INTO deliveries (id,unit_id,resident_id,delivery_type,company_name,delivery_person_name,mobile,status,gate,guard_id,package_photo_url,is_deleted) VALUES (:id,:unit_id,:resident_id,:delivery_type,:company_name,:delivery_person_name,:mobile,:status,:gate,:guard_id,:package_photo_url,0)"), {**values, "id": delivery_id})
        return delivery_id

    async def deliveries(self, unit_id: str | None = None, active: bool = False) -> list[dict]:
        query = "SELECT d.*,un.unit_number,b.name block_name FROM deliveries d LEFT JOIN units un ON un.id=d.unit_id LEFT JOIN blocks b ON b.id=un.block_id WHERE d.is_deleted=0"
        params: dict = {}
        if unit_id:
            query += " AND d.unit_id=:unit_id"
            params["unit_id"] = unit_id
        if active:
            query += " AND d.status IN ('Inside Premises','Collected at Gate')"
        else:
            query += " AND d.status IN ('Completed','Cancelled')" if not unit_id else ""
        query += " ORDER BY COALESCE(d.check_out,d.check_in) DESC LIMIT 100"
        result = await self.session.execute(text(query), params)
        return [dict(row) for row in result.mappings().all()]

    async def complete_delivery(self, delivery_id: str) -> bool:
        result = await self.session.execute(text("UPDATE deliveries SET status='Completed',check_out=CURRENT_TIMESTAMP WHERE id=:id AND is_deleted=0"), {"id": delivery_id})
        return bool(result.rowcount)

    async def resident_search(self, query: str) -> list[dict]:
        result = await self.session.execute(text("SELECT ud.user_id,ud.name,ud.contact_number,un.id unit_id,un.unit_number,b.name block_name FROM user_details ud JOIN units un ON un.id=ud.unit_id LEFT JOIN blocks b ON b.id=un.block_id WHERE ud.is_deleted=0 AND (ud.name LIKE :query OR ud.contact_number LIKE :query OR un.unit_number LIKE :query) LIMIT 20"), {"query": f"%{query}%"})
        return [dict(row) for row in result.mappings().all()]

    async def vehicles(self) -> list[dict]:
        result = await self.session.execute(text("SELECT v.id,v.type vehicle_type,v.registration_number,ud.name homeowner_name,un.unit_number,b.name block_name FROM vehicles v JOIN user_details ud ON ud.user_id=v.user_id AND ud.is_deleted=0 LEFT JOIN units un ON un.id=ud.unit_id LEFT JOIN blocks b ON b.id=un.block_id WHERE v.is_deleted=0 ORDER BY un.unit_number,v.registration_number"))
        return [dict(row) for row in result.mappings().all()]
