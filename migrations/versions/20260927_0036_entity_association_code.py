"""Rename the entity association code column and preserve existing values.

Revision ID: 20260927_0036
Revises: 20260926_0035
"""

import sqlalchemy as sa
from alembic import op


revision = "20260927_0036"
down_revision = "20260926_0035"
branch_labels = None
depends_on = None


def _column_names(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _index_names(table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def upgrade() -> None:
    table_name = "entities"
    if table_name not in set(sa.inspect(op.get_bind()).get_table_names()):
        return

    column_names = _column_names(table_name)
    if "association_id" not in column_names or "association_code" in column_names:
        return

    index_names = _index_names(table_name)
    if "ix_entities_association_id" in index_names:
        op.drop_index("ix_entities_association_id", table_name=table_name)

    op.alter_column(
        table_name,
        "association_id",
        new_column_name="association_code",
        existing_type=sa.CHAR(36),
        existing_nullable=True,
    )
    if "ix_entities_association_code" not in _index_names(table_name):
        op.create_index("ix_entities_association_code", table_name, ["association_code"])


def downgrade() -> None:
    table_name = "entities"
    if table_name not in set(sa.inspect(op.get_bind()).get_table_names()):
        return

    column_names = _column_names(table_name)
    if "association_code" not in column_names or "association_id" in column_names:
        return

    index_names = _index_names(table_name)
    if "ix_entities_association_code" in index_names:
        op.drop_index("ix_entities_association_code", table_name=table_name)

    op.alter_column(
        table_name,
        "association_code",
        new_column_name="association_id",
        existing_type=sa.CHAR(36),
        existing_nullable=True,
    )
    if "ix_entities_association_id" not in _index_names(table_name):
        op.create_index("ix_entities_association_id", table_name, ["association_id"])
