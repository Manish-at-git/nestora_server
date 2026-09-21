"""Create normalized country, region, district, and city reference tables."""

from alembic import op
import sqlalchemy as sa


revision = "20260921_0033"
down_revision = "20260920_0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "location_countries",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("iso2_code", sa.String(2), nullable=False, unique=True),
        sa.Column("iso3_code", sa.String(3), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("currency_code", sa.String(3), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "location_regions",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("country_id", sa.CHAR(36), sa.ForeignKey("location_countries.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False, server_default="STATE"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("country_id", "code", name="uq_location_regions_country_code"),
    )
    op.create_index("ix_location_regions_country_id", "location_regions", ["country_id"])
    op.create_table(
        "location_districts",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("region_id", sa.CHAR(36), sa.ForeignKey("location_regions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False, server_default="DISTRICT"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("region_id", "code", name="uq_location_districts_region_code"),
    )
    op.create_index("ix_location_districts_region_id", "location_districts", ["region_id"])
    op.create_table(
        "location_cities",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("region_id", sa.CHAR(36), sa.ForeignKey("location_regions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("district_id", sa.CHAR(36), sa.ForeignKey("location_districts.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("region_id", "district_id", "name", name="uq_location_cities_region_district_name"),
    )
    op.create_index("ix_location_cities_region_id", "location_cities", ["region_id"])
    op.create_index("ix_location_cities_district_id", "location_cities", ["district_id"])

    for table_name in ("associations", "employees", "vendors"):
        columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}
        if "city_id" not in columns:
            op.add_column(table_name, sa.Column("city_id", sa.CHAR(36), nullable=True))
            op.create_foreign_key(
                f"fk_{table_name}_city_id", table_name, "location_cities", ["city_id"], ["id"], ondelete="RESTRICT"
            )


def downgrade() -> None:
    for table_name in ("vendors", "employees", "associations"):
        op.drop_constraint(f"fk_{table_name}_city_id", table_name, type_="foreignkey")
        op.drop_column(table_name, "city_id")
    op.drop_index("ix_location_cities_district_id", table_name="location_cities")
    op.drop_index("ix_location_cities_region_id", table_name="location_cities")
    op.drop_table("location_cities")
    op.drop_index("ix_location_districts_region_id", table_name="location_districts")
    op.drop_table("location_districts")
    op.drop_index("ix_location_regions_country_id", table_name="location_regions")
    op.drop_table("location_regions")
    op.drop_table("location_countries")
