"""Add the manager-only Staff Attendance Report feature."""

import uuid

import sqlalchemy as sa
from alembic import op


revision = "20261116_0063"
down_revision = "20261116_0062"
branch_labels = None
depends_on = None

FEATURE_ID = "70000000-0000-4000-8000-000000000003"
FEATURE_CODE = "staff_attendance_report"


def upgrade() -> None:
    bind = op.get_bind()
    feature_id = bind.execute(sa.text("SELECT id FROM features WHERE code=:code"), {"code": FEATURE_CODE}).scalar()
    if feature_id is None:
        feature_id = FEATURE_ID
        bind.execute(
            sa.text(
                "INSERT INTO features (id,code,name,description,icon,route,order_index,is_system,is_active,is_deleted) "
                "VALUES (:id,:code,:name,:description,:icon,:route,13,1,1,0)"
            ),
            {
                "id": feature_id,
                "code": FEATURE_CODE,
                "name": "Staff Attendance Report",
                "description": "Month-wise staff attendance, completed hours, and open check-ins.",
                "icon": "CalendarDays",
                "route": "/staff/attendance-report",
            },
        )
    else:
        bind.execute(
            sa.text(
                "UPDATE features SET name='Staff Attendance Report',route='/staff/attendance-report',"
                "icon='CalendarDays',order_index=13,is_active=1,is_deleted=0 WHERE id=:id"
            ),
            {"id": feature_id},
        )
    roles = bind.execute(sa.text("SELECT id FROM roles WHERE code IN ('super_admin','admin') AND is_deleted=0")).scalars()
    for role_id in roles:
        permission_id = bind.execute(
            sa.text("SELECT id FROM role_feature_permissions WHERE role_id=:role_id AND feature_id=:feature_id"),
            {"role_id": role_id, "feature_id": feature_id},
        ).scalar()
        if permission_id:
            bind.execute(
                sa.text(
                    "UPDATE role_feature_permissions SET can_view=1,can_create=0,can_update=0,can_delete=0,"
                    "sidebar_order=13,is_deleted=0 WHERE id=:id"
                ),
                {"id": permission_id},
            )
        else:
            bind.execute(
                sa.text(
                    "INSERT INTO role_feature_permissions "
                    "(id,role_id,feature_id,can_view,can_create,can_update,can_delete,is_deleted,sidebar_order) "
                    "VALUES (:id,:role_id,:feature_id,1,0,0,0,0,13)"
                ),
                {"id": str(uuid.uuid4()), "role_id": role_id, "feature_id": feature_id},
            )


def downgrade() -> None:
    raise RuntimeError("Staff Attendance Report feature removal requires a reviewed, data-preserving downgrade.")
