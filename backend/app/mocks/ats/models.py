import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.common.clock import now
from app.db.base import Base


class MockAtsEvent(Base):
    """События, принятые встроенным моком ATS (демо): тип, верна ли подпись, тело."""
    __tablename__ = "mock_ats_events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    endpoint_id: Mapped[uuid.UUID] = mapped_column(index=True)
    type: Mapped[str] = mapped_column(String(60))
    valid: Mapped[bool] = mapped_column(Boolean)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    body: Mapped[str] = mapped_column(Text)
