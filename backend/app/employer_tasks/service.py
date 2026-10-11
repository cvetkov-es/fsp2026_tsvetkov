"""Задачи работодателей (процесс 4.6). Решение — не отклик и на грейд не влияет; оценённое — активность кандидата."""
import uuid
from datetime import datetime, timedelta

from pydantic import Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.assessment.bank.canon import CanonError, canonical
from app.auth.models import User
from app.candidates.models import CandidateProfile
from app.candidates.service import get_or_create_profile
from app.common.clock import now
from app.common.errors import AppError
from app.config.params import PARAMS
from app.contacts.models import CompanyBlock
from app.contacts.service import _members, invite
from app.employer_tasks.models import EmployerTask, TaskSubmission
from app.employer_tasks.schemas import EvaluateIn, SubmissionIn, TaskIn, TaskInviteIn
from app.employers.models import Company
from app.employers.service import require_company
from app.llm.client import LLM, LLMOut
from app.llm.masking import mask
from app.matching.service import alias
from app.moderation.models import Case
from app.moderation.service import open_case
from app.notifications.service import notify

TRUSTED = ("L1", "L2", "L3")
HINT_SYSTEM = ("Ты помогаешь работодателю проверить решение тестовой задачи. Оцени, отвечает ли решение условию: "
               "fits = yes, partly или no, и summary — одно-два предложения по существу, без оценки личности. "
               "Решение принимает человек, твой ответ — только совет.")


class HintOut(LLMOut):
    fits: str = Field(pattern="^(yes|partly|no)$")
    summary: str = Field(max_length=400)


def task_state(task: EmployerTask, t: datetime) -> str:
    """Срок вышел — «закрыта» (лениво, без worker); снятая модератором остаётся «снята»."""
    if task.status == "open" and task.deadline <= t:
        return "closed"
    return task.status


def create_task(db: Session, user: User, data: TaskIn) -> EmployerTask:
    company = require_company(db, user)
    if company.trust_level not in TRUSTED:
        raise AppError(403, "trust_required", "Публиковать задачи можно с уровня доверия L1 (корпоративный домен)")
    t = now()
    if not t < data.deadline <= t + timedelta(days=PARAMS.task_ttl_days):
        raise AppError(422, "bad_deadline", f"Срок должен быть в будущем и не дальше {PARAMS.task_ttl_days} дней")
    if data.reference_answer and data.answer_kind is None:
        raise AppError(422, "answer_kind_required", "Укажите, как сравнивать с эталоном: число или текст")
    if data.reference_answer:
        try:
            canonical(data.answer_kind, data.reference_answer)
        except (CanonError, TypeError, ValueError, OverflowError) as e:  # иначе автопроверка молча «не совпадает» у всех
            raise AppError(422, "bad_reference", "Эталон не подходит под выбранный вид сравнения",
                           "Для вида «число» укажите эталон числом, например 400 или 12,5") from e
    task = EmployerTask(company_id=company.id, author_user_id=user.id, specialization=data.specialization,
                        title=data.title, text=data.text, reference_answer=data.reference_answer,
                        answer_kind=data.answer_kind if data.reference_answer else None, deadline=data.deadline)
    db.add(task)
    db.commit()
    return task


def _submission_status(s: TaskSubmission) -> str:
    if s.verdict:
        return s.verdict
    if s.auto_correct is not None:
        return "auto_correct" if s.auto_correct else "auto_wrong"
    return "pending"


def feed(db: Session, user: User, specialization: str | None) -> list[dict]:
    p = get_or_create_profile(db, user)
    t = now()
    spec = specialization or p.specialization
    blocked = set(db.scalars(select(CompanyBlock.company_id).where(CompanyBlock.user_id == user.id)))
    mine = {s.task_id: s for s in db.scalars(select(TaskSubmission).where(TaskSubmission.user_id == user.id))}
    stmt = select(EmployerTask).where(EmployerTask.status == "open", EmployerTask.deadline > t)
    if spec:
        stmt = stmt.where(EmployerTask.specialization == spec)
    out = []
    for task in db.scalars(stmt.order_by(EmployerTask.deadline)):
        if task.company_id in blocked:
            continue
        c = db.get(Company, task.company_id)
        s = mine.get(task.id)
        out.append({"id": str(task.id), "title": task.title, "text": task.text, "specialization": task.specialization,
                    "deadline": task.deadline, "has_reference": task.reference_answer is not None,
                    "answer_max": PARAMS.task_answer_max,
                    "company": {"name": c.name, "trust_level": c.trust_level},
                    "my_submission": None if s is None else {"status": _submission_status(s), "comment": s.comment}})
    return out


def _auto(task: EmployerTask, answer: str) -> bool | None:
    if task.reference_answer is None:
        return None
    try:
        return canonical(task.answer_kind, answer) == canonical(task.answer_kind, task.reference_answer)
    except (CanonError, TypeError, ValueError, OverflowError):
        return False


def submit(db: Session, user: User, task_id: uuid.UUID, data: SubmissionIn) -> dict:
    get_or_create_profile(db, user)  # у кандидата без профиля решение тоже должно получить псевдоним
    task = db.get(EmployerTask, task_id, with_for_update=True)
    if task is None or task.status == "removed":
        raise AppError(404, "task_not_found", "Задача не найдена")
    if task_state(task, now()) != "open":
        raise AppError(409, "task_closed", "Срок задачи истёк")
    if db.get(CompanyBlock, (user.id, task.company_id)):
        raise AppError(409, "company_blocked", "Эта компания скрыта в ваших настройках")
    if db.scalar(select(TaskSubmission.id).where(TaskSubmission.task_id == task.id, TaskSubmission.user_id == user.id)):
        raise AppError(409, "already_submitted", "Решение уже отправлено")
    s = TaskSubmission(task_id=task.id, user_id=user.id, answer=data.answer, auto_correct=_auto(task, data.answer))
    db.add(s)
    db.flush()
    for uid in _members(db, task.company_id):
        notify(db, uid, "task_submission", {"title": task.title, "link": "/employer/tasks"}, f"task_submission:{s.id}:{uid}")
    db.commit()
    return {"status": _submission_status(s), "comment": None}


