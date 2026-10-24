"""Place financial statement features under the Financials navigation item."""

from alembic import op
import sqlalchemy as sa


revision = "20261024_0044"
down_revision = "20261024_0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE features AS statement_feature
            JOIN features AS financials_feature
              ON financials_feature.code = 'financials'
            SET statement_feature.parent_id = financials_feature.id
            WHERE statement_feature.route IN (
                '/financials/balance-sheet',
                '/financials/income-statement'
            )
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE features
            SET parent_id = NULL
            WHERE route IN (
                '/financials/balance-sheet',
                '/financials/income-statement'
            )
            """
        )
    )
