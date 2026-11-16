"""Keep Super Admin violations access review-only.

Revision ID: 20261114_0058
Revises: 20261114_0057
"""

import sqlalchemy as sa
from alembic import op


revision = "20261114_0058"
down_revision = "20261114_0057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "UPDATE role_feature_permissions p "
            "JOIN roles r ON r.id = p.role_id "
            "JOIN features f ON f.id = p.feature_id "
            "SET p.can_create = 0 "
            "WHERE r.code = 'super_admin' AND f.code = 'violations'"
        )
    )


def downgrade() -> None:
    raise RuntimeError("Role-permission rollback requires explicit review.")
