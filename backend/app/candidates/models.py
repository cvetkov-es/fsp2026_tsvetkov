import secrets
import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    PrimaryKeyConstraint,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.clock import now
from app.db.base import Base


class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    specialization: Mapped[str | None] = mapped_column(String(40))
    # Юниорский трек (2.10): профиль несовершеннолетнего — черновик до согласия законного представителя
    guardian_email: Mapped[str | None] = mapped_column(String(254))
    guardian_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claimed_grade: Mapped[str | None] = mapped_column(String(20))
    grade_status: Mapped[str] = mapped_column(String(20), default="not_tested", index=True)
    confirmed_grade: Mapped[str | None] = mapped_column(String(20))
    status_attempt_id: Mapped[uuid.UUID | None] = mapped_column()
    theta: Mapped[float | None] = mapped_column(Float)
    se: Mapped[float | None] = mapped_column(Float)
    s_cache: Mapped[float | None] = mapped_column(Float)
    # Последняя смена категории (специализация или грейд): голоса до неё — в архиве навсегда (процесс 5)
    grade_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cooldown_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    public_ref: Mapped[str] = mapped_column(String(12), unique=True, default=lambda: secrets.token_hex(4))
    full_name: Mapped[str | None] = mapped_column(String(200))
    contacts: Mapped[dict] = mapped_column(JSONB, default=dict)
    experience_years: Mapped[float | None] = mapped_column(Float)
    formats: Mapped[list[str]] = mapped_column(ARRAY(String(10)), default=list)
    city: Mapped[str | None] = mapped_column(String(80))
    domains: Mapped[list[str]] = mapped_column(ARRAY(String(40)), default=list)
    salary_threshold: Mapped[int | None] = mapped_column(Integer)
    salary_gross_net: Mapped[str] = mapped_column(String(5), default="net")
    open_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fsp_status: Mapped[str] = mapped_column(String(20), default="NOT_LINKED")
    fsp_f: Mapped[float] = mapped_column(Float, default=0.0)
    fsp_summary: Mapped[str | None] = mapped_column(String(300))
    m: Mapped[float] = mapped_column(Float, default=1.0)
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False)


class CandidateStack(Base):
    __tablename__ = "candidate_stack"
    __table_args__ = (PrimaryKeyConstraint("user_id", "tech"),)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    tech: Mapped[str] = mapped_column(String(60))


class SkillResult(Base):
    __tablename__ = "skill_results"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    skill_code: Mapped[str] = mapped_column(String(30))
    passed: Mapped[bool] = mapped_column(Boolean)
    attempt_id: Mapped[uuid.UUID | None] = mapped_column()
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
