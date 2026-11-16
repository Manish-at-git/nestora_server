"""Add association staff records and permanent QR attendance logs."""

import sqlalchemy as sa
from alembic import op


revision = "20261114_0053"
down_revision = "20261101_0052"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    tables = _tables()
    if "staff_members" not in tables:
        op.create_table(
            "staff_members",
            sa.Column("id", sa.CHAR(36), primary_key=True),
            sa.Column("association_id", sa.CHAR(36), nullable=False),
            sa.Column("staff_code", sa.String(30), nullable=False, unique=True),
            sa.Column("first_name", sa.String(100), nullable=False),
            sa.Column("last_name", sa.String(100), nullable=False),
            sa.Column("designation", sa.String(100), nullable=False),
            sa.Column("contact_number", sa.String(30), nullable=False),
            sa.Column("email", sa.String(150)),
            sa.Column("id_proof_url", sa.String(255)),
            sa.Column("profile_pic_url", sa.String(255)),
            sa.Column("pass_code", sa.String(50), nullable=False, unique=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["association_id"], ["associations.id"], ondelete="RESTRICT"),
        )
        op.create_index("ix_staff_members_association_id", "staff_members", ["association_id"])
        op.create_index("ix_staff_members_pass_code", "staff_members", ["pass_code"])

    if "staff_attendance" not in tables:
        op.create_table(
            "staff_attendance",
            sa.Column("id", sa.CHAR(36), primary_key=True),
            sa.Column("staff_id", sa.CHAR(36), nullable=False),
            sa.Column("association_id", sa.CHAR(36), nullable=False),
            sa.Column("check_in_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("check_out_at", sa.DateTime(timezone=True)),
            sa.Column("checked_in_by", sa.CHAR(36)),
            sa.Column("checked_out_by", sa.CHAR(36)),
            sa.Column("gate", sa.String(100)),
            sa.Column("remarks", sa.Text()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["staff_id"], ["staff_members.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["association_id"], ["associations.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["checked_in_by"], ["accounts.account_id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["checked_out_by"], ["accounts.account_id"], ondelete="SET NULL"),
        )
        op.create_index("ix_staff_attendance_staff_id", "staff_attendance", ["staff_id"])
        op.create_index("ix_staff_attendance_association_id", "staff_attendance", ["association_id"])


def downgrade() -> None:
    raise RuntimeError("Staff attendance records require a reviewed, data-preserving downgrade.")
