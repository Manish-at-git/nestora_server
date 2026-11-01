"""Store whether a homeowner unit document is visible to board members.

Revision ID: 20261101_0052
Revises: 20261101_0051
"""

import sqlalchemy as sa
from alembic import op


revision = "20261101_0052"
down_revision = "20261101_0051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "unit_documents",
        sa.Column("is_visible_to_board", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )


def downgrade() -> None:
    op.drop_column("unit_documents", "is_visible_to_board")
