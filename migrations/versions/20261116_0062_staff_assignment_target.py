"""Allow staff to be assigned to a common area or one residential unit."""

import sqlalchemy as sa
from alembic import op


revision = "20261116_0062"
down_revision = "20261116_0061"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing_columns = {column["name"] for column in inspector.get_columns("staff_members")}

    if "assignment_type" not in existing_columns:
        op.add_column(
            "staff_members",
            sa.Column("assignment_type", sa.String(length=20), nullable=False, server_default="common_area"),
        )
    if "block_id" not in existing_columns:
        op.add_column("staff_members", sa.Column("block_id", sa.CHAR(length=36), nullable=True))
        op.create_foreign_key("fk_staff_members_block_id", "staff_members", "blocks", ["block_id"], ["id"], ondelete="RESTRICT")
        op.create_index("ix_staff_members_block_id", "staff_members", ["block_id"])
    if "unit_id" not in existing_columns:
        op.add_column("staff_members", sa.Column("unit_id", sa.CHAR(length=36), nullable=True))
        op.create_foreign_key("fk_staff_members_unit_id", "staff_members", "units", ["unit_id"], ["id"], ondelete="RESTRICT")
        op.create_index("ix_staff_members_unit_id", "staff_members", ["unit_id"])


def downgrade() -> None:
    raise RuntimeError("Staff assignment targets require a reviewed, data-preserving downgrade.")
