"""Explicit transaction helper for workflows that must commit all changes or none of them."""

from sqlalchemy.ext.asyncio import AsyncSession


class UnitOfWork:
    """Wrap one session transaction; repositories never commit independently."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._transaction_started_here = False

    async def __aenter__(self) -> "UnitOfWork":
        """Start an explicit transaction before a multi-step business workflow."""
        # Auth dependencies can have already performed a read using this request's
        # session. SQLAlchemy starts a transaction for that read, so reuse it.
        if not self.session.in_transaction():
            await self.session.begin()
            self._transaction_started_here = True
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        """Commit only on success, otherwise roll back every statement in this workflow."""
        if exc_type is None and self.session.in_transaction():
            await self.session.commit()
        elif exc_type is not None and self.session.in_transaction():
            await self.session.rollback()
