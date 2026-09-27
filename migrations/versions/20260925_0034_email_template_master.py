"""Create the soft-deletable Email Template Master table.

Revision ID: 20260925_0034
Revises: 20260921_0033
"""

import sqlalchemy as sa
from alembic import op


revision = "20260925_0034"
down_revision = "20260921_0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "email_templates" not in tables:
        op.create_table(
            "email_templates",
            sa.Column("id", sa.CHAR(36), primary_key=True),
            sa.Column("name", sa.String(150), nullable=False),
            sa.Column("event_type", sa.String(100), nullable=False),
            sa.Column("subject", sa.String(255), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
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
        op.create_index(
            "ix_email_templates_event_type",
            "email_templates",
            ["event_type"],
        )
        return

    columns = {column["name"] for column in inspector.get_columns("email_templates")}
    if "is_deleted" not in columns:
        op.add_column(
            "email_templates",
            sa.Column(
                "is_deleted",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )

    indexes = {
        index["name"] for index in sa.inspect(bind).get_indexes("email_templates")
    }
    if "ix_email_templates_event_type" not in indexes:
        op.create_index(
            "ix_email_templates_event_type",
            "email_templates",
            ["event_type"],
        )


def downgrade() -> None:
    # Preserve template data because this migration can adopt a legacy table.
    # A downgrade cannot safely distinguish an adopted table from a new one.
    pass
