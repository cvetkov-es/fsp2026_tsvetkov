"""Уведомления: запись идемпотентна по dedupe_key, письма отправляет worker."""
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.common.clock import now
from app.notifications.models import Notification

TITLES = {
    "invitation": "Новое приглашение от компании «{company}»",
    "offer_v2": "Компания «{company}» прислала обновлённый оффер",
    "invitation_reminder": "Приглашение от «{company}» истекает {expires}",
    "invitation_accepted": "{alias}: приглашение принято, контакты открыты",
    "invitation_declined": "{alias}: приглашение отклонено",
    "invitation_countered": "{alias}: встречное условие",
    "counter_declined": "Компания «{company}» не приняла встречное условие",
    "contacts_revoked": "{alias}: контакты скрыты кандидатом",
    "invitation_withdrawn": "Компания «{company}» отозвала приглашение",
    "invitation_expired": "{alias}: приглашение истекло без ответа",
    "counter_expired": "Компания «{company}» не ответила на встречное условие в срок",
    "message": "Новое сообщение в чате с {who}",
    "stage_reminder": "{alias}: этап найма не менялся {days_text}. Обновите его",
    "vote_digest": "Новые оценки по собеседованиям: {companies}",
    "vote_dispute_resolved": "Спор об оценке рассмотрен: {result}",
    "signal": "{alias}: кандидат отметил интерес к вашей компании",
    "task_submission": "Новое решение задачи «{title}»",
    "task_evaluated": "Решение задачи «{title}»: {result}",
    "task_removed": "Задача «{title}» снята модератором",
    "case_resolved": "Обращение рассмотрено: {result}",
    "application": "{alias}: отклик на вакансию «{title}»",
    "application_accepted": "Компания «{company}» приняла отклик, контакты открыты",
    "application_declined": "Компания «{company}» отклонила отклик",
    "group_invitation": "Командное приглашение от компании «{company}» для команды «{team}»",
    "group_min_reached": "Командное приглашение «{team}»: минимальный состав набран",
    "case_opened": "Новое обращение в модерацию: {type}",
}


def title_of(kind: str, payload: dict) -> str:
    try:
        return TITLES[kind].format(**payload)
    except (KeyError, IndexError):
        return "Уведомление платформы"


def notify(db: Session, user_id: uuid.UUID, kind: str, payload: dict, dedupe_key: str) -> None:
    db.execute(insert(Notification).values(user_id=user_id, kind=kind, payload=payload, dedupe_key=dedupe_key,
                                           created_at=now()).on_conflict_do_nothing(index_elements=["dedupe_key"]))


def latest(db: Session, user_id: uuid.UUID, limit: int = 20) -> tuple[list[dict], int]:
    rows = db.scalars(select(Notification).where(Notification.user_id == user_id)
                      .order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit))
    unread = db.scalar(select(func.count()).select_from(Notification).where(
        Notification.user_id == user_id, Notification.read_at.is_(None)))
    items = [{"id": n.id, "kind": n.kind, "title": title_of(n.kind, n.payload), "link": n.payload.get("link"),
              "created_at": n.created_at, "read": n.read_at is not None} for n in rows]
    return items, unread


def mark_read(db: Session, user_id: uuid.UUID) -> None:
    db.execute(update(Notification).where(Notification.user_id == user_id, Notification.read_at.is_(None))
               .values(read_at=now()))
    db.commit()
