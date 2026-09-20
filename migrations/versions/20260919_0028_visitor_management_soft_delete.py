"""Add approved soft-delete flags to visitor-management records."""

from alembic import op
import sqlalchemy as sa


revision = "20260919_0028"
down_revision = "20260919_0027"
branch_labels = None
depends_on = None


TABLES = ("visitors", "visitor_visits", "pre_approved_visitors", "visitor_logs", "deliveries", "vehicles")


def _add_if_missing(table: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return
    if "is_deleted" not in {column["name"] for column in inspector.get_columns(table)}:
        op.add_column(table, sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")))


def _create_if_missing() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "visitors" not in tables:
        op.create_table(
            "visitors",
            sa.Column("id", sa.CHAR(36), primary_key=True),
            sa.Column("name", sa.String(150), nullable=False),
            sa.Column("mobile", sa.String(30), nullable=False),
            sa.Column("photo_url", sa.String(255)),
            sa.Column("id_type", sa.String(50)),
            sa.Column("id_number", sa.String(100)),
            sa.Column("status", sa.String(30), server_default="Active"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        )
    if "visitor_visits" not in tables:
        op.create_table(
            "visitor_visits",
            sa.Column("id", sa.CHAR(36), primary_key=True),
            sa.Column("visitor_id", sa.CHAR(36), nullable=False),
            sa.Column("unit_id", sa.CHAR(36), nullable=False),
            sa.Column("purpose", sa.String(255)),
            sa.Column("visitor_type", sa.String(50)),
            sa.Column("number_of_visitors", sa.Integer(), server_default="1"),
            sa.Column("vehicle_number", sa.String(50)),
            sa.Column("notes", sa.Text()),
            sa.Column("expected_duration", sa.String(50)),
            sa.Column("status", sa.String(30), server_default="Pending"),
            sa.Column("pass_code", sa.String(50)),
            sa.Column("check_in_time", sa.DateTime()),
            sa.Column("check_out_time", sa.DateTime()),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        )


def upgrade() -> None:
    _create_if_missing()
    for table in TABLES:
        _add_if_missing(table)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table in reversed(TABLES):
        if table in inspector.get_table_names() and "is_deleted" in {column["name"] for column in inspector.get_columns(table)}:
            op.drop_column(table, "is_deleted")
