"""Зеркало реестра семейств в БД (экспозиция, статус) и версии порогов.

Функции только делают flush: их вызывают и посреди /next под FOR UPDATE,
а commit там снял бы блокировку попытки. Фиксирует транзакцию вызывающий.
Вставки идут через ON CONFLICT: две первые транзакции на пустой БД не падают на PK.
"""
from sqlalchemy import case, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.assessment.bank.base import REGISTRY
from app.assessment.bank.families import load_all
from app.assessment.models import ItemFamilyRow, ThresholdsRow
from app.common.clock import now
from app.config.params import PARAMS

EXPERT_VERSION = "expert-1"
_SYNCED = ("specialization", "area", "level", "fmt", "b", "median_time_s", "status", "synced_at")


def sync_bank(db: Session) -> int:
    load_all()
    t = now()
    rows = [{"code": f.code, "specialization": f.specialization, "area": f.area, "level": f.level,
             "fmt": f.fmt, "b": f.b(PARAMS.b_levels), "median_time_s": f.median_time_s,
             "status": "active", "exposure_count": 0, "synced_at": t} for f in REGISTRY.values()]
    if rows:
        stmt = insert(ItemFamilyRow).values(rows)
        # exposure_count не трогаем: показы копятся между синхронизациями
        # «suspended» — решение модератора: синхронизация банка его не отменяет
        set_ = {k: stmt.excluded[k] for k in _SYNCED if k != "status"} | {
            "status": case((ItemFamilyRow.status == "suspended", "suspended"), else_=stmt.excluded.status)}
        db.execute(stmt.on_conflict_do_update(index_elements=[ItemFamilyRow.code], set_=set_))
    # решение модератора («suspended») сильнее, чем исчезновение семейства из реестра: вернётся в код — останется снятым
    db.execute(update(ItemFamilyRow).where(ItemFamilyRow.code.not_in(list(REGISTRY)), ItemFamilyRow.status != "suspended")
               .values(status="retired").execution_options(synchronize_session="fetch"))
    db.flush()
    return len(REGISTRY)


def ensure_thresholds(db: Session) -> None:
    if db.get(ThresholdsRow, EXPERT_VERSION) is None:
        db.execute(insert(ThresholdsRow).values(
            version=EXPERT_VERSION, cut_j=PARAMS.cut_j, cut_m=PARAMS.cut_m, cut_s=PARAMS.cut_s,
            virtual_gap=PARAMS.senior_virtual_gap, source="expert", created_at=now(),
        ).on_conflict_do_nothing(index_elements=[ThresholdsRow.version]))
        db.flush()
