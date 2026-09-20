"""Add soft-delete flags to amenities and amenity bookings."""

from alembic import op
import sqlalchemy as sa


revision = "20260919_0020"
down_revision = "20260919_0019"
branch_labels = None
depends_on = None


def _add_if_missing(table: str) -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns(table)}
    if "is_deleted" not in columns:
        op.add_column(
            table,
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        )


def upgrade() -> None:
    _add_if_missing("amenities")
    _add_if_missing("amenity_bookings")


def downgrade() -> None:
    bind = op.get_bind()
    for table in ("amenity_bookings", "amenities"):
        columns = {column["name"] for column in sa.inspect(bind).get_columns(table)}
        if "is_deleted" in columns:
            op.drop_column(table, "is_deleted")

