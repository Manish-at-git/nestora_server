"""Support owner-occupied and rented assessment rates.

Revision ID: 20261101_0051
Revises: 20261025_0050
"""

import sqlalchemy as sa
from alembic import op


revision = "20261101_0051"
down_revision = "20261025_0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "assessment_rules",
        sa.Column(
            "is_advanced_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "assessment_rules",
        sa.Column("owner_occupied_amount", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        "assessment_rules",
        sa.Column("rented_amount", sa.Numeric(12, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("assessment_rules", "rented_amount")
    op.drop_column("assessment_rules", "owner_occupied_amount")
    op.drop_column("assessment_rules", "is_advanced_enabled")
