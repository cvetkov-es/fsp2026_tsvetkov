"""Тип обращения «Бесплатная работа» (процесс 4.6, 7; план 07b2): карточка и исполнение решения."""
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit.service import audit
from app.common.clock import now
from app.contacts.service import _members
from app.employer_tasks.models import EmployerTask, TaskSubmission
from app.employers.models import Company
from app.moderation.models import Case
from app.moderation.types import CaseType, register, row
from app.notifications.service import notify


def summary(db: Session, case: Case) -> list[dict]:
    task = db.get(EmployerTask, uuid.UUID(case.refs["task_id"]))
    if task is None:  # задача удалена вместе с компанией — обращение можно закрыть, а очередь не падает
        return [row("Задача", "удалена вместе с компанией. Обращение можно закрыть")]
    n = db.scalar(select(func.count()).select_from(TaskSubmission).where(TaskSubmission.task_id == task.id))
    return [row("Компания", db.get(Company, task.company_id).name), row("Задача", task.title),
            row("Срок", task.deadline.strftime("%d.%m.%Y")), row("Решений", n), row("Текст задачи", task.text[:600])]


def _close_sibling_complaints(db: Session, case: Case) -> None:
    """Задача снята — остальные открытые жалобы на неё закрываются вместе с первой и не висят в очереди."""
    for sib in db.scalars(select(Case).where(Case.type == "free_work", Case.status == "open", Case.id != case.id,
                                             Case.refs["task_id"].astext == case.refs["task_id"]).with_for_update()):
        sib.status, sib.resolution, sib.resolution_text = "resolved", "remove", "Задача снята по другой жалобе"
        sib.resolved_by, sib.resolved_at = case.resolved_by, now()
        notify(db, sib.opened_by, "case_resolved", {"result": "задача снята", "link": "/candidate/tasks"},
               f"case_resolved:{sib.id}")
        audit(db, case.resolved_by, "case.resolve", "case", str(sib.id))


def apply(db: Session, case: Case, action: str) -> str:
    task = db.get(EmployerTask, uuid.UUID(case.refs["task_id"]), with_for_update=True)
    if task is None:
        return "задача уже удалена"
    if action != "remove":
        return "жалоба отклонена"
    task.status = "removed"
    for uid in _members(db, task.company_id):
        notify(db, uid, "task_removed", {"title": task.title, "link": "/employer/tasks"}, f"task_removed:{case.id}:{uid}")
    _close_sibling_complaints(db, case)
    return "задача снята"


register("free_work", CaseType(
    title="«Бесплатная работа»", actions={"remove": "Снять задачу", "dismiss": "Отклонить жалобу"}, summary=summary,
    apply=apply, link="/candidate/tasks"))
