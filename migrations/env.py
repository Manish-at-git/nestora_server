"""Alembic environment that imports the new server's metadata and database configuration."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.db.base import Base
from app.modules.auth import models as auth_models  # noqa: F401 - registers mapped tables
from app.modules.iam import models as iam_models  # noqa: F401 - registers mapped tables
from app.modules.associations import models as association_models  # noqa: F401 - registers FK targets
from app.modules.documents import models as document_models  # noqa: F401 - registers mapped tables
from app.modules.chart_of_accounts import models as chart_of_accounts_models  # noqa: F401 - registers mapped tables
from app.modules.marketplace import models as marketplace_models  # noqa: F401 - registers mapped tables
from app.modules.visitor_management import models as visitor_management_models  # noqa: F401 - registers mapped tables
from app.modules.wallet import models as wallet_models  # noqa: F401 - registers mapped tables
from app.modules.locations import models as location_models  # noqa: F401 - registers mapped tables

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
# ConfigParser reserves '%' for interpolation. SQLAlchemy percent-encodes
# password characters such as '@' as '%40', so escape it only for Alembic's
# configuration layer; engine_from_config restores the original URL value.
config.set_main_option("sqlalchemy.url", get_settings().sync_database_url.replace("%", "%%"))
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Generate SQL without connecting when an operator explicitly requests offline mode."""
    context.configure(
        url=get_settings().sync_database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "pyformat"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Open a short synchronous Alembic connection only when a migration command is run."""
    configuration = config.get_section(config.config_ini_section, {})
    connectable = engine_from_config(configuration, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
