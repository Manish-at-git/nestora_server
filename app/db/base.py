"""The one SQLAlchemy metadata registry Alembic uses to discover all new server tables."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for every mapped database table in the new server."""
