"""Allow violations to target association residents before account activation.

Revision ID: 20261114_0060
Revises: 20261114_0059
"""

import sqlalchemy as sa
from alembic import op


revision = "20261114_0060"
down_revision = "20261114_0059"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("violations", sa.Column("violator_user_id", sa.CHAR(36), nullable=True))
    op.create_index("ix_violations_violator_user_id", "violations", ["violator_user_id"])
    op.create_foreign_key(
        "fk_violations_violator_user_id",
        "violations",
        "user_details",
        ["violator_user_id"],
        ["user_id"],
    )
    op.get_bind().execute(
        sa.text(
            "UPDATE violations v JOIN accounts a ON a.account_id = v.violator_account_id "
            "SET v.violator_user_id = a.user_id WHERE v.violator_account_id IS NOT NULL"
        )
    )


def downgrade() -> None:
    raise RuntimeError("Violation-report data requires an explicit reviewed rollback.")
