import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.clock import now
from app.db.base import Base


class Company(Base):
    __tablename__ = "companies"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    industry: Mapped[str | None] = mapped_column(String(100))
    contacts: Mapped[dict] = mapped_column(JSONB, default=dict)
    domain: Mapped[str | None] = mapped_column(String(120))
    inn: Mapped[str | None] = mapped_column(String(12))
    legal_name: Mapped[str | None] = mapped_column(String(300))  # название юрлица из DaData (L2)
    trust_level: Mapped[str] = mapped_column(String(2), default="L0")
    quota_penalty_slots: Mapped[int] = mapped_column(Integer, default=0)
    quota_penalty_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class CompanyMember(Base):
    __tablename__ = "company_members"
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, unique=True)


class Need(Base):
    __tablename__ = "needs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    specialization: Mapped[str] = mapped_column(String(40))
    grades: Mapped[list[str]] = mapped_column(ARRAY(String(20)))
    must: Mapped[list[str]] = mapped_column(ARRAY(String(60)), default=list)
    nice: Mapped[list[str]] = mapped_column(ARRAY(String(60)), default=list)
    formats: Mapped[list[str]] = mapped_column(ARRAY(String(10)), default=list)
    city: Mapped[str | None] = mapped_column(String(80))
    salary_from: Mapped[int] = mapped_column(Integer)
    salary_to: Mapped[int] = mapped_column(Integer)
    gross_net: Mapped[str] = mapped_column(String(5))
    contact_method: Mapped[str] = mapped_column(String(20), default="chat")
    raw_text: Mapped[str | None] = mapped_column(Text)
    employment: Mapped[str] = mapped_column(String(12), default="full", server_default="full")  # full | internship | vacation (2.10)
    status: Mapped[str] = mapped_column(String(10), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
