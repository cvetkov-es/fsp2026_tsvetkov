import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.clock import now
from app.db.base import Base

# Ожидают ответа и занимают слот квоты (процесс 4.4)
ACTIVE = ("sent", "viewed", "countered", "offer_v2", "conditionally_accepted")  # условное согласие занимает слот квоты
FINAL = ("accepted", "declined", "company_declined", "expired", "withdrawn", "revoked")


class Contact(Base):
    """Приглашение и всё, что с ним происходит (процесс 2.8, 9; техдизайн 4.6)."""
    __tablename__ = "contacts"
    # Гарантия БД: одно активное приглашение на пару «потребность — кандидат»
    __table_args__ = (Index("uq_contacts_active_pair", "need_id", "user_id", unique=True,
                            postgresql_where=text("status IN ('sent', 'viewed', 'countered', 'offer_v2', 'conditionally_accepted')")),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    channel: Mapped[str] = mapped_column(String(20), default="invitation")  # invitation | group_member | task_author | application
    group_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("group_invites.id", ondelete="SET NULL"), index=True)
    need_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("needs.id", ondelete="CASCADE"), index=True)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # Каналы техдизайна 4.6: отклик на вакансию и приглашение автора решения задачи
    vacancy_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("vacancies.id", ondelete="SET NULL"))
    task_submission_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("task_submissions.id", ondelete="SET NULL"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(30), default="sent", index=True)  # включая conditionally_accepted
    salary_from: Mapped[int] = mapped_column(Integer)
    salary_to: Mapped[int] = mapped_column(Integer)
    gross_net: Mapped[str] = mapped_column(String(5))
    description: Mapped[str] = mapped_column(Text, default="")
    why_you: Mapped[str] = mapped_column(Text, default="")
    next_step: Mapped[str] = mapped_column(Text, default="")
    contact_method: Mapped[str] = mapped_column(String(20), default="chat")
    hours_per_week: Mapped[int | None] = mapped_column(Integer)  # для несовершеннолетнего — не больше лимита ст. 92 ТК РФ
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    counter_amount: Mapped[int | None] = mapped_column(Integer)
    counter_comment: Mapped[str | None] = mapped_column(Text)
    counter_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decline_reason: Mapped[str | None] = mapped_column(String(30))
    decline_comment: Mapped[str | None] = mapped_column(Text)
    early_reinvite: Mapped[bool] = mapped_column(Boolean, default=False)
    viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    contacts_revealed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class ContactEvent(Base):
    __tablename__ = "contact_events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    contact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(30))
    actor: Mapped[str] = mapped_column(String(10))  # candidate | employer | system
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    contact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"), index=True)
    author_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    text: Mapped[str] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class CompanyBlock(Base):
    """«Не показывать эту компанию»: новые приглашения от неё получают ответ «кандидат недоступен» (процесс 2.8)."""
    __tablename__ = "profile_company_blocks"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


def effective_status(c: Contact, t: datetime) -> str:
    """Статус с учётом времени (техдизайн, решение 4): истёкшее приглашение или встречное условие — expired."""
    if c.status in ("sent", "viewed", "offer_v2") and c.expires_at <= t:
        return "expired"
    if c.status == "countered" and c.counter_expires_at is not None and c.counter_expires_at <= t:
        return "expired"
    return c.status
