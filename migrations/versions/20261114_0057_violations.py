"""Create the association-scoped violations workflow and its feature permissions.

Revision ID: 20261114_0057
Revises: 20261114_0056
"""

import uuid

import sqlalchemy as sa
from alembic import op

revision = "20261114_0057"
down_revision = "20261114_0056"
branch_labels = None
depends_on = None

VIOLATIONS_FEATURE_ID = "8c91f9f5-4efb-42d8-89aa-1c57c6f2d2f7"
PERMISSIONS = {
    "super_admin": (True, True, True, False),
    "admin": (True, True, True, False),
    "board_member": (True, False, True, False),
    "homeowner": (True, True, True, False),
}


def upgrade() -> None:
    op.create_table(
        "violation_sequences",
        sa.Column("association_id", sa.CHAR(36), nullable=False),
        sa.Column("next_number", sa.Integer(), nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint("association_id"),
    )
    op.create_table(
        "violations",
        sa.Column("id", sa.CHAR(36), nullable=False),
        sa.Column("association_id", sa.CHAR(36), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("display_id", sa.String(32), nullable=False),
        sa.Column("reporter_account_id", sa.CHAR(36), nullable=False),
        sa.Column("reporter_unit_id", sa.CHAR(36), nullable=False),
        sa.Column("violator_account_id", sa.CHAR(36), nullable=False),
        sa.Column("violator_unit_id", sa.CHAR(36), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("incident_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("proof_url", sa.String(2048), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="New"),
        sa.Column("offense_count", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(32), nullable=True),
        sa.Column("fine_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("fine_applied", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("fine_transaction_id", sa.CHAR(36), nullable=True),
        sa.Column("admin_notes", sa.Text(), nullable=True),
        sa.Column("board_notes", sa.Text(), nullable=True),
        sa.Column("violator_response", sa.String(64), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["reporter_account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["violator_account_id"], ["accounts.account_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("association_id", "sequence_number", name="uq_violations_association_sequence"),
        sa.UniqueConstraint("fine_transaction_id", name="uq_violations_fine_transaction"),
    )
    for name, columns in {
        "ix_violations_association": ["association_id"],
        "ix_violations_reporter": ["reporter_account_id"],
        "ix_violations_violator": ["violator_account_id"],
        "ix_violations_status": ["status"],
    }.items():
        op.create_index(name, "violations", columns)
    op.create_table(
        "violation_messages",
        sa.Column("id", sa.CHAR(36), nullable=False),
        sa.Column("violation_id", sa.CHAR(36), nullable=False),
        sa.Column("sender_account_id", sa.CHAR(36), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("attachment_url", sa.String(2048), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["violation_id"], ["violations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_account_id"], ["accounts.account_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_violation_messages_violation", "violation_messages", ["violation_id"])
    op.create_index("ix_violation_messages_sender", "violation_messages", ["sender_account_id"])

    bind = op.get_bind()
    feature_id = bind.execute(sa.text("SELECT id FROM features WHERE code = 'violations' AND is_deleted = 0")).scalar()
    if feature_id is None:
        bind.execute(
            sa.text(
                "INSERT INTO features (id, code, name, description, icon, route, order_index, is_system, is_active, is_deleted) "
                "VALUES (:id, 'violations', 'Violations', :description, 'ShieldAlert', '/violations', 48, 1, 1, 0)"
            ),
            {"id": VIOLATIONS_FEATURE_ID, "description": "Association violation reporting, review, and resolution."},
        )
        feature_id = VIOLATIONS_FEATURE_ID
    roles = bind.execute(sa.text("SELECT id, code FROM roles WHERE code IN ('super_admin', 'admin', 'board_member', 'homeowner') AND is_deleted = 0")).mappings()
    for role in roles:
        can_view, can_create, can_update, can_delete = PERMISSIONS[role["code"]]
        existing_id = bind.execute(sa.text("SELECT id FROM role_feature_permissions WHERE role_id = :role_id AND feature_id = :feature_id"), {"role_id": role["id"], "feature_id": feature_id}).scalar()
        values = {"can_view": can_view, "can_create": can_create, "can_update": can_update, "can_delete": can_delete, "sidebar_order": 48}
        if existing_id:
            bind.execute(sa.text("UPDATE role_feature_permissions SET can_view=:can_view, can_create=:can_create, can_update=:can_update, can_delete=:can_delete, is_deleted=0, sidebar_order=:sidebar_order WHERE id=:id"), {**values, "id": existing_id})
        else:
            bind.execute(sa.text("INSERT INTO role_feature_permissions (id, role_id, feature_id, can_view, can_create, can_update, can_delete, is_deleted, sidebar_order) VALUES (:id, :role_id, :feature_id, :can_view, :can_create, :can_update, :can_delete, 0, :sidebar_order)"), {**values, "id": str(uuid.uuid4()), "role_id": role["id"], "feature_id": feature_id})


def downgrade() -> None:
    raise RuntimeError("Violations migrations are data-bearing and require an explicit reviewed rollback.")
