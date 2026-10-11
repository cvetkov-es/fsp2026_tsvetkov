import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.clock import now
from app.db.base import Base


class ItemFamilyRow(Base):
    __tablename__ = "item_families"
    code: Mapped[str] = mapped_column(String(80), primary_key=True)
    specialization: Mapped[str] = mapped_column(String(40), index=True)
    area: Mapped[str] = mapped_column(String(40))
    level: Mapped[int] = mapped_column(Integer)
    fmt: Mapped[str] = mapped_column(String(20))
    b: Mapped[float] = mapped_column(Float)
    median_time_s: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="active")
    exposure_count: Mapped[int] = mapped_column(Integer, default=0)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ThresholdsRow(Base):
    __tablename__ = "thresholds"
    version: Mapped[str] = mapped_column(String(40), primary_key=True)
    cut_j: Mapped[float] = mapped_column(Float)
    cut_m: Mapped[float] = mapped_column(Float)
    cut_s: Mapped[float] = mapped_column(Float)
    virtual_gap: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(20), default="expert")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Attempt(Base):
    __tablename__ = "attempts"
    # Гарантия БД поверх блокировки профиля: у кандидата не больше одной незавершённой попытки грейда
    __table_args__ = (Index("uq_attempts_active_grade", "user_id", unique=True,
                            postgresql_where=text("kind = 'grade' AND status = 'in_progress'")),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20), default="grade")
    specialization: Mapped[str] = mapped_column(String(40))
    target_grade: Mapped[str] = mapped_column(String(20))
    express: Mapped[bool] = mapped_column(default=False)
    item_cap: Mapped[int] = mapped_column(Integer)
    extra_time: Mapped[bool] = mapped_column(default=False)
    thresholds_version: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default="in_progress", index=True)
    decision: Mapped[str | None] = mapped_column(String(20))
    decided_at_n: Mapped[int | None] = mapped_column(Integer)
    border: Mapped[bool] = mapped_column(default=False)
    confident: Mapped[bool] = mapped_column(default=False)
    bank_exhausted: Mapped[bool] = mapped_column(default=False)
    theta: Mapped[float | None] = mapped_column(Float)
    se: Mapped[float | None] = mapped_column(Float)
    p_confirm: Mapped[float | None] = mapped_column(Float)
    s: Mapped[float | None] = mapped_column(Float)
    synthetic: Mapped[bool] = mapped_column(default=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AttemptItem(Base):
    __tablename__ = "attempt_items"
    __table_args__ = (UniqueConstraint("attempt_id", "seq"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("attempts.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    phase: Mapped[int] = mapped_column(Integer)
    family_code: Mapped[str] = mapped_column(String(80), index=True)
    area: Mapped[str] = mapped_column(String(40))
    level: Mapped[int] = mapped_column(Integer)
    b: Mapped[float] = mapped_column(Float)
    seed: Mapped[str] = mapped_column(String(24))
    instance: Mapped[dict] = mapped_column(JSONB)  # только на сервере: ключ ответа здесь
    time_limit_s: Mapped[int] = mapped_column(Integer)
    presented_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    time_ms: Mapped[int | None] = mapped_column(Integer)
    response: Mapped[Any] = mapped_column(JSONB, nullable=True)
    correct: Mapped[bool | None] = mapped_column()
    timed_out: Mapped[bool] = mapped_column(default=False)
    events: Mapped[list] = mapped_column(JSONB, default=list)
