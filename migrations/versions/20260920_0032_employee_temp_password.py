"""Store the employee onboarding password until the employee resets it."""

from alembic import op
import sqlalchemy as sa


revision = "20260920_0032"
down_revision = "20260920_0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "employees" not in sa.inspect(bind).get_table_names():
        return
    columns = {column["name"] for column in sa.inspect(bind).get_columns("employees")}
    if "temp_password" not in columns:
        op.add_column("employees", sa.Column("temp_password", sa.String(255), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    if "employees" not in sa.inspect(bind).get_table_names():
        return
    columns = {column["name"] for column in sa.inspect(bind).get_columns("employees")}
    if "temp_password" in columns:
        op.drop_column("employees", "temp_password")
