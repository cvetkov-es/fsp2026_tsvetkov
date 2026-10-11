import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.clock import now
from app.db.base import Base


class LabRun(Base):
    """Прогон лаборатории (техдизайн 4.9). Только синтетика: ПДн здесь нет."""
    __tablename__ = "lab_runs"
    # Гарантия БД: один активный прогон на стенд — два одновременных POST не поставят два прогона
    __table_args__ = (Index("uq_lab_runs_one_active", text("(true)"), unique=True,
                            postgresql_where=text("status IN ('queued', 'running')")),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(20))  # validate | ui
    population: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(10), default="queued", index=True)  # queued | running | done | failed
    results: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
