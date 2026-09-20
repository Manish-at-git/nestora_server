import uuid
from datetime import date, datetime

from sqlalchemy import CHAR, Boolean, Date, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BoardMember(Base):
    __tablename__ = "board_members"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    association_id: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    term_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    term_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", server_default="active")
    created_by: Mapped[str | None] = mapped_column(CHAR(36), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
