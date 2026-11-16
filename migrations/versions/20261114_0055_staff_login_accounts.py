"""Give association staff restricted login accounts and temporary passwords."""

import uuid

import sqlalchemy as sa
from alembic import op

from app.core.access_codes import generate_access_code
from app.core.security import hash_password


revision = "20261114_0055"
down_revision = "20261114_0054"
branch_labels = None
depends_on = None

STAFF_ROLE_ID = "70000000-0000-4000-8000-000000000002"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("staff_members")}
    if "account_id" not in columns:
        op.add_column("staff_members", sa.Column("account_id", sa.CHAR(36), nullable=True))
    if "temp_password" not in columns:
        op.add_column("staff_members", sa.Column("temp_password", sa.String(255), nullable=True))

    foreign_keys = {
        (tuple(key["constrained_columns"]), key["referred_table"])
        for key in inspector.get_foreign_keys("staff_members")
    }
    if (("account_id",), "accounts") not in foreign_keys:
        op.create_foreign_key(
            "fk_staff_members_account_id",
            "staff_members",
            "accounts",
            ["account_id"],
            ["account_id"],
            ondelete="SET NULL",
        )

    indexes = {index["name"] for index in inspector.get_indexes("staff_members")}
    if "uq_staff_members_account_id" not in indexes:
        op.create_unique_constraint("uq_staff_members_account_id", "staff_members", ["account_id"])

    staff_role_exists = bind.execute(
        sa.text("SELECT id FROM roles WHERE code = :code"), {"code": "staff"}
    ).scalar()
    if staff_role_exists is None:
        bind.execute(
            sa.text(
                "INSERT INTO roles (id, code, name, description, is_system, is_active, is_deleted) "
                "VALUES (:id, :code, :name, :description, 1, 1, 0)"
            ),
            {
                "id": STAFF_ROLE_ID,
                "code": "staff",
                "name": "Staff",
                "description": "Daily association worker with sign-in access and no default feature permissions.",
            },
        )

    existing_staff = list(bind.execute(
        sa.text(
            "SELECT id, email FROM staff_members "
            "WHERE account_id IS NULL AND is_deleted = 0 AND email IS NOT NULL AND TRIM(email) <> ''"
        )
    ).mappings())
    for staff in existing_staff:
        email = staff["email"].strip().lower()
        account_exists = bind.execute(
            sa.text("SELECT account_id FROM accounts WHERE LOWER(email) = :email LIMIT 1"),
            {"email": email},
        ).scalar()
        if account_exists:
            continue
        temporary_password = generate_access_code()
        account_id = str(uuid.uuid4())
        bind.execute(
            sa.text(
                "INSERT INTO accounts (account_id, email, password_hash, role_id, status) "
                "VALUES (:account_id, :email, :password_hash, :role_id, 'active')"
            ),
            {
                "account_id": account_id,
                "email": email,
                "password_hash": hash_password(temporary_password),
                "role_id": staff_role_exists or STAFF_ROLE_ID,
            },
        )
        bind.execute(
            sa.text(
                "UPDATE staff_members SET account_id = :account_id, temp_password = :temp_password WHERE id = :staff_id"
            ),
            {"account_id": account_id, "temp_password": temporary_password, "staff_id": staff["id"]},
        )


def downgrade() -> None:
    raise RuntimeError("Staff login records require a reviewed, data-preserving downgrade.")
