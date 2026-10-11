"""Групповое приглашение (процесс 4.5): пакет индивидуальных офферов с общим group_id."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.common.clock import now
from app.db.base import Base


class GroupInvite(Base):
    __tablename__ = "group_invites"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    need_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("needs.id", ondelete="CASCADE"))
    team_id: Mapped[str] = mapped_column(String(80))
    team_name: Mapped[str] = mapped_column(String(200))
    min_size: Mapped[int] = mapped_column(Integer)
    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # отправлены офферы v2
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # работодатель отозвал приглашение команды
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
