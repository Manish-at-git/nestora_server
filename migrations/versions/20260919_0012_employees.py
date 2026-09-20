"""Add employee soft deletion and the account-to-employee link."""

from alembic import op
import sqlalchemy as sa


revision = "20260919_0012"
down_revision = "20260919_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "employees" not in tables:
        op.create_table(
            "employees",
            sa.Column("employee_id", sa.CHAR(36), primary_key=True),
            sa.Column("employee_id_number", sa.String(50), nullable=False, unique=True),
            sa.Column("name", sa.String(150), nullable=False),
            sa.Column("address", sa.String(255), nullable=False),
            sa.Column("email", sa.String(150), nullable=False),
            sa.Column("contact_number", sa.String(30), nullable=False),
            sa.Column("first_name", sa.String(100)),
            sa.Column("last_name", sa.String(100)),
            sa.Column("address_line_1", sa.String(255)),
            sa.Column("address_line_2", sa.String(255)),
            sa.Column("city", sa.String(100)),
            sa.Column("state", sa.String(100)),
            sa.Column("pincode", sa.String(20)),
            sa.Column("emergency_contact_name", sa.String(150)),
            sa.Column("emergency_contact_number", sa.String(30)),
            sa.Column("id_proof_url", sa.String(255)),
            sa.Column("profile_pic_url", sa.String(255)),
            sa.Column("onboard_date", sa.Date()),
            sa.Column("end_date", sa.Date()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    elif "is_deleted" not in {column["name"] for column in inspector.get_columns("employees")}:
        op.add_column(
            "employees",
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        )

    if "accounts" in tables:
        account_columns = {column["name"] for column in inspector.get_columns("accounts")}
        if "employee_id" not in account_columns:
            op.add_column("accounts", sa.Column("employee_id", sa.CHAR(36), nullable=True))
        foreign_keys = {
            (tuple(key["constrained_columns"]), key["referred_table"])
            for key in sa.inspect(bind).get_foreign_keys("accounts")
        }
        if (("employee_id",), "employees") not in foreign_keys:
            op.create_foreign_key(
                "fk_accounts_employee",
                "accounts",
                "employees",
                ["employee_id"],
                ["employee_id"],
                ondelete="CASCADE",
            )


def downgrade() -> None:
    # Keep employee records and account links intact on downgrade.
    pass
