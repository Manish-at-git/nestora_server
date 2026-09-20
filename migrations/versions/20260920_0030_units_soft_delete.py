"""Add the soft-delete flag required by unit-scoped document queries."""

from alembic import op
import sqlalchemy as sa


revision = "20260920_0030"
down_revision = "20260919_0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "units" not in tables:
        return
    columns = {column["name"] for column in inspector.get_columns("units")}
    if "is_deleted" not in columns:
        op.add_column(
            "units",
            sa.Column(
                "is_deleted",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("0"),
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "units" not in tables:
        return
    columns = {column["name"] for column in inspector.get_columns("units")}
    if "is_deleted" in columns:
        op.drop_column("units", "is_deleted")
