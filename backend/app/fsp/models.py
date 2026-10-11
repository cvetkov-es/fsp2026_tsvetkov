import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.clock import now
from app.db.base import Base


class OidcState(Base):
    """state входа через FSP ID: одноразовый, живёт OIDC_TTL_MIN, привязан к cookie браузера."""
    __tablename__ = "oidc_states"
    state: Mapped[str] = mapped_column(String(64), primary_key=True)
    nonce: Mapped[str] = mapped_column(String(64))
    code_verifier: Mapped[str] = mapped_column(String(128))
    purpose: Mapped[str] = mapped_column(String(10))  # login | link
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OidcPending(Base):
    """FSP ID подтвердил человека, но аккаунта ещё нет: «билет» на страницу согласий."""
    __tablename__ = "oidc_pending"
    ticket: Mapped[str] = mapped_column(String(64), primary_key=True)
    subject: Mapped[str] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(320))
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    name: Mapped[str | None] = mapped_column(String(200))
    access_token: Mapped[str | None] = mapped_column(Text)  # короткоживущий; стирается при использовании билета
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FspSnapshot(Base):
    __tablename__ = "fsp_snapshots"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    status: Mapped[str] = mapped_column(String(10))  # ok | error
    payload: Mapped[dict | None] = mapped_column(JSONB)


class FspResult(Base):
    """Нормализованный результат; пересобирается при каждой удачной синхронизации (техдизайн 4.4)."""
    __tablename__ = "fsp_results"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fsp_snapshots.id", ondelete="CASCADE"))
    competition_id: Mapped[str] = mapped_column(String(80))
    competition_title: Mapped[str] = mapped_column(String(300))
    discipline: Mapped[str] = mapped_column(String(20))
    stage_type: Mapped[str] = mapped_column(String(12))
    level: Mapped[str] = mapped_column(String(20))
    date: Mapped[date] = mapped_column(Date)
    place: Mapped[int | None] = mapped_column(Integer)
    field_size: Mapped[int | None] = mapped_column(Integer)
    team_id: Mapped[str | None] = mapped_column(String(80), index=True)
    team_name: Mapped[str | None] = mapped_column(String(120))
    team_size: Mapped[int | None] = mapped_column(Integer)
    tier: Mapped[str] = mapped_column(String(12))
    counted: Mapped[bool] = mapped_column(Boolean)
    note: Mapped[str | None] = mapped_column(String(60))


class FspRank(Base):
    __tablename__ = "fsp_ranks"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    rank: Mapped[str] = mapped_column(String(4))
    assigned_at: Mapped[date] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(Date)
