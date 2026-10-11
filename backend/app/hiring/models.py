"""Доска найма и голоса (процесс 4.7, 5, 9; техдизайн 4.7)."""
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.clock import now
from app.db.base import Base


class PipelineStage(Base):
    """Этап найма по принятому приглашению — отдельная ось от статуса контакта (процесс 9).

    Текущий этап — последняя запись. Ответ на вопрос об уровне хранится здесь же, голос — в votes."""
    __tablename__ = "pipeline_stages"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    contact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"), index=True)
    stage: Mapped[str] = mapped_column(String(20))  # first | technical | offer | hired | rejected
    level: Mapped[str | None] = mapped_column(String(10))  # below | meets | above | unknown
    reason: Mapped[str | None] = mapped_column(String(30))  # причина отказа (финал)
    weak_areas: Mapped[list] = mapped_column(JSONB, default=list)
    vote_note: Mapped[str | None] = mapped_column(String(20))  # почему ответ не стал голосом
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))  # None — засев
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Vote(Base):
    """Голос компании об уровне кандидата относительно ожиданий от его грейда (процесс 5).

    Хранятся только явные состояния: pending, disputed, annulled, upheld. «Действует», «истёк» и «архив»
    вычисляются при чтении (hiring.votes.vote_state) — от worker логика не зависит."""
    __tablename__ = "votes"
    __table_args__ = (Index("ix_votes_user_status", "user_id", "status"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    contact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"), unique=True)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    value: Mapped[str] = mapped_column(String(10))  # below | meets | above
    pending_value: Mapped[str | None] = mapped_column(String(10))  # ответ компании во время спора — ждёт модератора
    weight: Mapped[float] = mapped_column(Float)
    trust_at_vote: Mapped[str] = mapped_column(String(2))  # уровень компании при ответе (VOTES_UNLOCK — только L2+)
    spec_at_vote: Mapped[str] = mapped_column(String(40))
    grade_at_vote: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # последний ответ компании
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    dispute_reason: Mapped[str | None] = mapped_column(String(30))
    dispute_comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class HelperUse(Base):
    """Выданный помощником набор вопросов к собеседованию: считается в месячный лимит компании (процесс 4.7)."""
    __tablename__ = "helper_uses"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    contact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"), index=True)
    questions: Mapped[list] = mapped_column(JSONB, default=list)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
