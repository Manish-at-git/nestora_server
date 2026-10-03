"""SQL access for visitor passes, gate logs, requests, and deliveries."""

import uuid

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession


class VisitorManagementRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def unit_for_user(self, user_id: str | None) -> str | None:
        if not user_id:
            return None
        return await self.session.scalar(
            text(
                "SELECT unit_id FROM user_details WHERE user_id=:user_id AND is_deleted=0 LIMIT 1"
            ),
            {"user_id": user_id},
        )

    async def association_ids_for_account(self, account_id: str) -> list[str]:
        """Return operational associations assigned to an employee account."""
        result = await self.session.scalars(
            text("SELECT association_id FROM admin_associations WHERE admin_id=:account_id"),
            {"account_id": account_id},
        )
        return list(result.all())

    async def account_ids_for_unit(self, unit_id: str) -> list[str]:
        result = await self.session.scalars(
            text(
                "SELECT ac.account_id FROM accounts ac "
                "JOIN user_details ud ON ud.user_id=ac.user_id "
                "WHERE ud.unit_id=:unit_id AND ud.is_deleted=0 "
                "AND ac.status='active' ORDER BY ac.created_at"
            ),
            {"unit_id": unit_id},
        )
        return list(result.all())

    async def find_visitor(
        self,
        mobile: str,
        association_ids: list[str] | None = None,
    ) -> dict | None:
        if association_ids is not None and not association_ids:
            return None
        query = "SELECT DISTINCT vis.* FROM visitors vis"
        params: dict = {"mobile": mobile}
        if association_ids is not None:
            query += (
                " JOIN visitor_visits vv ON vv.visitor_id=vis.id AND vv.is_deleted=0"
                " JOIN units un ON un.id=vv.unit_id JOIN blocks b ON b.id=un.block_id"
            )
        query += " WHERE vis.mobile=:mobile AND vis.is_deleted=0"
        if association_ids is not None:
            query += " AND b.association_id IN :association_ids"
            params["association_ids"] = tuple(association_ids)
        query += " ORDER BY vis.created_at DESC LIMIT 1"
        statement = text(query)
        if association_ids is not None:
            statement = statement.bindparams(bindparam("association_ids", expanding=True))
        row = await self.session.execute(
            statement,
            params,
        )
        value = row.mappings().first()
        return dict(value) if value else None

    async def save_visitor(self, values: dict) -> str:
        visitor = await self.find_visitor(values["mobile"])
        if visitor:
            await self.session.execute(
                text(
                    "UPDATE visitors SET name=:name, photo_url=COALESCE(:photo_url,photo_url), id_type=:id_type, id_number=:id_number WHERE id=:id AND is_deleted=0"
                ),
                {**values, "id": visitor["id"]},
            )
            return visitor["id"]
        visitor_id = str(uuid.uuid4())
        await self.session.execute(
            text(
                "INSERT INTO visitors (id,name,mobile,photo_url,id_type,id_number,is_deleted) VALUES (:id,:name,:mobile,:photo_url,:id_type,:id_number,0)"
            ),
            {**values, "id": visitor_id},
        )
        return visitor_id

    async def create_visit(self, values: dict) -> str:
        visit_id = str(uuid.uuid4())
        await self.session.execute(
            text(
                "INSERT INTO visitor_visits (id,visitor_id,unit_id,purpose,visitor_type,number_of_visitors,vehicle_number,notes,expected_duration,status,is_deleted) VALUES (:id,:visitor_id,:unit_id,:purpose,:visitor_type,:number_of_visitors,:vehicle_number,:notes,:expected_duration,'Pending',0)"
            ),
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
        result = await self.session.execute(
            text(
                "SELECT v.id visit_id,vis.name,vis.mobile,vis.photo_url,v.purpose,v.visitor_type,v.number_of_visitors,v.created_at FROM visitor_visits v JOIN visitors vis ON vis.id=v.visitor_id AND vis.is_deleted=0 WHERE v.unit_id=:unit_id AND v.status='Pending' AND v.is_deleted=0 ORDER BY v.created_at DESC"
            ),
            {"unit_id": unit_id},
        )
        return [dict(row) for row in result.mappings().all()]

    async def security_gate_requests(self, association_ids: list[str] | None) -> list[dict]:
        """Return walk-in requests that still need a gate decision or action."""
        if association_ids is not None and not association_ids:
            return []
        query = (
            "SELECT v.id visit_id,vis.name visitor_name,vis.mobile,v.visitor_type,v.purpose,"
            "v.status,v.created_at,v.check_in_time,un.unit_number,b.name block_name "
            "FROM visitor_visits v "
            "JOIN visitors vis ON vis.id=v.visitor_id AND vis.is_deleted=0 "
            "LEFT JOIN units un ON un.id=v.unit_id "
            "LEFT JOIN blocks b ON b.id=un.block_id "
            "WHERE v.status IN ('Pending','Approved','Denied') AND v.is_deleted=0"
        )
        params: dict = {}
        if association_ids is not None:
            query += " AND b.association_id IN :association_ids"
            params["association_ids"] = tuple(association_ids)
        query += " ORDER BY v.created_at DESC LIMIT 100"
        statement = text(query)
        if association_ids is not None:
            statement = statement.bindparams(bindparam("association_ids", expanding=True))
        result = await self.session.execute(statement, params)
        return [dict(row) for row in result.mappings().all()]

    async def gate_request_history(
        self,
        *,
        unit_id: str | None = None,
        association_ids: list[str] | None = None,
    ) -> list[dict]:
        """Return the complete walk-in approval lifecycle visible to a role."""
        if association_ids is not None and not association_ids:
            return []

        query = (
            "SELECT v.id visit_id,vis.name visitor_name,vis.mobile,v.visitor_type,v.purpose,"
            "v.status,v.created_at,v.check_in_time,v.check_out_time,un.unit_number,b.name block_name "
            "FROM visitor_visits v "
            "JOIN visitors vis ON vis.id=v.visitor_id AND vis.is_deleted=0 "
            "LEFT JOIN units un ON un.id=v.unit_id "
            "LEFT JOIN blocks b ON b.id=un.block_id "
            "WHERE v.is_deleted=0"
        )
        params: dict = {}
        if unit_id:
            query += " AND v.unit_id=:unit_id"
            params["unit_id"] = unit_id
        if association_ids is not None:
            query += " AND b.association_id IN :association_ids"
            params["association_ids"] = tuple(association_ids)
        query += " ORDER BY v.created_at DESC LIMIT 100"

        statement = text(query)
        if association_ids is not None:
            statement = statement.bindparams(bindparam("association_ids", expanding=True))
        result = await self.session.execute(statement, params)
        return [dict(row) for row in result.mappings().all()]

    async def update_visit(self, visit_id: str, values: dict) -> None:
        fields = ",".join(f"{key}=:{key}" for key in values)
        await self.session.execute(
            text(f"UPDATE visitor_visits SET {fields} WHERE id=:id AND is_deleted=0"),
            {**values, "id": visit_id},
        )

    async def preapproved_create(self, values: dict) -> str:
        pass_id = str(uuid.uuid4())
        await self.session.execute(
            text(
                "INSERT INTO pre_approved_visitors (id,resident_id,unit_id,visitor_name,mobile,visitor_type,pass_code,otp,visit_date,start_time,end_time,number_of_visitors,vehicle_number,purpose,pass_type,status,created_by,is_deleted) VALUES (:id,:resident_id,:unit_id,:visitor_name,:mobile,:visitor_type,:pass_code,:otp,:visit_date,:start_time,:end_time,:number_of_visitors,:vehicle_number,:purpose,:pass_type,'Active',:created_by,0)"
            ),
            {**values, "id": pass_id},
        )
        return pass_id

    async def resident_preapproved(self, unit_id: str) -> list[dict]:
        result = await self.session.execute(
            text(
                "SELECT p.*,un.unit_number,b.name block_name,(SELECT check_in FROM visitor_logs WHERE pre_approved_id=p.id AND is_deleted=0 ORDER BY check_in DESC LIMIT 1) last_check_in FROM pre_approved_visitors p LEFT JOIN units un ON un.id=p.unit_id LEFT JOIN blocks b ON b.id=un.block_id WHERE p.unit_id=:unit_id AND p.is_deleted=0 ORDER BY p.visit_date DESC,p.start_time DESC"
            ),
            {"unit_id": unit_id},
        )
        return [dict(row) for row in result.mappings().all()]

    async def pass_is_in_associations(self, pass_id: str, association_ids: list[str]) -> bool:
        if not association_ids:
            return False
        statement = text(
            "SELECT 1 FROM pre_approved_visitors p "
            "JOIN units un ON un.id=p.unit_id "
            "JOIN blocks b ON b.id=un.block_id "
            "WHERE p.id=:pass_id AND p.is_deleted=0 "
            "AND b.association_id IN :association_ids LIMIT 1"
        ).bindparams(bindparam("association_ids", expanding=True))
        return bool(
            await self.session.scalar(
                statement,
                {"pass_id": pass_id, "association_ids": tuple(association_ids)},
            )
        )

    async def unit_is_in_associations(
        self,
        unit_id: str,
        association_ids: list[str],
    ) -> bool:
        if not association_ids:
            return False
        statement = text(
            "SELECT 1 FROM units un JOIN blocks b ON b.id=un.block_id "
            "WHERE un.id=:unit_id AND b.association_id IN :association_ids LIMIT 1"
        ).bindparams(bindparam("association_ids", expanding=True))
        return bool(
            await self.session.scalar(
                statement,
                {"unit_id": unit_id, "association_ids": tuple(association_ids)},
            )
        )

    async def get_pass(
        self, pass_id: str | None = None, pass_code: str | None = None
    ) -> dict | None:
        condition = "id=:id" if pass_id else "pass_code=:pass_code"
        params = {"id": pass_id} if pass_id else {"pass_code": pass_code}
        row = await self.session.execute(
            text(f"SELECT * FROM pre_approved_visitors WHERE {condition} AND is_deleted=0 LIMIT 1"),
            params,
        )
        value = row.mappings().first()
        return dict(value) if value else None

    async def public_pass(self, pass_code: str) -> dict | None:
        row = await self.session.execute(
            text(
                "SELECT p.visitor_name,CONCAT('******',RIGHT(p.mobile,4)) mobile,"
                "p.visitor_type,p.pass_code,p.visit_date,p.start_time,p.end_time,"
                "p.number_of_visitors,p.pass_type,p.status,un.unit_number,b.name block_name "
                "FROM pre_approved_visitors p LEFT JOIN units un ON un.id=p.unit_id "
                "LEFT JOIN blocks b ON b.id=un.block_id "
                "WHERE p.pass_code=:pass_code AND p.is_deleted=0 LIMIT 1"
            ),
            {"pass_code": pass_code},
        )
        value = row.mappings().first()
        return dict(value) if value else None

    async def cancel_pass(self, pass_id: str, unit_id: str) -> bool:
        result = await self.session.execute(
            text(
                "UPDATE pre_approved_visitors SET status='Cancelled' WHERE id=:id AND unit_id=:unit_id AND is_deleted=0"
            ),
            {"id": pass_id, "unit_id": unit_id},
        )
        return bool(result.rowcount)

    async def passes(
        self,
        search: str | None = None,
        today: bool = False,
        association_ids: list[str] | None = None,
    ) -> list[dict]:
        if association_ids is not None and not association_ids:
            return []
        query = (
            "SELECT p.id,p.resident_id,p.unit_id,p.visitor_name,p.mobile,p.visitor_type,"
            "p.pass_code,p.visit_date,p.start_time,p.end_time,p.number_of_visitors,"
            "p.vehicle_number,p.purpose,p.pass_type,p.status,p.created_at,"
            "(SELECT id FROM visitor_logs WHERE pre_approved_id=p.id "
            "AND check_out IS NULL AND is_deleted=0 LIMIT 1) active_log_id,"
            "ud.name resident_name,un.unit_number,b.name block_name "
            "FROM pre_approved_visitors p "
            "JOIN user_details ud ON ud.user_id=p.resident_id AND ud.is_deleted=0 "
            "LEFT JOIN units un ON un.id=p.unit_id "
            "LEFT JOIN blocks b ON b.id=un.block_id WHERE p.is_deleted=0"
        )
        params: dict = {}
        if association_ids is not None:
            query += " AND b.association_id IN :association_ids"
            params["association_ids"] = tuple(association_ids)
        if today:
            query += " AND p.visit_date=CURDATE() AND p.status IN ('Active','Used')"
        if search:
            query += " AND (p.visitor_name LIKE :query OR p.mobile LIKE :query OR p.pass_code LIKE :query OR p.otp=:otp OR un.unit_number LIKE :query)"
            params.update({"query": f"%{search}%", "otp": search})
        query += " ORDER BY p.visit_date DESC,p.start_time ASC LIMIT 100"
        statement = text(query)
        if association_ids is not None:
            statement = statement.bindparams(bindparam("association_ids", expanding=True))
        result = await self.session.execute(statement, params)
        return [dict(row) for row in result.mappings().all()]

    async def create_log(self, values: dict) -> str:
        log_id = str(uuid.uuid4())
        await self.session.execute(
            text(
                "INSERT INTO visitor_logs (id,pre_approved_id,gate,guard_id,visitor_photo_url,remarks,is_deleted) VALUES (:id,:pre_approved_id,:gate,:guard_id,:visitor_photo_url,:remarks,0)"
            ),
            {**values, "id": log_id},
        )
        return log_id

    async def active_log(self, pass_id: str) -> dict | None:
        row = await self.session.execute(
            text(
                "SELECT * FROM visitor_logs WHERE pre_approved_id=:pass_id AND check_out IS NULL AND is_deleted=0 ORDER BY check_in DESC LIMIT 1"
            ),
            {"pass_id": pass_id},
        )
        value = row.mappings().first()
        return dict(value) if value else None

    async def close_log(self, log_id: str) -> bool:
        result = await self.session.execute(
            text(
                "UPDATE visitor_logs SET check_out=CURRENT_TIMESTAMP WHERE id=:id AND check_out IS NULL AND is_deleted=0"
            ),
            {"id": log_id},
        )
        return bool(result.rowcount)

    async def get_log(self, log_id: str) -> dict | None:
        row = await self.session.execute(
            text("SELECT * FROM visitor_logs WHERE id=:id AND is_deleted=0 LIMIT 1"), {"id": log_id}
        )
        value = row.mappings().first()
        return dict(value) if value else None

    async def log_is_in_associations(self, log_id: str, association_ids: list[str]) -> bool:
        if not association_ids:
            return False
        statement = text(
            "SELECT 1 FROM visitor_logs l "
            "JOIN pre_approved_visitors p ON p.id=l.pre_approved_id AND p.is_deleted=0 "
            "JOIN units un ON un.id=p.unit_id "
            "JOIN blocks b ON b.id=un.block_id "
            "WHERE l.id=:log_id AND l.is_deleted=0 "
            "AND b.association_id IN :association_ids LIMIT 1"
        ).bindparams(bindparam("association_ids", expanding=True))
        return bool(
            await self.session.scalar(
                statement,
                {"log_id": log_id, "association_ids": tuple(association_ids)},
            )
        )

    async def visitor_queue(
        self,
        recent_hours: int | None = None,
        association_ids: list[str] | None = None,
    ) -> list[dict]:
        if association_ids is not None and not association_ids:
            return []
        query = "SELECT l.id log_id,p.id pass_id,p.visitor_name,p.mobile,p.visitor_type,p.pass_type,p.pass_code,l.check_in,l.check_out,un.unit_number,b.name block_name FROM visitor_logs l JOIN pre_approved_visitors p ON p.id=l.pre_approved_id AND p.is_deleted=0 LEFT JOIN units un ON un.id=p.unit_id LEFT JOIN blocks b ON b.id=un.block_id WHERE l.is_deleted=0"
        params: dict = {}
        if association_ids is not None:
            query += " AND b.association_id IN :association_ids"
            params["association_ids"] = tuple(association_ids)
        if recent_hours is None:
            query += " AND l.check_out IS NULL"
        else:
            query += f" AND l.check_out IS NOT NULL AND l.check_out >= DATE_SUB(NOW(), INTERVAL {int(recent_hours)} HOUR)"
        query += " ORDER BY COALESCE(l.check_out,l.check_in) DESC LIMIT 100"
        statement = text(query)
        if association_ids is not None:
            statement = statement.bindparams(bindparam("association_ids", expanding=True))
        result = await self.session.execute(statement, params)
        return [dict(row) for row in result.mappings().all()]

    async def history(
        self,
        *,
        unit_id: str | None = None,
        association_ids: list[str] | None = None,
    ) -> list[dict]:
        if association_ids is not None and not association_ids:
            return []
        preapproved_where = ["l.check_out IS NOT NULL", "l.is_deleted=0"]
        walk_in_where = ["v.status IN ('Denied','Checked-Out')", "v.is_deleted=0"]
        params: dict = {}
        if unit_id:
            preapproved_where.append("p.unit_id=:unit_id")
            walk_in_where.append("v.unit_id=:unit_id")
            params["unit_id"] = unit_id
        if association_ids is not None:
            preapproved_where.append("b.association_id IN :association_ids")
            walk_in_where.append("b.association_id IN :association_ids")
            params["association_ids"] = tuple(association_ids)
        query = (
            "SELECT l.id visit_id,p.visitor_name,p.mobile,p.purpose,p.visitor_type,"
            "l.check_in,l.check_out,'Checked-Out' status,un.unit_number,b.name block_name,"
            "'Pre-Approved' entry_type FROM visitor_logs l "
            "JOIN pre_approved_visitors p ON p.id=l.pre_approved_id AND p.is_deleted=0 "
            "LEFT JOIN units un ON un.id=p.unit_id LEFT JOIN blocks b ON b.id=un.block_id "
            f"WHERE {' AND '.join(preapproved_where)} UNION ALL "
            "SELECT v.id visit_id,vis.name visitor_name,vis.mobile,v.purpose,v.visitor_type,"
            "COALESCE(v.check_in_time,v.created_at) check_in,v.check_out_time check_out,v.status,"
            "un.unit_number,b.name block_name,'Walk-In' entry_type FROM visitor_visits v "
            "JOIN visitors vis ON vis.id=v.visitor_id AND vis.is_deleted=0 "
            "LEFT JOIN units un ON un.id=v.unit_id LEFT JOIN blocks b ON b.id=un.block_id "
            f"WHERE {' AND '.join(walk_in_where)} "
            "ORDER BY check_out DESC,check_in DESC LIMIT 100"
        )
        statement = text(query)
        if association_ids is not None:
            statement = statement.bindparams(bindparam("association_ids", expanding=True))
        result = await self.session.execute(statement, params)
        return [dict(row) for row in result.mappings().all()]

    async def active_visitors(self, association_ids: list[str] | None) -> list[dict]:
        if association_ids is not None and not association_ids:
            return []
        params: dict = {}
        association_filter = ""
        if association_ids is not None:
            association_filter = " AND b.association_id IN :association_ids"
            params["association_ids"] = tuple(association_ids)
        query = (
            "SELECT l.id entry_id,'pre_approved' source_type,p.visitor_name,p.mobile,"
            "p.visitor_type,p.purpose,p.end_time scheduled_end,l.gate,l.check_in,"
            "un.unit_number,b.name block_name FROM visitor_logs l "
            "JOIN pre_approved_visitors p ON p.id=l.pre_approved_id AND p.is_deleted=0 "
            "LEFT JOIN units un ON un.id=p.unit_id LEFT JOIN blocks b ON b.id=un.block_id "
            "WHERE l.check_out IS NULL AND l.is_deleted=0"
            f"{association_filter} UNION ALL "
            "SELECT v.id entry_id,'walk_in' source_type,vis.name visitor_name,vis.mobile,"
            "v.visitor_type,v.purpose,NULL scheduled_end,NULL gate,v.check_in_time check_in,"
            "un.unit_number,b.name block_name FROM visitor_visits v "
            "JOIN visitors vis ON vis.id=v.visitor_id AND vis.is_deleted=0 "
            "LEFT JOIN units un ON un.id=v.unit_id LEFT JOIN blocks b ON b.id=un.block_id "
            "WHERE v.status='Checked-In' AND v.is_deleted=0"
            f"{association_filter} ORDER BY check_in DESC"
        )
        statement = text(query)
        if association_ids is not None:
            statement = statement.bindparams(bindparam("association_ids", expanding=True))
        result = await self.session.execute(statement, params)
        return [dict(row) for row in result.mappings().all()]

    async def visit_is_in_associations(
        self,
        visit_id: str,
        association_ids: list[str],
    ) -> bool:
        if not association_ids:
            return False
        statement = text(
            "SELECT 1 FROM visitor_visits v JOIN units un ON un.id=v.unit_id "
            "JOIN blocks b ON b.id=un.block_id WHERE v.id=:visit_id "
            "AND v.is_deleted=0 AND b.association_id IN :association_ids LIMIT 1"
        ).bindparams(bindparam("association_ids", expanding=True))
        return bool(
            await self.session.scalar(
                statement,
                {"visit_id": visit_id, "association_ids": tuple(association_ids)},
            )
        )

    async def check_in_visit(self, visit_id: str) -> bool:
        result = await self.session.execute(
            text(
                "UPDATE visitor_visits SET status='Checked-In',check_in_time=CURRENT_TIMESTAMP "
                "WHERE id=:id AND status='Approved' AND is_deleted=0"
            ),
            {"id": visit_id},
        )
        return bool(result.rowcount)

    async def check_out_visit(self, visit_id: str) -> bool:
        result = await self.session.execute(
            text(
                "UPDATE visitor_visits SET status='Checked-Out',check_out_time=CURRENT_TIMESTAMP "
                "WHERE id=:id AND status='Checked-In' AND is_deleted=0"
            ),
            {"id": visit_id},
        )
        return bool(result.rowcount)

    async def create_delivery(self, values: dict) -> str:
        delivery_id = str(uuid.uuid4())
        await self.session.execute(
            text(
                "INSERT INTO deliveries (id,unit_id,resident_id,delivery_type,company_name,delivery_person_name,mobile,status,gate,guard_id,package_photo_url,is_deleted) VALUES (:id,:unit_id,:resident_id,:delivery_type,:company_name,:delivery_person_name,:mobile,:status,:gate,:guard_id,:package_photo_url,0)"
            ),
            {**values, "id": delivery_id},
        )
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
        result = await self.session.execute(
            text(
                "UPDATE deliveries SET status='Completed',check_out=CURRENT_TIMESTAMP WHERE id=:id AND is_deleted=0"
            ),
            {"id": delivery_id},
        )
        return bool(result.rowcount)

    async def resident_search(
        self,
        query: str,
        association_ids: list[str] | None,
    ) -> list[dict]:
        if association_ids is not None and not association_ids:
            return []
        sql = "SELECT ud.user_id,ud.name,ud.contact_number,un.id unit_id,un.unit_number,b.name block_name FROM user_details ud JOIN units un ON un.id=ud.unit_id LEFT JOIN blocks b ON b.id=un.block_id WHERE ud.is_deleted=0"
        params: dict = {"query": f"%{query}%"}
        if association_ids is not None:
            sql += " AND b.association_id IN :association_ids"
            params["association_ids"] = tuple(association_ids)
        sql += " AND (ud.name LIKE :query OR ud.contact_number LIKE :query OR un.unit_number LIKE :query) LIMIT 20"
        statement = text(sql)
        if association_ids is not None:
            statement = statement.bindparams(bindparam("association_ids", expanding=True))
        result = await self.session.execute(statement, params)
        return [dict(row) for row in result.mappings().all()]

    async def vehicles(self) -> list[dict]:
        result = await self.session.execute(
            text(
                "SELECT v.id,v.type vehicle_type,v.registration_number,ud.name homeowner_name,un.unit_number,b.name block_name FROM vehicles v JOIN user_details ud ON ud.user_id=v.user_id AND ud.is_deleted=0 LEFT JOIN units un ON un.id=ud.unit_id LEFT JOIN blocks b ON b.id=un.block_id WHERE v.is_deleted=0 ORDER BY un.unit_number,v.registration_number"
            )
        )
        return [dict(row) for row in result.mappings().all()]
