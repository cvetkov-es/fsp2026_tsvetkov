"""Задачи работодателей и решения (процесс 4.6; техдизайн 4.6)."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.clock import now
from app.db.base import Base


class EmployerTask(Base):
    __tablename__ = "employer_tasks"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    specialization: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(200))
    text: Mapped[str] = mapped_column(Text)
    reference_answer: Mapped[str | None] = mapped_column(Text)  # только на сервере: автопроверка
    answer_kind: Mapped[str | None] = mapped_column(String(10))  # number | text — как сравнивать с эталоном
    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(10), default="open", index=True)  # open | closed | removed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class TaskSubmission(Base):
    __tablename__ = "task_submissions"
    __table_args__ = (UniqueConstraint("task_id", "user_id"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employer_tasks.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    answer: Mapped[str] = mapped_column(Text)
    auto_correct: Mapped[bool | None] = mapped_column(Boolean)  # None — эталона нет, проверяет работодатель
    verdict: Mapped[str | None] = mapped_column(String(10))  # accepted | rejected
    comment: Mapped[str | None] = mapped_column(Text)
    llm_hint: Mapped[dict | None] = mapped_column(JSONB)  # совет, а не решение
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
