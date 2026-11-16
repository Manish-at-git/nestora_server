"""Add employee-style contact and address fields to association staff."""

import sqlalchemy as sa
from alembic import op


revision = "20261114_0054"
down_revision = "20261114_0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("staff_members")}
    additions = (
        ("address_line_1", sa.String(255)),
        ("address_line_2", sa.String(255)),
        ("city_id", sa.CHAR(36)),
        ("pincode", sa.String(20)),
        ("emergency_contact_name", sa.String(150)),
        ("emergency_contact_number", sa.String(30)),
    )
    for name, column_type in additions:
        if name not in columns:
            op.add_column("staff_members", sa.Column(name, column_type, nullable=True))

    foreign_keys = {
        (tuple(key["constrained_columns"]), key["referred_table"])
        for key in inspector.get_foreign_keys("staff_members")
    }
    if (("city_id",), "location_cities") not in foreign_keys:
        op.create_foreign_key(
            "fk_staff_members_city_id",
            "staff_members",
            "location_cities",
            ["city_id"],
            ["id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    raise RuntimeError("Staff profile data requires a reviewed, data-preserving downgrade.")