def complain(db: Session, user: User, task_id: uuid.UUID, comment: str) -> None:
    task = db.get(EmployerTask, task_id, with_for_update=True)  # две жалобы подряд не проходят мимо проверки дубля
    if task is None or task.status == "removed":
        raise AppError(404, "task_not_found", "Задача не найдена")
    dup = db.scalar(select(Case.id).where(Case.type == "free_work", Case.opened_by == user.id,
                                          Case.refs["task_id"].astext == str(task.id)))
    if dup:
        raise AppError(409, "already_complained", "Жалоба на эту задачу уже отправлена")
    open_case(db, "free_work", {"task_id": str(task.id)}, user.id, comment)
    db.commit()


def _own_task(db: Session, user: User, task_id: uuid.UUID) -> EmployerTask:
    company = require_company(db, user)
    task = db.get(EmployerTask, task_id)
    if task is None or task.company_id != company.id:
        raise AppError(404, "task_not_found", "Задача не найдена")
    return task


def _own_submission(db: Session, user: User, submission_id: uuid.UUID) -> tuple[TaskSubmission, EmployerTask]:
    s = db.get(TaskSubmission, submission_id, with_for_update=True)
    if s is None:
        raise AppError(404, "submission_not_found", "Решение не найдено")
    return s, _own_task(db, user, s.task_id)


def company_tasks(db: Session, user: User) -> list[dict]:
    company = require_company(db, user)
    t = now()
    tasks = list(db.scalars(select(EmployerTask).where(EmployerTask.company_id == company.id)
                            .order_by(EmployerTask.created_at.desc())))
    ids = [x.id for x in tasks]
    counts = dict(db.execute(select(TaskSubmission.task_id, func.count()).where(TaskSubmission.task_id.in_(ids))
                             .group_by(TaskSubmission.task_id)).all())
    # «ждут проверки» — без оценки работодателя и без результата автопроверки по эталону
    pending = dict(db.execute(select(TaskSubmission.task_id, func.count()).where(
        TaskSubmission.task_id.in_(ids), TaskSubmission.verdict.is_(None), TaskSubmission.auto_correct.is_(None))
        .group_by(TaskSubmission.task_id)).all())
    return [{"id": str(x.id), "title": x.title, "specialization": x.specialization, "deadline": x.deadline,
             "status": task_state(x, t), "submissions": counts.get(x.id, 0), "pending": pending.get(x.id, 0)}
            for x in tasks]


def _submission_out(db: Session, s: TaskSubmission) -> dict:
    p = db.get(CandidateProfile, s.user_id)
    return {"id": str(s.id), "alias": alias(p), "ref": p.public_ref, "answer": s.answer, "auto_correct": s.auto_correct,
            "verdict": s.verdict, "comment": s.comment, "llm_hint": s.llm_hint, "created_at": s.created_at}


def task_submissions(db: Session, user: User, task_id: uuid.UUID) -> dict:
    task = _own_task(db, user, task_id)
    rows = db.scalars(select(TaskSubmission).where(TaskSubmission.task_id == task.id).order_by(TaskSubmission.created_at))
    return {"task": {"id": str(task.id), "title": task.title, "text": task.text, "reference_answer": task.reference_answer,
                     "answer_kind": task.answer_kind, "deadline": task.deadline, "status": task_state(task, now())},
            "items": [_submission_out(db, s) for s in rows]}


def evaluate(db: Session, user: User, submission_id: uuid.UUID, data: EvaluateIn) -> dict:
    s, task = _own_submission(db, user, submission_id)
    t = now()
    s.verdict, s.comment, s.evaluated_at = data.verdict, data.comment or None, t
    p = db.get(CandidateProfile, s.user_id)
    p.last_activity_at = t  # оценённое решение задачи — значимая активность (процесс 6.4)
    result = "принято" if data.verdict == "accepted" else "не принято"
    notify(db, s.user_id, "task_evaluated", {"title": task.title, "result": result, "link": "/candidate/tasks"},
           f"task_evaluated:{s.id}:{data.verdict}")
    db.commit()
    return _submission_out(db, s)


def hint(db: Session, user: User, submission_id: uuid.UUID, llm: LLM) -> dict:
    s, task = _own_submission(db, user, submission_id)
    text = f"Задача: {task.text}\n\nРешение кандидата:\n{mask(s.answer).text}"[:PARAMS.llm_max_input_chars]
    res = llm.json("pd", HINT_SYSTEM, text, HintOut)
    if res is None:
        raise AppError(503, "llm_unavailable", "Подсказка ИИ сейчас недоступна. Проверьте решение сами")
    out, model = res
    s.llm_hint = {"fits": out.fits, "summary": out.summary, "model": model}
    db.commit()
    return _submission_out(db, s)


def invite_author(db: Session, user: User, submission_id: uuid.UUID, data: TaskInviteIn) -> dict:
    s, _task = _own_submission(db, user, submission_id)
    p = db.get(CandidateProfile, s.user_id)
    if data.ref != p.public_ref:
        raise AppError(422, "ref_mismatch", "Пригласить можно только автора этого решения")
    c = invite(db, user, data.need_id, data)
    c.channel, c.task_submission_id = "task_author", s.id
    db.commit()
    return {"contact_id": str(c.id)}
