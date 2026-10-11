"""Очередь обращений (процесс 7): общий сервис поверх реестра типов. Тип описывает свою карточку и исполнение решения
рядом со своей логикой (`app/moderation/types.py`), сервис о типах не знает."""
import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import audit
from app.auth.models import Role, User
from app.common.clock import now
from app.common.errors import AppError
from app.moderation.models import Case
from app.moderation.schemas import ResolveIn
from app.moderation.types import TYPES
from app.notifications.service import notify


def open_case(db: Session, type_: str, refs: dict, opened_by: uuid.UUID, comment: str = "") -> Case:
    t = TYPES[type_]  # неизвестный тип — KeyError: тип без карточки и действий в очереди невозможен
    case = Case(type=type_, refs=refs, opened_by=opened_by, comment=comment)
    db.add(case)
    db.flush()
    for uid in db.scalars(select(User.id).where(User.role.in_((Role.moderator, Role.admin)))):
        notify(db, uid, "case_opened", {"type": t.title, "link": "/moderation"}, f"case_opened:{case.id}:{uid}")
    return case


def case_out(db: Session, case: Case) -> dict:
    t = TYPES[case.type]
    return {"id": str(case.id), "type": case.type, "type_title": t.title, "status": case.status,
            "created_at": case.created_at, "due_at": case.created_at + timedelta(days=t.due_days) if t.due_days else None,
            "comment": case.comment, "resolution": case.resolution, "resolution_text": case.resolution_text,
            "summary": t.summary(db, case), "actions": [{"code": c, "title": x} for c, x in t.actions.items()]}


def list_cases(db: Session, status: str) -> list[dict]:
    rows = db.scalars(select(Case).where(Case.status == status).order_by(Case.created_at))
    return [case_out(db, c) for c in rows]


def my_cases(db: Session, user: User) -> list[dict]:
    """Обращения, которые открыл сам пользователь: тип, статус, срок ответа и итог с текстом модератора."""
    out = []
    for c in db.scalars(select(Case).where(Case.opened_by == user.id).order_by(Case.created_at.desc())):
        t = TYPES[c.type]
        out.append({"id": str(c.id), "type": c.type, "type_title": t.title, "status": c.status, "created_at": c.created_at,
                    "due_at": c.created_at + timedelta(days=t.due_days) if t.due_days else None,
                    "outcome": (c.refs.get("result") or t.actions.get(c.resolution)) if c.resolution else None, "resolution_text": c.resolution_text})
    return out


def resolve(db: Session, user: User, case_id: uuid.UUID, data: ResolveIn) -> dict:
    case = db.get(Case, case_id, with_for_update=True)
    if case is None:
        raise AppError(404, "case_not_found", "Обращение не найдено")
    if case.status != "open":
        raise AppError(409, "case_closed", "Обращение уже рассмотрено")
    t = TYPES[case.type]
    if data.action not in t.actions:
        raise AppError(422, "bad_action", "Это действие не подходит к обращению")
    case.resolved_by, case.resolved_at = user.id, now()  # типам нужен исполнитель, например чтобы закрыть связанные обращения
    result = t.apply(db, case, data.action)
    case.refs = {**case.refs, "result": result}  # человеческий итог для «Моих обращений» (подпись кнопки читалась бы как приказ)
    recipient = t.recipient(db, case)
    if recipient is not None:
        notify(db, recipient, t.notify_kind, {"result": result, "link": t.link}, f"{t.notify_kind}:{case.id}")
    case.status, case.resolution, case.resolution_text = "resolved", data.action, data.resolution_text
    audit(db, user.id, "case.resolve", "case", str(case.id))
    db.commit()
    return case_out(db, case)


# Реестр заполняется при импорте модулей типов: до первого запроса они должны быть загружены.
# Цикла нет: модули типов импортируют moderation.types и модели, но не moderation.service.
import app.employer_tasks.moderation  # noqa: E402, F401
import app.hiring.disputes  # noqa: E402, F401
import app.moderation.complaints  # noqa: E402, F401
import app.trust.service  # noqa: E402, F401
