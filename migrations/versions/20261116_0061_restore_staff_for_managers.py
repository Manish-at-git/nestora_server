"""Restore the main Staff menu for managers without duplicating it for Security."""

import uuid

import sqlalchemy as sa
from alembic import op


revision = "20261116_0061"
down_revision = "20261114_0060"
branch_labels = None
depends_on = None

STAFF_FEATURE_ID = "70000000-0000-4000-8000-000000000001"
STAFF_SIDEBAR_ORDER = 12
MANAGER_PERMISSIONS = {
    "super_admin": (True, True, True, False),
    "admin": (True, True, True, False),
}


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE features SET code = 'staff', name = 'Staff', route = '/staff', icon = 'IdCard', "
            "order_index = :sidebar_order, is_active = 1, is_deleted = 0 WHERE id = :feature_id"
        ),
        {"feature_id": STAFF_FEATURE_ID, "sidebar_order": STAFF_SIDEBAR_ORDER},
    )

    roles = bind.execute(
        sa.text("SELECT id, code FROM roles WHERE code IN ('super_admin', 'admin', 'security') AND is_deleted = 0")
    ).mappings()
    for role in roles:
        permission_id = bind.execute(
            sa.text(
                "SELECT id FROM role_feature_permissions WHERE role_id = :role_id AND feature_id = :feature_id"
            ),
            {"role_id": role["id"], "feature_id": STAFF_FEATURE_ID},
        ).scalar()

        if role["code"] == "security":
            if permission_id:
                bind.execute(
                    sa.text("UPDATE role_feature_permissions SET is_deleted = 1, sidebar_order = 0 WHERE id = :id"),
                    {"id": permission_id},
                )
            continue

        can_view, can_create, can_update, can_delete = MANAGER_PERMISSIONS[role["code"]]
        values = {
            "can_view": can_view,
            "can_create": can_create,
            "can_update": can_update,
            "can_delete": can_delete,
            "sidebar_order": STAFF_SIDEBAR_ORDER,
        }
        if permission_id:
            bind.execute(
                sa.text(
                    "UPDATE role_feature_permissions SET can_view = :can_view, can_create = :can_create, "
                    "can_update = :can_update, can_delete = :can_delete, is_deleted = 0, "
                    "sidebar_order = :sidebar_order WHERE id = :id"
                ),
                {**values, "id": permission_id},
            )
        else:
            bind.execute(
                sa.text(
                    "INSERT INTO role_feature_permissions "
                    "(id, role_id, feature_id, can_view, can_create, can_update, can_delete, is_deleted, sidebar_order) "
                    "VALUES (:id, :role_id, :feature_id, :can_view, :can_create, :can_update, :can_delete, 0, :sidebar_order)"
                ),
                {**values, "id": str(uuid.uuid4()), "role_id": role["id"], "feature_id": STAFF_FEATURE_ID},
            )


def downgrade() -> None:
    raise RuntimeError("Staff navigation restoration requires a reviewed, data-preserving downgrade.")
