"""Create the global Nearby Places catalogue.

Revision ID: 20260926_0035
Revises: 20260925_0034
"""

import sqlalchemy as sa
from alembic import op


revision = "20260926_0035"
down_revision = "20260925_0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "nearby_places" not in table_names:
        op.create_table(
            "nearby_places",
            sa.Column("id", sa.CHAR(36), primary_key=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("category", sa.String(100), nullable=False),
            sa.Column(
                "distance", sa.String(100), nullable=False, server_default="0.5 km away"
            ),
            sa.Column("rating", sa.Numeric(3, 1), nullable=False, server_default="4.8"),
            sa.Column("reviews", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(100), nullable=False, server_default="Open"),
            sa.Column("address", sa.Text(), nullable=False),
            sa.Column("phone", sa.String(100), nullable=True),
            sa.Column("image", sa.Text(), nullable=True),
            sa.Column("tags", sa.Text(), nullable=True),
            sa.Column("website", sa.Text(), nullable=True),
            sa.Column(
                "is_active", sa.Boolean(), nullable=False, server_default=sa.true()
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )

    index_names = {
        index["name"] for index in sa.inspect(bind).get_indexes("nearby_places")
    }
    if "ix_nearby_places_category" not in index_names:
        op.create_index("ix_nearby_places_category", "nearby_places", ["category"])
    if "ix_nearby_places_is_active" not in index_names:
        op.create_index("ix_nearby_places_is_active", "nearby_places", ["is_active"])


def downgrade() -> None:
    op.drop_index("ix_nearby_places_is_active", table_name="nearby_places")
    op.drop_index("ix_nearby_places_category", table_name="nearby_places")
    op.drop_table("nearby_places")
