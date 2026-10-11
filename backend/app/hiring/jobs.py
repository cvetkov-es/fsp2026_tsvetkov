"""Задачи worker для доски найма: напоминания компании и дайджест кандидату. Логика продукта от них не зависит."""
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.assessment.phrases import ru_plural
from app.candidates.models import CandidateProfile
from app.common.clock import MSK
from app.config.params import PARAMS
from app.contacts.models import Contact
from app.contacts.service import _members
from app.employers.models import Company
from app.hiring.models import PipelineStage, Vote
from app.hiring.service import FINAL
from app.matching.service import alias
from app.notifications.service import notify


def remind_stages(db: Session, t: datetime) -> int:
    """REMINDER_DAYS после принятия или последнего этапа без финала — напомнить компании обновить этап (процесс 4.7)."""
    n = 0
    for c in db.scalars(select(Contact).where(Contact.status == "accepted")):
        last_stage = db.scalar(select(PipelineStage).where(PipelineStage.contact_id == c.id)
                               .order_by(PipelineStage.at.desc(), PipelineStage.id.desc()).limit(1))
        if last_stage is not None and last_stage.stage in FINAL:
            continue
        since = last_stage.at if last_stage else (c.contacts_revealed_at or c.updated_at)
        due = [d for d in PARAMS.reminder_days if t - since >= timedelta(days=d)]
        if not due:
            continue
        threshold, elapsed = max(due), (t - since).days
        payload = {"alias": alias(db.get(CandidateProfile, c.user_id)),
                   "days_text": f"{elapsed} {ru_plural(elapsed, 'день', 'дня', 'дней')}",
                   "link": f"/employer/needs/{c.need_id}/board"}
        for uid in _members(db, c.company_id):
            notify(db, uid, "stage_reminder", payload, f"stage_reminder:{c.id}:{threshold}:{since:%Y%m%d%H%M}:{uid}")
            n += 1
    return n


def digest_week_end(t: datetime) -> datetime:
    """Последний понедельник 10:00 МСК не позже t: дайджест за неделю до него уйдёт, даже если worker простоял."""
    local = t.astimezone(MSK)
    monday = (local - timedelta(days=local.weekday())).replace(hour=10, minute=0, second=0, microsecond=0)
    return monday if monday <= local else monday - timedelta(days=7)


def vote_digest(db: Session, t: datetime) -> int:
    """Еженедельный дайджест (процесс 2.9 [И20]): оценки, которые компании дали за неделю до последнего понедельника
    10:00 МСК, нейтрально — «компания X оставила оценку». Сама оценка — только в «Моих оценках»."""
    end = digest_week_end(t)
    week = end.isocalendar()
    names: dict = defaultdict(set)
    for v in db.scalars(select(Vote).where(Vote.answered_at >= end - timedelta(days=7), Vote.answered_at < end)):
        names[v.user_id].add(db.get(Company, v.company_id).name)
    for uid, companies in names.items():
        notify(db, uid, "vote_digest", {"companies": ", ".join(sorted(companies)), "link": "/candidate/reviews"},
               f"vote_digest:{uid}:{week.year}-{week.week}")
    return len(names)
