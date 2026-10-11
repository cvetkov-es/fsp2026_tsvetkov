"""Типы обращений одной очереди модерации (процесс 7): подпись, действия, карточка и исполнение решения."""
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.moderation.models import Case


@dataclass(frozen=True)
class CaseType:
    title: str
    actions: dict[str, str]  # код действия → подпись кнопки; первое — основное
    summary: Callable[[Session, Case], list[dict]]  # [{"label", "value"}] — карточка для модератора
    apply: Callable[[Session, Case, str], str]  # исполнить решение (case.resolved_by уже стоит) → итог для уведомления
    recipient: Callable[[Session, Case], uuid.UUID | None] = field(default=lambda db, case: case.opened_by)
    notify_kind: str = "case_resolved"
    link: str = "/"
    due_days: int | None = None  # срок ответа, если он есть (ст. 16)


TYPES: dict[str, CaseType] = {}


def register(code: str, t: CaseType) -> None:
    TYPES[code] = t


def row(label: str, value) -> dict:
    return {"label": label, "value": str(value)}
