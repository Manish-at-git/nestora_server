"""Restore evidence and unknown-violator fields for homeowner reports.

Revision ID: 20261114_0059
Revises: 20261114_0058
"""

import sqlalchemy as sa
from alembic import op


revision = "20261114_0059"
down_revision = "20261114_0058"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "violations",
        sa.Column("knows_violator", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column("violations", sa.Column("audio_url", sa.String(2048), nullable=True))
    op.alter_column(
        "violations",
        "violator_account_id",
        existing_type=sa.CHAR(36),
        nullable=True,
    )
    op.alter_column(
        "violations",
        "violator_unit_id",
        existing_type=sa.CHAR(36),
        nullable=True,
    )


def downgrade() -> None:
    raise RuntimeError("Violation-report data requires an explicit reviewed rollback.")
