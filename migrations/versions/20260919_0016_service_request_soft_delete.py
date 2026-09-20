"""Add soft-delete support to service requests.

Revision ID: 20260919_0016
Revises: 20260919_0015
"""

from alembic import op
import sqlalchemy as sa


revision = "20260919_0016"
down_revision = "20260919_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "service_requests" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("service_requests")}
    if "is_deleted" not in columns:
        op.add_column(
            "service_requests",
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "service_requests" not in tables:
        return
    columns = {column["name"] for column in sa.inspect(bind).get_columns("service_requests")}
    if "is_deleted" in columns:
        op.drop_column("service_requests", "is_deleted")
