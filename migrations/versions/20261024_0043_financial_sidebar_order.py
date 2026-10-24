"""Normalize Financials submenu ordering to the legacy sequence."""

from alembic import op
import sqlalchemy as sa


revision = "20261024_0043"
down_revision = "20261018_0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE role_feature_permissions
            SET sidebar_order = CASE (
                SELECT route FROM features
                WHERE features.id = role_feature_permissions.feature_id
            )
                WHEN '/financials/balance-sheet' THEN 1
                WHEN '/financials/income-statement' THEN 2
                WHEN '/financials/delinquency-report' THEN 3
                WHEN '/financials/prepaid-report' THEN 4
                WHEN '/financials/vendor-aging' THEN 5
                WHEN '/financials/invoices' THEN 6
                WHEN '/financials/bank-transactions' THEN 7
                WHEN '/financials/bank-statements' THEN 8
                WHEN '/financials/other-reports' THEN 9
                ELSE sidebar_order
            END
            WHERE feature_id IN (
                SELECT id FROM features
                WHERE route IN (
                    '/financials/balance-sheet',
                    '/financials/income-statement',
                    '/financials/delinquency-report',
                    '/financials/prepaid-report',
                    '/financials/vendor-aging',
                    '/financials/invoices',
                    '/financials/bank-transactions',
                    '/financials/bank-statements',
                    '/financials/other-reports'
                )
            )
            """
        )
    )


def downgrade() -> None:
    # This migration normalizes data and cannot safely infer each deployment's
    # previous custom ordering.
    pass
