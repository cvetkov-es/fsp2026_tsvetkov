from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.common.clock import now
from app.db.base import Base


class MockFspKey(Base):
    """Ключ подписи мока: в БД, чтобы оба воркера uvicorn подписывали и проверяли одним ключом."""
    __tablename__ = "mock_fsp_keys"
    kid: Mapped[str] = mapped_column(String(40), primary_key=True)
    private_pem: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class MockFspCode(Base):
    """Код авторизации: выдаёт один воркер, обменивает другой — поэтому тоже в БД."""
    __tablename__ = "mock_fsp_codes"
    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    subject: Mapped[str] = mapped_column(String(64))
    client_id: Mapped[str] = mapped_column(String(100))
    redirect_uri: Mapped[str] = mapped_column(String(300))
    nonce: Mapped[str] = mapped_column(String(128))
    code_challenge: Mapped[str] = mapped_column(String(128))
    scope: Mapped[str] = mapped_column(String(200))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
