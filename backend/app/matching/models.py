import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.clock import now
from app.db.base import Base


class Shortlist(Base):
    __tablename__ = "shortlist"
    need_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("needs.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    pinned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class SearchLog(Base):
    __tablename__ = "search_logs"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    need_id: Mapped[uuid.UUID] = mapped_column(index=True)
    company_id: Mapped[uuid.UUID] = mapped_column(index=True)
    filters: Mapped[dict] = mapped_column(JSONB, default=dict)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class SelectionSnapshot(Base):
    __tablename__ = "selection_snapshots"
    need_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("needs.id", ondelete="CASCADE"), primary_key=True)
    refs: Mapped[list] = mapped_column(JSONB, default=list)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ExplanationCache(Base):
    """Перефразированные объяснения (техдизайн 4.5): ключ — потребность, кандидат и отпечаток фактов."""
    __tablename__ = "explanations"
    __table_args__ = (UniqueConstraint("need_id", "user_id", "facts_hash"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    need_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("needs.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    facts_hash: Mapped[str] = mapped_column(String(64))
    template_text: Mapped[str] = mapped_column(Text)
    llm_text: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
